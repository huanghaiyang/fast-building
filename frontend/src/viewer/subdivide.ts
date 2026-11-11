/**
 * Loop 曲面细分：把三角网格细分成更平滑的曲面，仅用于预览渲染。
 *
 * 只处理位置与 UV，不保留切线等附加属性；细分后按顶点位置合并法线，
 * 让曲率处平滑过渡，同时 UV 仍按三角形逐角插值，避免贴图错位。
 */

import { BufferGeometry, Float32BufferAttribute } from "three";

interface Soup {
  /** 每个顶点 3 个分量 */
  positions: number[];
  /** 每个三角形角点的 UV，长度为 faces.length * 2 */
  uvs: number[];
  /** 每个三角形 3 个顶点索引 */
  faces: number[];
  hasUv: boolean;
}

const WELD = 1e5;
const EDGE_KEY_RADIX = 2097152;

function edgeKey(a: number, b: number): number {
  return a < b ? a * EDGE_KEY_RADIX + b : b * EDGE_KEY_RADIX + a;
}

function readSoup(source: BufferGeometry): Soup {
  const position = source.getAttribute("position");
  const uv = source.getAttribute("uv");
  const index = source.getIndex();
  const cornerCount = index ? index.count : position.count;

  const weldIndex = new Map<string, number>();
  const positions: number[] = [];
  const faces: number[] = [];
  const uvs: number[] = [];
  const hasUv = Boolean(uv);

  for (let corner = 0; corner < cornerCount; corner += 1) {
    const vertexIndex = index ? index.getX(corner) : corner;
    const x = position.getX(vertexIndex);
    const y = position.getY(vertexIndex);
    const z = position.getZ(vertexIndex);
    const key = `${Math.round(x * WELD)}_${Math.round(y * WELD)}_${Math.round(z * WELD)}`;
    let welded = weldIndex.get(key);
    if (welded === undefined) {
      welded = positions.length / 3;
      positions.push(x, y, z);
      weldIndex.set(key, welded);
    }
    faces.push(welded);
    uvs.push(uv ? uv.getX(vertexIndex) : 0, uv ? uv.getY(vertexIndex) : 0);
  }

  return { positions, uvs, faces, hasUv };
}

function loopPass(soup: Soup): Soup {
  const vertexCount = soup.positions.length / 3;
  const neighbors: number[][] = Array.from({ length: vertexCount }, () => []);
  const edges = new Map<number, { a: number; b: number; opposite: number[] }>();

  const addEdge = (a: number, b: number, opposite: number) => {
    const key = edgeKey(a, b);
    let record = edges.get(key);
    if (!record) {
      record = { a, b, opposite: [] };
      edges.set(key, record);
      neighbors[a].push(b);
      neighbors[b].push(a);
    }
    record.opposite.push(opposite);
  };

  for (let f = 0; f < soup.faces.length; f += 3) {
    const a = soup.faces[f];
    const b = soup.faces[f + 1];
    const c = soup.faces[f + 2];
    addEdge(a, b, c);
    addEdge(b, c, a);
    addEdge(c, a, b);
  }

  const positions = soup.positions.slice();
  const nextFaces: number[] = [];
  const nextUvs: number[] = [];

  // 边界顶点：只受两个边界邻点影响，避免细分后收缩
  const boundary = new Map<number, number[]>();
  for (const record of edges.values()) {
    if (record.opposite.length !== 1) continue;
    (boundary.get(record.a) ?? boundary.set(record.a, []).get(record.a)!).push(record.b);
    (boundary.get(record.b) ?? boundary.set(record.b, []).get(record.b)!).push(record.a);
  }

  const smoothed = new Array<number>(vertexCount * 3);
  for (let v = 0; v < vertexCount; v += 1) {
    const x = positions[v * 3];
    const y = positions[v * 3 + 1];
    const z = positions[v * 3 + 2];
    const boundaryNeighbors = boundary.get(v);

    if (boundaryNeighbors && boundaryNeighbors.length >= 2) {
      const [n1, n2] = boundaryNeighbors;
      smoothed[v * 3] = 0.75 * x + 0.125 * (positions[n1 * 3] + positions[n2 * 3]);
      smoothed[v * 3 + 1] = 0.75 * y + 0.125 * (positions[n1 * 3 + 1] + positions[n2 * 3 + 1]);
      smoothed[v * 3 + 2] = 0.75 * z + 0.125 * (positions[n1 * 3 + 2] + positions[n2 * 3 + 2]);
      continue;
    }
    if (boundaryNeighbors) {
      smoothed[v * 3] = x;
      smoothed[v * 3 + 1] = y;
      smoothed[v * 3 + 2] = z;
      continue;
    }

    const ring = neighbors[v];
    const n = ring.length;
    if (n < 3) {
      smoothed[v * 3] = x;
      smoothed[v * 3 + 1] = y;
      smoothed[v * 3 + 2] = z;
      continue;
    }
    const beta = (5 / 8 - (3 / 8 + 0.25 * Math.cos((2 * Math.PI) / n)) ** 2) / n;
    let sx = 0;
    let sy = 0;
    let sz = 0;
    for (const neighbor of ring) {
      sx += positions[neighbor * 3];
      sy += positions[neighbor * 3 + 1];
      sz += positions[neighbor * 3 + 2];
    }
    smoothed[v * 3] = (1 - n * beta) * x + beta * sx;
    smoothed[v * 3 + 1] = (1 - n * beta) * y + beta * sy;
    smoothed[v * 3 + 2] = (1 - n * beta) * z + beta * sz;
  }

  // 边点：内部边取 3/8 两端 + 1/8 两个对顶点，边界边取中点
  const edgePoint = new Map<number, number>();
  const edgePositions: number[] = [];
  for (const [key, record] of edges) {
    const a = record.a;
    const b = record.b;
    if (record.opposite.length === 2) {
      const [o1, o2] = record.opposite;
      for (let axis = 0; axis < 3; axis += 1) {
        edgePositions.push(
          (3 / 8) * (positions[a * 3 + axis] + positions[b * 3 + axis]) +
            (1 / 8) * (positions[o1 * 3 + axis] + positions[o2 * 3 + axis]),
        );
      }
    } else {
      for (let axis = 0; axis < 3; axis += 1) {
        edgePositions.push(
          0.5 * (positions[a * 3 + axis] + positions[b * 3 + axis]),
        );
      }
    }
    edgePoint.set(key, vertexCount + edgePoint.size);
  }

  const nextPositions = smoothed.concat(edgePositions);
  const midpoint = (u1: number, v1: number, u2: number, v2: number) => [(u1 + u2) / 2, (v1 + v2) / 2];

  for (let f = 0; f < soup.faces.length; f += 3) {
    const a = soup.faces[f];
    const b = soup.faces[f + 1];
    const c = soup.faces[f + 2];
    const uvA = [soup.uvs[f * 2], soup.uvs[f * 2 + 1]];
    const uvB = [soup.uvs[(f + 1) * 2], soup.uvs[(f + 1) * 2 + 1]];
    const uvC = [soup.uvs[(f + 2) * 2], soup.uvs[(f + 2) * 2 + 1]];

    const ab = edgePoint.get(edgeKey(a, b))!;
    const bc = edgePoint.get(edgeKey(b, c))!;
    const ca = edgePoint.get(edgeKey(c, a))!;

    const uvAb = midpoint(uvA[0], uvA[1], uvB[0], uvB[1]);
    const uvBc = midpoint(uvB[0], uvB[1], uvC[0], uvC[1]);
    const uvCa = midpoint(uvC[0], uvC[1], uvA[0], uvA[1]);

    const children: Array<[number, number[], number, number[], number, number[]]> = [
      [a, uvA, ab, uvAb, ca, uvCa],
      [ab, uvAb, b, uvB, bc, uvBc],
      [ca, uvCa, bc, uvBc, c, uvC],
      [ab, uvAb, bc, uvBc, ca, uvCa],
    ];
    for (const [i0, t0, i1, t1, i2, t2] of children) {
      nextFaces.push(i0, i1, i2);
      nextUvs.push(t0[0], t0[1], t1[0], t1[1], t2[0], t2[1]);
    }
  }

  return { positions: nextPositions, uvs: nextUvs, faces: nextFaces, hasUv: soup.hasUv };
}

function toGeometry(soup: Soup): BufferGeometry {
  // 先按拓扑合并计算平滑法线，再摊平成非索引几何以保留逐角 UV
  const indexed = new BufferGeometry();
  indexed.setAttribute("position", new Float32BufferAttribute(soup.positions, 3));
  indexed.setIndex(soup.faces);
  indexed.computeVertexNormals();
  const normals = indexed.getAttribute("normal");

  const positions: number[] = [];
  const normalData: number[] = [];
  const uvs: number[] = [];
  for (let corner = 0; corner < soup.faces.length; corner += 1) {
    const vertex = soup.faces[corner];
    positions.push(
      soup.positions[vertex * 3],
      soup.positions[vertex * 3 + 1],
      soup.positions[vertex * 3 + 2],
    );
    normalData.push(normals.getX(vertex), normals.getY(vertex), normals.getZ(vertex));
    if (soup.hasUv) uvs.push(soup.uvs[corner * 2], soup.uvs[corner * 2 + 1]);
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new Float32BufferAttribute(normalData, 3));
  if (soup.hasUv) geometry.setAttribute("uv", new Float32BufferAttribute(uvs, 2));
  indexed.dispose();
  return geometry;
}

/** 返回细分后的新几何；调用方负责在不再使用时释放。 */
export function subdivideGeometry(source: BufferGeometry, levels: number): BufferGeometry {
  const rounds = Math.max(0, Math.min(2, Math.floor(levels)));
  if (rounds === 0) return source;
  let soup = readSoup(source);
  for (let i = 0; i < rounds; i += 1) soup = loopPass(soup);
  return toGeometry(soup);
}

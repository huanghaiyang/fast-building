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
/** 二面角超过该阈值视为硬边：硬边不参与平滑，避免窗洞、方盒被细分拉歪。 */
const SHARP_COS = Math.cos((35 * Math.PI) / 180);

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
  const edges = new Map<
    number,
    { a: number; b: number; opposite: number[]; normals: number[][] }
  >();

  const faceNormal = (a: number, b: number, c: number): number[] => {
    const ax = soup.positions[a * 3];
    const ay = soup.positions[a * 3 + 1];
    const az = soup.positions[a * 3 + 2];
    const ux = soup.positions[b * 3] - ax;
    const uy = soup.positions[b * 3 + 1] - ay;
    const uz = soup.positions[b * 3 + 2] - az;
    const vx = soup.positions[c * 3] - ax;
    const vy = soup.positions[c * 3 + 1] - ay;
    const vz = soup.positions[c * 3 + 2] - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    return [nx / length, ny / length, nz / length];
  };

  const addEdge = (a: number, b: number, opposite: number, normal: number[]) => {
    const key = edgeKey(a, b);
    let record = edges.get(key);
    if (!record) {
      record = { a, b, opposite: [], normals: [] };
      edges.set(key, record);
      neighbors[a].push(b);
      neighbors[b].push(a);
    }
    record.opposite.push(opposite);
    record.normals.push(normal);
  };

  for (let f = 0; f < soup.faces.length; f += 3) {
    const a = soup.faces[f];
    const b = soup.faces[f + 1];
    const c = soup.faces[f + 2];
    const normal = faceNormal(a, b, c);
    addEdge(a, b, c, normal);
    addEdge(b, c, a, normal);
    addEdge(c, a, b, normal);
  }

  const positions = soup.positions.slice();
  const nextFaces: number[] = [];
  const nextUvs: number[] = [];

  // 硬边（边界、非流形、二面角过大）上的顶点保持原位，窗洞和方盒不会被磨圆
  const sharpEdges = new Set<number>();
  const fixedVertices = new Set<number>();
  for (const [key, record] of edges) {
    let sharp = record.opposite.length !== 2;
    if (!sharp) {
      const [n1, n2] = record.normals;
      sharp = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2] < SHARP_COS;
    }
    if (!sharp) continue;
    sharpEdges.add(key);
    fixedVertices.add(record.a);
    fixedVertices.add(record.b);
  }

  const smoothed = new Array<number>(vertexCount * 3);
  for (let v = 0; v < vertexCount; v += 1) {
    const x = positions[v * 3];
    const y = positions[v * 3 + 1];
    const z = positions[v * 3 + 2];
    const ring = neighbors[v];
    const n = ring.length;

    if (fixedVertices.has(v) || n < 3) {
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

  // 边点：硬边取中点，其余取 3/8 两端 + 1/8 两个对顶点
  const edgePoint = new Map<number, number>();
  const edgePositions: number[] = [];
  for (const [key, record] of edges) {
    const a = record.a;
    const b = record.b;
    if (!sharpEdges.has(key) && record.opposite.length === 2) {
      const [o1, o2] = record.opposite;
      for (let axis = 0; axis < 3; axis += 1) {
        edgePositions.push(
          (3 / 8) * (positions[a * 3 + axis] + positions[b * 3 + axis]) +
            (1 / 8) * (positions[o1 * 3 + axis] + positions[o2 * 3 + axis]),
        );
      }
    } else {
      for (let axis = 0; axis < 3; axis += 1) {
        edgePositions.push(0.5 * (positions[a * 3 + axis] + positions[b * 3 + axis]));
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
  // 逐角法线：只在夹角小于阈值的相邻面之间平滑，硬边两侧保持各自的法线，
  // 这样细分后的窗框、墙面仍然棱角分明，不会出现发亮的扭曲条纹。
  const faceCount = soup.faces.length / 3;
  const faceNormals: number[][] = new Array(faceCount);
  const vertexFaces: number[][] = Array.from(
    { length: soup.positions.length / 3 },
    () => [],
  );
  for (let f = 0; f < faceCount; f += 1) {
    const a = soup.faces[f * 3];
    const b = soup.faces[f * 3 + 1];
    const c = soup.faces[f * 3 + 2];
    const ax = soup.positions[a * 3];
    const ay = soup.positions[a * 3 + 1];
    const az = soup.positions[a * 3 + 2];
    const ux = soup.positions[b * 3] - ax;
    const uy = soup.positions[b * 3 + 1] - ay;
    const uz = soup.positions[b * 3 + 2] - az;
    const vx = soup.positions[c * 3] - ax;
    const vy = soup.positions[c * 3 + 1] - ay;
    const vz = soup.positions[c * 3 + 2] - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    faceNormals[f] = [nx / length, ny / length, nz / length];
    vertexFaces[a].push(f);
    vertexFaces[b].push(f);
    vertexFaces[c].push(f);
  }

  const positions: number[] = [];
  const normalData: number[] = [];
  const uvs: number[] = [];
  for (let corner = 0; corner < soup.faces.length; corner += 1) {
    const vertex = soup.faces[corner];
    const own = faceNormals[Math.floor(corner / 3)];
    let nx = 0;
    let ny = 0;
    let nz = 0;
    for (const face of vertexFaces[vertex]) {
      const normal = faceNormals[face];
      const dot = normal[0] * own[0] + normal[1] * own[1] + normal[2] * own[2];
      if (dot < SHARP_COS) continue;
      nx += normal[0];
      ny += normal[1];
      nz += normal[2];
    }
    const length = Math.hypot(nx, ny, nz);
    if (length < 1e-6) {
      nx = own[0];
      ny = own[1];
      nz = own[2];
    } else {
      nx /= length;
      ny /= length;
      nz /= length;
    }

    positions.push(
      soup.positions[vertex * 3],
      soup.positions[vertex * 3 + 1],
      soup.positions[vertex * 3 + 2],
    );
    normalData.push(nx, ny, nz);
    if (soup.hasUv) uvs.push(soup.uvs[corner * 2], soup.uvs[corner * 2 + 1]);
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new Float32BufferAttribute(normalData, 3));
  if (soup.hasUv) geometry.setAttribute("uv", new Float32BufferAttribute(uvs, 2));
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

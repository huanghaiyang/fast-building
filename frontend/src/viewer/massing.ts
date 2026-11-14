/**
 * 纯前端即时体量预览（blocking）。
 *
 * 不经过 Blender，按生成参数直接拼出体量、楼板、门窗洞示意与屋顶，
 * 用于拖参数时秒级看到形体变化；最终细节模型仍由 Blender 生成。
 * 只追求比例与开间关系正确，不追求构造细节。
 */

import * as THREE from "three";

import type { Footprint } from "../api/client";

const WALL_THICKNESS = 0.3;
const SLAB_THICKNESS = 0.12;

function facadeColor(seedText: string): string {
  const palette = ["#c9b79b", "#b9a88f", "#b28e74", "#a9a3a0", "#c0ae94"];
  let hash = 0;
  for (let i = 0; i < seedText.length; i += 1) hash = (hash * 31 + seedText.charCodeAt(i)) >>> 0;
  return palette[hash % palette.length];
}

function box(
  width: number,
  height: number,
  depth: number,
  material: THREE.Material,
  position: [number, number, number],
): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(position[0], position[1], position[2]);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/** 生成体量示意模型（Y 向上，原点在footprint 中心的地面）。 */
export function buildMassing(spec: Footprint): { group: THREE.Group; stats: { meshes: number; triangles: number } } {
  const group = new THREE.Group();
  group.name = "FB_MASSING";

  const facade = new THREE.MeshStandardMaterial({ color: facadeColor(spec.textureset || "default"), roughness: 0.86 });
  const trim = new THREE.MeshStandardMaterial({ color: "#e7e2d8", roughness: 0.7 });
  const glass = new THREE.MeshStandardMaterial({ color: "#1b2a33", roughness: 0.2, metalness: 0.35 });
  const roofMat = new THREE.MeshStandardMaterial({ color: "#7b4a3a", roughness: 0.8 });
  const slabMat = new THREE.MeshStandardMaterial({ color: "#9a958d", roughness: 0.9 });
  const doorMat = new THREE.MeshStandardMaterial({ color: "#5a4130", roughness: 0.75 });

  const width = spec.width;
  const depth = spec.depth;
  const floorHeight = spec.floor_height;
  const bays = Math.max(1, spec.bays);
  const bayWidth = width / bays;
  const wallHeight = Math.max(1.6, floorHeight - SLAB_THICKNESS);

  for (let floor = 0; floor < spec.floors; floor += 1) {
    const baseY = floor * floorHeight;
    const wallY = baseY + SLAB_THICKNESS + wallHeight * 0.5;

    // 楼板
    group.add(box(width, SLAB_THICKNESS, depth, slabMat, [0, baseY + SLAB_THICKNESS * 0.5, 0]));

    // 四面墙
    group.add(box(width, wallHeight, WALL_THICKNESS, facade, [0, wallY, -depth * 0.5 + WALL_THICKNESS * 0.5]));
    group.add(box(width, wallHeight, WALL_THICKNESS, facade, [0, wallY, depth * 0.5 - WALL_THICKNESS * 0.5]));
    group.add(box(WALL_THICKNESS, wallHeight, depth - WALL_THICKNESS * 2, facade, [-width * 0.5 + WALL_THICKNESS * 0.5, wallY, 0]));
    group.add(box(WALL_THICKNESS, wallHeight, depth - WALL_THICKNESS * 2, facade, [width * 0.5 - WALL_THICKNESS * 0.5, wallY, 0]));

    // 墙角压边，读起来更像木筋/石砌转角
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) {
        group.add(
          box(
            WALL_THICKNESS * 1.15,
            wallHeight,
            WALL_THICKNESS * 1.15,
            trim,
            [sx * (width * 0.5 - WALL_THICKNESS * 0.5), wallY, sz * (depth * 0.5 - WALL_THICKNESS * 0.5)],
          ),
        );
      }
    }

    // 门窗示意（前后立面按开间排布）
    const windowW = Math.min(spec.openings.window_w, bayWidth * 0.55);
    const windowH = Math.min(spec.openings.window_h, wallHeight * 0.62);
    const sill = Math.min(spec.openings.sill_h, wallHeight * 0.42);
    for (let bay = 0; bay < bays; bay += 1) {
      const centerX = -width * 0.5 + bayWidth * (bay + 0.5);
      const zFront = depth * 0.5 + 0.02;
      const zBack = -depth * 0.5 - 0.02;
      const y = baseY + SLAB_THICKNESS + sill + windowH * 0.5;
      if (floor === 0 && bay === Math.floor(bays / 2)) {
        const doorW = Math.min(spec.openings.door_w, bayWidth * 0.6);
        const doorH = Math.min(spec.openings.door_h, wallHeight - 0.2);
        group.add(box(doorW, doorH, 0.06, doorMat, [centerX, baseY + SLAB_THICKNESS + doorH * 0.5, zFront]));
      } else {
        group.add(box(windowW, windowH, 0.06, glass, [centerX, y, zFront]));
      }
      group.add(box(windowW, windowH, 0.06, glass, [centerX, y, zBack]));

      // 侧墙：每层两扇，沿进深方向均分
      for (const sideX of [-1, 1]) {
        for (const ratio of [0.3, 0.7]) {
          const sideZ = -depth * 0.5 + depth * ratio;
          const sideW = Math.min(spec.openings.window_w, depth * 0.22);
          group.add(
            box(0.06, windowH, sideW, glass, [
              sideX * (width * 0.5 + 0.02),
              baseY + SLAB_THICKNESS + sill + windowH * 0.5,
              sideZ,
            ]),
          );
        }
      }
    }
  }

  const totalHeight = spec.floors * floorHeight;

  if (spec.roof === "gable") {
    const rise = (width * 0.5) * Math.tan(THREE.MathUtils.degToRad(spec.roof_pitch));
    const overhang = 0.4;
    const half = width * 0.5 + overhang;
    const shape = new THREE.Shape();
    shape.moveTo(-half, 0);
    shape.lineTo(half, 0);
    shape.lineTo(0, rise);
    shape.closePath();
    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: depth + overhang * 2,
      bevelEnabled: false,
    });
    geometry.translate(0, 0, -(depth + overhang * 2) * 0.5);
    const roof = new THREE.Mesh(geometry, roofMat);
    roof.position.set(0, totalHeight, 0);
    roof.castShadow = true;
    roof.receiveShadow = true;
    group.add(roof);
  } else {
    group.add(box(width + 0.2, 0.24, depth + 0.2, roofMat, [0, totalHeight + 0.12, 0]));
    // 女儿墙
    const parapet = 0.55;
    group.add(box(width + 0.2, parapet, 0.2, facade, [0, totalHeight + 0.24 + parapet * 0.5, -(depth * 0.5 + 0.1)]));
    group.add(box(width + 0.2, parapet, 0.2, facade, [0, totalHeight + 0.24 + parapet * 0.5, depth * 0.5 + 0.1]));
  }

  // 阳台示意
  if (spec.balcony && spec.floors > 1) {
    const y = floorHeight + SLAB_THICKNESS * 0.5;
    group.add(box(width * 0.42, 0.14, 1.0, slabMat, [0, y, -depth * 0.5 - 0.5]));
    group.add(box(width * 0.42, 0.9, 0.08, trim, [0, y + 0.5, -depth * 0.5 - 0.98]));
  }

  let meshes = 0;
  let triangles = 0;
  group.traverse((child) => {
    if (!(child as THREE.Mesh).isMesh) return;
    meshes += 1;
    const geometry = (child as THREE.Mesh).geometry;
    const index = geometry.getIndex();
    if (index) triangles += index.count / 3;
    else if (geometry.attributes.position) triangles += geometry.attributes.position.count / 3;
  });

  return { group, stats: { meshes, triangles: Math.round(triangles) } };
}

/** 释放体量模型占用的几何与材质。 */
export function disposeMassing(group: THREE.Group): void {
  group.traverse((child) => {
    if (!(child as THREE.Mesh).isMesh) return;
    (child as THREE.Mesh).geometry.dispose();
    const material = (child as THREE.Mesh).material;
    const list = Array.isArray(material) ? material : [material];
    for (const item of list) item?.dispose();
  });
}

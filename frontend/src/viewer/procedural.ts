/**
 * 程序化贴图与材质增强。
 *
 * 这里生成两类灰度数据贴图：
 * - grunge：PBR 污渍遮罩，用于把 albedo 压向污渍色、并扰动粗糙度；
 * - roughness：细碎粗糙度起伏，叠加到标准材质的 roughnessMap。
 *
 * 全部用画布就地生成，不依赖外部资源；通过 onBeforeCompile 注入标准材质，
 * 避免覆盖 glTF 自带的 albedo / normal 贴图。
 */

import * as THREE from "three";

function createRng(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 生成一张低频值噪声，返回 [0,1] 的二维数组。 */
function valueNoise(size: number, cell: number, rng: () => number): Float32Array {
  const gridSize = Math.ceil(size / cell) + 2;
  const grid = new Float32Array(gridSize * gridSize);
  for (let i = 0; i < grid.length; i += 1) grid[i] = rng();
  const out = new Float32Array(size * size);
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const gx = x / cell;
      const gy = y / cell;
      const x0 = Math.floor(gx);
      const y0 = Math.floor(gy);
      const tx = gx - x0;
      const ty = gy - y0;
      const sx = tx * tx * (3 - 2 * tx);
      const sy = ty * ty * (3 - 2 * ty);
      const a = grid[y0 * gridSize + x0];
      const b = grid[y0 * gridSize + x0 + 1];
      const c = grid[(y0 + 1) * gridSize + x0];
      const d = grid[(y0 + 1) * gridSize + x0 + 1];
      out[y * size + x] = (a * (1 - sx) + b * sx) * (1 - sy) + (c * (1 - sx) + d * sx) * sy;
    }
  }
  return out;
}

function blend(target: Float32Array, source: Float32Array, weight: number): void {
  for (let i = 0; i < target.length; i += 1) {
    target[i] = target[i] * (1 - weight) + source[i] * weight;
  }
}

function smoothstep(edge0: number, edge1: number, value: number): number {
  const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

/** 生成污渍遮罩：大块渗染 + 细碎污点，0 表示干净，1 表示最脏。 */
function grungeData(size: number, seed: number): Float32Array {
  const rng = createRng(seed);
  const broad = valueNoise(size, size / 5, rng);
  const medium = valueNoise(size, size / 14, rng);
  const fine = valueNoise(size, size / 44, rng);
  blend(broad, medium, 0.45);
  blend(broad, fine, 0.12);

  const out = new Float32Array(size * size);
  for (let i = 0; i < out.length; i += 1) {
    const streak = Math.abs(broad[i] - 0.5) * 2;
    const base = smoothstep(0.38, 0.92, broad[i] * 0.82 + streak * 0.18);
    const speck = smoothstep(0.55, 0.95, fine[i]);
    out[i] = Math.min(1, base * 0.9 + speck * 0.22);
  }
  return out;
}

/** 生成粗糙度灰度噪声，围绕 0.5 起伏。 */
function roughnessData(size: number, seed: number): Float32Array {
  const rng = createRng(seed);
  const coarse = valueNoise(size, size / 9, rng);
  const fine = valueNoise(size, size / 30, rng);
  const out = new Float32Array(size * size);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = 0.34 + (coarse[i] * 0.6 + fine[i] * 0.4) * 0.62;
  }
  return out;
}

function toTexture(data: Float32Array, size: number): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const image = ctx.createImageData(size, size);
    for (let i = 0; i < data.length; i += 1) {
      const value = Math.round(Math.min(1, Math.max(0, data[i])) * 255);
      image.data[i * 4] = value;
      image.data[i * 4 + 1] = value;
      image.data[i * 4 + 2] = value;
      image.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(image, 0, 0);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.NoColorSpace;
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  return texture;
}

let grungeTexture: THREE.CanvasTexture | null = null;
let roughnessTexture: THREE.CanvasTexture | null = null;

export function getGrungeTexture(): THREE.CanvasTexture {
  if (!grungeTexture) grungeTexture = toTexture(grungeData(512, 20261111), 512);
  return grungeTexture;
}

export function getRoughnessTexture(): THREE.CanvasTexture {
  if (!roughnessTexture) roughnessTexture = toTexture(roughnessData(256, 778899), 256);
  return roughnessTexture;
}

export interface GrungeUniforms {
  uGrungeMap: { value: THREE.Texture | null };
  uGrungeStrength: { value: number };
  uGrungeScale: { value: number };
  uStainColor: { value: THREE.Color };
  uGrungeRough: { value: number };
}

export function createGrungeUniforms(): GrungeUniforms {
  return {
    uGrungeMap: { value: null },
    uGrungeStrength: { value: 0 },
    uGrungeScale: { value: 3 },
    uStainColor: { value: new THREE.Color("#2f2a24") },
    uGrungeRough: { value: 0.45 },
  };
}

/**
 * 给标准材质注入污渍着色。可重复调用，只打一次补丁。
 * 通过共享 uniforms 修改强度，不需要重新编译着色器。
 */
export function patchGrunge(
  material: THREE.MeshStandardMaterial,
  uniforms: GrungeUniforms,
): void {
  if (material.userData.fbGrungePatched) return;
  material.userData.fbGrungePatched = true;

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uGrungeMap = uniforms.uGrungeMap;
    shader.uniforms.uGrungeStrength = uniforms.uGrungeStrength;
    shader.uniforms.uGrungeScale = uniforms.uGrungeScale;
    shader.uniforms.uStainColor = uniforms.uStainColor;
    shader.uniforms.uGrungeRough = uniforms.uGrungeRough;

    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nuniform float uGrungeScale;\nvarying vec2 vFbGrungeUv;",
      )
      .replace("#include <uv_vertex>", "#include <uv_vertex>\nvFbGrungeUv = uv * uGrungeScale;");

    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        [
          "#include <common>",
          "uniform sampler2D uGrungeMap;",
          "uniform float uGrungeStrength;",
          "uniform float uGrungeRough;",
          "uniform vec3 uStainColor;",
          "varying vec2 vFbGrungeUv;",
        ].join("\n"),
      )
      .replace(
        "#include <map_fragment>",
        [
          "#include <map_fragment>",
          "float fbStain = texture2D( uGrungeMap, vFbGrungeUv ).r;",
          "diffuseColor.rgb = mix( diffuseColor.rgb, uStainColor, clamp( fbStain * uGrungeStrength, 0.0, 1.0 ) );",
        ].join("\n"),
      )
      .replace(
        "#include <roughnessmap_fragment>",
        [
          "#include <roughnessmap_fragment>",
          "roughnessFactor = clamp( roughnessFactor + ( fbStain - 0.42 ) * uGrungeRough, 0.04, 1.0 );",
        ].join("\n"),
      );
  };
  material.customProgramCacheKey = () => "fb-grunge";
  material.needsUpdate = true;
}

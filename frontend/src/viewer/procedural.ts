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

export interface SurfaceSettings {
  /** 次表面散射强度（0~1）。 */
  subsurface: number;
  /** 次表面散射透出的颜色。 */
  subsurfaceColor: string;
  /** 漫反射包裹系数，让背光面也有柔和过渡。 */
  diffuseWrap: number;
}

export interface MaterialFXUniforms {
  uGrungeMap: { value: THREE.Texture | null };
  uGrungeStrength: { value: number };
  uGrungeScale: { value: number };
  uStainColor: { value: THREE.Color };
  uGrungeRough: { value: number };
  uTime: { value: number };
  uWetness: { value: number };
  uRainFlow: { value: number };
  /** 积雪覆盖 0~1：按世界法线朝上程度在表面叠加雪层。 */
  uSnow: { value: number };
  uSSS: { value: number };
  uSSSColor: { value: THREE.Color };
  uDiffuseWrap: { value: number };
  uSunDir: { value: THREE.Vector3 };
}

export function createMaterialFXUniforms(): MaterialFXUniforms {
  return {
    uGrungeMap: { value: null },
    uGrungeStrength: { value: 0 },
    uGrungeScale: { value: 3 },
    uStainColor: { value: new THREE.Color("#2f2a24") },
    uGrungeRough: { value: 0.45 },
    uTime: { value: 0 },
    uWetness: { value: 0 },
    uRainFlow: { value: 0.6 },
    uSnow: { value: 0 },
    uSSS: { value: 0.35 },
    uSSSColor: { value: new THREE.Color("#c96a3f") },
    uDiffuseWrap: { value: 0.4 },
    uSunDir: { value: new THREE.Vector3(0.5, 0.7, 0.4).normalize() },
  };
}

/**
 * 给标准材质注入统一表面效果：
 * - PBR 污渍蒙版；
 * - 湿润变暗与粗糙度下降；
 * - 沿重力方向流动的雨水条纹；
 * - 漫反射包裹与次表面散射近似。
 *
 * 所有效果共享 uniforms，运行期调参不需要重编译着色器。
 */
export function patchMaterialFX(
  material: THREE.MeshStandardMaterial,
  uniforms: MaterialFXUniforms,
): void {
  if (material.userData.fbMaterialFxPatched) return;
  material.userData.fbMaterialFxPatched = true;

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uGrungeMap = uniforms.uGrungeMap;
    shader.uniforms.uGrungeStrength = uniforms.uGrungeStrength;
    shader.uniforms.uGrungeScale = uniforms.uGrungeScale;
    shader.uniforms.uStainColor = uniforms.uStainColor;
    shader.uniforms.uGrungeRough = uniforms.uGrungeRough;
    shader.uniforms.uTime = uniforms.uTime;
    shader.uniforms.uWetness = uniforms.uWetness;
    shader.uniforms.uRainFlow = uniforms.uRainFlow;
    shader.uniforms.uSnow = uniforms.uSnow;
    shader.uniforms.uSSS = uniforms.uSSS;
    shader.uniforms.uSSSColor = uniforms.uSSSColor;
    shader.uniforms.uDiffuseWrap = uniforms.uDiffuseWrap;
    shader.uniforms.uSunDir = uniforms.uSunDir;

    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        [
          "#include <common>",
          "uniform float uGrungeScale;",
          "varying vec2 vFbGrungeUv;",
          "varying vec3 vFbWorldPos;",
          "varying vec3 vFbWorldNormal;",
        ].join("\n"),
      )
      .replace(
        "#include <beginnormal_vertex>",
        "#include <beginnormal_vertex>\nvFbWorldNormal = normalize( mat3( modelMatrix ) * objectNormal );",
      )
      .replace("#include <uv_vertex>", "#include <uv_vertex>\nvFbGrungeUv = uv * uGrungeScale;")
      .replace(
        "#include <project_vertex>",
        "#include <project_vertex>\nvFbWorldPos = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;",
      );

    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        [
          "#include <common>",
          "uniform sampler2D uGrungeMap;",
          "uniform float uGrungeStrength;",
          "uniform float uGrungeRough;",
          "uniform vec3 uStainColor;",
          "uniform float uTime;",
          "uniform float uWetness;",
          "uniform float uRainFlow;",
          "uniform float uSnow;",
          "uniform float uSSS;",
          "uniform vec3 uSSSColor;",
          "uniform float uDiffuseWrap;",
          "uniform vec3 uSunDir;",
          "varying vec2 vFbGrungeUv;",
          "varying vec3 vFbWorldPos;",
          "varying vec3 vFbWorldNormal;",
          "float fbHash( vec2 p ) { return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 ); }",
          "float fbNoise( vec2 p ) {",
          "  vec2 i = floor( p );",
          "  vec2 f = fract( p );",
          "  f = f * f * ( 3.0 - 2.0 * f );",
          "  float a = fbHash( i );",
          "  float b = fbHash( i + vec2( 1.0, 0.0 ) );",
          "  float c = fbHash( i + vec2( 0.0, 1.0 ) );",
          "  float d = fbHash( i + vec2( 1.0, 1.0 ) );",
          "  return mix( mix( a, b, f.x ), mix( c, d, f.x ), f.y );",
          "}",
          "float fbFbm( vec2 p ) {",
          "  float value = 0.0;",
          "  float amplitude = 0.5;",
          "  for ( int i = 0; i < 4; i ++ ) {",
          "    value += amplitude * fbNoise( p );",
          "    p *= 2.03;",
          "    amplitude *= 0.5;",
          "  }",
          "  return value;",
          "}",
          "float fbWaterStreak( vec3 p, float t ) {",
          "  // 多层水膜：大块积水 + 顺重力下淌细流 + 边缘破断 + 水珠",
          "  float film = fbFbm( vec2( p.x * 0.62 + p.z * 0.38, p.z * 0.66 - p.x * 0.27 ) );",
          "  float runnel = fbFbm( vec2( p.x * 2.7, p.y * 0.5 + t * 0.95 ) );",
          "  float breakup = fbFbm( vec2( p.x * 5.4, p.y * 1.35 + t * 1.8 ) );",
          "  float beads = fbNoise( vec2( p.x * 9.5, p.y * 5.2 + t * 0.32 ) );",
          "  float sheet = smoothstep( 0.4, 0.86, film );",
          "  float streaks = smoothstep( 0.46, 0.9, runnel ) * smoothstep( 0.32, 0.68, breakup );",
          "  float drops = smoothstep( 0.72, 0.96, beads ) * 0.22;",
          "  return clamp( sheet * 0.5 + streaks * 0.85 + drops, 0.0, 1.0 );",
          "}",
          "float fbSnowMask( vec3 p, vec3 n ) {",
          "  // 朝上的面先积雪；立面靠噪声形成不规则的挂雪边缘",
          "  float up = clamp( n.y, 0.0, 1.0 );",
          "  float patchy = fbFbm( vec2( p.x * 0.55 + p.z * 0.33, p.z * 0.48 - p.x * 0.26 ) );",
          "  float settled = smoothstep( 0.12, 0.85, up + ( patchy - 0.5 ) * 0.42 );",
          "  float edge = smoothstep( 0.3, 0.72, fbFbm( p.xz * 1.6 ) );",
          "  return clamp( settled * uSnow * mix( 0.55, 1.0, edge ), 0.0, 1.0 );",
          "}",
        ].join("\n"),
      )
      .replace(
        "#include <map_fragment>",
        [
          "#include <map_fragment>",
          "float fbStain = texture2D( uGrungeMap, vFbGrungeUv ).r;",
          "diffuseColor.rgb = mix( diffuseColor.rgb, uStainColor, clamp( fbStain * uGrungeStrength, 0.0, 1.0 ) );",
          "vec3 fbWorldNormal = normalize( vFbWorldNormal );",
          "float fbFlow = fbWaterStreak( vFbWorldPos, uTime ) * mix( 0.4, 1.0, smoothstep( -0.35, 0.65, fbWorldNormal.y ) );",
          "diffuseColor.rgb *= mix( 1.0, 0.72, uWetness );",
          "diffuseColor.rgb *= 1.0 - fbFlow * uRainFlow * 0.12;",
          "float fbSnow = fbSnowMask( vFbWorldPos, fbWorldNormal );",
          "diffuseColor.rgb = mix( diffuseColor.rgb, vec3( 0.93, 0.95, 0.99 ), fbSnow );",
        ].join("\n"),
      )
      .replace(
        "#include <roughnessmap_fragment>",
        [
          "#include <roughnessmap_fragment>",
          "roughnessFactor = clamp( roughnessFactor + ( fbStain - 0.42 ) * uGrungeRough, 0.04, 1.0 );",
          "roughnessFactor = mix( roughnessFactor, 0.14, uWetness * 0.72 );",
          "roughnessFactor = mix( roughnessFactor, 0.035, fbFlow * uRainFlow * 0.75 );",
          "roughnessFactor = mix( roughnessFactor, 0.84, fbSnow );",
          "roughnessFactor = clamp( roughnessFactor, 0.025, 1.0 );",
        ].join("\n"),
      )
      .replace(
        "#include <metalnessmap_fragment>",
        [
          "#include <metalnessmap_fragment>",
          "metalnessFactor = mix( metalnessFactor, 0.18, uWetness * 0.5 );",
          "metalnessFactor = mix( metalnessFactor, 0.0, fbSnow );",
        ].join("\n"),
      )
      .replace(
        "#include <lights_fragment_end>",
        [
          "#include <lights_fragment_end>",
          "vec3 fbSunView = normalize( ( viewMatrix * vec4( uSunDir, 0.0 ) ).xyz );",
          "float fbNdotL = max( dot( normalize( normal ), fbSunView ), 0.0 );",
          "float fbWrap = fbNdotL * 0.5 + 0.5;",
          "float fbBack = pow( max( dot( -normalize( vViewPosition ), fbSunView ), 0.0 ), 2.5 );",
          "reflectedLight.directDiffuse += diffuseColor.rgb * uDiffuseWrap * fbWrap * 0.08;",
          "reflectedLight.directDiffuse += diffuseColor.rgb * uSSSColor * uSSS * ( fbWrap * 0.18 + fbBack * 0.8 );",
          "vec3 fbViewDir = normalize( -vViewPosition );",
          "float fbFresnel = pow( 1.0 - max( dot( normalize( normal ), fbViewDir ), 0.0 ), 3.0 );",
          "float fbSheen = uWetness * ( 0.08 + fbFlow * uRainFlow * 0.3 ) * mix( 0.4, 1.0, fbFresnel );",
          "reflectedLight.indirectSpecular += vec3( 0.55, 0.62, 0.72 ) * fbSheen;",
          "reflectedLight.indirectSpecular += vec3( 0.42, 0.48, 0.58 ) * fbSnow * ( 0.1 + fbFresnel * 0.16 );",
        ].join("\n"),
      );
  };
  material.customProgramCacheKey = () => "fb-material-fx";
  material.needsUpdate = true;
}

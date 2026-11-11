/**
 * three.js 建筑预览器。
 *
 * 只负责场景、相机、灯光、GLB 加载与视图操作，React 层通过方法调用控制。
 * 环境光使用程序化天空（等距圆柱贴图）经 PMREM 生成，避免依赖外部 HDR 资源。
 */

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { RainSystem, VolumetricLight, VoxelFracture } from "./effects";
import {
  GrungeUniforms,
  createGrungeUniforms,
  getGrungeTexture,
  getRoughnessTexture,
  patchGrunge,
} from "./procedural";
import { subdivideGeometry } from "./subdivide";

export interface ViewerStats {
  meshes: number;
  triangles: number;
  textures: number;
  size: [number, number, number];
}

export type ViewerStatus = "idle" | "loading" | "ready" | "error";

export type ViewAxis = "px" | "nx" | "py" | "ny" | "pz" | "nz";

export const VIEW_AXES: Array<{ id: ViewAxis; label: string }> = [
  { id: "px", label: "+X" },
  { id: "nx", label: "-X" },
  { id: "py", label: "+Y" },
  { id: "ny", label: "-Y" },
  { id: "pz", label: "+Z" },
  { id: "nz", label: "-Z" },
];

export type EnvironmentPreset = "midday" | "golden" | "overcast" | "night" | "studio";

export type ShadowQuality = "low" | "medium" | "high";

export const SHADOW_QUALITIES: Array<{ id: ShadowQuality; label: string }> = [
  { id: "low", label: "低" },
  { id: "medium", label: "中" },
  { id: "high", label: "高" },
];

export const ENVIRONMENTS: Array<{ id: EnvironmentPreset; label: string }> = [
  { id: "midday", label: "晴天正午" },
  { id: "golden", label: "黄昏斜阳" },
  { id: "overcast", label: "阴天柔光" },
  { id: "night", label: "夜晚月光" },
  { id: "studio", label: "影棚中性" },
];

export interface NodeInfo {
  id: string;
  name: string;
  material: string;
  triangles: number;
}

export interface NodeMaterialState {
  color: string;
  roughness: number;
  metalness: number;
  emissive: string;
  emissiveIntensity: number;
}

export type ClipAxis = "x" | "y" | "z";

export interface ClipSettings {
  enabled: boolean;
  axis: ClipAxis;
  position: number;
  flipped: boolean;
}

export type AttractorMode = "attract" | "repel";

export interface AttractorSettings {
  enabled: boolean;
  mode: AttractorMode;
  strength: number;
  radius: number;
  point: [number, number, number];
}

export interface FractureSettings {
  enabled: boolean;
  amount: number;
  cell: number;
}

export interface VolumetricSettings {
  enabled: boolean;
  intensity: number;
}

export interface SunSettings {
  /** 方位角（度）：绕建筑旋转太阳，0~360。 */
  azimuth: number;
  /** 高度角（度）：0 为地平线，90 为天顶。 */
  elevation: number;
}

/** 主光到场景中心的距离，保证阴影相机覆盖面稳定。 */
const SUN_DISTANCE = 46;

export interface RoughnessSettings {
  enabled: boolean;
  scale: number;
  strength: number;
}

export interface GrungeSettings {
  enabled: boolean;
  strength: number;
  scale: number;
  color: string;
  roughness: number;
}

export interface BlockInfo {
  id: string;
  name: string;
  position: [number, number, number];
  size: [number, number, number];
  color: string;
}

export interface BlockPatch {
  position?: [number, number, number];
  size?: [number, number, number];
  color?: string;
}

interface SkyConfig {
  top: string;
  horizon: string;
  bottom: string;
  sun?: { color: string; radius: number };
}

interface EnvironmentConfig {
  exposure: number;
  background: string;
  fog: [string, number, number];
  hemi: { sky: string; ground: string; intensity: number };
  key: { color: string; intensity: number; position: [number, number, number] };
  fill: { color: string; intensity: number; position: [number, number, number] };
  ground: string;
  gridOpacity: number;
  sky?: SkyConfig;
}

const ENV_CONFIGS: Record<EnvironmentPreset, EnvironmentConfig> = {
  midday: {
    exposure: 1.0,
    background: "#a8cbe8",
    fog: ["#bcd6e8", 90, 340],
    hemi: { sky: "#cfe6ff", ground: "#5b5648", intensity: 1.1 },
    key: { color: "#fff4e0", intensity: 2.7, position: [26, 38, 20] },
    fill: { color: "#a9c8ff", intensity: 0.5, position: [-20, 16, -22] },
    ground: "#6e6a5e",
    gridOpacity: 0.32,
    sky: {
      top: "#3f7fc4",
      horizon: "#cfe4f2",
      bottom: "#6b6b60",
      sun: { color: "#fff6d8", radius: 70 },
    },
  },
  golden: {
    exposure: 1.05,
    background: "#e0a86e",
    fog: ["#e8b887", 70, 320],
    hemi: { sky: "#ffd9a8", ground: "#4a3a30", intensity: 0.75 },
    key: { color: "#ffb46b", intensity: 2.3, position: [30, 12, 18] },
    fill: { color: "#7f9fd8", intensity: 0.35, position: [-18, 10, -20] },
    ground: "#5a4a3c",
    gridOpacity: 0.28,
    sky: {
      top: "#2f4f7a",
      horizon: "#f2b06a",
      bottom: "#4a3a30",
      sun: { color: "#ffcf8a", radius: 110 },
    },
  },
  overcast: {
    exposure: 1.1,
    background: "#dfe5ea",
    fog: ["#c9d0d6", 80, 320],
    hemi: { sky: "#e8eef4", ground: "#6a6f72", intensity: 1.35 },
    key: { color: "#eef2f6", intensity: 1.1, position: [18, 30, 14] },
    fill: { color: "#dfe6ee", intensity: 0.6, position: [-16, 14, -18] },
    ground: "#7c807f",
    gridOpacity: 0.35,
    sky: { top: "#c2ccd4", horizon: "#eef2f5", bottom: "#8a8f90" },
  },
  night: {
    exposure: 1.15,
    background: "#0d1520",
    fog: ["#0d1520", 60, 280],
    hemi: { sky: "#38507a", ground: "#0a0d12", intensity: 0.55 },
    key: { color: "#b9cdf7", intensity: 0.95, position: [-24, 30, 18] },
    fill: { color: "#2f4a7a", intensity: 0.25, position: [16, 12, -18] },
    ground: "#1b2028",
    gridOpacity: 0.5,
    sky: {
      top: "#050914",
      horizon: "#16243c",
      bottom: "#0a0e16",
      sun: { color: "#e8f0ff", radius: 30 },
    },
  },
  studio: {
    exposure: 1.05,
    background: "#0a0e13",
    fog: ["#0a0e13", 80, 220],
    hemi: { sky: "#9db4d0", ground: "#141414", intensity: 0.85 },
    key: { color: "#fff0d8", intensity: 2.4, position: [22, 32, 18] },
    fill: { color: "#8fb6ff", intensity: 0.55, position: [-18, 14, -20] },
    ground: "#0f151c",
    gridOpacity: 0.55,
  },
};

export class BuildingViewer {
  private readonly container: HTMLElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly controls: OrbitControls;
  private readonly loader = new GLTFLoader();
  private readonly pmrem: THREE.PMREMGenerator;
  private readonly resizeObserver: ResizeObserver;

  private hemi!: THREE.HemisphereLight;
  private key!: THREE.DirectionalLight;
  private fill!: THREE.DirectionalLight;
  private groundMaterial!: THREE.MeshStandardMaterial;
  private grid!: THREE.GridHelper;

  private envTarget: THREE.WebGLRenderTarget | null = null;
  private studioTarget: THREE.WebGLRenderTarget | null = null;
  private skyTexture: THREE.Texture | null = null;

  private model: THREE.Object3D | null = null;
  private readonly originalGeometries = new Map<THREE.Mesh, THREE.BufferGeometry>();
  private animationId = 0;
  private disposed = false;
  private defaultPosition = new THREE.Vector3(20, 16, 24);
  private defaultTarget = new THREE.Vector3(0, 3, 0);
  private viewDistance = 26;

  private ambientMultiplier = 1;
  private baseHemiIntensity = 1;
  private shadowQuality: ShadowQuality = "medium";
  private subdivisionLevel = 0;

  // ---------------------------------------------------------------- 实时工作室
  onNodePick: ((node: NodeInfo | null) => void) | null = null;
  onClipPosition: ((position: number) => void) | null = null;
  onAttractorPoint: ((point: [number, number, number]) => void) | null = null;
  onBlocksChanged: ((blocks: BlockInfo[]) => void) | null = null;
  onSelectedBlock: ((block: BlockInfo | null) => void) | null = null;
  onSunChange: ((sun: SunSettings) => void) | null = null;

  private sunSettings: SunSettings = { azimuth: 52, elevation: 49 };
  private skyConfig: SkyConfig | null = null;
  private skyTimer = 0;
  private readonly sunDir = new THREE.Vector3();

  private readonly raycaster = new THREE.Raycaster();
  private readonly nodes = new Map<string, THREE.Mesh>();
  private selectionHelper: THREE.BoxHelper | null = null;

  private modelBox = new THREE.Box3(new THREE.Vector3(-6, 0, -6), new THREE.Vector3(6, 6, 6));
  private readonly clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
  private clipSettings: ClipSettings = { enabled: false, axis: "x", position: 0, flipped: false };
  private clipHelper!: THREE.PlaneHelper;
  private clipDragEnabled = false;
  private clipDragging = false;
  private clipLastY = 0;
  private clipApplied = false;

  private readonly grungeUniforms: GrungeUniforms = createGrungeUniforms();
  private grungeSettings: GrungeSettings = {
    enabled: false,
    strength: 0.55,
    scale: 3,
    color: "#2f2a24",
    roughness: 0.45,
  };
  private roughnessSettings: RoughnessSettings = { enabled: false, scale: 6, strength: 0.6 };

  private readonly rain = new RainSystem();
  private readonly rainCenter = new THREE.Vector3(0, 0, 0);
  private baseFogNear = 80;
  private baseFogFar = 220;
  private readonly clock = new THREE.Clock();
  private wetness = 0;
  private rainLevel = 0;
  private baseGroundColor = new THREE.Color("#0f151c");
  private baseGroundRoughness = 0.96;

  private attractorSettings: AttractorSettings = {
    enabled: false,
    mode: "attract",
    strength: 1.6,
    radius: 4,
    point: [0, 3, 0],
  };
  private attractorPickMode = false;
  private readonly deformBases = new WeakMap<
    THREE.Mesh,
    { position: Float32Array; normal: Float32Array | null }
  >();

  private readonly voxel = new VoxelFracture();
  private fractureSettings: FractureSettings = { enabled: false, amount: 0, cell: 0.42 };
  private fractureCell = 0;

  private readonly volumetric = new VolumetricLight();
  private volumetricSettings: VolumetricSettings = { enabled: false, intensity: 0.8 };

  // ---------------------------------------------------------------- 第一人称
  onFirstPersonChange: ((enabled: boolean) => void) | null = null;
  onFirstPersonLock: ((locked: boolean) => void) | null = null;
  private firstPerson = false;
  private fpLocked = false;
  private readonly fpKeys = new Set<string>();
  private readonly fpSaved = {
    position: new THREE.Vector3(),
    target: new THREE.Vector3(),
    fov: 38,
  };
  private readonly fpMove = new THREE.Vector3();
  private fpYaw = 0;
  private fpPitch = 0;

  private readonly blockGroup = new THREE.Group();
  private readonly blocks: THREE.Mesh[] = [];
  private blockSeq = 0;
  private buildMode = false;
  private selectedBlockId: string | null = null;

  private pointerState = { x: 0, y: 0, active: false, moved: false };
  private viewLocked = false;

  constructor(container: HTMLElement) {
    this.container = container;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(container.clientWidth || 800, container.clientHeight || 600);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.localClippingEnabled = true;
    container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#0a0e13");
    this.scene.fog = new THREE.Fog("#0a0e13", 80, 220);

    this.camera = new THREE.PerspectiveCamera(
      38,
      (container.clientWidth || 800) / (container.clientHeight || 600),
      0.1,
      1000,
    );
    this.camera.position.copy(this.defaultPosition);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 200;
    // 放开俯仰限制，才能切到 +Y / -Y 的正交视角
    this.controls.maxPolarAngle = Math.PI;
    this.controls.target.copy(this.defaultTarget);
    this.controls.autoRotateSpeed = 0.7;
    this.controls.update();

    this.pmrem = new THREE.PMREMGenerator(this.renderer);
    this.setupLights();
    this.setupGround();
    this.applyEnvironment("midday");

    this.scene.add(this.rain.group);
    this.scene.add(this.volumetric.group);
    this.scene.add(this.voxel.group);
    this.scene.add(this.blockGroup);

    this.clipHelper = new THREE.PlaneHelper(this.clipPlane, 24, 0x58e0c4);
    this.clipHelper.visible = false;
    const helperMaterial = this.clipHelper.material as THREE.LineBasicMaterial;
    helperMaterial.transparent = true;
    helperMaterial.opacity = 0.85;
    helperMaterial.depthTest = false;
    this.clipHelper.renderOrder = 3;
    this.scene.add(this.clipHelper);

    this.renderer.domElement.addEventListener("pointerdown", this.handlePointerDown);
    window.addEventListener("pointermove", this.handlePointerMove);
    window.addEventListener("pointerup", this.handlePointerUp);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.animate();
  }

  // ------------------------------------------------------------------ 场景
  private setupLights(): void {
    this.hemi = new THREE.HemisphereLight(0x9db4d0, 0x141414, 0.85);
    this.scene.add(this.hemi);

    const key = new THREE.DirectionalLight(0xfff0d8, 2.4);
    key.position.set(22, 32, 18);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 220;
    key.shadow.camera.left = -45;
    key.shadow.camera.right = 45;
    key.shadow.camera.top = 45;
    key.shadow.camera.bottom = -45;
    key.shadow.bias = -0.0004;
    this.scene.add(key);
    this.key = key;

    const fill = new THREE.DirectionalLight(0x8fb6ff, 0.55);
    fill.position.set(-18, 14, -20);
    this.scene.add(fill);
    this.fill = fill;
  }

  private setupGround(): void {
    this.groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f151c,
      roughness: 0.96,
      metalness: 0.0,
    });
    const ground = new THREE.Mesh(new THREE.CircleGeometry(90, 64), this.groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.02;
    ground.receiveShadow = true;
    this.scene.add(ground);

    this.grid = new THREE.GridHelper(160, 80, 0x2b3947, 0x18222c);
    this.grid.position.y = 0.005;
    (this.grid.material as THREE.Material).transparent = true;
    (this.grid.material as THREE.Material).opacity = 0.55;
    this.scene.add(this.grid);
  }

  /** 依据方位角/高度角计算指向太阳的单位向量。 */
  private sunDirection(): THREE.Vector3 {
    const elevation = THREE.MathUtils.degToRad(this.sunSettings.elevation);
    const azimuth = THREE.MathUtils.degToRad(this.sunSettings.azimuth);
    this.sunDir.set(
      Math.cos(elevation) * Math.sin(azimuth),
      Math.sin(elevation),
      Math.cos(elevation) * Math.cos(azimuth),
    );
    return this.sunDir;
  }

  /** 生成纵向渐变的等距圆柱天空贴图，太阳光晕按当前方位角/高度角绘制。 */
  private createSkyTexture(sky: SkyConfig): THREE.Texture {
    const width = 1024;
    const height = 512;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, sky.top);
      gradient.addColorStop(0.5, sky.horizon);
      gradient.addColorStop(1, sky.bottom);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      if (sky.sun) {
        // 与 three.js 的等距圆柱映射一致，光晕才会落在主光的真实方向上
        const dir = this.sunDirection();
        const u = Math.atan2(dir.z, dir.x) / (Math.PI * 2) + 0.5;
        const v = Math.asin(THREE.MathUtils.clamp(dir.y, -1, 1)) / Math.PI + 0.5;
        const cx = u * width;
        const cy = (1 - v) * height;
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, sky.sun.radius);
        glow.addColorStop(0, sky.sun.color);
        glow.addColorStop(0.35, `${sky.sun.color}99`);
        glow.addColorStop(1, `${sky.sun.color}00`);
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, width, height);
      }
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.mapping = THREE.EquirectangularReflectionMapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  private ensureStudioTarget(): THREE.WebGLRenderTarget {
    if (!this.studioTarget) {
      this.studioTarget = this.pmrem.fromScene(new RoomEnvironment(), 0.04);
    }
    return this.studioTarget;
  }

  private disposeEnvironment(): void {
    this.envTarget?.dispose();
    this.envTarget = null;
    this.skyTexture?.dispose();
    this.skyTexture = null;
  }

  private applyEnvironment(preset: EnvironmentPreset): void {
    const config = ENV_CONFIGS[preset] ?? ENV_CONFIGS.midday;
    this.renderer.toneMappingExposure = config.exposure;

    const [fogColor, near, far] = config.fog;
    this.scene.fog = new THREE.Fog(fogColor, near, far);
    this.baseFogNear = near;
    this.baseFogFar = far;

    this.baseHemiIntensity = config.hemi.intensity;
    this.hemi.color.set(config.hemi.sky);
    this.hemi.groundColor.set(config.hemi.ground);
    this.hemi.intensity = this.baseHemiIntensity * this.ambientMultiplier;

    this.key.color.set(config.key.color);
    this.key.intensity = config.key.intensity;
    // 环境预设给出太阳的初始方位与高度，之后可在面板里手动细调
    this.sunSettings = this.sunFromVector(config.key.position);
    this.key.position.copy(this.sunDirection()).multiplyScalar(SUN_DISTANCE);

    this.fill.color.set(config.fill.color);
    this.fill.intensity = config.fill.intensity;
    this.fill.position.set(...config.fill.position);

    this.groundMaterial.color.set(config.ground);
    this.baseGroundColor.set(config.ground);
    (this.grid.material as THREE.Material).opacity = config.gridOpacity;

    this.disposeEnvironment();
    this.skyConfig = config.sky ?? null;
    if (config.sky) {
      const skyTexture = this.createSkyTexture(config.sky);
      this.skyTexture = skyTexture;
      this.scene.background = skyTexture;
      this.envTarget = this.pmrem.fromEquirectangular(skyTexture);
      this.scene.environment = this.envTarget.texture;
    } else {
      this.scene.background = new THREE.Color(config.background);
      // 影棚环境贴图可复用，不能随切换释放
      this.scene.environment = this.ensureStudioTarget().texture;
    }
    this.scene.environmentIntensity = this.ambientMultiplier;
    this.applyWetness();
    this.updateVolumetricAnchor();
    this.onSunChange?.(this.getSun());
  }

  /** 当前阳光方位角与高度角（度）。 */
  getSun(): SunSettings {
    return { ...this.sunSettings };
  }

  /** 调整阳光朝向与高度：主光、天空光晕、阴影与体积光同步更新。 */
  setSun(patch: Partial<SunSettings>): void {
    const azimuth = (((patch.azimuth ?? this.sunSettings.azimuth) % 360) + 360) % 360;
    const elevation = Math.max(0, Math.min(90, patch.elevation ?? this.sunSettings.elevation));
    if (
      Math.abs(azimuth - this.sunSettings.azimuth) < 0.01 &&
      Math.abs(elevation - this.sunSettings.elevation) < 0.01
    ) {
      return;
    }
    this.sunSettings = { azimuth, elevation };
    this.key.position.copy(this.sunDirection()).multiplyScalar(SUN_DISTANCE);
    this.updateVolumetricAnchor();
    this.scheduleSkyRebuild();
    this.onSunChange?.(this.getSun());
  }

  /** 由光照位置反推方位角与高度角，用于环境切换时同步滑块。 */
  private sunFromVector(position: [number, number, number]): SunSettings {
    const vector = new THREE.Vector3(...position);
    const length = vector.length() || 1;
    const elevation = THREE.MathUtils.radToDeg(
      Math.asin(THREE.MathUtils.clamp(vector.y / length, -1, 1)),
    );
    const azimuth = ((THREE.MathUtils.radToDeg(Math.atan2(vector.x, vector.z)) % 360) + 360) % 360;
    return { azimuth, elevation: Math.max(0, Math.min(90, elevation)) };
  }

  /** 拖动滑块时合并重建：先实时更新主光，稍后再重绘天空与环境贴图。 */
  private scheduleSkyRebuild(): void {
    if (this.skyTimer) window.clearTimeout(this.skyTimer);
    this.skyTimer = window.setTimeout(() => {
      this.skyTimer = 0;
      if (this.disposed) return;
      this.rebuildSky();
    }, 90);
  }

  /** 重绘天空贴图并刷新 IBL，让太阳光晕跟随手动调整的角度。 */
  private rebuildSky(): void {
    if (!this.skyConfig) return;
    const texture = this.createSkyTexture(this.skyConfig);
    this.skyTexture?.dispose();
    this.skyTexture = texture;
    this.scene.background = texture;
    this.envTarget?.dispose();
    this.envTarget = this.pmrem.fromEquirectangular(texture);
    this.scene.environment = this.envTarget.texture;
    this.scene.environmentIntensity = this.ambientMultiplier;
  }

  private resize(): void {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    if (!width || !height) return;
    this.renderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  private animate = (): void => {
    if (this.disposed) return;
    this.animationId = requestAnimationFrame(this.animate);
    const delta = this.clock.getDelta();
    this.rain.update(delta);
    this.volumetric.update(delta, this.camera);
    this.updateFirstPerson(delta);
    if (!this.firstPerson) this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };

  // ------------------------------------------------------------------ 模型
  load(url: string, onStats: (stats: ViewerStats) => void, onStatus: (status: ViewerStatus, message?: string) => void): void {
    onStatus("loading");
    this.loader.load(
      url,
      (gltf) => {
        this.clearModel();
        const model = gltf.scene;
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh;
            mesh.castShadow = true;
            mesh.receiveShadow = true;

            // 每个节点独立克隆材质，后续单节点调色/粗糙度不会互相污染
            const source = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const cloned = source.map((material) => {
              const next = material.clone();
              const standard = next as THREE.MeshStandardMaterial;
              next.userData.fbOriginalRoughnessMap = standard.roughnessMap ?? null;
              next.userData.fbBaseRoughness = standard.roughness ?? 1;
              next.userData.fbOriginalSide = next.side;
              return next;
            });
            mesh.material = Array.isArray(mesh.material) ? cloned : cloned[0];

            mesh.userData.fbInitialStates = cloned.map((material) => {
              const standard = material as THREE.MeshStandardMaterial;
              return {
                color: `#${standard.color.getHexString()}`,
                roughness: standard.roughness,
                metalness: standard.metalness,
                emissive: `#${standard.emissive.getHexString()}`,
                emissiveIntensity: standard.emissiveIntensity,
              };
            });

            for (const material of cloned) {
              for (const key of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"] as const) {
                const texture = (material as THREE.MeshStandardMaterial)[key];
                if (texture) {
                  texture.wrapS = THREE.RepeatWrapping;
                  texture.wrapT = THREE.RepeatWrapping;
                  texture.needsUpdate = true;
                }
              }
            }

            const id = `node-${this.nodes.size}`;
            mesh.userData.nodeId = id;
            this.nodes.set(id, mesh);
          }
        });

        // 落地并居中
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.x -= center.x;
        model.position.z -= center.z;
        model.position.y -= box.min.y;
        this.scene.add(model);
        this.model = model;
        if (this.subdivisionLevel > 0) this.applySubdivision();

        const maxDim = Math.max(size.x, size.y, size.z, 1);
        const fitBox = new THREE.Box3().setFromObject(model);
        const sphere = fitBox.getBoundingSphere(new THREE.Sphere());
        const distance = (sphere.radius / Math.sin((this.camera.fov * Math.PI) / 360)) * 1.06;
        const direction = new THREE.Vector3(1, 0.52, 1.15).normalize();
        const target = new THREE.Vector3(0, size.y * 0.42, 0);
        this.camera.position.copy(target).addScaledVector(direction, distance);
        this.camera.near = Math.max(0.05, distance / 500);
        this.camera.far = distance * 12;
        this.camera.updateProjectionMatrix();
        this.controls.target.copy(target);
        this.controls.maxDistance = maxDim * 8;
        this.controls.update();
        this.defaultPosition = this.camera.position.clone();
        this.defaultTarget = target.clone();
        this.viewDistance = distance;

        this.modelBox.copy(fitBox);
        const centerOnGround = fitBox.getCenter(new THREE.Vector3());
        this.rainCenter.set(centerOnGround.x, 0, centerOnGround.z);
        this.rain.setCenter(this.rainCenter);
        this.clipSettings.position = this.clampClipPosition(this.clipSettings.position);
        this.fractureCell = 0;
        this.updateVolumetricAnchor();
        this.applyStudioState();
        this.onNodePick?.(null);

        onStats(this.collectStats(model, size));
        onStatus("ready");
      },
      undefined,
      (error) => {
        onStatus("error", error instanceof Error ? error.message : "模型加载失败");
      },
    );
  }

  private collectStats(model: THREE.Object3D, size: THREE.Vector3): ViewerStats {
    let meshes = 0;
    let triangles = 0;
    const textures = new Set<string>();
    model.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      meshes += 1;
      const geometry = (child as THREE.Mesh).geometry;
      triangles += geometry.index
        ? Math.floor(geometry.index.count / 3)
        : Math.floor((geometry.getAttribute("position")?.count ?? 0) / 3);
      const materials = Array.isArray((child as THREE.Mesh).material)
        ? ((child as THREE.Mesh).material as THREE.Material[])
        : [(child as THREE.Mesh).material as THREE.Material];
      for (const material of materials) {
        if (!material) continue;
        const standard = material as THREE.MeshStandardMaterial;
        for (const key of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"] as const) {
          const texture = standard[key];
          if (texture) textures.add(texture.uuid);
        }
      }
    });
    return {
      meshes,
      triangles,
      textures: textures.size,
      size: [
        Number(size.x.toFixed(2)),
        Number(size.y.toFixed(2)),
        Number(size.z.toFixed(2)),
      ],
    };
  }

  private clearModel(): void {
    this.selectNode(null);
    this.nodes.clear();
    this.voxel.clear();
    this.fractureCell = 0;
    this.selectedBlockId = null;
    if (!this.model) return;
    this.scene.remove(this.model);
    this.model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        const original = this.originalGeometries.get(mesh);
        if (original && original !== mesh.geometry) original.dispose();
        mesh.geometry.dispose();
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) material?.dispose();
      }
    });
    this.originalGeometries.clear();
    this.model = null;
  }

  // ------------------------------------------------------------------ 视图操作
  setAutoRotate(enabled: boolean): void {
    this.controls.autoRotate = enabled;
  }

  setWireframe(enabled: boolean): void {
    this.model?.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      const materials = Array.isArray((child as THREE.Mesh).material)
        ? ((child as THREE.Mesh).material as THREE.Material[])
        : [(child as THREE.Mesh).material as THREE.Material];
      for (const material of materials) {
        if (material && "wireframe" in material) {
          (material as THREE.MeshStandardMaterial).wireframe = enabled;
        }
      }
    });
  }

  /** 切换到沿坐标轴的正交式视角（俯视为 +Y，仰视为 -Y）。 */
  setView(axis: ViewAxis): void {
    const directions: Record<ViewAxis, THREE.Vector3> = {
      px: new THREE.Vector3(1, 0, 0),
      nx: new THREE.Vector3(-1, 0, 0),
      py: new THREE.Vector3(0, 1, 0),
      ny: new THREE.Vector3(0, -1, 0),
      pz: new THREE.Vector3(0, 0, 1),
      nz: new THREE.Vector3(0, 0, -1),
    };
    const target = this.controls.target.clone();
    this.camera.up.set(0, 1, 0);
    if (axis === "py") this.camera.up.set(0, 0, -1);
    if (axis === "ny") this.camera.up.set(0, 0, 1);
    this.camera.position.copy(target).addScaledVector(directions[axis], this.viewDistance);
    this.camera.lookAt(target);
    this.controls.update();
  }

  /** 锁定视角：禁止旋转、平移与缩放，画面固定不动。 */
  setLocked(locked: boolean): void {
    this.viewLocked = locked;
    this.controls.enableRotate = !locked && !this.clipDragEnabled;
    this.controls.enablePan = !locked && !this.clipDragEnabled;
    this.controls.enableZoom = !locked;
    if (locked) this.controls.autoRotate = false;
  }

  setEnvironment(preset: EnvironmentPreset): void {
    this.applyEnvironment(preset);
  }

  /** 环境光倍率：同时缩放半球光与 IBL 强度，范围 0~2。 */
  setAmbient(multiplier: number): void {
    this.ambientMultiplier = Math.max(0, Math.min(2, multiplier));
    this.hemi.intensity = this.baseHemiIntensity * this.ambientMultiplier;
    this.scene.environmentIntensity = this.ambientMultiplier;
  }

  /** 阴影开关与质量（分辨率）。切换后需要重新编译材质。 */
  setShadows(enabled: boolean, quality: ShadowQuality = this.shadowQuality): void {
    this.shadowQuality = quality;
    const sizes: Record<ShadowQuality, number> = { low: 1024, medium: 2048, high: 4096 };

    this.renderer.shadowMap.enabled = enabled;
    this.key.castShadow = enabled;
    this.key.shadow.mapSize.setScalar(sizes[quality]);
    if (this.key.shadow.map) {
      this.key.shadow.map.dispose();
      this.key.shadow.map = null;
    }
    this.model?.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      const materials = Array.isArray((child as THREE.Mesh).material)
        ? ((child as THREE.Mesh).material as THREE.Material[])
        : [(child as THREE.Mesh).material as THREE.Material];
      for (const material of materials) {
        if (material) material.needsUpdate = true;
      }
    });
  }

  /** 曲面细分等级：0 关闭，1~2 级 Loop 细分（仅影响预览，不改变导出模型）。 */
  setSubdivision(level: number): void {
    const next = Math.max(0, Math.min(2, Math.floor(level)));
    if (next === this.subdivisionLevel) return;
    this.subdivisionLevel = next;
    this.applySubdivision();
  }

  private applySubdivision(): void {
    if (!this.model) return;
    this.model.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      const mesh = child as THREE.Mesh;
      let original = this.originalGeometries.get(mesh);
      if (!original) {
        original = mesh.geometry;
        this.originalGeometries.set(mesh, original);
      }
      const previous = mesh.geometry;
      const next = this.subdivisionLevel > 0 ? subdivideGeometry(original, this.subdivisionLevel) : original;
      if (previous !== next && previous !== original) previous.dispose();
      mesh.geometry = next;
      this.deformBases.delete(mesh);
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        if (material) material.needsUpdate = true;
      }
    });
    this.applyAttractor();
    this.fractureCell = 0;
    if (this.fractureSettings.enabled) this.applyFracture();
  }

  resetView(): void {
    this.camera.up.set(0, 1, 0);
    this.camera.position.copy(this.defaultPosition);
    this.controls.target.copy(this.defaultTarget);
    this.controls.update();
  }

  // ================================================================ 节点选择
  getNodes(): NodeInfo[] {
    const infos: NodeInfo[] = [];
    for (const mesh of this.nodes.values()) infos.push(this.nodeInfo(mesh));
    return infos;
  }

  private nodeInfo(mesh: THREE.Mesh): NodeInfo {
    const geometry = mesh.geometry;
    const triangles = geometry.index
      ? Math.floor(geometry.index.count / 3)
      : Math.floor((geometry.getAttribute("position")?.count ?? 0) / 3);
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const first = materials[0];
    return {
      id: mesh.userData.nodeId as string,
      name: mesh.name || first?.name || "未命名节点",
      material: first?.name || "未命名材质",
      triangles,
    };
  }

  selectNode(id: string | null): void {
    const mesh = id ? (this.nodes.get(id) ?? null) : null;
    this.updateSelectionHelper(mesh);
    this.onNodePick?.(mesh ? this.nodeInfo(mesh) : null);
  }

  private updateSelectionHelper(mesh: THREE.Mesh | null): void {
    if (this.selectionHelper) {
      this.scene.remove(this.selectionHelper);
      this.selectionHelper.geometry.dispose();
      (this.selectionHelper.material as THREE.Material).dispose();
      this.selectionHelper = null;
    }
    if (!mesh) return;
    const helper = new THREE.BoxHelper(mesh, 0xf2b45c);
    helper.material.depthTest = false;
    helper.material.transparent = true;
    helper.renderOrder = 4;
    helper.visible = !this.fractureSettings.enabled;
    this.scene.add(helper);
    this.selectionHelper = helper;
  }

  private standardMaterials(mesh: THREE.Mesh): THREE.MeshStandardMaterial[] {
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    return materials.filter(
      (material): material is THREE.MeshStandardMaterial =>
        Boolean(material) && (material as THREE.MeshStandardMaterial).isMeshStandardMaterial,
    );
  }

  getNodeMaterialState(id: string): NodeMaterialState | null {
    const mesh = this.nodes.get(id);
    if (!mesh) return null;
    const material = this.standardMaterials(mesh)[0];
    if (!material) return null;
    return {
      color: `#${material.color.getHexString()}`,
      roughness: material.roughness,
      metalness: material.metalness,
      emissive: `#${material.emissive.getHexString()}`,
      emissiveIntensity: material.emissiveIntensity,
    };
  }

  /** 单节点材质：实时改写颜色 / 粗糙度 / 金属度 / 自发光。 */
  setNodeMaterial(id: string, patch: Partial<NodeMaterialState>): void {
    const mesh = this.nodes.get(id);
    if (!mesh) return;
    for (const material of this.standardMaterials(mesh)) {
      if (patch.color !== undefined) material.color.set(patch.color);
      if (patch.roughness !== undefined) material.roughness = patch.roughness;
      if (patch.metalness !== undefined) material.metalness = patch.metalness;
      if (patch.emissive !== undefined) material.emissive.set(patch.emissive);
      if (patch.emissiveIntensity !== undefined) {
        material.emissiveIntensity = patch.emissiveIntensity;
      }
    }
  }

  resetNodeMaterial(id: string): void {
    const mesh = this.nodes.get(id);
    if (!mesh) return;
    const states = mesh.userData.fbInitialStates as NodeMaterialState[] | undefined;
    this.standardMaterials(mesh).forEach((material, index) => {
      if (!states?.length) return;
      const state = states[Math.min(index, states.length - 1)];
      material.color.set(state.color);
      material.roughness = state.roughness;
      material.metalness = state.metalness;
      material.emissive.set(state.emissive);
      material.emissiveIntensity = state.emissiveIntensity;
    });
  }

  // ================================================================ PBR 污渍
  setGrunge(patch: Partial<GrungeSettings>): void {
    this.grungeSettings = { ...this.grungeSettings, ...patch };
    this.applyGrunge();
  }

  private applyGrunge(): void {
    const settings = this.grungeSettings;
    this.grungeUniforms.uGrungeMap.value = getGrungeTexture();
    this.grungeUniforms.uGrungeStrength.value = settings.enabled ? settings.strength : 0;
    this.grungeUniforms.uGrungeScale.value = Math.max(0.2, settings.scale);
    this.grungeUniforms.uStainColor.value.set(settings.color);
    this.grungeUniforms.uGrungeRough.value = settings.roughness;
    for (const mesh of this.nodes.values()) {
      for (const material of this.standardMaterials(mesh)) {
        patchGrunge(material, this.grungeUniforms);
      }
    }
  }

  // ================================================================ 粗糙度贴图
  setRoughness(patch: Partial<RoughnessSettings>): void {
    this.roughnessSettings = { ...this.roughnessSettings, ...patch };
    this.applyRoughness();
  }

  private applyRoughness(): void {
    const { enabled, scale, strength } = this.roughnessSettings;
    const texture = getRoughnessTexture();
    texture.repeat.set(Math.max(0.5, scale), Math.max(0.5, scale));
    texture.needsUpdate = true;
    for (const mesh of this.nodes.values()) {
      for (const material of this.standardMaterials(mesh)) {
        if (enabled) {
          material.roughnessMap = texture;
          material.roughness = Math.max(0.05, Math.min(1, strength));
        } else {
          material.roughnessMap =
            (material.userData.fbOriginalRoughnessMap as THREE.Texture | null) ?? null;
          material.roughness =
            (material.userData.fbBaseRoughness as number | undefined) ?? material.roughness;
        }
        material.needsUpdate = true;
      }
    }
  }

  // ================================================================ 天气
  setRain(intensity: number): void {
    this.rainLevel = Math.max(0, Math.min(1, intensity));
    this.rain.setIntensity(this.rainLevel);
    this.applyWetness();
  }

  setWetness(value: number): void {
    this.wetness = Math.max(0, Math.min(1, value));
    this.applyWetness();
  }

  private applyWetness(): void {
    this.groundMaterial.color.copy(this.baseGroundColor).multiplyScalar(1 - this.wetness * 0.32);
    this.groundMaterial.roughness = Math.max(0.08, this.baseGroundRoughness - this.wetness * 0.55);
    this.groundMaterial.metalness = this.wetness * 0.22;
    const fog = this.scene.fog as THREE.Fog | null;
    if (fog) {
      fog.near = this.baseFogNear * Math.max(0.35, 1 - this.rainLevel * 0.4 - this.wetness * 0.12);
      fog.far = this.baseFogFar * Math.max(0.3, 1 - this.rainLevel * 0.55 - this.wetness * 0.18);
    }
  }

  // ================================================================ 体积光
  setVolumetric(patch: Partial<VolumetricSettings>): void {
    const wasEnabled = this.volumetricSettings.enabled;
    this.volumetricSettings = { ...this.volumetricSettings, ...patch };
    if (this.volumetricSettings.enabled && !wasEnabled) {
      this.updateVolumetricAnchor();
    }
    this.volumetric.setIntensity(
      this.volumetricSettings.enabled ? this.volumetricSettings.intensity : 0,
    );
  }

  /** 光柱锚定在太阳灯与建筑体心之间，模型或环境变化时重建。 */
  private updateVolumetricAnchor(): void {
    const size = this.modelBox.getSize(new THREE.Vector3());
    const target = this.modelBox.getCenter(new THREE.Vector3());
    target.y = Math.max(this.modelBox.min.y + 0.6, this.modelBox.max.y * 0.35);
    const span = Math.max(size.length(), 16);
    this.volumetric.setup(this.key.position.clone(), target, span);
    this.volumetric.setIntensity(
      this.volumetricSettings.enabled ? this.volumetricSettings.intensity : 0,
    );
  }

  // ================================================================ 剖切
  getClipRange(axis: ClipAxis = this.clipSettings.axis): [number, number] {
    const min = this.modelBox.min[axis];
    const max = this.modelBox.max[axis];
    if (!Number.isFinite(min) || !Number.isFinite(max) || Math.abs(max - min) < 1e-4) {
      return [-10, 10];
    }
    return [min, max];
  }

  setClip(patch: Partial<ClipSettings>): void {
    const axisChanged = patch.axis !== undefined && patch.axis !== this.clipSettings.axis;
    this.clipSettings = { ...this.clipSettings, ...patch };
    if (axisChanged && patch.position === undefined) {
      const [min, max] = this.getClipRange(this.clipSettings.axis);
      this.clipSettings.position = (min + max) / 2;
    }
    this.clipSettings.position = this.clampClipPosition(this.clipSettings.position);
    this.applyClipping();
  }

  private clampClipPosition(position: number): number {
    const [min, max] = this.getClipRange(this.clipSettings.axis);
    return Math.min(max, Math.max(min, position));
  }

  private applyClipping(): void {
    const { enabled, axis, position, flipped } = this.clipSettings;
    const normal = new THREE.Vector3(
      axis === "x" ? -1 : 0,
      axis === "y" ? -1 : 0,
      axis === "z" ? -1 : 0,
    );
    if (flipped) normal.negate();
    this.clipPlane.normal.copy(normal);
    this.clipPlane.constant = flipped ? -position : position;
    this.clipHelper.visible = enabled;
    if (enabled) {
      const size = this.modelBox.getSize(new THREE.Vector3()).length();
      this.clipHelper.size = Math.max(8, size * 1.1);
    }
    const recompile = enabled !== this.clipApplied;
    this.clipApplied = enabled;
    for (const mesh of this.nodes.values()) {
      for (const material of this.standardMaterials(mesh)) {
        material.clippingPlanes = enabled ? [this.clipPlane] : null;
        material.clipShadows = enabled;
        material.side = enabled
          ? THREE.DoubleSide
          : ((material.userData.fbOriginalSide as THREE.Side | undefined) ?? THREE.FrontSide);
        if (recompile) material.needsUpdate = true;
      }
    }
    this.voxel.setClippingPlanes(enabled ? [this.clipPlane] : null);
  }

  /** 剖切拖动模式：鼠标上下拖动时沿当前轴推进/回退剖切面。 */
  setClipDragMode(enabled: boolean): void {
    this.clipDragEnabled = enabled;
    this.controls.enableRotate = !enabled && !this.viewLocked;
    this.controls.enablePan = !enabled && !this.viewLocked;
    this.renderer.domElement.style.cursor = enabled ? "ns-resize" : "";
  }

  // ================================================================ 吸引子 / 排斥子
  setAttractor(patch: Partial<AttractorSettings>): void {
    this.attractorSettings = { ...this.attractorSettings, ...patch };
    this.applyAttractor();
  }

  setAttractorPickMode(enabled: boolean): void {
    this.attractorPickMode = enabled;
  }

  private applyAttractor(): void {
    const { enabled, mode, strength, radius, point } = this.attractorSettings;
    const attractor = new THREE.Vector3(...point);
    for (const mesh of this.nodes.values()) {
      const geometry = mesh.geometry;
      const attribute = geometry.getAttribute("position") as THREE.BufferAttribute;
      const array = attribute.array as Float32Array;
      let base = this.deformBases.get(mesh);
      if (!base || base.position.length !== array.length) {
        const normalAttribute = geometry.getAttribute("normal") as THREE.BufferAttribute | undefined;
        base = {
          position: new Float32Array(array),
          normal: normalAttribute ? new Float32Array(normalAttribute.array as Float32Array) : null,
        };
        this.deformBases.set(mesh, base);
      }

      if (!enabled) {
        array.set(base.position);
        const normalAttribute = geometry.getAttribute("normal") as THREE.BufferAttribute | undefined;
        if (normalAttribute && base.normal) {
          (normalAttribute.array as Float32Array).set(base.normal);
          normalAttribute.needsUpdate = true;
        }
      } else {
        mesh.updateWorldMatrix(true, false);
        const localPoint = attractor
          .clone()
          .applyMatrix4(new THREE.Matrix4().copy(mesh.matrixWorld).invert());
        array.set(base.position);
        const radiusSq = radius * radius;
        for (let i = 0; i < array.length; i += 3) {
          const dx = base.position[i] - localPoint.x;
          const dy = base.position[i + 1] - localPoint.y;
          const dz = base.position[i + 2] - localPoint.z;
          const distanceSq = dx * dx + dy * dy + dz * dz;
          if (distanceSq >= radiusSq || distanceSq < 1e-8) continue;
          const distance = Math.sqrt(distanceSq);
          const t = 1 - distance / radius;
          const falloff = t * t * (3 - 2 * t);
          const amount = strength * falloff * (mode === "attract" ? -0.9 : 1);
          array[i] += (dx / distance) * amount;
          array[i + 1] += (dy / distance) * amount;
          array[i + 2] += (dz / distance) * amount;
        }
      }
      attribute.needsUpdate = true;
      if (enabled) geometry.computeVertexNormals();
      geometry.boundingSphere = null;
    }
  }

  // ================================================================ 体素碎裂
  setFracture(patch: Partial<FractureSettings>): void {
    this.fractureSettings = { ...this.fractureSettings, ...patch };
    this.applyFracture();
  }

  private applyFracture(): void {
    const { enabled, amount, cell } = this.fractureSettings;
    for (const mesh of this.nodes.values()) {
      mesh.visible = !enabled;
    }
    if (this.selectionHelper) this.selectionHelper.visible = !enabled;
    if (!this.model) {
      this.voxel.clear();
      return;
    }
    if (!enabled) {
      this.voxel.clear();
      this.fractureCell = 0;
      return;
    }
    if (this.fractureCell !== cell) {
      this.voxel.build(this.model, cell);
      this.fractureCell = cell;
    }
    this.voxel.setAmount(amount);
    this.voxel.setClippingPlanes(this.clipSettings.enabled ? [this.clipPlane] : null);
  }

  // ================================================================ 灵活搭建
  setBuildMode(enabled: boolean): void {
    this.buildMode = enabled;
    if (!enabled) this.selectBlock(null);
  }

  listBlocks(): BlockInfo[] {
    return this.blocks.map((mesh) => this.blockInfo(mesh));
  }

  private blockInfo(mesh: THREE.Mesh): BlockInfo {
    return {
      id: mesh.userData.blockId as string,
      name: mesh.userData.blockName as string,
      position: [mesh.position.x, mesh.position.y, mesh.position.z],
      size: [mesh.scale.x, mesh.scale.y, mesh.scale.z],
      color: `#${(mesh.material as THREE.MeshStandardMaterial).color.getHexString()}`,
    };
  }

  addBlock(patch?: Partial<BlockInfo>): BlockInfo {
    const size = patch?.size ?? [2.2, 2.6, 2.2];
    const position = patch?.position ?? [
      this.modelBox.max.x + 2.4 + (this.blocks.length % 3) * 2.6,
      size[1] / 2,
      Math.floor(this.blocks.length / 3) * 2.6 - 2,
    ];
    const color = patch?.color ?? "#c9b79a";
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(1, 1, 1),
      new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.04 }),
    );
    this.blockSeq += 1;
    mesh.userData.blockId = `block-${this.blockSeq}`;
    mesh.userData.blockName = `模块 ${this.blockSeq}`;
    mesh.scale.set(size[0], size[1], size[2]);
    mesh.position.set(position[0], position[1], position[2]);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    this.blockGroup.add(mesh);
    this.blocks.push(mesh);
    this.notifyBlocks();
    this.selectBlock(mesh.userData.blockId as string);
    return this.blockInfo(mesh);
  }

  updateBlock(id: string, patch: BlockPatch): void {
    const mesh = this.blocks.find((item) => item.userData.blockId === id);
    if (!mesh) return;
    if (patch.size) {
      mesh.scale.set(
        Math.max(0.2, patch.size[0]),
        Math.max(0.2, patch.size[1]),
        Math.max(0.2, patch.size[2]),
      );
    }
    if (patch.position) mesh.position.set(...patch.position);
    if (patch.color) {
      (mesh.material as THREE.MeshStandardMaterial).color.set(patch.color);
    }
    mesh.updateMatrixWorld();
    if (this.selectedBlockId === id) this.selectionHelper?.update();
    this.notifyBlocks();
  }

  removeBlock(id: string): void {
    const index = this.blocks.findIndex((item) => item.userData.blockId === id);
    if (index < 0) return;
    const [mesh] = this.blocks.splice(index, 1);
    this.blockGroup.remove(mesh);
    mesh.geometry.dispose();
    (mesh.material as THREE.Material).dispose();
    if (this.selectedBlockId === id) this.selectBlock(null);
    this.notifyBlocks();
  }

  duplicateBlock(id: string): void {
    const mesh = this.blocks.find((item) => item.userData.blockId === id);
    if (!mesh) return;
    this.addBlock({
      position: [mesh.position.x + 0.9, mesh.position.y, mesh.position.z],
      size: [mesh.scale.x, mesh.scale.y, mesh.scale.z],
      color: `#${(mesh.material as THREE.MeshStandardMaterial).color.getHexString()}`,
    });
  }

  selectBlock(id: string | null): void {
    this.selectedBlockId = id;
    const mesh = id ? (this.blocks.find((item) => item.userData.blockId === id) ?? null) : null;
    if (mesh) {
      this.onNodePick?.(null);
    }
    this.updateSelectionHelper(mesh);
    if (mesh) this.selectionHelper?.update();
    this.onSelectedBlock?.(mesh ? this.blockInfo(mesh) : null);
  }

  private notifyBlocks(): void {
    this.onBlocksChanged?.(this.listBlocks());
  }

  // ================================================================ 第一人称
  setFirstPerson(enabled: boolean): void {
    if (this.firstPerson === enabled) return;
    this.firstPerson = enabled;
    const dom = this.renderer.domElement;

    if (enabled) {
      this.fpSaved.position.copy(this.camera.position);
      this.fpSaved.target.copy(this.controls.target);
      this.fpSaved.fov = this.camera.fov;
      this.controls.enabled = false;
      this.controls.autoRotate = false;
      this.fpKeys.clear();
      this.fpLocked = false;

      const size = this.modelBox.getSize(new THREE.Vector3());
      const center = this.modelBox.getCenter(new THREE.Vector3());
      const offset = Math.max(size.z * 0.35 + 2.5, 3.5);
      this.camera.position.set(center.x, 1.65, this.modelBox.max.z + offset);
      this.camera.rotation.order = "YXZ";
      this.fpYaw = 0;
      this.fpPitch = 0;
      this.applyFirstPersonRotation();
      this.camera.fov = 72;
      this.camera.updateProjectionMatrix();

      window.addEventListener("keydown", this.handleFpKeyDown);
      window.addEventListener("keyup", this.handleFpKeyUp);
      window.addEventListener("pointermove", this.handleFpMouseMove);
      dom.addEventListener("click", this.handleFpClick);
      document.addEventListener("pointerlockchange", this.handlePointerLockChange);
      dom.style.cursor = "crosshair";
    } else {
      this.fpKeys.clear();
      window.removeEventListener("keydown", this.handleFpKeyDown);
      window.removeEventListener("keyup", this.handleFpKeyUp);
      window.removeEventListener("pointermove", this.handleFpMouseMove);
      dom.removeEventListener("click", this.handleFpClick);
      document.removeEventListener("pointerlockchange", this.handlePointerLockChange);
      if (document.pointerLockElement === dom) document.exitPointerLock();
      this.fpLocked = false;
      this.camera.rotation.set(0, 0, 0);
      this.camera.position.copy(this.fpSaved.position);
      this.controls.target.copy(this.fpSaved.target);
      this.camera.fov = this.fpSaved.fov;
      this.camera.updateProjectionMatrix();
      this.controls.enabled = true;
      this.controls.enableRotate = !this.viewLocked;
      this.controls.enablePan = !this.viewLocked;
      this.controls.update();
      dom.style.cursor = "";
      this.onFirstPersonLock?.(false);
    }
    this.onFirstPersonChange?.(enabled);
  }

  private applyFirstPersonRotation(): void {
    this.camera.rotation.set(this.fpPitch, this.fpYaw, 0, "YXZ");
  }

  private updateFirstPerson(delta: number): void {
    if (!this.firstPerson || !this.fpLocked) return;
    const speed =
      this.fpKeys.has("ShiftLeft") || this.fpKeys.has("ShiftRight") ? 7.5 : 3.2;
    const step = Math.min(delta, 0.05) * speed;
    const sin = Math.sin(this.fpYaw);
    const cos = Math.cos(this.fpYaw);
    this.fpMove.set(0, 0, 0);
    if (this.fpKeys.has("KeyW") || this.fpKeys.has("ArrowUp")) {
      this.fpMove.x -= sin;
      this.fpMove.z -= cos;
    }
    if (this.fpKeys.has("KeyS") || this.fpKeys.has("ArrowDown")) {
      this.fpMove.x += sin;
      this.fpMove.z += cos;
    }
    if (this.fpKeys.has("KeyA") || this.fpKeys.has("ArrowLeft")) {
      this.fpMove.x -= cos;
      this.fpMove.z += sin;
    }
    if (this.fpKeys.has("KeyD") || this.fpKeys.has("ArrowRight")) {
      this.fpMove.x += cos;
      this.fpMove.z -= sin;
    }
    if (this.fpMove.lengthSq() > 0) {
      this.fpMove.normalize().multiplyScalar(step);
      this.camera.position.add(this.fpMove);
    }
    this.camera.position.y = 1.65;
  }

  private handleFpClick = (): void => {
    if (!this.firstPerson) return;
    if (document.pointerLockElement !== this.renderer.domElement) {
      void this.renderer.domElement.requestPointerLock();
    }
  };

  private handlePointerLockChange = (): void => {
    const locked = document.pointerLockElement === this.renderer.domElement;
    this.fpLocked = locked;
    this.onFirstPersonLock?.(locked);
    if (!locked && this.firstPerson) {
      this.setFirstPerson(false);
    }
  };

  private handleFpMouseMove = (event: PointerEvent): void => {
    if (!this.firstPerson || document.pointerLockElement !== this.renderer.domElement) return;
    this.fpYaw -= event.movementX * 0.0025;
    this.fpPitch = Math.max(-1.32, Math.min(1.32, this.fpPitch - event.movementY * 0.0022));
    this.applyFirstPersonRotation();
  };

  private handleFpKeyDown = (event: KeyboardEvent): void => {
    const code = event.code;
    if (code.startsWith("Arrow") || code === "KeyW" || code === "KeyA" || code === "KeyS" || code === "KeyD") {
      if (code.startsWith("Arrow")) event.preventDefault();
      this.fpKeys.add(code);
    } else if (code === "ShiftLeft" || code === "ShiftRight") {
      this.fpKeys.add(code);
    }
  };

  private handleFpKeyUp = (event: KeyboardEvent): void => {
    this.fpKeys.delete(event.code);
  };

  // ================================================================ 指针交互
  private handlePointerDown = (event: PointerEvent): void => {
    if (event.button !== 0 || this.firstPerson) return;
    this.pointerState = { x: event.clientX, y: event.clientY, active: true, moved: false };
    if (this.clipDragEnabled && this.clipSettings.enabled) {
      this.clipDragging = true;
      this.clipLastY = event.clientY;
    }
  };

  private handlePointerMove = (event: PointerEvent): void => {
    if (!this.pointerState.active) return;
    if (
      Math.abs(event.clientX - this.pointerState.x) +
        Math.abs(event.clientY - this.pointerState.y) >
      5
    ) {
      this.pointerState.moved = true;
    }
    if (!this.clipDragging) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const dy = event.clientY - this.clipLastY;
    this.clipLastY = event.clientY;
    const [min, max] = this.getClipRange();
    const extent = Math.max(max - min, 0.1);
    const next = this.clipSettings.position - (dy / Math.max(rect.height, 1)) * extent * 1.4;
    this.setClip({ position: next });
    this.onClipPosition?.(this.clipSettings.position);
  };

  private handlePointerUp = (event: PointerEvent): void => {
    if (!this.pointerState.active) return;
    const clicked = event.button === 0 && !this.pointerState.moved && !this.clipDragging;
    this.pointerState.active = false;
    this.clipDragging = false;
    if (clicked) this.pick(event);
  };

  private pick(event: PointerEvent): void {
    const rect = this.renderer.domElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);

    if (this.buildMode) {
      const hits = this.raycaster.intersectObjects(this.blocks, false);
      const blockId = hits[0]?.object.userData.blockId as string | undefined;
      this.selectBlock(blockId ?? null);
      return;
    }

    const meshes = [...this.nodes.values()].filter((mesh) => mesh.visible);
    if (this.attractorPickMode) {
      const hit = this.raycaster.intersectObjects(meshes, false)[0];
      if (hit) {
        const point: [number, number, number] = [
          Number(hit.point.x.toFixed(2)),
          Number(hit.point.y.toFixed(2)),
          Number(hit.point.z.toFixed(2)),
        ];
        this.attractorSettings = { ...this.attractorSettings, point };
        this.applyAttractor();
        this.onAttractorPoint?.(point);
      }
      return;
    }

    if (this.fractureSettings.enabled) return;
    const hit = this.raycaster.intersectObjects(meshes, false)[0];
    this.selectNode((hit?.object.userData.nodeId as string | undefined) ?? null);
  }

  private applyStudioState(): void {
    this.applyGrunge();
    this.applyRoughness();
    this.applyClipping();
    this.applyAttractor();
    this.applyFracture();
  }

  dispose(): void {
    this.disposed = true;
    cancelAnimationFrame(this.animationId);
    if (this.skyTimer) window.clearTimeout(this.skyTimer);
    this.resizeObserver.disconnect();
    if (this.firstPerson) this.setFirstPerson(false);
    this.renderer.domElement.removeEventListener("pointerdown", this.handlePointerDown);
    window.removeEventListener("pointermove", this.handlePointerMove);
    window.removeEventListener("pointerup", this.handlePointerUp);
    this.clearModel();
    this.rain.dispose();
    this.volumetric.dispose();
    this.voxel.dispose();
    this.clipHelper.geometry.dispose();
    (this.clipHelper.material as THREE.Material).dispose();
    for (const block of this.blocks) {
      block.geometry.dispose();
      (block.material as THREE.Material).dispose();
    }
    this.blocks.length = 0;
    this.disposeEnvironment();
    this.studioTarget?.dispose();
    this.controls.dispose();
    this.pmrem.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}

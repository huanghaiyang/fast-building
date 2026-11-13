/**
 * three.js 建筑预览器。
 *
 * 只负责场景、相机、灯光、GLB 加载与视图操作，React 层通过方法调用控制。
 * 环境光使用程序化天空（等距圆柱贴图）经 PMREM 生成，避免依赖外部 HDR 资源。
 */

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { SimplifyModifier } from "three/examples/jsm/modifiers/SimplifyModifier.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { RainSystem, SnowSystem, VolumetricLight, VoxelFracture } from "./effects";
import {
  MaterialFXUniforms,
  SurfaceSettings,
  createMaterialFXUniforms,
  getGrungeTexture,
  getRoughnessTexture,
  patchMaterialFX,
} from "./procedural";
import { createWaterMaterial, createWaterUniforms, isWaterMaterial } from "./water";
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
  /** 从模型根到该节点的分组路径，用于构建树形选择器。 */
  path: string[];
}

export type { SurfaceSettings } from "./procedural";

export interface NodeMaterialState {
  color: string;
  roughness: number;
  metalness: number;
  emissive: string;
  emissiveIntensity: number;
  /** 法线贴图强度。 */
  normalScale: number;
  /** IBL 环境反射强度。 */
  envMapIntensity: number;
  opacity: number;
  transparent: boolean;
}

export type ClipAxis = "x" | "y" | "z";

export interface ClipSettings {
  enabled: boolean;
  axis: ClipAxis;
  position: number;
  flipped: boolean;
}

export type AttractorMode = "attract" | "repel";

export interface AttractorItem {
  id: string;
  mode: AttractorMode;
  strength: number;
  radius: number;
  point: [number, number, number];
  enabled: boolean;
}

export interface FractureSettings {
  enabled: boolean;
  amount: number;
  cell: number;
  /** 是否切换为物理崩塌模拟。 */
  collapse: boolean;
  /** 崩塌初始冲击强度。 */
  impulse: number;
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

/** 昼夜循环设置。 */
export interface SunCycleSettings {
  enabled: boolean;
  /** 时间推进速度（小时/秒）。 */
  speed: number;
}

/** 雪景设置：降雪强度、积雪覆盖与是否自动积雪。 */
export interface SnowSettings {
  intensity: number;
  cover: number;
  auto: boolean;
}

/** 可开合构件（门/窗）的概要信息。 */
export interface OpenableInfo {
  id: string;
  kind: "door" | "window";
  opened: boolean;
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

const ENV_CONFIGS: Record<EnvironmentPreset, EnvironmentConfig> = {  midday: {
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

/** 昼夜循环的调色板（按太阳高度角插值）。 */
const DIURNAL = {
  keyDawn: new THREE.Color("#ff9a4d"),
  keyNoon: new THREE.Color("#fff4e0"),
  keyNight: new THREE.Color("#7f97c9"),
  hemiNight: new THREE.Color("#1b2740"),
  hemiDay: new THREE.Color("#cfe6ff"),
  fogNight: new THREE.Color("#0b1220"),
  fogDay: new THREE.Color("#bcd6e8"),
  fogGold: new THREE.Color("#e8b887"),
  skyTopNight: new THREE.Color("#050914"),
  skyTopDay: new THREE.Color("#3f7fc4"),
  skyHorizonNight: new THREE.Color("#16243c"),
  skyHorizonDay: new THREE.Color("#cfe4f2"),
  skyHorizonGold: new THREE.Color("#f2b06a"),
  skyBottomNight: new THREE.Color("#0a0e16"),
  skyBottomDay: new THREE.Color("#6b6b60"),
  sunGold: new THREE.Color("#ffcf8a"),
  sunNoon: new THREE.Color("#fff6d8"),
  snowGround: new THREE.Color("#eef4fb"),
} as const;

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
  onAttractorPicked: ((id: string, point: [number, number, number]) => void) | null = null;
  /** 拖拽场景中的量场标记点时回调，用于同步面板数值。 */
  onAttractorMoved: ((id: string, point: [number, number, number]) => void) | null = null;
  onBlocksChanged: ((blocks: BlockInfo[]) => void) | null = null;
  onSelectedBlock: ((block: BlockInfo | null) => void) | null = null;
  onSunChange: ((sun: SunSettings) => void) | null = null;

  private sunSettings: SunSettings = { azimuth: 52, elevation: 49 };
  private skyConfig: SkyConfig | null = null;
  private skyStars = 0;
  private lastSkyRebuild = 0;
  private lastDayTick = 0;
  private skyTimer = 0;
  private readonly sunDir = new THREE.Vector3();

  private readonly raycaster = new THREE.Raycaster();
  private readonly nodes = new Map<string, THREE.Mesh>();
  private selectionHelper: THREE.BoxHelper | null = null;
  private hoverHelper: THREE.BoxHelper | null = null;
  private hoveredNodeId: string | null = null;

  private modelBox = new THREE.Box3(new THREE.Vector3(-6, 0, -6), new THREE.Vector3(6, 6, 6));
  private readonly clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
  private clipSettings: ClipSettings = { enabled: false, axis: "x", position: 0, flipped: false };
  private clipHelper!: THREE.PlaneHelper;
  private clipDragEnabled = false;
  private clipDragging = false;
  private clipDragStartX = 0;
  private clipDragStartY = 0;
  private clipDragStartPosition = 0;
  private clipDragDirX = 0;
  private clipDragDirY = -1;
  private clipDragPixelsPerUnit = 200;
  private clipApplied = false;

  private readonly fxUniforms: MaterialFXUniforms = createMaterialFXUniforms();
  private grungeSettings: GrungeSettings = {
    enabled: false,
    strength: 0.55,
    scale: 3,
    color: "#2f2a24",
    roughness: 0.45,
  };
  private surfaceSettings: SurfaceSettings = {
    subsurface: 0.35,
    subsurfaceColor: "#c96a3f",
    diffuseWrap: 0.4,
  };
  private roughnessSettings: RoughnessSettings = { enabled: false, scale: 6, strength: 0.6 };
  private wetFlow = 0.6;

  private readonly rain = new RainSystem();
  private readonly rainCenter = new THREE.Vector3(0, 0, 0);
  private baseFogNear = 80;
  private baseFogFar = 220;
  private readonly clock = new THREE.Clock();
  private wetness = 0;
  private rainLevel = 0;
  private baseGroundColor = new THREE.Color("#0f151c");
  private baseGroundRoughness = 0.96;

  // ---------------------------------------------------------------- 雪景 / 水体 / 动态构件
  private readonly snow = new SnowSystem();
  private snowIntensity = 0;
  private snowCover = 0;
  private snowAuto = false;
  private readonly waterUniforms = createWaterUniforms();
  private waterMaterial: THREE.ShaderMaterial | null = null;
  private readonly waterMeshes: THREE.Mesh[] = [];
  private readonly wheelNodes: THREE.Object3D[] = [];
  private wheelSpin = true;
  private readonly openables: Array<{
    id: string;
    node: THREE.Object3D;
    kind: "door" | "window";
    baseRotationY: number;
    openDeg: number;
    sign: number;
    progress: number;
    target: number;
  }> = [];

  // ---------------------------------------------------------------- 昼夜循环
  onDayTimeChange: ((hour: number, sun: SunSettings) => void) | null = null;
  private sunCycle = false;
  private sunCycleSpeed = 0.15; // 小时/秒
  private sunHour = 10;
  private readonly diurnalColor = new THREE.Color();
  private readonly diurnalColorB = new THREE.Color();
  private readonly diurnalColorC = new THREE.Color();
  private readonly diurnalColorD = new THREE.Color();
  /** 昼夜循环下地面的明度缩放（1 = 预设原色）。 */
  private diurnalLight = 1;

  private attractorItems: AttractorItem[] = [];
  private attractorEnabled = false;
  private attractorPickMode = false;
  private attractorPickId: string | null = null;
  private readonly attractorGroup = new THREE.Group();
  private readonly attractorGuides = new Map<
    string,
    { core: THREE.Mesh; halo: THREE.Mesh }
  >();
  private attractorDragId: string | null = null;
  private attractorDragControls = true;
  private readonly attractorDragPlane = new THREE.Plane();
  private readonly attractorDragOffset = new THREE.Vector3();
  private readonly attractorDragPoint = new THREE.Vector3();
  private readonly deformBases = new WeakMap<
    THREE.Mesh,
    { position: Float32Array; normal: Float32Array | null }
  >();

  private simplifyOverall = 1;
  private readonly simplifyNodes = new Map<string, number>();
  private readonly simplifyCache = new Map<string, THREE.BufferGeometry>();

  private readonly voxel = new VoxelFracture();
  private fractureSettings: FractureSettings = {
    enabled: false,
    amount: 0.6,
    cell: 0.42,
    collapse: false,
    impulse: 1.2,
  };
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
  private blockDragging = false;
  private blockDragId: string | null = null;
  private blockDragPlaneY = 0;
  private blockDragStartY = 0;
  private blockDragPointerY = 0;
  private readonly blockDragOrigin = new THREE.Vector3();
  private readonly blockDragOffset = new THREE.Vector3();
  private readonly buildPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

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
    this.scene.add(this.snow.group);
    this.scene.add(this.volumetric.group);
    this.scene.add(this.voxel.group);
    this.scene.add(this.blockGroup);
    this.attractorGroup.renderOrder = 5;
    this.scene.add(this.attractorGroup);

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
    window.addEventListener("keydown", this.handleGlobalKeyDown);

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

  /** 生成纵向渐变的等距圆柱天空贴图，太阳光晕按当前方位角/高度角绘制；stars 为夜空星点强度。 */
  private createSkyTexture(sky: SkyConfig, stars = 0): THREE.Texture {
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

      // 夜空星点：按强度铺一层随机星，避免夜晚天空一片死黑
      if (stars > 0.01) {
        let seed = 20261113;
        const rand = () => {
          seed = (seed * 16807) % 2147483647;
          return seed / 2147483647;
        };
        ctx.fillStyle = "#e8f2ff";
        for (let i = 0; i < 320; i += 1) {
          const x = rand() * width;
          const y = rand() * height * 0.55;
          const radius = rand() * 1.5 + 0.35;
          ctx.globalAlpha = stars * (0.3 + rand() * 0.7);
          ctx.beginPath();
          ctx.arc(x, y, radius, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
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
    this.fxUniforms.uSunDir.value.copy(this.sunDir);

    this.fill.color.set(config.fill.color);
    this.fill.intensity = config.fill.intensity;
    this.fill.position.set(...config.fill.position);

    this.groundMaterial.color.set(config.ground);
    this.baseGroundColor.set(config.ground);
    this.diurnalLight = 1;
    (this.grid.material as THREE.Material).opacity = config.gridOpacity;

    this.disposeEnvironment();
    this.skyConfig = config.sky ?? null;
    this.skyStars = preset === "night" ? 0.55 : 0;
    if (config.sky) {
      const skyTexture = this.createSkyTexture(config.sky, this.skyStars);
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
    this.fxUniforms.uSunDir.value.copy(this.sunDir);
    this.updateVolumetricAnchor();
    this.scheduleSkyRebuild();
    this.onSunChange?.(this.getSun());
  }

  // ================================================================ 昼夜循环
  /** 开 / 关真实昼夜循环；speed 为时间推进速度（小时/秒）。 */
  setSunCycle(enabled: boolean, speed?: number): void {
    this.sunCycle = enabled;
    if (speed !== undefined) this.sunCycleSpeed = Math.max(0.005, Math.min(2, speed));
    if (enabled) this.applyDiurnal(this.sunHour, true);
  }

  /** 直接跳到某个时刻（0~24 点）。 */
  setHour(hour: number): void {
    this.sunHour = ((hour % 24) + 24) % 24;
    this.applyDiurnal(this.sunHour, true);
  }

  getHour(): number {
    return this.sunHour;
  }

  isSunCycleEnabled(): boolean {
    return this.sunCycle;
  }

  /** 按一天中的时刻推算太阳角度、光色、天空与雾，主光/天空/阴影/体积光同步。 */
  private applyDiurnal(hour: number, force: boolean): void {
    const smooth = (edge0: number, edge1: number, value: number) => {
      const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
      return t * t * (3 - 2 * t);
    };

    const hours = ((hour % 24) + 24) % 24;
    const angle = ((hours - 6) / 12) * Math.PI;
    const sinAngle = Math.sin(angle);
    const elevation = sinAngle * 72;
    const sunHeight = Math.max(0, sinAngle);
    const daylight = smooth(-0.06, 0.2, sinAngle);
    const golden = (1 - smooth(0.12, 0.6, sunHeight)) * daylight;

    this.sunSettings = {
      azimuth: (((90 + ((hours - 6) / 12) * 180) % 360) + 360) % 360,
      elevation: Math.max(0, elevation),
    };
    this.key.position.copy(this.sunDirection()).multiplyScalar(SUN_DISTANCE);
    this.fxUniforms.uSunDir.value.copy(this.sunDir);
    this.updateVolumetricAnchor();

    // 主光：低角度偏橙、正午暖白、夜间转冷月光
    this.key.color
      .copy(DIURNAL.keyDawn)
      .lerp(DIURNAL.keyNoon, smooth(0.08, 0.55, sunHeight))
      .lerp(DIURNAL.keyNight, 1 - daylight);
    this.key.intensity = 0.14 + 2.7 * daylight * (0.55 + 0.45 * sunHeight);
    this.fill.intensity = 0.12 + 0.45 * daylight;
    this.fill.color.copy(DIURNAL.hemiNight).lerp(DIURNAL.hemiDay, daylight);

    this.hemi.color.copy(DIURNAL.hemiNight).lerp(DIURNAL.hemiDay, daylight);
    this.baseHemiIntensity = 0.4 + 0.85 * daylight;
    this.hemi.intensity = this.baseHemiIntensity * this.ambientMultiplier;
    this.diurnalLight = 0.3 + 0.7 * daylight;

    const fog = this.scene.fog as THREE.Fog | null;
    if (fog) {
      const rainFade = Math.max(0.35, 1 - this.rainLevel * 0.5 - this.wetness * 0.15);
      fog.color.copy(DIURNAL.fogNight).lerp(DIURNAL.fogDay, daylight);
      if (golden > 0.001) fog.color.lerp(DIURNAL.fogGold, golden * 0.45);
      fog.near = this.baseFogNear * (0.55 + 0.45 * daylight) * rainFade;
      fog.far = this.baseFogFar * (0.5 + 0.5 * daylight) * rainFade;
    }
    this.renderer.toneMappingExposure = 0.82 + 0.24 * daylight;

    const skyTop = this.diurnalColor
      .copy(DIURNAL.skyTopNight)
      .lerp(DIURNAL.skyTopDay, daylight);
    const skyHorizon = this.diurnalColorB
      .copy(DIURNAL.skyHorizonNight)
      .lerp(DIURNAL.skyHorizonDay, daylight);
    if (golden > 0.001) skyHorizon.lerp(DIURNAL.skyHorizonGold, golden * 0.6);
    const skyBottom = this.diurnalColorC
      .copy(DIURNAL.skyBottomNight)
      .lerp(DIURNAL.skyBottomDay, daylight);
    const sunColor = this.diurnalColorD
      .copy(DIURNAL.sunGold)
      .lerp(DIURNAL.sunNoon, smooth(0.1, 0.6, sunHeight));

    this.skyConfig = {
      top: `#${skyTop.getHexString()}`,
      horizon: `#${skyHorizon.getHexString()}`,
      bottom: `#${skyBottom.getHexString()}`,
      sun:
        elevation > -3
          ? {
              color: `#${sunColor.getHexString()}`,
              radius: 60 + 90 * (1 - sunHeight) + 40 * golden,
            }
          : undefined,
    };
    this.skyStars = 1 - daylight;

    const now = performance.now();
    if (force || now - this.lastSkyRebuild > 600) {
      this.lastSkyRebuild = now;
      this.rebuildSky();
    }
    if (force || now - this.lastDayTick > 200) {
      this.lastDayTick = now;
      this.onDayTimeChange?.(hours, this.getSun());
    }
  }

  /** 由光照位置反推方位角与高度角，用于环境切换时同步滑块。 */
  private sunFromVector(position: [number, number, number]): SunSettings {    const vector = new THREE.Vector3(...position);
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
    const texture = this.createSkyTexture(this.skyConfig, this.skyStars);
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
    this.fxUniforms.uTime.value += delta;
    this.rain.update(delta);
    this.snow.update(delta);
    this.updateSnowCover(delta);
    this.updateOpenables(delta);
    this.updateWater(delta);
    if (this.wheelSpin) {
      for (const wheel of this.wheelNodes) wheel.rotation.z -= delta * 0.9;
    }
    if (this.sunCycle) {
      this.sunHour = (this.sunHour + delta * this.sunCycleSpeed) % 24;
      this.applyDiurnal(this.sunHour, false);
    }
    this.volumetric.update(delta, this.camera);
    this.voxel.update(delta);
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
                normalScale: standard.normalScale?.x ?? 1,
                envMapIntensity: standard.envMapIntensity ?? 1,
                opacity: standard.opacity,
                transparent: standard.transparent,
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

        // 门窗开合、水轮转动、水面材质替换（需在材质克隆之后）
        this.prepareInteractive(model);

        // 落地并居中
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.x -= center.x;
        model.position.z -= center.z;
        model.position.y -= box.min.y;
        this.scene.add(model);
        this.model = model;
        if (this.subdivisionLevel > 0 || this.simplifyOverall < 0.999) {
          this.applyGeometryPipeline();
        }

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
        this.snow.setCenter(this.rainCenter);
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
    this.hoverNode(null);
    this.nodes.clear();
    this.voxel.clear();
    this.fractureCell = 0;
    this.selectedBlockId = null;
    this.waterMeshes.length = 0;
    this.wheelNodes.length = 0;
    this.openables.length = 0;
    this.waterMaterial?.dispose();
    this.waterMaterial = null;
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
    for (const geometry of this.simplifyCache.values()) geometry.dispose();
    this.simplifyCache.clear();
    this.simplifyNodes.clear();
    this.simplifyOverall = 1;
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
    this.applyGeometryPipeline();
  }

  /** 整体三角面比例：1 为原始网格，数值越小面数越少（仅影响预览）。 */
  setSimplifyOverall(ratio: number): void {
    const next = Math.max(0.1, Math.min(1, ratio));
    if (next === this.simplifyOverall) return;
    this.simplifyOverall = next;
    this.applyGeometryPipeline();
  }

  /** 单节点三角面比例：1 表示跟随整体设置。 */
  setNodeSimplify(nodeId: string, ratio: number): void {
    const next = Math.max(0.1, Math.min(1, ratio));
    if (next >= 0.999) this.simplifyNodes.delete(nodeId);
    else this.simplifyNodes.set(nodeId, next);
    this.applyGeometryPipeline();
  }

  /** 新建量场作用点的默认位置：建筑正前方、约半高处。 */
  getAttractorSpawn(): [number, number, number] {
    // 优先落在视口可见区域（避开展开的工作室面板）的模型表面上
    const samples: Array<[number, number]> = [
      [0.38, 0.05],
      [0.55, 0.05],
      [0.2, 0.1],
      [0.0, 0.05],
    ];
    const direction = this.camera.getWorldDirection(new THREE.Vector3());
    for (const [ndcX, ndcY] of samples) {
      this.raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
      const hit = this.raycaster.intersectObjects([...this.nodes.values()], false)[0];
      if (hit) {
        const point = hit.point.clone().addScaledVector(direction, -0.6);
        return [
          Math.round(point.x * 10) / 10,
          Math.round(point.y * 10) / 10,
          Math.round(point.z * 10) / 10,
        ];
      }
    }
    const center = new THREE.Vector3();
    this.modelBox.getCenter(center);
    return [
      Math.round(center.x * 10) / 10,
      Math.round((this.modelBox.min.y + (this.modelBox.max.y - this.modelBox.min.y) * 0.45) * 10) / 10,
      Math.round((this.modelBox.max.z + 1.5) * 10) / 10,
    ];
  }

  /** 当前节点实际三角面数（简化/细分之后）。 */
  getNodeTriangleCount(nodeId: string): number {
    const mesh = this.nodes.get(nodeId);
    if (!mesh) return 0;
    const geometry = mesh.geometry;
    const index = geometry.getIndex();
    const count = index ? index.count : geometry.getAttribute("position").count;
    return Math.floor(count / 3);
  }

  private isSimplifyCached(geometry: THREE.BufferGeometry): boolean {
    for (const cached of this.simplifyCache.values()) {
      if (cached === geometry) return true;
    }
    return false;
  }

  private getSimplifiedGeometry(
    nodeId: string,
    ratio: number,
    original: THREE.BufferGeometry,
  ): THREE.BufferGeometry {
    const key = `${nodeId}:${ratio.toFixed(2)}`;
    const cached = this.simplifyCache.get(key);
    if (cached) return cached;
    try {
      const vertexCount = original.getAttribute("position").count;
      const remove = Math.floor(vertexCount * (1 - ratio));
      if (remove < 4) return original;
      const simplified = new SimplifyModifier().modify(original, remove);
      simplified.computeBoundingSphere();
      this.simplifyCache.set(key, simplified);
      return simplified;
    } catch {
      return original;
    }
  }

  /** 统一应用三角面简化与曲面细分，两者都以原始几何为基准。 */
  private applyGeometryPipeline(): void {
    if (!this.model) return;
    this.model.traverse((child) => {
      if (!(child as THREE.Mesh).isMesh) return;
      const mesh = child as THREE.Mesh;
      let original = this.originalGeometries.get(mesh);
      if (!original) {
        original = mesh.geometry;
        this.originalGeometries.set(mesh, original);
      }
      const nodeId = (mesh.userData.nodeId as string | undefined) ?? "";
      const ratio = this.simplifyNodes.get(nodeId) ?? this.simplifyOverall;
      let base = original;
      if (ratio < 0.999) base = this.getSimplifiedGeometry(nodeId, ratio, original);

      const previous = mesh.geometry;
      const next = this.subdivisionLevel > 0 ? subdivideGeometry(base, this.subdivisionLevel) : base;
      if (
        previous !== next &&
        previous !== original &&
        !this.isSimplifyCached(previous)
      ) {
        previous.dispose();
      }
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
    const path: string[] = [];
    let parent = mesh.parent;
    while (parent && parent !== this.model) {
      const label = parent.name.trim();
      if (label && !/^(Scene|Sketchfab_model|GLTF_SceneRootNode)$/i.test(label)) {
        path.unshift(label);
      }
      parent = parent.parent;
    }
    return {
      id: mesh.userData.nodeId as string,
      name: mesh.name || first?.name || "未命名节点",
      material: first?.name || "未命名材质",
      triangles,
      path,
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
      normalScale: material.normalScale?.x ?? 1,
      envMapIntensity: material.envMapIntensity ?? 1,
      opacity: material.opacity,
      transparent: material.transparent,
    };
  }

  /** 单节点材质：实时改写 PBR 参数（颜色 / 粗糙度 / 金属度 / 法线 / IBL / 透明度）。 */
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
      if (patch.normalScale !== undefined && material.normalScale) {
        material.normalScale.set(patch.normalScale, patch.normalScale);
      }
      if (patch.envMapIntensity !== undefined) {
        material.envMapIntensity = patch.envMapIntensity;
      }
      let recompile = false;
      if (patch.opacity !== undefined) material.opacity = patch.opacity;
      if (patch.transparent !== undefined && material.transparent !== patch.transparent) {
        material.transparent = patch.transparent;
        recompile = true;
      }
      if (recompile) {
        material.depthWrite = !material.transparent;
        material.needsUpdate = true;
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
      if (material.normalScale) material.normalScale.set(state.normalScale, state.normalScale);
      material.envMapIntensity = state.envMapIntensity;
      material.opacity = state.opacity;
      material.transparent = state.transparent;
      material.depthWrite = !state.transparent;
      material.needsUpdate = true;
    });
  }

  /** 节点列表悬停高亮：只绘制包围盒，不修改材质本身。 */
  hoverNode(id: string | null): void {
    if (id === this.hoveredNodeId) return;
    this.hoveredNodeId = id;
    if (this.hoverHelper) {
      this.scene.remove(this.hoverHelper);
      this.hoverHelper.geometry.dispose();
      (this.hoverHelper.material as THREE.Material).dispose();
      this.hoverHelper = null;
    }
    const mesh = id ? (this.nodes.get(id) ?? null) : null;
    if (!mesh || this.fractureSettings.enabled) return;
    const helper = new THREE.BoxHelper(mesh, 0x58e0c4);
    helper.material.depthTest = false;
    helper.material.transparent = true;
    helper.material.opacity = 0.95;
    helper.renderOrder = 5;
    this.scene.add(helper);
    this.hoverHelper = helper;
  }

  // ================================================================ PBR 污渍
  setGrunge(patch: Partial<GrungeSettings>): void {
    this.grungeSettings = { ...this.grungeSettings, ...patch };
    this.applyGrunge();
  }

  private applyGrunge(): void {
    const settings = this.grungeSettings;
    this.fxUniforms.uGrungeMap.value = getGrungeTexture();
    this.fxUniforms.uGrungeStrength.value = settings.enabled ? settings.strength : 0;
    this.fxUniforms.uGrungeScale.value = Math.max(0.2, settings.scale);
    this.fxUniforms.uStainColor.value.set(settings.color);
    this.fxUniforms.uGrungeRough.value = settings.roughness;
    this.patchAllMaterials();
  }

  private patchAllMaterials(): void {
    for (const mesh of this.nodes.values()) {
      for (const material of this.standardMaterials(mesh)) {
        patchMaterialFX(material, this.fxUniforms);
      }
    }
  }

  // ================================================================ 表面散射
  /** 漫反射包裹与次表面散射：全局作用于所有节点材质。 */
  setSurface(patch: Partial<SurfaceSettings>): void {
    this.surfaceSettings = { ...this.surfaceSettings, ...patch };
    this.fxUniforms.uSSS.value = this.surfaceSettings.subsurface;
    this.fxUniforms.uSSSColor.value.set(this.surfaceSettings.subsurfaceColor);
    this.fxUniforms.uDiffuseWrap.value = this.surfaceSettings.diffuseWrap;
    this.patchAllMaterials();
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

  /** 雨水流动强度：控制墙面流动水痕的可见度。 */
  setWetFlow(value: number): void {
    this.wetFlow = Math.max(0, Math.min(1, value));
    this.fxUniforms.uRainFlow.value = this.wetFlow;
    this.patchAllMaterials();
  }

  private applyWetness(): void {
    this.fxUniforms.uWetness.value = this.wetness;
    this.fxUniforms.uRainFlow.value = this.wetFlow;
    this.fxUniforms.uSnow.value = this.snowCover;
    this.patchAllMaterials();
    this.groundMaterial.color
      .copy(this.baseGroundColor)
      .multiplyScalar((1 - this.wetness * 0.32) * this.diurnalLight)
      .lerp(DIURNAL.snowGround, this.snowCover * 0.92);
    this.groundMaterial.roughness = THREE.MathUtils.lerp(
      Math.max(0.08, this.baseGroundRoughness - this.wetness * 0.55),
      0.95,
      this.snowCover,
    );
    this.groundMaterial.metalness = this.wetness * 0.22 * (1 - this.snowCover);
    const fog = this.scene.fog as THREE.Fog | null;
    if (fog) {
      fog.near = this.baseFogNear * Math.max(0.35, 1 - this.rainLevel * 0.4 - this.wetness * 0.12);
      fog.far = this.baseFogFar * Math.max(0.3, 1 - this.rainLevel * 0.55 - this.wetness * 0.18);
    }
  }

  // ================================================================ 雪景
  /** 降雪强度 0~1（0 关闭）。 */
  setSnow(intensity: number): void {
    this.snowIntensity = Math.max(0, Math.min(1, intensity));
    this.snow.setIntensity(this.snowIntensity);
  }

  /** 积雪覆盖 0~1：沿朝上的表面累计，地面同步变白。 */
  setSnowCover(cover: number): void {
    this.snowCover = Math.max(0, Math.min(1, cover));
    this.applyWetness();
  }

  /** 自动积雪：降雪时覆盖度缓慢增长，停雪后缓慢融化；关闭后由滑块直接控制。 */
  setSnowAuto(enabled: boolean): void {
    this.snowAuto = enabled;
  }

  getSnow(): SnowSettings {
    return { intensity: this.snowIntensity, cover: this.snowCover, auto: this.snowAuto };
  }

  private updateSnowCover(delta: number): void {
    if (!this.snowAuto) return;
    if (this.snowIntensity > 0.001) {
      const target = Math.min(1, this.snowIntensity * 0.95);
      if (this.snowCover < target) this.setSnowCover(Math.min(target, this.snowCover + delta * 0.055));
    } else if (this.snowCover > 0) {
      this.setSnowCover(Math.max(0, this.snowCover - delta * 0.02));
    }
  }

  // ================================================================ 水轮 / 水面
  /** 水轮是否持续转动。 */
  setWaterwheelSpin(enabled: boolean): void {
    this.wheelSpin = enabled;
  }

  getWaterwheelCount(): number {
    return this.wheelNodes.length;
  }

  private updateWater(delta: number): void {
    this.waterUniforms.uTime.value += delta;
    this.waterUniforms.uSunDir.value.copy(this.sunDir);
    this.waterUniforms.uSunColor.value
      .copy(this.key.color)
      .multiplyScalar(Math.min(1, 0.35 + this.key.intensity * 0.28));
    this.waterUniforms.uSkyColor.value.copy(this.hemi.color);
  }

  // ================================================================ 可开合门窗
  getOpenableCount(): number {
    return this.openables.length;
  }

  getOpenables(): OpenableInfo[] {
    return this.openables.map((item) => ({
      id: item.id,
      kind: item.kind,
      opened: item.target > 0.5,
    }));
  }

  /** 批量开 / 关所有门窗。 */
  setOpenables(open: boolean): void {
    for (const item of this.openables) item.target = open ? 1 : 0;
  }

  /** 切换单个门窗（点击画面中的门扇/窗扇时调用）。 */
  toggleOpenable(id: string): void {
    const item = this.openables.find((entry) => entry.id === id);
    if (item) item.target = item.target > 0.5 ? 0 : 1;
  }

  private updateOpenables(delta: number): void {
    const step = Math.min(1, delta * 5.5);
    for (const item of this.openables) {
      if (Math.abs(item.target - item.progress) < 0.0005) continue;
      item.progress += (item.target - item.progress) * step;
      item.node.rotation.y =
        item.baseRotationY + item.sign * THREE.MathUtils.degToRad(item.openDeg) * item.progress;
    }
  }

  /** 模型加载后识别水面、水轮与门窗（依赖节点 extras / 材质名）。 */
  private prepareInteractive(model: THREE.Object3D): void {
    this.waterMeshes.length = 0;
    this.wheelNodes.length = 0;
    this.openables.length = 0;
    this.waterMaterial?.dispose();
    this.waterMaterial = null;

    let waterUsed = false;
    const waterMaterial = createWaterMaterial(this.waterUniforms);

    model.traverse((child) => {
      const mesh = child as THREE.Mesh;

      // 水面：生成器把轮坑水面写成 FB_water 材质
      if (mesh.isMesh && isWaterMaterial(mesh.material)) {
        const previous = mesh.material;
        mesh.material = waterMaterial;
        mesh.castShadow = false;
        mesh.receiveShadow = true;
        this.waterMeshes.push(mesh);
        waterUsed = true;
        for (const item of Array.isArray(previous) ? previous : [previous]) item?.dispose();
      }

      // 水轮：按节点名识别，只登记最外层，绕局部轴自转
      if (/water.?wheel|mill_wheel/i.test(child.name)) {
        let parent = child.parent;
        let nested = false;
        while (parent && parent !== model) {
          if (/water.?wheel|mill_wheel/i.test(parent.name)) {
            nested = true;
            break;
          }
          parent = parent.parent;
        }
        if (!nested) this.wheelNodes.push(child);
      }

      // 门窗：生成器写入 extras（fb_kind / fb_open_deg / fb_open_sign）
      const kind = child.userData?.fb_kind as string | undefined;
      if ((kind === "door" || kind === "window") && !child.userData.fbOpenableId) {
        const id = `openable-${this.openables.length}`;
        this.openables.push({
          id,
          node: child,
          kind: kind as "door" | "window",
          baseRotationY: child.rotation.y,
          openDeg: Number(child.userData.fb_open_deg ?? (kind === "door" ? 95 : 32)),
          sign: Number(child.userData.fb_open_sign ?? -1),
          progress: 0,
          target: 0,
        });
        child.traverse((node) => {
          node.userData.fbOpenableId = id;
        });
      }
    });

    if (waterUsed) {
      this.waterMaterial = waterMaterial;
    } else {
      waterMaterial.dispose();
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
    this.renderer.domElement.style.cursor = enabled ? "move" : this.buildMode ? "grab" : "";
  }

  /**
   * 计算当前剖切轴在屏幕上的投影方向与像素/米比例。
   * 鼠标位移投影到该方向后，拖动方向与剖切面推进方向始终一致，
   * 避免 X/Z 轴因相机朝向出现的反向问题。
   */
  private updateClipDragFrame(): void {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const axis = this.clipSettings.axis;
    const origin = this.modelBox.getCenter(new THREE.Vector3());
    origin[axis] = this.clipSettings.position;
    const probe = origin.clone();
    probe[axis] += 1;
    const start = origin.clone().project(this.camera);
    const end = probe.clone().project(this.camera);
    const dx = ((end.x - start.x) * rect.width) / 2;
    const dy = (-(end.y - start.y) * rect.height) / 2;
    const length = Math.hypot(dx, dy);
    if (length < 4) {
      // 剖切轴几乎正对相机，退化为上下拖动
      this.clipDragDirX = 0;
      this.clipDragDirY = -1;
      this.clipDragPixelsPerUnit = Math.max(40, rect.height * 0.35);
      return;
    }
    this.clipDragDirX = dx / length;
    this.clipDragDirY = dy / length;
    this.clipDragPixelsPerUnit = Math.max(length, rect.height * 0.12);
  }

  // ================================================================ 吸引子 / 排斥子
  /** 设置吸引子 / 排斥子列表；列表为空或总开关关闭时恢复原始网格。 */
  setAttractors(items: AttractorItem[], enabled: boolean): void {
    this.attractorItems = items.map((item) => ({
      ...item,
      point: [...item.point] as [number, number, number],
    }));
    this.attractorEnabled = enabled;
    this.applyAttractor();
    this.syncAttractorGuides();
  }

  setAttractorPickMode(enabled: boolean, id: string | null = null): void {
    this.attractorPickMode = enabled;
    this.attractorPickId = enabled ? id : null;
    this.syncAttractorGuides();
  }

  /** 在场景中显示可拖拽的量场标记：实心球为作用点，线框球为影响半径。 */
  private syncAttractorGuides(): void {
    const visible = this.attractorEnabled || this.attractorPickMode;
    this.attractorGroup.visible = visible && this.attractorItems.length > 0;

    const alive = new Set<string>();
    for (const item of this.attractorItems) {
      alive.add(item.id);
      let guide = this.attractorGuides.get(item.id);
      if (!guide) {
        const core = new THREE.Mesh(
          new THREE.SphereGeometry(0.3, 16, 12),
          new THREE.MeshBasicMaterial({
            transparent: true,
            opacity: 0.95,
            depthTest: false,
            depthWrite: false,
          }),
        );
        core.renderOrder = 21;
        const halo = new THREE.Mesh(
          new THREE.SphereGeometry(1, 20, 14),
          new THREE.MeshBasicMaterial({
            wireframe: true,
            transparent: true,
            opacity: 0.26,
            depthWrite: false,
          }),
        );
        core.userData.attractorId = item.id;
        halo.userData.attractorId = item.id;
        this.attractorGroup.add(core, halo);
        guide = { core, halo };
        this.attractorGuides.set(item.id, guide);
      }
      const color = item.mode === "attract" ? 0x58e0c4 : 0xff8a5c;
      const coreMaterial = guide.core.material as THREE.MeshBasicMaterial;
      const haloMaterial = guide.halo.material as THREE.MeshBasicMaterial;
      coreMaterial.color.setHex(color);
      haloMaterial.color.setHex(color);
      coreMaterial.opacity = item.enabled ? 0.95 : 0.4;
      haloMaterial.opacity = item.enabled ? 0.26 : 0.1;
      guide.core.position.set(...item.point);
      guide.halo.position.copy(guide.core.position);
      guide.halo.scale.setScalar(Math.max(0.25, item.radius));
      guide.halo.visible = item.radius > 0.25;
    }

    for (const [id, guide] of this.attractorGuides) {
      if (alive.has(id)) continue;
      this.attractorGroup.remove(guide.core, guide.halo);
      guide.core.geometry.dispose();
      guide.halo.geometry.dispose();
      (guide.core.material as THREE.Material).dispose();
      (guide.halo.material as THREE.Material).dispose();
      this.attractorGuides.delete(id);
    }
  }

  /** 拾取量场标记点，返回对应条目。 */
  private hitAttractorGuide(event: PointerEvent): AttractorItem | null {
    if (!this.attractorGroup.visible || !this.setRayFromEvent(event)) return null;
    const hits = this.raycaster.intersectObjects(this.attractorGroup.children, false);
    for (const hit of hits) {
      const id = hit.object.userData.attractorId as string | undefined;
      if (!id) continue;
      const item = this.attractorItems.find((entry) => entry.id === id);
      if (item) return item;
    }
    return null;
  }

  private beginAttractorDrag(item: AttractorItem, event: PointerEvent): void {
    this.attractorDragId = item.id;
    this.attractorDragControls = this.controls.enabled;
    this.controls.enabled = false;
    this.renderer.domElement.style.cursor = "grabbing";
    this.renderer.domElement.setPointerCapture?.(event.pointerId);
    // 拖动平面垂直于相机视线，保证鼠标移动与标记位移一致
    const normal = this.camera.getWorldDirection(new THREE.Vector3()).negate();
    const center = new THREE.Vector3(...item.point);
    this.attractorDragPlane.setFromNormalAndCoplanarPoint(normal, center);
    this.raycaster.ray.intersectPlane(this.attractorDragPlane, this.attractorDragPoint);
    this.attractorDragOffset.copy(center).sub(this.attractorDragPoint);
  }

  private dragAttractor(event: PointerEvent): void {
    const id = this.attractorDragId;
    if (!id || !this.setRayFromEvent(event)) return;
    if (!this.raycaster.ray.intersectPlane(this.attractorDragPlane, this.attractorDragPoint)) return;
    this.attractorDragPoint.add(this.attractorDragOffset);
    const item = this.attractorItems.find((entry) => entry.id === id);
    if (!item) return;
    const point: [number, number, number] = [
      Math.round(this.attractorDragPoint.x * 100) / 100,
      Math.round(this.attractorDragPoint.y * 100) / 100,
      Math.round(this.attractorDragPoint.z * 100) / 100,
    ];
    item.point = point;
    item.enabled = true;
    this.applyAttractor();
    this.syncAttractorGuides();
    this.onAttractorMoved?.(id, point);
  }

  private endAttractorDrag(): void {
    if (!this.attractorDragId) return;
    this.attractorDragId = null;
    this.controls.enabled = this.attractorDragControls;
    this.renderer.domElement.style.cursor = this.buildMode ? "grab" : "";
  }

  private applyAttractor(): void {
    const items = this.attractorEnabled
      ? this.attractorItems.filter((item) => item.enabled && item.radius > 0 && item.strength > 0)
      : [];

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

      if (!items.length) {
        array.set(base.position);
        const normalAttribute = geometry.getAttribute("normal") as THREE.BufferAttribute | undefined;
        if (normalAttribute && base.normal) {
          (normalAttribute.array as Float32Array).set(base.normal);
          normalAttribute.needsUpdate = true;
        }
      } else {
        mesh.updateWorldMatrix(true, false);
        const inverse = new THREE.Matrix4().copy(mesh.matrixWorld).invert();
        const localItems = items.map((item) => {
          const point = new THREE.Vector3(...item.point).applyMatrix4(inverse);
          return {
            point,
            radius: item.radius,
            radiusSq: item.radius * item.radius,
            strength: item.strength,
            sign: item.mode === "attract" ? -0.9 : 1,
          };
        });
        array.set(base.position);
        for (let i = 0; i < array.length; i += 3) {
          let offsetX = 0;
          let offsetY = 0;
          let offsetZ = 0;
          for (const item of localItems) {
            const dx = base.position[i] - item.point.x;
            const dy = base.position[i + 1] - item.point.y;
            const dz = base.position[i + 2] - item.point.z;
            const distanceSq = dx * dx + dy * dy + dz * dz;
            if (distanceSq >= item.radiusSq || distanceSq < 1e-8) continue;
            const distance = Math.sqrt(distanceSq);
            const t = 1 - distance / item.radius;
            const falloff = t * t * (3 - 2 * t);
            const amount = (item.strength * falloff * item.sign) / distance;
            offsetX += dx * amount;
            offsetY += dy * amount;
            offsetZ += dz * amount;
          }
          array[i] += offsetX;
          array[i + 1] += offsetY;
          array[i + 2] += offsetZ;
        }
      }
      attribute.needsUpdate = true;
      if (items.length) geometry.computeVertexNormals();
      geometry.boundingSphere = null;
    }
  }

  // ================================================================ 体素碎裂
  setFracture(patch: Partial<FractureSettings>): void {
    this.fractureSettings = { ...this.fractureSettings, ...patch };
    this.applyFracture();
  }

  private applyFracture(): void {
    const { enabled, amount, cell, collapse, impulse } = this.fractureSettings;
    for (const mesh of this.nodes.values()) {
      mesh.visible = !enabled;
    }
    if (this.selectionHelper) this.selectionHelper.visible = !enabled;
    if (this.hoverHelper) this.hoverHelper.visible = !enabled;
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
    this.voxel.setCollapse(collapse, impulse);
    this.voxel.setClippingPlanes(this.clipSettings.enabled ? [this.clipPlane] : null);
  }

  /** 重新触发一次物理崩塌。 */
  triggerCollapse(): void {
    if (!this.fractureSettings.enabled) return;
    this.voxel.triggerCollapse();
  }

  // ================================================================ 灵活搭建
  setBuildMode(enabled: boolean): void {
    this.buildMode = enabled;
    this.renderer.domElement.style.cursor = enabled ? "grab" : "";
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
    mesh.userData.blockName = patch?.name ?? `模块 ${this.blockSeq}`;
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
      name: mesh.userData.blockName as string,
    });
  }

  /**
   * 智能扩展：沿指定轴把模块延伸一个自身长度。
   * - 与相邻模块有缝隙时，自动吸附到相邻面，做到无缝拼接；
   * - 已与相邻模块贴合时，在相邻模块外侧追加一个同尺寸模块。
   */
  smartExpand(id: string, axis: "x" | "y" | "z"): void {
    const mesh = this.blocks.find((item) => item.userData.blockId === id);
    if (!mesh) return;
    const box = new THREE.Box3().setFromObject(mesh);
    const step = mesh.scale[axis];
    const otherAxes = (["x", "y", "z"] as const).filter((item) => item !== axis);
    const otherBox = new THREE.Box3();
    let nearest: { delta: number; max: number } | null = null;

    for (const other of this.blocks) {
      if (other === mesh) continue;
      otherBox.setFromObject(other);
      const overlaps = otherAxes.every(
        (item) => box.min[item] < otherBox.max[item] - 0.05 && box.max[item] > otherBox.min[item] + 0.05,
      );
      if (!overlaps) continue;
      const delta = otherBox.min[axis] - box.max[axis];
      if (delta < -0.05 || delta > step + 0.6) continue;
      if (!nearest || delta < nearest.delta) {
        nearest = { delta, max: otherBox.max[axis] };
      }
    }

    if (nearest && nearest.delta > 0.05) {
      // 填补缝隙，扩展后与相邻模块贴合
      const grow = nearest.delta;
      mesh.scale[axis] += grow;
      mesh.position[axis] += grow / 2;
    } else if (nearest) {
      // 已贴合：在相邻模块外侧追加一个同尺寸模块
      const position: [number, number, number] = [mesh.position.x, mesh.position.y, mesh.position.z];
      const index = axis === "x" ? 0 : axis === "y" ? 1 : 2;
      position[index] = nearest.max + step / 2;
      this.addBlock({
        name: mesh.userData.blockName as string,
        size: [mesh.scale.x, mesh.scale.y, mesh.scale.z],
        color: `#${(mesh.material as THREE.MeshStandardMaterial).color.getHexString()}`,
        position,
      });
      return;
    } else {
      mesh.scale[axis] += step;
      mesh.position[axis] += step / 2;
    }

    mesh.updateMatrixWorld();
    this.selectionHelper?.update();
    this.onSelectedBlock?.(this.blockInfo(mesh));
    this.notifyBlocks();
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

  /** 搭建模式快捷删除；输入框内不拦截。 */
  private handleGlobalKeyDown = (event: KeyboardEvent): void => {
    if (!this.buildMode || !this.selectedBlockId) return;
    const target = event.target as HTMLElement | null;
    if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      this.removeBlock(this.selectedBlockId);
    }
  };

  // ================================================================ 指针交互
  private handlePointerDown = (event: PointerEvent): void => {
    if (event.button !== 0 || this.firstPerson) return;
    this.pointerState = { x: event.clientX, y: event.clientY, active: true, moved: false };

    const guide = this.hitAttractorGuide(event);
    if (guide) {
      this.beginAttractorDrag(guide, event);
      return;
    }

    if (this.buildMode) {
      const hit = this.raycastBlock(event);
      if (hit) {
        const blockId = hit.object.userData.blockId as string;
        this.selectBlock(blockId);
        this.beginBlockDrag(blockId, event);
        return;
      }
      if (!event.altKey) this.selectBlock(null);
    }

    if (this.clipDragEnabled && this.clipSettings.enabled) {
      this.clipDragging = true;
      this.clipDragStartX = event.clientX;
      this.clipDragStartY = event.clientY;
      this.clipDragStartPosition = this.clipSettings.position;
      this.updateClipDragFrame();
    }
  };

  private handlePointerMove = (event: PointerEvent): void => {
    if (!this.pointerState.active) {
      // 悬停量场标记时给出可拖拽提示
      if (!this.buildMode && !this.firstPerson && this.attractorGroup.visible) {
        this.renderer.domElement.style.cursor = this.hitAttractorGuide(event) ? "grab" : "";
      }
      return;
    }
    if (
      Math.abs(event.clientX - this.pointerState.x) +
        Math.abs(event.clientY - this.pointerState.y) >
      5
    ) {
      this.pointerState.moved = true;
    }
    if (this.blockDragging) {
      this.dragBlock(event);
      return;
    }
    if (this.attractorDragId) {
      this.dragAttractor(event);
      return;
    }
    if (!this.clipDragging) return;
    // 把鼠标位移投影到剖切轴在屏幕上的方向，保证拖动方向与剖切推进一致
    const dx = event.clientX - this.clipDragStartX;
    const dy = event.clientY - this.clipDragStartY;
    const along = dx * this.clipDragDirX + dy * this.clipDragDirY;
    const next = this.clipDragStartPosition + along / this.clipDragPixelsPerUnit;
    this.setClip({ position: next });
    this.onClipPosition?.(this.clipSettings.position);
  };

  private handlePointerUp = (event: PointerEvent): void => {
    if (!this.pointerState.active) return;
    const clicked =
      event.button === 0 &&
      !this.pointerState.moved &&
      !this.clipDragging &&
      !this.blockDragging &&
      !this.attractorDragId;
    this.pointerState.active = false;
    if (this.blockDragging) this.endBlockDrag();
    if (this.attractorDragId) this.endAttractorDrag();
    this.clipDragging = false;
    if (!clicked) return;
    if (this.buildMode && event.altKey) this.addBlockAtPointer(event);
    else this.pick(event);
  };

  private setRayFromEvent(event: PointerEvent): boolean {
    const rect = this.renderer.domElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    return true;
  }

  private raycastBlock(event: PointerEvent): THREE.Intersection | null {
    if (!this.setRayFromEvent(event)) return null;
    return this.raycaster.intersectObjects(this.blocks, false)[0] ?? null;
  }

  /** 把屏幕坐标投到指定高度的水平面。 */
  private rayPlanePoint(event: PointerEvent, y: number): THREE.Vector3 | null {
    if (!this.setRayFromEvent(event)) return null;
    this.buildPlane.constant = -y;
    const point = new THREE.Vector3();
    return this.raycaster.ray.intersectPlane(this.buildPlane, point) ? point : null;
  }

  private beginBlockDrag(blockId: string, event: PointerEvent): void {
    const mesh = this.blocks.find((item) => item.userData.blockId === blockId);
    if (!mesh) return;
    this.blockDragging = true;
    this.blockDragId = blockId;
    this.blockDragPlaneY = mesh.position.y;
    this.blockDragStartY = mesh.position.y;
    this.blockDragPointerY = event.clientY;
    this.blockDragOrigin.copy(mesh.position);
    const point = this.rayPlanePoint(event, mesh.position.y);
    if (point) {
      this.blockDragOffset.set(mesh.position.x - point.x, 0, mesh.position.z - point.z);
    } else {
      this.blockDragOffset.set(0, 0, 0);
    }
    this.controls.enabled = false;
    this.renderer.domElement.style.cursor = "grabbing";
  }

  private dragBlock(event: PointerEvent): void {
    const mesh = this.blocks.find((item) => item.userData.blockId === this.blockDragId);
    if (!mesh) return;
    if (event.shiftKey) {
      // Shift 拖动：沿竖直方向升降
      const dy = event.clientY - this.blockDragPointerY;
      const y = Math.max(mesh.scale.y / 2, this.blockDragStartY - dy * 0.025);
      mesh.position.set(this.blockDragOrigin.x, y, this.blockDragOrigin.z);
    } else {
      const point = this.rayPlanePoint(event, this.blockDragPlaneY);
      if (point) {
        const snap = (value: number) => Math.round(value * 10) / 10;
        mesh.position.set(
          snap(point.x + this.blockDragOffset.x),
          this.blockDragStartY,
          snap(point.z + this.blockDragOffset.z),
        );
      }
    }
    mesh.updateMatrixWorld();
    this.selectionHelper?.update();
    this.onSelectedBlock?.(this.blockInfo(mesh));
    this.notifyBlocks();
  }

  private endBlockDrag(): void {
    this.blockDragging = false;
    this.blockDragId = null;
    this.controls.enabled = true;
    this.controls.enableRotate = !this.viewLocked && !this.clipDragEnabled;
    this.controls.enablePan = !this.viewLocked && !this.clipDragEnabled;
    this.renderer.domElement.style.cursor = this.buildMode ? "grab" : "";
  }

  /** Alt + 点击地面：在落点新增模块。 */
  private addBlockAtPointer(event: PointerEvent): void {
    const point = this.rayPlanePoint(event, 0);
    if (!point) return;
    const snap = (value: number) => Math.round(value * 10) / 10;
    this.addBlock({ position: [snap(point.x), 1.3, snap(point.z)] });
  }

  private pick(event: PointerEvent): void {
    if (!this.setRayFromEvent(event)) return;

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
        const target = this.attractorPickId
          ? this.attractorItems.find((item) => item.id === this.attractorPickId)
          : null;
        if (target) {
          target.point = point;
          target.enabled = true;
          this.applyAttractor();
          this.onAttractorPicked?.(target.id, point);
        }
      }
      return;
    }

    if (this.fractureSettings.enabled) return;
    const hit = this.raycaster.intersectObjects(meshes, false)[0];
    // 点中门扇/窗扇则切换开合状态（同时保留节点选中）
    const openableId = hit?.object.userData.fbOpenableId as string | undefined;
    if (openableId) this.toggleOpenable(openableId);
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
    window.removeEventListener("keydown", this.handleGlobalKeyDown);
    this.clearModel();
    this.rain.dispose();
    this.snow.dispose();
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

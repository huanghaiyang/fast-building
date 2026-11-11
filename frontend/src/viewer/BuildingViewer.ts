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

interface SkyConfig {
  top: string;
  horizon: string;
  bottom: string;
  sun?: { color: string; x: number; y: number; radius: number };
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
      sun: { color: "#fff6d8", x: 0.74, y: 0.26, radius: 70 },
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
      sun: { color: "#ffcf8a", x: 0.8, y: 0.44, radius: 110 },
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
      sun: { color: "#e8f0ff", x: 0.24, y: 0.3, radius: 30 },
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

  constructor(container: HTMLElement) {
    this.container = container;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(container.clientWidth || 800, container.clientHeight || 600);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
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

  /** 生成纵向渐变的等距圆柱天空贴图，可选叠加太阳光晕。 */
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
        const cx = sky.sun.x * width;
        const cy = sky.sun.y * height;
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

    this.baseHemiIntensity = config.hemi.intensity;
    this.hemi.color.set(config.hemi.sky);
    this.hemi.groundColor.set(config.hemi.ground);
    this.hemi.intensity = this.baseHemiIntensity * this.ambientMultiplier;

    this.key.color.set(config.key.color);
    this.key.intensity = config.key.intensity;
    this.key.position.set(...config.key.position);

    this.fill.color.set(config.fill.color);
    this.fill.intensity = config.fill.intensity;
    this.fill.position.set(...config.fill.position);

    this.groundMaterial.color.set(config.ground);
    (this.grid.material as THREE.Material).opacity = config.gridOpacity;

    this.disposeEnvironment();
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
    this.controls.update();
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
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            for (const material of materials) {
              if (!material) continue;
              for (const key of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"] as const) {
                const texture = (material as THREE.MeshStandardMaterial)[key];
                if (texture) {
                  texture.wrapS = THREE.RepeatWrapping;
                  texture.wrapT = THREE.RepeatWrapping;
                  texture.needsUpdate = true;
                }
              }
            }
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
    this.controls.enableRotate = !locked;
    this.controls.enablePan = !locked;
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
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        if (material) material.needsUpdate = true;
      }
    });
  }

  resetView(): void {
    this.camera.up.set(0, 1, 0);
    this.camera.position.copy(this.defaultPosition);
    this.controls.target.copy(this.defaultTarget);
    this.controls.update();
  }

  dispose(): void {
    this.disposed = true;
    cancelAnimationFrame(this.animationId);
    this.resizeObserver.disconnect();
    this.clearModel();
    this.disposeEnvironment();
    this.studioTarget?.dispose();
    this.controls.dispose();
    this.pmrem.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}

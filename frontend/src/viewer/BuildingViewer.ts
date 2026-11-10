/**
 * three.js 建筑预览器。
 *
 * 只负责场景、相机、灯光、GLB 加载与视图操作，React 层通过方法调用控制。
 * 使用 RoomEnvironment 提供环境反射，让 PBR 材质的金属度/粗糙度有正确表现。
 */

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export interface ViewerStats {
  meshes: number;
  triangles: number;
  textures: number;
  size: [number, number, number];
}

export type ViewerStatus = "idle" | "loading" | "ready" | "error";

export class BuildingViewer {
  private readonly container: HTMLElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly controls: OrbitControls;
  private readonly loader = new GLTFLoader();
  private readonly pmrem: THREE.PMREMGenerator;
  private readonly resizeObserver: ResizeObserver;

  private model: THREE.Object3D | null = null;
  private animationId = 0;
  private disposed = false;
  private defaultPosition = new THREE.Vector3(20, 16, 24);
  private defaultTarget = new THREE.Vector3(0, 3, 0);

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
    this.controls.maxPolarAngle = Math.PI / 2 - 0.02;
    this.controls.target.copy(this.defaultTarget);
    this.controls.autoRotateSpeed = 0.7;
    this.controls.update();

    this.pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    this.setupLights();
    this.setupGround();

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.animate();
  }

  // ------------------------------------------------------------------ 场景
  private setupLights(): void {
    const hemi = new THREE.HemisphereLight(0x9db4d0, 0x141414, 0.85);
    this.scene.add(hemi);

    const key = new THREE.DirectionalLight(0xfff0d8, 2.4);
    key.position.set(22, 32, 18);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 160;
    key.shadow.camera.left = -45;
    key.shadow.camera.right = 45;
    key.shadow.camera.top = 45;
    key.shadow.camera.bottom = -45;
    key.shadow.bias = -0.0004;
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0x8fb6ff, 0.55);
    fill.position.set(-18, 14, -20);
    this.scene.add(fill);
  }

  private setupGround(): void {
    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(90, 64),
      new THREE.MeshStandardMaterial({ color: 0x0f151c, roughness: 0.96, metalness: 0.0 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.02;
    ground.receiveShadow = true;
    this.scene.add(ground);

    const grid = new THREE.GridHelper(160, 80, 0x2b3947, 0x18222c);
    grid.position.y = 0.005;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.55;
    this.scene.add(grid);
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
        mesh.geometry.dispose();
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) material?.dispose();
      }
    });
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

  resetView(): void {
    this.camera.position.copy(this.defaultPosition);
    this.controls.target.copy(this.defaultTarget);
    this.controls.update();
  }

  dispose(): void {
    this.disposed = true;
    cancelAnimationFrame(this.animationId);
    this.resizeObserver.disconnect();
    this.clearModel();
    this.controls.dispose();
    this.pmrem.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}

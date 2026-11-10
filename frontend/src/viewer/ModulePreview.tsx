/** 模块库内的轻量三维预览：单个模块 GLB 的独立小画布。 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

interface Props {
  moduleId: string;
}

export function ModulePreview({ moduleId }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    setStatus("loading");

    const width = host.clientWidth || 240;
    const height = host.clientHeight || 168;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, width / height, 0.05, 200);
    camera.position.set(3.4, 2.6, 4.2);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.enablePan = false;
    controls.minDistance = 1;
    controls.maxDistance = 40;
    controls.target.set(0, 1, 0);
    controls.update();

    scene.add(new THREE.HemisphereLight(0xdfe9f5, 0x2a2b26, 1.5));
    const key = new THREE.DirectionalLight(0xfff2dd, 2.4);
    key.position.set(4, 7, 5);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x9fc0ff, 0.7);
    fill.position.set(-5, 3, -4);
    scene.add(fill);

    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTarget = pmrem.fromScene(new RoomEnvironment(), 0.04);
    scene.environment = envTarget.texture;

    let model: THREE.Object3D | null = null;
    let disposed = false;
    let frame = 0;

    const loader = new GLTFLoader();
    loader.load(
      `/api/modules/${encodeURIComponent(moduleId)}/preview.glb`,
      (gltf) => {
        if (disposed) return;
        model = gltf.scene;
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const material = (child as THREE.Mesh).material;
            const list = Array.isArray(material) ? material : [material];
            for (const item of list) {
              if (item && "envMapIntensity" in item) {
                (item as THREE.MeshStandardMaterial).envMapIntensity = 0.9;
              }
            }
          }
        });

        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.x -= center.x;
        model.position.z -= center.z;
        model.position.y -= box.min.y;
        scene.add(model);

        const radius = Math.max(size.length() * 0.5, 0.6);
        const distance = radius / Math.sin((camera.fov * Math.PI) / 360);
        const target = new THREE.Vector3(0, size.y * 0.45, 0);
        camera.position.copy(target).add(new THREE.Vector3(0.95, 0.7, 1.15).normalize().multiplyScalar(distance * 1.02));
        controls.target.copy(target);
        controls.update();
        setStatus("ready");
      },
      undefined,
      () => {
        if (!disposed) setStatus("error");
      },
    );

    const resizeObserver = new ResizeObserver(() => {
      const nextWidth = host.clientWidth;
      const nextHeight = host.clientHeight;
      if (!nextWidth || !nextHeight) return;
      renderer.setSize(nextWidth, nextHeight);
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
    });
    resizeObserver.observe(host);

    const animate = () => {
      if (disposed) return;
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      if (model) {
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            (child as THREE.Mesh).geometry.dispose();
            const material = (child as THREE.Mesh).material;
            const list = Array.isArray(material) ? material : [material];
            for (const item of list) item?.dispose();
          }
        });
      }
      controls.dispose();
      envTarget.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [moduleId]);

  return (
    <div className="module-preview">
      <div className="module-preview-canvas" ref={hostRef} />
      {status === "loading" && (
        <div className="module-preview-state">
          <span className="spinner" />
          <span>正在构建预览...</span>
        </div>
      )}
      {status === "error" && <div className="module-preview-state">预览生成失败，可重试展开</div>}
      <span className="module-preview-hint">拖动可旋转</span>
    </div>
  );
}

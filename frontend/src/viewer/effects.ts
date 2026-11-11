/**
 * 实时特效：降雨与体素碎裂。
 *
 * 两者都只作用于预览场景，不会写回生成的 GLB。
 */

import * as THREE from "three";

/** 雨幕：用线段模拟雨丝，数量与不透明度由雨量控制。 */
export class RainSystem {
  readonly group = new THREE.Group();
  private readonly count: number;
  private readonly positions: Float32Array;
  private readonly drops: Float32Array;
  private readonly geometry: THREE.BufferGeometry;
  private readonly material: THREE.LineBasicMaterial;
  private readonly lines: THREE.LineSegments;
  private readonly center = new THREE.Vector3(0, 0, 0);
  private intensity = 0;
  private area = 64;
  private top = 44;
  private readonly bottom = -1;
  private wind = 1.2;

  constructor(count = 3600) {
    this.count = count;
    this.positions = new Float32Array(count * 6);
    this.drops = new Float32Array(count * 5);

    for (let i = 0; i < count; i += 1) {
      this.resetDrop(i, true);
    }

    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));
    this.geometry.setDrawRange(0, 0);

    this.material = new THREE.LineBasicMaterial({
      color: 0xbed7ea,
      transparent: true,
      opacity: 0.42,
      depthWrite: false,
      fog: true,
    });

    this.lines = new THREE.LineSegments(this.geometry, this.material);
    this.lines.frustumCulled = false;
    this.lines.renderOrder = 2;
    this.group.add(this.lines);
    this.group.visible = false;
  }

  private resetDrop(index: number, initial: boolean): void {
    const base = index * 5;
    this.drops[base] = this.center.x + (Math.random() - 0.5) * this.area;
    this.drops[base + 1] = initial ? Math.random() * this.top : this.top + Math.random() * 6;
    this.drops[base + 2] = this.center.z + (Math.random() - 0.5) * this.area;
    this.drops[base + 3] = 17 + Math.random() * 15;
    this.drops[base + 4] = 0.35 + Math.random() * 0.8;
  }

  setCenter(center: THREE.Vector3): void {
    this.center.copy(center);
    for (let i = 0; i < this.count; i += 1) this.resetDrop(i, true);
  }

  /** 雨量 0~1；0 时整体隐藏。 */
  setIntensity(value: number): void {
    this.intensity = Math.max(0, Math.min(1, value));
    this.group.visible = this.intensity > 0.001;
    this.material.opacity = 0.2 + this.intensity * 0.42;
    const active = Math.floor(this.count * Math.max(this.intensity, 0.001));
    this.geometry.setDrawRange(0, active * 2);
  }

  update(dt: number): void {
    if (!this.group.visible) return;
    const active = Math.floor(this.count * this.intensity);
    const step = Math.min(dt, 0.06);
    for (let i = 0; i < active; i += 1) {
      const base = i * 5;
      this.drops[base] += this.wind * step;
      this.drops[base + 1] -= this.drops[base + 3] * step;
      if (this.drops[base + 1] < this.bottom) {
        this.resetDrop(i, false);
      }
      const offset = i * 6;
      const x = this.drops[base];
      const y = this.drops[base + 1];
      const z = this.drops[base + 2];
      const length = this.drops[base + 4];
      this.positions[offset] = x;
      this.positions[offset + 1] = y;
      this.positions[offset + 2] = z;
      this.positions[offset + 3] = x - this.wind * 0.03;
      this.positions[offset + 4] = y + length;
      this.positions[offset + 5] = z;
    }
    const attribute = this.geometry.getAttribute("position") as THREE.BufferAttribute;
    attribute.needsUpdate = true;
  }

  dispose(): void {
    this.geometry.dispose();
    this.material.dispose();
  }
}

interface VoxelCell {
  position: THREE.Vector3;
  color: THREE.Color;
  jitter: THREE.Vector3;
  spin: THREE.Vector3;
  scale: number;
}

/**
 * 体素碎裂：把模型三角面重采样成体素方块，按爆散量向外位移并旋转。
 * 属于近似体素化，只追求视觉密度与碎片感。
 */
export class VoxelFracture {
  readonly group = new THREE.Group();
  private mesh: THREE.InstancedMesh | null = null;
  private cells: VoxelCell[] = [];
  private center = new THREE.Vector3();
  private amount = 0;
  private cellSize = 0.42;
  private dirty = true;

  constructor() {
    this.group.visible = false;
  }

  build(model: THREE.Object3D, cellSize: number, maxVoxels = 9000): void {
    this.clear();
    const size = Math.max(0.08, cellSize);
    this.cellSize = size;
    const seen = new Set<string>();
    const cells: VoxelCell[] = [];
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    const c = new THREE.Vector3();
    const point = new THREE.Vector3();
    const fallback = new THREE.Color("#9c8f7a");

    model.updateWorldMatrix(true, true);
    model.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh || !mesh.geometry) return;
      const position = mesh.geometry.getAttribute("position");
      if (!position) return;
      const index = mesh.geometry.index;
      const triangleCount = index ? Math.floor(index.count / 3) : Math.floor(position.count / 3);
      const stride = Math.max(1, Math.ceil(triangleCount / 5000));
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const first = materials[0] as THREE.MeshStandardMaterial | undefined;
      const color = first?.color ? first.color.clone() : fallback.clone();
      if (color.r > 0.86 && color.g > 0.86 && color.b > 0.86) color.copy(fallback);

      for (let t = 0; t < triangleCount; t += stride) {
        if (cells.length >= maxVoxels) break;
        const i0 = index ? index.getX(t * 3) : t * 3;
        const i1 = index ? index.getX(t * 3 + 1) : t * 3 + 1;
        const i2 = index ? index.getX(t * 3 + 2) : t * 3 + 2;
        a.fromBufferAttribute(position, i0).applyMatrix4(mesh.matrixWorld);
        b.fromBufferAttribute(position, i1).applyMatrix4(mesh.matrixWorld);
        c.fromBufferAttribute(position, i2).applyMatrix4(mesh.matrixWorld);
        const edge = Math.max(a.distanceTo(b), b.distanceTo(c), c.distanceTo(a));
        const steps = Math.min(5, Math.max(1, Math.ceil(edge / size)));

        for (let i = 0; i <= steps; i += 1) {
          for (let j = 0; j <= steps - i; j += 1) {
            const u = i / steps;
            const v = j / steps;
            const w = 1 - u - v;
            point.set(
              a.x * w + b.x * u + c.x * v,
              a.y * w + b.y * u + c.y * v,
              a.z * w + b.z * u + c.z * v,
            );
            const key = `${Math.round(point.x / size)}|${Math.round(point.y / size)}|${Math.round(
              point.z / size,
            )}`;
            if (seen.has(key)) continue;
            seen.add(key);
            cells.push({
              position: new THREE.Vector3(
                Math.round(point.x / size) * size,
                Math.round(point.y / size) * size,
                Math.round(point.z / size) * size,
              ),
              color: color.clone(),
              jitter: new THREE.Vector3(
                Math.random() - 0.5,
                Math.random() * 0.35,
                Math.random() - 0.5,
              ).normalize(),
              spin: new THREE.Vector3(
                Math.random() - 0.5,
                Math.random() - 0.5,
                Math.random() - 0.5,
              ).multiplyScalar(6),
              scale: 0.72 + Math.random() * 0.4,
            });
            if (cells.length >= maxVoxels) break;
          }
          if (cells.length >= maxVoxels) break;
        }
      }
    });

    if (!cells.length) return;
    this.cells = cells;
    const box = new THREE.Box3();
    for (const cell of cells) box.expandByPoint(cell.position);
    box.getCenter(this.center);

    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.82,
      metalness: 0.02,
    });
    this.mesh = new THREE.InstancedMesh(geometry, material, cells.length);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = true;
    for (let i = 0; i < cells.length; i += 1) {
      this.mesh.setColorAt(i, cells[i].color);
    }
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
    this.group.add(this.mesh);
    this.group.visible = true;
    this.dirty = true;
    this.updateMatrices();
  }

  setAmount(amount: number): void {
    this.amount = Math.max(0, amount);
    this.dirty = true;
    this.updateMatrices();
  }

  /** 与主模型共用剖切平面，保持剖切效果一致。 */
  setClippingPlanes(planes: THREE.Plane[] | null): void {
    if (!this.mesh) return;
    const material = this.mesh.material as THREE.MeshStandardMaterial;
    material.clippingPlanes = planes;
    material.needsUpdate = true;
  }

  private updateMatrices(): void {
    if (!this.mesh || !this.dirty) return;
    this.dirty = false;
    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const position = new THREE.Vector3();
    const euler = new THREE.Euler();

    for (let i = 0; i < this.cells.length; i += 1) {
      const cell = this.cells[i];
      const direction = cell.position.clone().sub(this.center);
      if (direction.lengthSq() < 1e-6) direction.set(0, 1, 0);
      direction.normalize().add(cell.jitter).normalize();
      const spread = this.amount * (0.55 + cell.scale * 0.7);
      position.copy(cell.position).addScaledVector(direction, spread);
      position.y -= this.amount * this.amount * 0.16 * cell.scale;

      euler.set(
        cell.spin.x * this.amount * 0.1,
        cell.spin.y * this.amount * 0.1,
        cell.spin.z * this.amount * 0.1,
      );
      quaternion.setFromEuler(euler);
      const voxel = this.cellSize * 0.94 * cell.scale;
      scale.setScalar(Math.max(0.03, voxel));
      matrix.compose(position, quaternion, scale);
      this.mesh.setMatrixAt(i, matrix);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
    this.mesh.computeBoundingSphere();
  }

  clear(): void {
    if (this.mesh) {
      this.group.remove(this.mesh);
      this.mesh.geometry.dispose();
      (this.mesh.material as THREE.Material).dispose();
      this.mesh.dispose();
      this.mesh = null;
    }
    this.cells = [];
    this.group.visible = false;
  }

  dispose(): void {
    this.clear();
  }
}

/**
 * 体积光：沿太阳方向生成若干可面向相机的加色光柱，并附带缓慢漂浮的浮尘。
 * 光柱参与深度测试，会被建筑遮挡，从而产生体积透视感。
 */
export class VolumetricLight {
  readonly group = new THREE.Group();
  private shafts: Array<{ mesh: THREE.Mesh; axis: THREE.Vector3 }> = [];
  private dust: THREE.Points | null = null;
  private dustMaterial: THREE.PointsMaterial | null = null;
  private dustTexture: THREE.Texture | null = null;
  private readonly uniforms = {
    uTime: { value: 0 },
    uIntensity: { value: 0 },
  };
  private intensity = 0;

  constructor() {
    this.group.visible = false;
    this.group.renderOrder = 1;
  }

  setIntensity(value: number): void {
    this.intensity = Math.max(0, Math.min(2, value));
    this.uniforms.uIntensity.value = this.intensity;
    if (this.dustMaterial) this.dustMaterial.opacity = this.intensity * 0.75;
    this.group.visible = this.intensity > 0.001;
  }

  setup(sun: THREE.Vector3, target: THREE.Vector3, span: number): void {
    this.clear();
    const direction = target.clone().sub(sun);
    const length = Math.max(12, direction.length() * 1.06);
    direction.normalize();
    const yAxis = direction.clone().negate();
    const xAxis = new THREE.Vector3().crossVectors(yAxis, new THREE.Vector3(0, 1, 0));
    if (xAxis.lengthSq() < 1e-4) xAxis.set(1, 0, 0);
    xAxis.normalize();
    const zAxis = new THREE.Vector3().crossVectors(xAxis, yAxis).normalize();
    const center = sun.clone().addScaledVector(direction, length * 0.5);
    const width = Math.max(span, 16) * 0.52;

    const vertexShader = [
      "varying vec2 vUv;",
      "void main() {",
      "  vUv = uv;",
      "  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );",
      "}",
    ].join("\n");

    const fragmentShader = [
      "uniform float uTime;",
      "uniform float uIntensity;",
      "varying vec2 vUv;",
      "float hash( vec2 p ) { return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 ); }",
      "float noise( vec2 p ) {",
      "  vec2 i = floor( p );",
      "  vec2 f = fract( p );",
      "  vec2 u = f * f * ( 3.0 - 2.0 * f );",
      "  return mix( mix( hash( i ), hash( i + vec2( 1.0, 0.0 ) ), u.x ),",
      "              mix( hash( i + vec2( 0.0, 1.0 ) ), hash( i + vec2( 1.0, 1.0 ) ), u.x ), u.y );",
      "}",
      "void main() {",
      "  float edge = smoothstep( 0.0, 0.34, vUv.x ) * smoothstep( 1.0, 0.66, vUv.x );",
      "  float fade = pow( vUv.y, 1.25 );",
      "  float grain = noise( vec2( vUv.x * 7.0, vUv.y * 2.4 - uTime * 0.12 ) );",
      "  float alpha = edge * fade * ( 0.35 + 0.65 * grain ) * uIntensity * 0.26;",
      "  vec3 color = mix( vec3( 0.78, 0.84, 1.0 ), vec3( 1.0, 0.9, 0.7 ), vUv.y );",
      "  if ( alpha < 0.002 ) discard;",
      "  gl_FragColor = vec4( color, alpha );",
      "}",
    ].join("\n");

    for (let i = 0; i < 6; i += 1) {
      const material = new THREE.ShaderMaterial({
        uniforms: this.uniforms,
        vertexShader,
        fragmentShader,
        transparent: true,
        depthWrite: false,
        depthTest: true,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), material);
      const offset = (i - 2.5) * span * 0.1;
      mesh.position
        .copy(center)
        .addScaledVector(xAxis, offset)
        .addScaledVector(zAxis, offset * 0.55);
      mesh.scale.set(width * (0.72 + (i % 3) * 0.16), length, 1);
      mesh.renderOrder = 1;
      this.group.add(mesh);
      this.shafts.push({ mesh, axis: yAxis.clone() });
    }

    // 浮尘
    const dustCount = 700;
    const positions = new Float32Array(dustCount * 3);
    const dustColor = new THREE.Color(0xffe6bd);
    for (let i = 0; i < dustCount; i += 1) {
      const along = (Math.random() - 0.5) * length;
      const lateralX = (Math.random() - 0.5) * width * 0.9;
      const lateralZ = (Math.random() - 0.5) * width * 0.9;
      positions[i * 3] =
        center.x + direction.x * along + xAxis.x * lateralX + zAxis.x * lateralZ;
      positions[i * 3 + 1] =
        center.y + direction.y * along + xAxis.y * lateralX + zAxis.y * lateralZ;
      positions[i * 3 + 2] =
        center.z + direction.z * along + xAxis.z * lateralX + zAxis.z * lateralZ;
    }
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    this.dustTexture = this.createDustTexture();
    this.dustMaterial = new THREE.PointsMaterial({
      color: dustColor,
      size: 0.16,
      map: this.dustTexture,
      transparent: true,
      opacity: this.intensity * 0.75,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    this.dust = new THREE.Points(dustGeometry, this.dustMaterial);
    this.dust.renderOrder = 1;
    this.group.add(this.dust);

    this.group.visible = this.intensity > 0.001;
  }

  private createDustTexture(): THREE.CanvasTexture {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
      gradient.addColorStop(0, "rgba(255,255,255,1)");
      gradient.addColorStop(0.4, "rgba(255,255,255,0.6)");
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 64, 64);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  update(delta: number, camera: THREE.Camera): void {
    if (!this.group.visible) return;
    this.uniforms.uTime.value += delta;
    const toCamera = new THREE.Vector3();
    const x = new THREE.Vector3();
    const z = new THREE.Vector3();
    const basis = new THREE.Matrix4();
    for (const shaft of this.shafts) {
      toCamera.copy(camera.position).sub(shaft.mesh.position);
      x.crossVectors(shaft.axis, toCamera);
      if (x.lengthSq() < 1e-6) continue;
      x.normalize();
      z.crossVectors(x, shaft.axis).normalize();
      basis.makeBasis(x, shaft.axis, z);
      shaft.mesh.quaternion.setFromRotationMatrix(basis);
    }
  }

  private clear(): void {
    for (const shaft of this.shafts) {
      this.group.remove(shaft.mesh);
      shaft.mesh.geometry.dispose();
      (shaft.mesh.material as THREE.Material).dispose();
    }
    this.shafts = [];
    if (this.dust) {
      this.group.remove(this.dust);
      this.dust.geometry.dispose();
    }
    this.dust = null;
    this.dustMaterial?.dispose();
    this.dustMaterial = null;
    this.dustTexture?.dispose();
    this.dustTexture = null;
    this.group.visible = false;
  }

  dispose(): void {
    this.clear();
  }
}


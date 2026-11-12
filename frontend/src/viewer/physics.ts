/**
 * 轻量刚体物理引擎：服务于体素崩塌预览。
 *
 * 只实现崩塌所需的子集：重力积分、地面碰撞、摩擦、弹性、角速度阻尼与休眠。
 * 固定步长积分保证不同帧率下崩塌结果一致，休眠机制避免数千体素长期空转。
 */

import * as THREE from "three";

export interface VoxelBody {
  /** 体素中心位置。 */
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  quaternion: THREE.Quaternion;
  angular: THREE.Vector3;
  /** 半边长，用于地面碰撞。 */
  half: number;
  restitution: number;
  friction: number;
  sleeping: boolean;
  /** 静止累计时间，用于进入休眠。 */
  restTime: number;
}

export function createVoxelBody(half: number): VoxelBody {
  return {
    position: new THREE.Vector3(),
    velocity: new THREE.Vector3(),
    quaternion: new THREE.Quaternion(),
    angular: new THREE.Vector3(),
    half,
    restitution: 0.16,
    friction: 0.72,
    sleeping: false,
    restTime: 0,
  };
}

const UP = new THREE.Vector3(0, 1, 0);

export class VoxelPhysicsWorld {
  gravity = -24;
  groundY = 0;
  readonly bodies: VoxelBody[] = [];

  private accumulator = 0;
  private readonly fixedStep = 1 / 120;
  private awake = 0;

  private readonly axis = new THREE.Vector3();
  private readonly spin = new THREE.Quaternion();

  clear(): void {
    this.bodies.length = 0;
    this.accumulator = 0;
    this.awake = 0;
  }

  add(body: VoxelBody): void {
    this.bodies.push(body);
  }

  /** 唤醒全部体素。 */
  wakeAll(): void {
    for (const body of this.bodies) {
      body.sleeping = false;
      body.restTime = 0;
    }
    this.awake = this.bodies.length;
  }

  /** 返回当前是否仍有活动体素，供渲染层跳过无效刷新。 */
  get active(): boolean {
    return this.awake > 0;
  }

  step(delta: number): void {
    if (!this.bodies.length) return;
    this.accumulator = Math.min(this.accumulator + Math.min(delta, 0.1), 0.2);
    while (this.accumulator >= this.fixedStep) {
      this.substep(this.fixedStep);
      this.accumulator -= this.fixedStep;
    }
  }

  private substep(dt: number): void {
    let awake = 0;
    for (const body of this.bodies) {
      if (body.sleeping) continue;

      body.velocity.y += this.gravity * dt;
      body.position.addScaledVector(body.velocity, dt);

      const angularSpeed = body.angular.length();
      if (angularSpeed > 1e-4) {
        this.axis.copy(body.angular).divideScalar(angularSpeed);
        this.spin.setFromAxisAngle(this.axis, angularSpeed * dt);
        body.quaternion.premultiply(this.spin).normalize();
      }

      const floor = this.groundY + body.half;
      if (body.position.y <= floor) {
        body.position.y = floor;
        if (body.velocity.y < 0) {
          body.velocity.y = -body.velocity.y * body.restitution;
        }
        // 地面摩擦与角速度衰减
        const damping = Math.pow(1 - body.friction, dt * 10);
        body.velocity.x *= damping;
        body.velocity.z *= damping;
        body.angular.multiplyScalar(Math.pow(0.02, dt));
        if (Math.abs(body.velocity.y) < 0.45) body.velocity.y = 0;
        // 姿态回正到最近的 90° 倍数，避免方块以角尖悬停
        if (body.velocity.lengthSq() < 0.08 && body.angular.lengthSq() < 0.2) {
          body.velocity.x = 0;
          body.velocity.z = 0;
          body.angular.set(0, 0, 0);
          this.settleRotation(body);
        }
      }

      const moving =
        body.velocity.lengthSq() > 0.0025 || body.angular.lengthSq() > 0.01;
      if (moving) {
        body.restTime = 0;
      } else {
        body.restTime += dt;
        if (body.restTime > 0.3) body.sleeping = true;
      }
      if (!body.sleeping) awake += 1;
    }
    this.awake = awake;
  }

  /** 把接近地面的体素旋转吸附到 90° 栅格，崩塌结束后堆叠更整齐。 */
  private settleRotation(body: VoxelBody): void {
    if (body.position.y > this.groundY + body.half + 0.01) return;
    const quaternion = body.quaternion;
    const up = UP.clone().applyQuaternion(quaternion);
    const dot = up.dot(UP);
    if (dot < 0.92) return;
    body.quaternion.identity();
  }
}

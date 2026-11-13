/**
 * 动态水面材质。
 *
 * 磨坊水渠/轮坑里的水在 GLB 中只是一张平面网格（材质名 FB_water），
 * 这里把它替换成程序化水面着色器：
 * - 两层不同速度的噪声滚动形成流动波纹，法线由高度场求导得到；
 * - 菲涅耳混合深/浅水色与天空色，低角度更亮；
 * - 沿太阳方向的高光与细碎波光，避免“塑料片”观感；
 * - 顺流方向拉长的泡沫条纹。
 *
 * 不依赖任何贴图，所有参数通过 uniforms 暴露，便于后续接面板。
 */

import * as THREE from "three";

export interface WaterUniforms {
  uTime: { value: number };
  uSunDir: { value: THREE.Vector3 };
  uSunColor: { value: THREE.Color };
  uSkyColor: { value: THREE.Color };
  uDeepColor: { value: THREE.Color };
  uShallowColor: { value: THREE.Color };
  uOpacity: { value: number };
  uFlow: { value: number };
}

export function createWaterUniforms(): WaterUniforms {
  return {
    uTime: { value: 0 },
    uSunDir: { value: new THREE.Vector3(0.4, 0.8, 0.3).normalize() },
    uSunColor: { value: new THREE.Color("#fff2d8") },
    uSkyColor: { value: new THREE.Color("#bcd6e8") },
    uDeepColor: { value: new THREE.Color("#0b2f35") },
    uShallowColor: { value: new THREE.Color("#2f7f7a") },
    uOpacity: { value: 0.82 },
    uFlow: { value: 0.85 },
  };
}

const vertexShader = /* glsl */ `
  varying vec3 vFbWaterPos;
  varying vec3 vFbWaterNormal;

  void main() {
    vec4 world = modelMatrix * vec4( position, 1.0 );
    vFbWaterPos = world.xyz;
    vFbWaterNormal = normalize( mat3( modelMatrix ) * normal );
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform vec3 uSunDir;
  uniform vec3 uSunColor;
  uniform vec3 uSkyColor;
  uniform vec3 uDeepColor;
  uniform vec3 uShallowColor;
  uniform float uOpacity;
  uniform float uFlow;

  varying vec3 vFbWaterPos;
  varying vec3 vFbWaterNormal;

  float fbHash( vec2 p ) {
    return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 );
  }

  float fbNoise( vec2 p ) {
    vec2 i = floor( p );
    vec2 f = fract( p );
    f = f * f * ( 3.0 - 2.0 * f );
    float a = fbHash( i );
    float b = fbHash( i + vec2( 1.0, 0.0 ) );
    float c = fbHash( i + vec2( 0.0, 1.0 ) );
    float d = fbHash( i + vec2( 1.0, 1.0 ) );
    return mix( mix( a, b, f.x ), mix( c, d, f.x ), f.y );
  }

  float fbFbm( vec2 p ) {
    float value = 0.0;
    float amplitude = 0.5;
    for ( int i = 0; i < 4; i ++ ) {
      value += amplitude * fbNoise( p );
      p *= 2.03;
      amplitude *= 0.5;
    }
    return value;
  }

  // 水面高度场：多向正弦波 + 低频噪声，梯度用来求法线
  float fbWave( vec2 p, float t ) {
    float s1 = sin( p.x * 2.6 + t * 1.9 + fbNoise( p * 0.6 ) * 2.4 );
    float s2 = sin( p.y * 3.4 - t * 1.45 + fbNoise( p * 0.8 + 11.0 ) * 1.8 );
    float s3 = sin( ( p.x + p.y ) * 1.5 + t * 1.05 );
    float noise = fbFbm( p * 1.6 + vec2( t * 0.5, -t * 0.35 ) );
    return s1 * 0.34 + s2 * 0.26 + s3 * 0.2 + noise * 0.55;
  }

  void main() {
    vec3 viewDir = normalize( cameraPosition - vFbWaterPos );
    vec2 p = vFbWaterPos.xz;
    float t = uTime * uFlow;

    // 用有限差分求水面法线，获得随流变化的细微波纹
    vec2 eps = vec2( 0.06, 0.0 );
    float h0 = fbWave( p, t );
    float hx = fbWave( p + eps.xy, t );
    float hz = fbWave( p + eps.yx, t );
    vec3 normal = normalize( vec3( ( hx - h0 ) * 3.2, 1.0, ( hz - h0 ) * 3.2 ) );

    vec3 halfDir = normalize( uSunDir + viewDir );
    float spec = pow( max( dot( normal, halfDir ), 0.0 ), 240.0 );
    float sparkle = pow( max( dot( normal, halfDir ), 0.0 ), 28.0 ) * 0.22;
    float fresnel = pow( 1.0 - clamp( dot( normal, viewDir ), 0.0, 1.0 ), 5.0 );

    // 顺流拉长的泡沫条纹 + 波纹亮带
    float foamField = fbFbm( p * vec2( 2.8, 1.35 ) + vec2( t * 1.3, 0.0 ) );
    float foam = smoothstep( 0.62, 0.88, foamField ) * smoothstep( 0.15, 0.85, h0 ) * 0.45;
    float ripple = smoothstep( 0.55, 1.0, h0 * 0.5 + 0.5 ) * 0.06;

    vec3 color = mix( uDeepColor, uShallowColor, 0.25 + 0.5 * ( h0 * 0.5 + 0.5 ) );
    color += vec3( 0.05, 0.14, 0.13 ) * ripple;
    color += uSkyColor * fresnel * 0.3;
    color += uSunColor * ( spec * 2.2 + sparkle );
    float streak = smoothstep( 0.45, 0.95, sin( p.x * 5.2 - t * 2.2 + h0 * 3.6 ) * 0.5 + 0.5 ) * 0.07;
    color += uSkyColor * streak;
    color = mix( color, vec3( 0.9, 0.95, 1.0 ), foam );

    float alpha = clamp( uOpacity + fresnel * 0.18 + spec * 0.5 + foam * 0.15, 0.0, 1.0 );
    gl_FragColor = vec4( color, alpha );

    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export function createWaterMaterial(uniforms: WaterUniforms): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTime: uniforms.uTime,
      uSunDir: uniforms.uSunDir,
      uSunColor: uniforms.uSunColor,
      uSkyColor: uniforms.uSkyColor,
      uDeepColor: uniforms.uDeepColor,
      uShallowColor: uniforms.uShallowColor,
      uOpacity: uniforms.uOpacity,
      uFlow: uniforms.uFlow,
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: true,
    side: THREE.DoubleSide,
  });
}

/** 判断材质是否为生成器写出的水材质（FB_water / water）。 */
export function isWaterMaterial(material: THREE.Material | THREE.Material[] | undefined): boolean {
  const list = Array.isArray(material) ? material : material ? [material] : [];
  return list.some((item) => {
    const name = item.name || "";
    return /fb_water|(^|_)water($|_)/i.test(name);
  });
}

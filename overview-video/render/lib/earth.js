// Photoreal Earth seen from low orbit (three.js). Textures: Solar System Scope, CC BY 4.0 (based on NASA data).
import * as THREE from 'three';

const R = 6371; // km
const TEX = '/assets/textures/';

const earthVert = `
varying vec2 vUv; varying vec3 vN; varying vec3 vW;
void main() {
  vUv = uv; vN = normalize(mat3(modelMatrix) * normal);
  vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;
const earthFrag = `
uniform sampler2D dayMap, nightMap, cloudMap, specMap; uniform vec3 sunDir; uniform float cloudShift, nightBoost;
varying vec2 vUv; varying vec3 vN; varying vec3 vW;
void main() {
  vec3 N = normalize(vN); vec3 V = normalize(cameraPosition - vW);
  float ndl = dot(N, sunDir);
  vec3 day = texture2D(dayMap, vUv).rgb;
  float cl = texture2D(cloudMap, vUv + vec2(cloudShift, 0.0)).r;
  vec3 dayCol = mix(day, vec3(0.97, 0.98, 1.0), clamp(cl * 1.05 - 0.05, 0.0, 1.0) * 0.85);
  float lit = clamp(ndl, 0.0, 1.0);
  vec3 col = dayCol * (0.02 + lit * 1.15);
  float spec = texture2D(specMap, vUv).r * (1.0 - cl);
  vec3 H = normalize(sunDir + V);
  col += vec3(1.0, 0.92, 0.8) * pow(max(dot(N, H), 0.0), 60.0) * spec * 0.55 * lit;
  vec3 night = texture2D(nightMap, vUv).rgb * (1.0 - cl * 0.8);
  col += night * nightBoost * (1.0 - smoothstep(-0.12, 0.12, ndl));
  // atmospheric scattering toward the limb (blue haze, warm at terminator)
  float fres = pow(1.0 - max(dot(N, V), 0.0), 2.2);
  vec3 haze = mix(vec3(1.0, 0.55, 0.3), vec3(0.35, 0.6, 1.0), smoothstep(-0.05, 0.35, ndl));
  col = mix(col, haze * (0.25 + lit), fres * 0.75 * smoothstep(-0.25, 0.2, ndl));
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}`;
const atmoVert = `
varying vec3 vN; varying vec3 vW;
void main() { vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const atmoFrag = `
uniform vec3 sunDir; uniform float uR; varying vec3 vN; varying vec3 vW;
void main() {
  vec3 dir = normalize(vW - cameraPosition);
  float tc = -dot(cameraPosition, dir);
  vec3 closest = cameraPosition + dir * max(tc, 0.0);
  float hgt = length(closest) - uR;                 // lowest altitude of the view ray (km)
  float g = exp(-max(hgt, 0.0) / 9.0) * 1.35 + exp(-max(hgt, 0.0) / 30.0) * 0.35;
  float s = smoothstep(-0.25, 0.35, dot(normalize(closest), sunDir));
  vec3 c = mix(vec3(1.0, 0.45, 0.2), vec3(0.32, 0.6, 1.0), s);
  float a = clamp(g * (0.08 + s), 0.0, 1.0);
  gl_FragColor = vec4(c * a, a);
  #include <colorspace_fragment>
}`;

function dirLatLon(lat, lon) {
  const a = THREE.MathUtils.degToRad(lat), b = THREE.MathUtils.degToRad(lon);
  return new THREE.Vector3(Math.cos(a) * Math.cos(b), Math.sin(a), -Math.cos(a) * Math.sin(b));
}

export async function createEarth(width = 1920, height = 1080) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, alpha: true });
  renderer.setSize(width, height, false);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 5, 4e6);
  const loader = new THREE.TextureLoader();
  const load = (f, srgb = true) => new Promise((res, rej) => loader.load(TEX + f, t => { if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); res(t); }, undefined, rej));
  const [day, night, clouds, spec, stars] = await Promise.all([
    load('8k_earth_daymap.jpg'), load('8k_earth_nightmap.jpg'), load('8k_earth_clouds.jpg', false), load('8k_earth_specular_map.jpg', false), load('8k_stars_milky_way.jpg')]);
  stars.colorSpace = THREE.SRGBColorSpace;
  clouds.wrapS = THREE.RepeatWrapping;
  const uniforms = { dayMap: { value: day }, nightMap: { value: night }, cloudMap: { value: clouds }, specMap: { value: spec },
    sunDir: { value: new THREE.Vector3(1, 0, 0) }, cloudShift: { value: 0 }, nightBoost: { value: 1.3 } };
  const earth = new THREE.Mesh(new THREE.SphereGeometry(R, 512, 256), new THREE.ShaderMaterial({ uniforms, vertexShader: earthVert, fragmentShader: earthFrag }));
  scene.add(earth);
  const atmoU = { sunDir: uniforms.sunDir, uR: { value: R } };
  const atmo = new THREE.Mesh(new THREE.SphereGeometry(R + 90, 256, 128), new THREE.ShaderMaterial({ uniforms: atmoU, vertexShader: atmoVert, fragmentShader: atmoFrag, side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(atmo);
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1.5e6, 64, 32), new THREE.MeshBasicMaterial({ map: stars, side: THREE.BackSide, color: new THREE.Color(0.55, 0.55, 0.6), depthWrite: false, depthTest: false }));
  sky.renderOrder = -1;
  scene.add(sky);
  // sun: additive sprite placed far away along sunDir so the Earth occludes it correctly
  const sunTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
    const r = g.createRadialGradient(256, 256, 0, 256, 256, 256);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.04, 'rgba(255,250,235,1)'); r.addColorStop(0.1, 'rgba(255,220,170,0.55)'); r.addColorStop(0.35, 'rgba(255,170,110,0.12)'); r.addColorStop(1, 'rgba(255,150,90,0)');
    g.fillStyle = r; g.fillRect(0, 0, 512, 512);
    g.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 12; k++) { g.save(); g.translate(256, 256); g.rotate(k * Math.PI / 6 + 0.2); const lg = g.createLinearGradient(0, 0, 250, 0); lg.addColorStop(0, 'rgba(255,240,220,0.5)'); lg.addColorStop(1, 'rgba(255,240,220,0)'); g.fillStyle = lg; g.fillRect(0, -1.5, 250, 3); g.restore(); }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
  const sun = new THREE.Sprite(new THREE.SpriteMaterial({ map: sunTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  sun.scale.setScalar(2.2e5); scene.add(sun);

  // view: lat/lon of the point below the camera, altitude (km), heading (deg, 0 = north, 90 = east),
  // pitch (deg below the local horizontal), sun: {az, el} relative to heading (deg)
  function render(v) {
    const up = dirLatLon(v.lat, v.lon);
    const pos = up.clone().multiplyScalar(R + v.alt);
    const north0 = new THREE.Vector3(0, 1, 0);
    const east = new THREE.Vector3().crossVectors(north0, up).normalize();
    const north = new THREE.Vector3().crossVectors(up, east).normalize();
    const h = THREE.MathUtils.degToRad(v.heading);
    const fwd = north.clone().multiplyScalar(Math.cos(h)).add(east.clone().multiplyScalar(Math.sin(h)));
    const right = new THREE.Vector3().crossVectors(fwd, up).normalize();
    const p = THREE.MathUtils.degToRad(v.pitch);
    const look = fwd.clone().multiplyScalar(Math.cos(p)).add(up.clone().multiplyScalar(-Math.sin(p)));
    camera.fov = v.fov || 45; camera.updateProjectionMatrix();
    camera.position.copy(pos); camera.up.copy(Math.abs(v.pitch) > 85 ? fwd : up);
    camera.lookAt(pos.clone().add(look));
    const az = THREE.MathUtils.degToRad(v.sun.az), el = THREE.MathUtils.degToRad(v.sun.el);
    uniforms.sunDir.value.copy(fwd.clone().multiplyScalar(Math.cos(el) * Math.cos(az)).add(right.clone().multiplyScalar(Math.cos(el) * Math.sin(az))).add(up.clone().multiplyScalar(Math.sin(el)))).normalize();
    sun.position.copy(camera.position).add(uniforms.sunDir.value.clone().multiplyScalar(1.2e6));
    sun.visible = v.sunVisible !== false; sun.material.opacity = v.sunLevel ?? 1;
    uniforms.cloudShift.value = v.cloudShift || 0;
    uniforms.nightBoost.value = v.nightBoost ?? 1.3;
    sky.material.color.setScalar(v.starLevel ?? 0.55);
    renderer.render(scene, camera);
    return renderer.domElement;
  }
  return { render, renderer };
}

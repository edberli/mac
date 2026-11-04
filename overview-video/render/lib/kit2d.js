// 2D cinematic-silhouette kit: characters, landmarks, Paris rooftops, effects, captions.
let ctx = null;
export const W = 1920, H = 1080;
export function bind(c) { ctx = c; }

// ---------------- utils ----------------
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
export const easeInOut = x => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
export function rng(seed) { seed = Math.max(1, Math.floor(seed)) % 2147483647; return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }
export function hexA(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
export function mix(h1, h2, t) { const p = c => c[0] === '#' ? parseInt(c.slice(1), 16) : (([r, g, b]) => (r << 16) | (g << 8) | b)(c.match(/\d+/g).map(Number));
  const a = p(h1), b = p(h2);
  const r = Math.round(lerp(a >> 16, b >> 16, t)), g = Math.round(lerp((a >> 8) & 255, (b >> 8) & 255, t)), bl = Math.round(lerp(a & 255, b & 255, t));
  return '#' + [r, g, bl].map(v => v.toString(16).padStart(2, '0')).join(''); }
export function rrect(c, x, y, w, h, r) { c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
export function offscreen(w, h, draw) { const o = document.createElement('canvas'); o.width = w; o.height = h; draw(o.getContext('2d'), o); return o; }
export function push(t0, t1, t, s0, s1, cx, cy) { const s = lerp(s0, s1, smooth(t0, t1, t)); ctx.translate(cx, cy); ctx.scale(s, s); ctx.translate(-cx, -cy); }
export function talkAt(TL, sp, f) { const e = TL.env[sp]; return e ? (e[Math.min(f, e.length - 1)] || 0) : 0; }

// ---------------- film finish ----------------
const noise = offscreen(512, 512, (n) => { const im = n.createImageData(512, 512), r = rng(3);
  for (let i = 0; i < im.data.length; i += 4) { const v = r() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; } n.putImageData(im, 0, 0); });
export function grain(alpha, f) { const r = rng(1000 + f); ctx.save(); ctx.globalAlpha = alpha; ctx.globalCompositeOperation = 'overlay';
  const ox = -r() * 512, oy = -r() * 512; for (let x = ox; x < W; x += 512) for (let y = oy; y < H; y += 512) ctx.drawImage(noise, x, y); ctx.restore(); }
export function vignette(a) { const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${a})`); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
export function bloomSun(x, y, r, inner, mid, a = 1) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, hexA(inner, 0.9 * a)); g.addColorStop(0.07, hexA(inner, 0.55 * a)); g.addColorStop(0.35, hexA(mid, 0.16 * a)); g.addColorStop(1, hexA(mid, 0));
  ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2); ctx.restore();
}
export function sunsetSky(stops) { const g = ctx.createLinearGradient(0, 0, 0, H); stops.forEach(([o, c]) => g.addColorStop(o, c)); ctx.fillStyle = g; ctx.fillRect(-200, -200, W + 400, H + 400); }
const STARS = (() => { const r = rng(5); return Array.from({ length: 420 }, () => [r() * W, r() * H, Math.pow(r(), 3) * 1.8 + 0.4, r() * 6]); })();
export function stars(a, t, maxY = H) { if (a <= 0) return; for (const [x, y, r, ph] of STARS) if (y < maxY) { ctx.fillStyle = `rgba(255,255,255,${a * (0.35 + 0.3 * Math.sin(t * 2 + ph)) * (1 - y / maxY)})`; ctx.fillRect(x, y, r, r); } }
const DUST = (() => { const r = rng(9); return Array.from({ length: 50 }, () => [r() * W, r() * H, r() * 2 + 0.6, r() * 6, r() * 0.5 + 0.2]); })();
export function dust(t, col = '255,200,150') { ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const [x, y, r, ph, sp] of DUST) { const yy = (y - t * 12 * sp + H) % H; ctx.fillStyle = `rgba(${col},${0.2 + 0.15 * Math.sin(t + ph)})`; ctx.beginPath(); ctx.arc(x + Math.sin(t * 0.5 + ph) * 10, yy, r, 0, Math.PI * 2); ctx.fill(); } ctx.restore(); }

// ---------------- human: side profile, facing right; origin = hip on the seat ----------------
// Built from separate pieces (legs, torso, head, near arm) so the arm can be posed with simple IK.
const ARM = { upper: 70, fore: 62 };
function torsoAngle(t, lean) { return 0.06 + lean * 0.22 + Math.sin(t * 1.6) * 0.006; }
function rot([x, y], a) { return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)]; }
function taper(c, ax, ay, ar, bx, by, br) {   // tapered capsule from A (radius ar) to B (radius br)
  const d = Math.hypot(bx - ax, by - ay), ang = Math.atan2(by - ay, bx - ax), off = Math.asin(clamp((ar - br) / d, -1, 1));
  c.moveTo(ax + Math.cos(ang + Math.PI / 2 + off) * ar, ay + Math.sin(ang + Math.PI / 2 + off) * ar);
  c.arc(ax, ay, ar, ang + Math.PI / 2 + off, ang - Math.PI / 2 - off);
  c.arc(bx, by, br, ang - Math.PI / 2 - off, ang + Math.PI / 2 + off);
  c.closePath();
}
function legsPath(c, t) {
  c.beginPath();
  c.moveTo(-34, 6); c.bezierCurveTo(-30, -24, 20, -26, 60, -22);              // top of thigh
  c.bezierCurveTo(92, -20, 114, -18, 118, 0); c.bezierCurveTo(120, 14, 106, 20, 92, 21);
  c.bezierCurveTo(40, 24, -10, 24, -30, 22); c.closePath(); c.fill(); c.beginPath(); 
  const sw = Math.sin(t * 1.1) * 0.03;
  c.save(); c.translate(104, 6); c.rotate(sw);
  c.moveTo(-15, -6); c.bezierCurveTo(-12, 40, -5, 80, -1, 104); c.lineTo(21, 104);
  c.bezierCurveTo(20, 76, 22, 36, 16, -4); c.closePath(); c.fill(); c.beginPath(); 
  c.moveTo(-6, 100); c.bezierCurveTo(-8, 116, 0, 122, 20, 122); c.lineTo(48, 122);   // sneaker
  c.bezierCurveTo(58, 122, 58, 112, 48, 108); c.bezierCurveTo(36, 104, 28, 98, 22, 96); c.closePath();
  c.restore();
}
function torsoPath(c, t, talk, lean, look) {
  c.save(); c.rotate(torsoAngle(t, lean));
  c.beginPath();
  c.moveTo(-34, 6);
  c.bezierCurveTo(-44, -40, -44, -96, -30, -128);
  c.bezierCurveTo(-22, -146, -8, -158, 6, -160);
  c.bezierCurveTo(22, -160, 34, -150, 38, -134);
  c.bezierCurveTo(44, -104, 44, -60, 38, -26);
  c.lineTo(36, 4); c.closePath(); c.fill(); c.beginPath(); 
  c.moveTo(-26, -136); c.bezierCurveTo(-34, -152, -20, -168, -4, -166); c.lineTo(6, -150); c.closePath(); c.fill(); c.beginPath();   // hood fold
  c.save(); c.translate(10, -160); c.rotate(look * 0.25 + talk * 0.03 * Math.sin(t * 9));
  c.moveTo(-10, 2);
  c.bezierCurveTo(-30, -10, -36, -46, -20, -70);
  c.bezierCurveTo(-6, -90, 30, -94, 46, -76);
  c.bezierCurveTo(52, -68, 53, -58, 51, -52);
  c.bezierCurveTo(54, -46, 60, -40, 62, -36);
  c.lineTo(55, -32); c.lineTo(56, -28); c.lineTo(53, -25); c.lineTo(55, -21);
  c.bezierCurveTo(54, -14, 50, -9, 43, -8);
  c.bezierCurveTo(34, -7, 26, -4, 22, 4);
  c.lineTo(20, 14); c.lineTo(-6, 14); c.closePath(); c.fill(); c.beginPath(); 
  // hair: cap over the skull with a soft fringe and a few tufts (stays above the ear)
  c.moveTo(-30, -44); c.bezierCurveTo(-36, -66, -26, -88, -4, -96);
  c.lineTo(4, -99); c.lineTo(10, -97); c.lineTo(17, -100); c.lineTo(23, -97);
  c.bezierCurveTo(38, -96, 52, -86, 54, -72);
  c.bezierCurveTo(50, -70, 46, -66, 44, -60); c.lineTo(40, -68);
  c.bezierCurveTo(28, -78, 6, -78, -10, -66); c.bezierCurveTo(-18, -58, -22, -50, -24, -40); c.closePath();
  c.restore();
  c.restore();
}
// near arm: shoulder follows the torso, hand stays on the knee; elbow solved with 2-bone IK
function armPath(c, t, lean, hand) {
  const [sx, sy] = rot([6, -132], torsoAngle(t, lean));
  const [hx, hy] = hand;
  const d = Math.min(Math.hypot(hx - sx, hy - sy), ARM.upper + ARM.fore - 1);
  const base = Math.atan2(hy - sy, hx - sx);
  const cosA = (ARM.upper * ARM.upper + d * d - ARM.fore * ARM.fore) / (2 * ARM.upper * d);
  const ea = base + Math.acos(clamp(cosA, -1, 1));            // elbow bends back/down
  const ex = sx + Math.cos(ea) * ARM.upper, ey = sy + Math.sin(ea) * ARM.upper;
  const fa = Math.atan2(hy - ey, hx - ex);
  c.beginPath();
  taper(c, sx, sy, 14, ex, ey, 10.5); c.fill(); c.beginPath(); // upper arm (hoodie sleeve)
  taper(c, ex, ey, 10.5, hx, hy, 7.5); c.fill(); c.beginPath(); // forearm
  // hand: palm + fingers draped over the knee, thumb on top
  c.save(); c.translate(hx, hy); c.rotate(fa + 0.5);
  c.moveTo(-2, -7); c.bezierCurveTo(6, -9, 16, -9, 22, -5);          // back of hand
  c.bezierCurveTo(28, -1, 31, 6, 28, 10);                           // fingertips curling over the knee
  c.bezierCurveTo(24, 12, 16, 9, 10, 8); c.lineTo(-2, 7); c.closePath(); c.fill(); c.beginPath(); 
  c.moveTo(14, -7); c.bezierCurveTo(18, -12, 24, -11, 25, -8); c.bezierCurveTo(22, -6, 18, -5, 14, -7); c.closePath();  // thumb
  c.restore();
}
const HS = 2, HOX = 80, HOY = 300;   // offscreen supersampling and origin
const hBody = offscreen(300 * HS, 460 * HS, () => {}), hArm = offscreen(300 * HS, 460 * HS, () => {}), hTint = offscreen(300 * HS, 460 * HS, () => {});
function maskTo(cv, draw) { const c = cv.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height);
  c.setTransform(HS, 0, 0, HS, HOX * HS, HOY * HS); c.fillStyle = '#000'; draw(c); }
function tinted(src, color) { const c = hTint.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over';
  c.clearRect(0, 0, hTint.width, hTint.height); c.drawImage(src, 0, 0); c.globalCompositeOperation = 'source-in'; c.fillStyle = color; c.fillRect(0, 0, hTint.width, hTint.height); c.globalCompositeOperation = 'source-over'; return hTint; }
function blit(cv, dx, dy) { ctx.drawImage(cv, -HOX + dx, -HOY + dy, cv.width / HS, cv.height / HS); }
export function drawHuman(x, y, t, talk, lean, look, rim, body = '#0b070c', hand = [84, -27]) {
  maskTo(hBody, c => { legsPath(c, t); c.fill(); torsoPath(c, t, talk, lean, look); c.fill(); armPath(c, t, lean, hand); c.fill(); });
  maskTo(hArm, c => { armPath(c, t, lean, hand); c.fill(); });
  ctx.save(); ctx.translate(x, y);
  blit(tinted(hBody, rim), 3, -2);        // rim light along the outer silhouette only
  blit(tinted(hBody, body), 0, 0);
  ctx.globalAlpha = 0.75; blit(tinted(hArm, rim), 1.8, -1.4); ctx.globalAlpha = 1;   // thin edge so the arm reads over the torso
  blit(tinted(hArm, body), 0, 0);
  ctx.restore();
}

// ---------------- AXIS ----------------
export const EYE = '#7ff3ff';
export function drawAxis(x, y, t, talk, p, look = -1, scale = 0.82) {
  ctx.save(); ctx.translate(x, y + Math.sin(t * 2) * 7); ctx.scale(scale, scale);
  const c = ctx, glow = p.glow || 0;
  c.save(); c.globalCompositeOperation = 'lighter';
  const g = c.createRadialGradient(0, 200, 0, 0, 200, 70 + glow * 40); g.addColorStop(0, hexA(p.eye, 0.5 + glow * 0.4)); g.addColorStop(1, hexA(p.eye, 0));
  c.fillStyle = g; c.beginPath(); c.ellipse(0, 200, 70 + glow * 40, 30 + glow * 10, 0, 0, Math.PI * 2); c.fill(); c.restore();
  const body = () => { c.beginPath();
    c.moveTo(-62, 70); c.quadraticCurveTo(-66, 62, -56, 60); c.lineTo(56, 60); c.quadraticCurveTo(66, 62, 62, 70);
    c.lineTo(32, 176); c.quadraticCurveTo(28, 184, 20, 184); c.lineTo(-20, 184); c.quadraticCurveTo(-28, 184, -32, 176); c.closePath();
    rrect(c, -66, -48, 132, 104, 46);
    for (const s of [-1, 1]) { const hy = 112 + Math.sin(t * 2 + s) * 5; rrect(c, s * 96 - 13, hy - 24, 26, 48, 13); } };
  // orbit ring around the head: back half first (hidden by the head), front half after the face
  const ra = t * (p.ringSpeed || 0.9), RX = 106, RY = 24, RCY = 4, RROT = -0.16;
  const ringArc = (from, to) => { c.save(); c.translate(0, RCY); c.rotate(RROT); c.strokeStyle = hexA(p.eye, 0.55 + glow * 0.4); c.lineWidth = 2.2 + glow * 1.5;
    c.shadowColor = p.eye; c.shadowBlur = 8; c.beginPath(); c.ellipse(0, 0, RX, RY, 0, from, to); c.stroke(); c.restore(); };
  const ringDot = () => { c.save(); c.translate(0, RCY); c.rotate(RROT); c.shadowColor = p.eye; c.shadowBlur = 16; c.fillStyle = p.eye; c.beginPath(); c.arc(Math.cos(ra) * RX, Math.sin(ra) * RY, 5, 0, Math.PI * 2); c.fill(); c.restore(); };
  const dotFront = Math.sin(ra) > 0;
  ringArc(Math.PI, Math.PI * 2); if (!dotFront) ringDot();
  c.save(); c.translate(p.rimDx, p.rimDy); body(); c.fillStyle = p.rim; c.fill(); c.restore();
  body(); c.fillStyle = p.body; c.fill();
  c.save(); body(); c.clip(); const sg = c.createLinearGradient(-70, 0, 70, 0); sg.addColorStop(0, 'rgba(0,0,0,0.35)'); sg.addColorStop(1, 'rgba(255,255,255,0.03)'); c.fillStyle = sg; c.fillRect(-120, -60, 240, 260); c.restore();
  c.beginPath(); rrect(c, -52, -20, 104, 42, 21); c.fillStyle = '#04050a'; c.fill();
  c.save(); c.shadowColor = p.eye; c.shadowBlur = 14 + talk * 18 + glow * 20; c.fillStyle = p.eye; c.globalAlpha = Math.min(1, 0.75 + talk * 0.25 + glow * 0.3);
  const bp = (t % 3.7), bl = bp < 0.14 ? 1 - Math.abs(bp - 0.07) / 0.07 : 0, eh = Math.max(7 * (1 - bl), 1.5);
  for (const s of [-1, 1]) { c.beginPath(); rrect(c, s * 22 - 13 + look * 6, 1 - eh / 2, 26, eh, eh / 2); c.fill(); }
  c.restore();
  c.save(); c.shadowColor = p.eye; c.shadowBlur = 18 + glow * 20; c.fillStyle = p.eye; c.globalAlpha = Math.min(1, 0.45 + 0.55 * talk + glow); c.beginPath(); c.arc(0, 108, 9, 0, Math.PI * 2); c.fill(); c.restore();
  ringArc(0, Math.PI); if (dotFront) ringDot();
  ctx.restore();
}

// ---------------- platform, particles, speed lines, clouds ----------------
export function platform(x, y, a, t) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a; ctx.globalCompositeOperation = 'lighter';
  ctx.strokeStyle = 'rgba(127,243,255,0.75)'; ctx.lineWidth = 1.6; ctx.shadowColor = EYE; ctx.shadowBlur = 10;
  ctx.beginPath(); ctx.ellipse(x, y, 220, 28, 0, 0, Math.PI * 2); ctx.stroke();
  ctx.shadowBlur = 0; ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(127,243,255,0.16)';
  ctx.beginPath(); ctx.ellipse(x, y, 165, 21, 0, 0, Math.PI * 2); ctx.stroke();
  // rotating tick marks on the rim
  ctx.strokeStyle = 'rgba(127,243,255,0.6)'; ctx.lineWidth = 2;
  for (let k = 0; k < 24; k++) { const a2 = k / 24 * Math.PI * 2 + t * 0.6; ctx.beginPath(); ctx.ellipse(x, y, 220, 28, 0, a2, a2 + 0.06); ctx.stroke(); }
  ctx.restore();
}
const PARTS = (() => { const r = rng(31); return Array.from({ length: 90 }, () => [r() * Math.PI * 2, 200 + r() * 500, r() * 0.5]); })();
export function convergeParticles(cx, cy, t, t0, t1) {
  if (t < t0 || t > t1 + 0.3) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const [ang, dist, delay] of PARTS) {
    const k = smooth(t0 + delay * (t1 - t0) * 0.6, t1, t);
    const tx = cx + Math.cos(ang) * 220, ty = cy + Math.sin(ang) * 28;
    const sx = cx + Math.cos(ang) * dist, sy = cy - 120 + Math.sin(ang) * dist * 0.5;
    const x = lerp(sx, tx, easeInOut(k)), y = lerp(sy, ty, easeInOut(k));
    ctx.fillStyle = `rgba(127,243,255,${0.8 * (1 - smooth(t1, t1 + 0.3, t)) * smooth(0, 0.15, k)})`;
    ctx.beginPath(); ctx.arc(x, y, 2.2, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}
const STREAKS = (() => { const r = rng(44); return Array.from({ length: 70 }, () => [r() * W, r() * H * 2, 60 + r() * 220, r()]); })();
export function speedLines(t, a) {
  if (a <= 0.01) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const [x, y0, len, ph] of STREAKS) { const y = ((y0 + t * 2600) % (H * 2)) - H * 0.5;
    const g = ctx.createLinearGradient(x, y, x, y + len); g.addColorStop(0, 'rgba(200,225,255,0)'); g.addColorStop(1, `rgba(200,225,255,${0.35 * a * (0.4 + ph * 0.6)})`);
    ctx.fillStyle = g; ctx.fillRect(x, y, 1.6, len); }
  ctx.restore();
}
const CLOUDS = (() => { const r = rng(55); return Array.from({ length: 26 }, () => [r() * W * 1.4 - 200, r() * 900, 180 + r() * 360, 30 + r() * 50, r()]); })();
export function riseClouds(u) {
  const band = smooth(0.12, 0.22, u) * (1 - smooth(0.36, 0.46, u)); if (band <= 0) return;
  const off = lerp(-1100, 2000, smooth(0.12, 0.46, u));
  ctx.save(); ctx.filter = 'blur(12px)';
  for (const [x, y, w, h] of CLOUDS) { const yy = y + off; if (yy < -200 || yy > H + 200) continue;
    ctx.fillStyle = `rgba(255,${Math.round(lerp(200, 170, u))},${Math.round(lerp(170, 200, u))},${0.4 * band})`; ctx.beginPath(); ctx.ellipse(x, yy, w, h, 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}

// ---------------- mountains + Great Wall ----------------
const R0 = rng(11);
const LAYERS = [470, 545, 620, 700, 775].map((base, i) => {
  const amp = [170, 160, 140, 115, 80][i];
  const comps = Array.from({ length: 3 }, (_, k) => ({ A: amp / (k + 1.3) * (0.7 + R0() * 0.6), f: (0.0018 + R0() * 0.0016) * (k + 1), p: R0() * 6.28 }));
  const pts = []; for (let x = -160; x <= W + 160; x += 8) { let h = 0; for (const c of comps) h += c.A * Math.pow(1 - Math.abs(Math.sin(c.f * x + c.p)), 1.6); pts.push([x, base - h + amp * 0.35]); }
  return { base, pts };
});
function ridgeY(L, x) { const i = clamp(Math.floor((x + 160) / 8), 0, L.pts.length - 2); const p = L.pts[i], q = L.pts[i + 1]; return lerp(p[1], q[1], (x - p[0]) / 8); }
const WALLS = [{ li: 2, x0: 150, x1: 1750, th: 7, towers: [380, 820, 1290, 1640] }, { li: 3, x0: -50, x1: 1500, th: 11, towers: [210, 640, 1080] }, { li: 4, x0: -100, x1: 2000, th: 18, towers: [520, 1460] }];
function wallOn(L, w, col, i) {
  const dark = mix(col, '#000000', 0.35);
  ctx.strokeStyle = dark; ctx.lineWidth = w.th; ctx.lineJoin = 'round'; ctx.beginPath(); for (let x = w.x0; x <= w.x1; x += 8) ctx.lineTo(x, ridgeY(L, x) + 2); ctx.stroke();
  ctx.fillStyle = dark; for (let x = w.x0; x <= w.x1; x += w.th * 1.6) ctx.fillRect(x, ridgeY(L, x) + 2 - w.th, w.th * 0.8, w.th * 0.8);
  for (const tx of w.towers) { const y = ridgeY(L, tx); ctx.fillRect(tx - w.th * 1.6, y - w.th * 3.2, w.th * 3.2, w.th * 3.6); }
  ctx.strokeStyle = `rgba(255,170,110,${0.55 - i * 0.08})`; ctx.lineWidth = 1.2; ctx.beginPath(); for (let x = w.x0; x <= w.x1; x += 8) ctx.lineTo(x, ridgeY(L, x) + 2 - w.th / 2); ctx.stroke();
}
export function sceneGreatWall(t, local, variant) {
  sunsetSky([[0, '#141a33'], [0.25, '#3b2a4f'], [0.45, '#a24e55'], [0.6, '#f08a4b'], [0.72, '#ffd08a'], [1, '#ffd08a']]);
  stars(0.5, t, 260);
  ctx.save();
  if (variant === 0) push(0, 2.2, local, 1.0, 1.07, 960, 600); else { ctx.translate(-260, -40); push(0, 3.2, local, 1.25, 1.33, 1220, 640); }
  bloomSun(1420, 600, 560, '#fff0c8', '#ff7a46');
  ctx.fillStyle = '#fff3d6'; ctx.beginPath(); ctx.arc(1420, 600, 34, 0, Math.PI * 2); ctx.fill();
  const cols = ['#d08a7c', '#a35e66', '#723b53', '#46223b', '#261324'];
  LAYERS.forEach((L, i) => {
    const hz = ctx.createLinearGradient(0, L.base - 260, 0, L.base + 40); hz.addColorStop(0, 'rgba(255,150,110,0)'); hz.addColorStop(1, `rgba(255,160,120,${0.22 - i * 0.03})`);
    ctx.fillStyle = hz; ctx.fillRect(-200, L.base - 260, W + 400, 300);
    ctx.beginPath(); ctx.moveTo(-160, H + 200); for (const [x, y] of L.pts) ctx.lineTo(x, y); ctx.lineTo(W + 160, H + 200); ctx.closePath();
    const lg = ctx.createLinearGradient(0, L.base - 180, 0, L.base + 220); lg.addColorStop(0, cols[i]); lg.addColorStop(1, mix(cols[i], '#0c0710', 0.55)); ctx.fillStyle = lg; ctx.fill();
    for (const w of WALLS) if (w.li === i) wallOn(L, w, cols[i], i);
  });
  dust(t); ctx.restore();
}

// ---------------- Statue of Liberty ----------------
function libertyPath(c) {
  c.beginPath();
  c.moveTo(-150, 0); c.lineTo(-150, -40); c.lineTo(-118, -40); c.lineTo(-118, -70); c.lineTo(-92, -70); c.lineTo(-92, -250); c.lineTo(-104, -250); c.lineTo(-104, -268);
  c.lineTo(104, -268); c.lineTo(104, -250); c.lineTo(92, -250); c.lineTo(92, -70); c.lineTo(118, -70); c.lineTo(118, -40); c.lineTo(150, -40); c.lineTo(150, 0); c.closePath();
  c.moveTo(-50, -268); c.bezierCurveTo(-52, -360, -44, -440, -36, -500); c.lineTo(-30, -512); c.lineTo(30, -512);
  c.bezierCurveTo(44, -470, 50, -380, 54, -268); c.closePath();
  c.moveTo(26, -500); c.lineTo(58, -470); c.lineTo(66, -400); c.lineTo(40, -392); c.lineTo(30, -440); c.closePath();
  c.moveTo(44, -470); c.lineTo(78, -462); c.lineTo(84, -390); c.lineTo(52, -384); c.closePath();
  c.moveTo(-34, -500); c.lineTo(-52, -640); c.lineTo(-38, -642); c.lineTo(-18, -506); c.closePath();
  c.moveTo(-62, -642); c.lineTo(-30, -642); c.lineTo(-38, -662); c.lineTo(-54, -662); c.closePath();
  c.moveTo(-46, -662); c.bezierCurveTo(-60, -676, -50, -694, -44, -704); c.bezierCurveTo(-40, -690, -30, -680, -46, -662); c.closePath();
  c.moveTo(-14, -512); c.lineTo(-14, -526); c.arc(0, -540, 17, Math.PI * 0.75, Math.PI * 2.25); c.lineTo(14, -512); c.closePath();
  for (let k = 0; k < 7; k++) { const a = -Math.PI * 0.85 + k * (Math.PI * 0.7 / 6); const bx = Math.cos(a) * 16, by = -548 + Math.sin(a) * 14;
    c.moveTo(bx - 3, by); c.lineTo(Math.cos(a) * 46, -548 + Math.sin(a) * 40); c.lineTo(bx + 3, by); c.closePath(); }
}
export function sceneLiberty(t, local) {
  sunsetSky([[0, '#1a1a38'], [0.3, '#4a2b52'], [0.55, '#c25a50'], [0.68, '#f39a55'], [0.72, '#ffd79a'], [1, '#3a1d2a']]);
  stars(0.4, t, 240);
  ctx.save(); push(0, 1.8, local, 1.0, 1.08, 1000, 600);
  bloomSun(1290, 770, 600, '#fff0c8', '#ff7a46');
  ctx.fillStyle = '#fff3d6'; ctx.beginPath(); ctx.arc(1290, 770, 40, 0, Math.PI * 2); ctx.fill();
  const r = rng(21); ctx.fillStyle = '#5a2c45';
  for (let x = -40; x < 900; x += 30 + r() * 30) { const h = 40 + r() * 120; ctx.fillRect(x, 778 - h, 26 + r() * 20, h); }
  const wg = ctx.createLinearGradient(0, 778, 0, H); wg.addColorStop(0, '#b45a52'); wg.addColorStop(1, '#1b0f1a'); ctx.fillStyle = wg; ctx.fillRect(-100, 778, W + 200, 400);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let k = 0; k < 26; k++) { const y = 790 + k * 10 + Math.sin(t * 2 + k) * 2, w = 180 - k * 5 + Math.sin(t * 3 + k * 1.7) * 30; ctx.fillStyle = `rgba(255,190,120,${0.35 - k * 0.012})`; ctx.fillRect(1290 - w / 2, y, w, 2); }
  ctx.restore();
  ctx.fillStyle = '#140a12'; ctx.beginPath(); ctx.moveTo(470, 782); ctx.bezierCurveTo(560, 760, 1080, 760, 1170, 782); ctx.lineTo(470, 782); ctx.fill();
  ctx.save(); ctx.translate(820, 776); ctx.scale(0.95, 0.95);
  ctx.save(); ctx.translate(3, -2); libertyPath(ctx); ctx.fillStyle = 'rgba(255,150,90,0.8)'; ctx.fill(); ctx.restore();
  libertyPath(ctx); ctx.fillStyle = '#140a12'; ctx.fill();
  ctx.restore();
  dust(t); ctx.restore();
}

// ---------------- Pyramids (on solid ground) ----------------
export function scenePyramids(t, local) {
  sunsetSky([[0, '#1d1a36'], [0.3, '#5a3550'], [0.55, '#d8704a'], [0.68, '#ffb066'], [0.72, '#ffe0a0'], [1, '#2a1612']]);
  stars(0.35, t, 220);
  ctx.save(); push(0, 2.3, local, 1.07, 1.0, 960, 700);
  bloomSun(1060, 740, 620, '#fff0c8', '#ff8a46');
  ctx.fillStyle = '#fff3d6'; ctx.beginPath(); ctx.arc(1060, 742, 44, 0, Math.PI * 2); ctx.fill();
  // desert floor reaching the horizon so nothing floats
  const gg = ctx.createLinearGradient(0, 776, 0, H); gg.addColorStop(0, '#6a3a2c'); gg.addColorStop(0.15, '#3a2018'); gg.addColorStop(1, '#120909');
  ctx.fillStyle = gg; ctx.fillRect(-200, 776, W + 400, 500);
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = 'rgba(255,190,120,0.35)'; ctx.fillRect(-200, 775, W + 400, 2); ctx.restore();
  const pyr = (cx, w, h, fill, rim) => { const by = 784; ctx.beginPath(); ctx.moveTo(cx - w / 2, by); ctx.lineTo(cx, by - h); ctx.lineTo(cx + w / 2, by); ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
    ctx.beginPath(); ctx.moveTo(cx, by - h); ctx.lineTo(cx + w / 2, by); ctx.lineTo(cx + w * 0.12, by); ctx.closePath(); ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.fill();
    ctx.strokeStyle = rim; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx - w / 2, by); ctx.lineTo(cx, by - h); ctx.stroke(); };
  pyr(1520, 300, 172, '#6b3a3a', 'rgba(255,170,110,0.5)');
  pyr(1250, 560, 344, '#4a2730', 'rgba(255,170,110,0.6)');
  pyr(720, 700, 424, '#2c171f', 'rgba(255,170,110,0.7)');
  const dune = x => 812 + Math.sin(x * 0.004) * 16 + Math.sin(x * 0.011 + 1) * 8;
  ctx.fillStyle = '#1a0e12'; ctx.beginPath(); ctx.moveTo(-200, H + 50);
  for (let x = -200; x <= W + 200; x += 20) ctx.lineTo(x, dune(x)); ctx.lineTo(W + 200, H + 50); ctx.fill();
  ctx.strokeStyle = 'rgba(255,170,110,0.35)'; ctx.lineWidth = 1.5; ctx.beginPath(); for (let x = -200; x <= W + 200; x += 20) ctx.lineTo(x, dune(x)); ctx.stroke();
  dust(t); ctx.restore();
}

// ---------------- Paris ----------------
const EIFFEL = offscreen(420, 820, (c) => {
  c.translate(210, 800); c.fillStyle = '#000';
  const prof = y => { const h = -y; if (h < 150) return 200 - h * 0.62; if (h < 330) return 107 - (h - 150) * 0.28; return Math.max(56 * Math.pow(1 - (h - 330) / 420, 1.6), 5); };
  c.beginPath(); c.moveTo(-prof(0), 0);
  for (let y = 0; y >= -750; y -= 6) c.lineTo(-prof(y), y);
  c.lineTo(-3, -790); c.lineTo(3, -790);
  for (let y = -750; y <= 0; y += 6) c.lineTo(prof(y), y);
  c.closePath(); c.fill();
  c.fillRect(-122, -158, 244, 16); c.fillRect(-64, -338, 128, 12); c.fillRect(-16, -700, 32, 18);
  c.globalCompositeOperation = 'destination-out';
  c.beginPath(); c.moveTo(-150, 2); c.bezierCurveTo(-120, -120, 120, -120, 150, 2); c.closePath(); c.fill();
  c.beginPath(); c.moveTo(-82, -170); c.bezierCurveTo(-60, -260, 60, -260, 82, -170); c.closePath(); c.fill();
  c.lineWidth = 1.1;
  for (let y = -170; y > -690; y -= 34) { const w = prof(y) - 8; c.beginPath(); c.moveTo(-w, y); c.lineTo(w * 0.1, y - 22); c.moveTo(w, y); c.lineTo(-w * 0.1, y - 22); c.stroke(); }
});
const EIFFEL_T = offscreen(420, 820, (c) => { c.drawImage(EIFFEL, 0, 0); c.globalCompositeOperation = 'source-in'; c.fillStyle = '#5a2a43'; c.fillRect(0, 0, 420, 820); });
const PARIS = (() => { const r = rng(77); const rows = [];
  [[700, 0.55, 50, 90, 26], [742, 0.75, 70, 130, 38], [790, 1.0, 90, 170, 52]].forEach(([base, sc, minW, maxW, roof], ri) => {
    const b = []; for (let x = -100; x < W + 100;) { const w = minW + r() * (maxW - minW), h = (60 + r() * 70) * sc;
      const wins = []; for (let k = 0; k < 10; k++) if (r() < 0.35 - ri * 0.05) wins.push([r() * (w - 16) + 4, r() * (h - 14) + 6, r()]);
      const chim = []; const nc = Math.floor(r() * 3); for (let k = 0; k < nc; k++) chim.push([r() * (w - 20) + 4, 10 + r() * 14]);
      b.push({ x, w, h, roof: roof * (0.7 + r() * 0.5), wins, chim }); x += w + r() * 6; }
    rows.push({ base, b, ri }); });
  return rows; })();
export function sceneParis(t, local, u) {
  const uc = smooth(0, 0.45, u);
  sunsetSky([[0, mix('#151a36', '#000005', uc)], [0.3, mix('#3d2a52', '#02030c', uc)], [0.55, mix('#b8584f', '#050816', uc)], [0.66, mix('#f2934e', '#070d22', uc)], [0.72, mix('#ffd497', '#0a1430', uc)], [1, mix('#ffd497', '#0a1430', uc)]]);
  stars(0.35 + uc * 0.65, t, lerp(250, H, uc));
  ctx.save();
  const lift = Math.pow(u, 2.2) * 1900;
  push(0, 14, local, 1.0, 1.06, 900, 640);
  ctx.translate(0, lift);
  bloomSun(1180, 700, 640, '#fff0c8', '#ff7a46', 1 - uc * 0.6);
  ctx.fillStyle = '#fff3d6'; ctx.beginPath(); ctx.arc(1180, 702, 36, 0, Math.PI * 2); ctx.fill();
  const hz = ctx.createLinearGradient(0, 560, 0, 760); hz.addColorStop(0, 'rgba(255,150,110,0)'); hz.addColorStop(1, 'rgba(255,170,120,0.25)'); ctx.fillStyle = hz; ctx.fillRect(-200, 560, W + 400, 200);
  const rowCol = ['#7a3e52', '#4a2438', '#26131f'];
  PARIS.forEach((row, ri) => {
    if (ri === 1) {
      ctx.save(); ctx.translate(1390, 740); ctx.scale(0.72, 0.72); ctx.translate(-210, -800); ctx.drawImage(EIFFEL_T, 0, 0); ctx.restore();
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = 'rgba(255,220,150,0.9)'; ctx.beginPath(); ctx.arc(1390, 740 - 790 * 0.72, 3 + Math.sin(t * 4), 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
    for (const b of row.b) {
      const top = row.base - b.h;
      ctx.fillStyle = rowCol[ri];
      ctx.beginPath(); ctx.moveTo(b.x, row.base + 400); ctx.lineTo(b.x, top); ctx.lineTo(b.x + b.roof * 0.35, top - b.roof); ctx.lineTo(b.x + b.w - b.roof * 0.35, top - b.roof); ctx.lineTo(b.x + b.w, top); ctx.lineTo(b.x + b.w, row.base + 400); ctx.fill();
      for (const [cx, ch] of b.chim) ctx.fillRect(b.x + cx, top - b.roof - ch, 12, ch + 2);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (const [wx, wy, ph] of b.wins) { ctx.fillStyle = `rgba(255,190,110,${(0.25 + 0.2 * ri) * (0.7 + 0.3 * Math.sin(t * 0.7 + ph * 9))})`; ctx.fillRect(b.x + wx, top + wy, 5 + ri * 2, 7 + ri * 2); }
      ctx.restore();
    }
    const h2 = ctx.createLinearGradient(0, row.base - 160, 0, row.base + 40); h2.addColorStop(0, 'rgba(255,150,110,0)'); h2.addColorStop(1, `rgba(255,150,110,${0.12 - ri * 0.04})`); ctx.fillStyle = h2; ctx.fillRect(-200, row.base - 160, W + 400, 200);
  });
  ctx.fillStyle = '#0e080d'; ctx.beginPath(); ctx.moveTo(-100, 808); ctx.lineTo(W + 100, 808); ctx.lineTo(W + 100, H + 2400); ctx.lineTo(-100, H + 2400); ctx.fill();
  ctx.fillStyle = '#140b12'; ctx.fillRect(-100, 800, W + 200, 16);
  ctx.fillStyle = 'rgba(255,160,100,0.55)'; ctx.fillRect(-100, 799, W + 200, 2);
  ctx.strokeStyle = 'rgba(255,160,100,0.08)'; ctx.lineWidth = 2; for (let x = -100; x < W + 100; x += 46) { ctx.beginPath(); ctx.moveTo(x, 818); ctx.lineTo(x - 30, H + 20); ctx.stroke(); }
  ctx.fillStyle = '#0e080d'; ctx.fillRect(210, 640, 120, 162); ctx.fillRect(200, 632, 140, 14);
  for (let k = 0; k < 4; k++) ctx.fillRect(220 + k * 28, 600, 16, 34);
  ctx.fillStyle = 'rgba(255,160,100,0.5)'; ctx.fillRect(330, 646, 2, 156); ctx.fillRect(200, 631, 140, 2);
  ctx.strokeStyle = '#0e080d'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(1650, 802); ctx.lineTo(1650, 640); ctx.moveTo(1610, 670); ctx.lineTo(1690, 670); ctx.moveTo(1620, 700); ctx.lineTo(1680, 700); ctx.stroke();
  ctx.restore();
}

// ---------------- text ----------------
export function captions(TL, t) {
  const ln = TL.lines.find(l => t >= l.start - 0.05 && t <= l.end + 0.25); if (!ln) return;
  ctx.save(); ctx.font = '600 40px Inter'; ctx.textAlign = 'center'; ctx.fillStyle = '#ffffff'; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 14;
  ctx.globalAlpha = smooth(ln.start - 0.05, ln.start + 0.1, t) * (1 - smooth(ln.end + 0.1, ln.end + 0.25, t));
  ctx.fillText(ln.text, W / 2, 1000); ctx.restore();
}
export function altitudeHUD(km, a) {
  if (a <= 0) return; ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = 'rgba(255,255,255,0.55)'; ctx.font = '600 15px Inter'; ctx.fillText('ALTITUDE', 72, 88);
  ctx.fillStyle = '#ffffff'; ctx.font = '600 44px Inter'; ctx.fillText(Math.round(km).toLocaleString('en-US') + ' km', 70, 136);
  ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(56, 70); ctx.lineTo(56, 146); ctx.stroke();
  ctx.restore();
}
function tag(text, sub, a) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.font = '600 22px Inter'; ctx.letterSpacing = '3px'; ctx.fillText(text, 72, 96);
  ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.font = '500 16px Inter'; ctx.letterSpacing = '1px'; ctx.fillText(sub, 72, 122); ctx.restore();
}
export function landmarkTag(text, sub, local) { tag(text, sub, smooth(0.15, 0.45, local) * (1 - smooth(1.4, 1.7, local))); }
export function placeTag(text, sub, local) { tag(text, sub, smooth(0.2, 0.6, local) * (1 - smooth(2.2, 2.7, local))); }

// ---------------- orbital observation deck (drawn over the Earth render) ----------------
// window: chamfered panoramic opening split into three panes; shutter: 0 = closed, 1 = fully open
const WIN = { x0: 170, x1: 1750, y0: 96, y1: 790, ch: 70, mull: [700, 1220] };
function winPath(c, inset = 0) {
  const { x0, x1, y0, y1, ch } = WIN, i = inset;
  c.moveTo(x0 + ch + i, y0 + i); c.lineTo(x1 - ch - i, y0 + i); c.lineTo(x1 - i, y0 + ch + i); c.lineTo(x1 - i, y1 - ch * 0.5 - i);
  c.lineTo(x1 - ch * 0.5 - i, y1 - i); c.lineTo(x0 + ch * 0.5 + i, y1 - i); c.lineTo(x0 + i, y1 - ch * 0.5 - i); c.lineTo(x0 + i, y0 + ch + i); c.closePath();
}
const LEDS = (() => { const r = rng(61); return Array.from({ length: 26 }, () => [r() < 0.5 ? 30 + r() * 110 : 1790 + r() * 110, 140 + r() * 640, r() < 0.7 ? '#7ff3ff' : '#ffb347', r() * 6]); })();
export function deckBack(t, shutter, glowCol = '#8fc4ff') {
  // glass: faint tint + reflections (over the Earth, under the frame)
  ctx.save(); ctx.beginPath(); winPath(ctx); ctx.clip();
  ctx.fillStyle = 'rgba(40,70,110,0.08)'; ctx.fillRect(0, 0, W, H);
  ctx.globalCompositeOperation = 'lighter';
  for (const [x, w, a] of [[420, 180, 0.05], [560, 40, 0.06], [1380, 260, 0.035]]) {
    const g = ctx.createLinearGradient(x, 0, x + w, 0); g.addColorStop(0, 'rgba(200,225,255,0)'); g.addColorStop(0.5, `rgba(200,225,255,${a})`); g.addColorStop(1, 'rgba(200,225,255,0)');
    ctx.save(); ctx.translate(x, 0); ctx.transform(1, 0, -0.35, 1, 0, 0); ctx.translate(-x, 0); ctx.fillStyle = g; ctx.fillRect(x, 0, w, H); ctx.restore(); }
  ctx.globalCompositeOperation = 'source-over';
  // shutter slats retract upward, staggered from the bottom
  const N = 12, slatH = (WIN.y1 - WIN.y0) / N;
  for (let k = 0; k < N; k++) {
    const e = easeInOut(clamp(shutter * 1.6 - (N - 1 - k) / N * 0.6));   // lower slats start first
    const h = slatH * (1 - e), top = WIN.y0 + k * slatH * (1 - e);
    if (h <= 0.3) continue;
    ctx.fillStyle = '#0c1018'; ctx.fillRect(WIN.x0, top, WIN.x1 - WIN.x0, h - 1.5);
    const sg = ctx.createLinearGradient(0, top, 0, top + h); sg.addColorStop(0, 'rgba(160,190,230,0.10)'); sg.addColorStop(1, 'rgba(0,0,0,0.25)');
    ctx.fillStyle = sg; ctx.fillRect(WIN.x0, top, WIN.x1 - WIN.x0, h - 1.5);
    if (shutter > 0) { ctx.fillStyle = `rgba(170,215,255,${0.4 * (1 - e)})`; ctx.fillRect(WIN.x0, top + h - 1.5, WIN.x1 - WIN.x0, 1.5); }
  }
  ctx.restore();
  // interior: everything outside the window opening
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, H); winPath(ctx); ctx.clip('evenodd');
  const wall = ctx.createRadialGradient(960, 520, 300, 960, 520, 1150); wall.addColorStop(0, '#141a26'); wall.addColorStop(1, '#05070b');
  ctx.fillStyle = wall; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(150,180,220,0.07)'; ctx.lineWidth = 1.5;
  for (const x of [60, 150, 1770, 1860]) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (const y of [60, 300, 560]) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(150, y); ctx.moveTo(1770, y); ctx.lineTo(W, y); ctx.stroke(); }
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const [x, y, col, ph] of LEDS) { ctx.fillStyle = hexA(col, 0.45 + 0.35 * Math.sin(t * 1.5 + ph)); ctx.fillRect(x, y, 6, 3); }
  ctx.restore();
  ctx.restore();
  // window frame: thick bezel with inner bevel lit by the Earth
  ctx.save(); ctx.beginPath(); winPath(ctx, -26); winPath(ctx); ctx.fillStyle = '#0b0e15'; ctx.fill('evenodd');
  ctx.strokeStyle = hexA(glowCol, 0.55 * clamp(shutter * 1.5)); ctx.lineWidth = 2; ctx.beginPath(); winPath(ctx, 1); ctx.stroke();
  ctx.strokeStyle = 'rgba(180,200,230,0.12)'; ctx.lineWidth = 1.5; ctx.beginPath(); winPath(ctx, -26); ctx.stroke();
  for (const mx of WIN.mull) { ctx.fillStyle = '#0b0e15'; ctx.fillRect(mx - 9, WIN.y0, 18, WIN.y1 - WIN.y0);
    ctx.fillStyle = hexA(glowCol, 0.4 * clamp(shutter * 1.5)); ctx.fillRect(mx + 8, WIN.y0 + 20, 1.5, WIN.y1 - WIN.y0 - 40); }
  // bolts on the bezel
  ctx.fillStyle = 'rgba(160,180,210,0.18)';
  for (let k = 0; k < 14; k++) { const x = lerp(WIN.x0 + 90, WIN.x1 - 90, k / 13); ctx.beginPath(); ctx.arc(x, WIN.y0 - 13, 2.2, 0, Math.PI * 2); ctx.arc(x, WIN.y1 + 13, 2.2, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
  // window sill / bench the human sits on (top surface at y = 822)
  ctx.save();
  ctx.fillStyle = '#0a0d14'; ctx.fillRect(0, 822, W, H - 822);
  const sill = ctx.createLinearGradient(0, 812, 0, 836); sill.addColorStop(0, '#1a2130'); sill.addColorStop(1, '#0a0d14');
  ctx.fillStyle = sill; ctx.fillRect(0, 812, W, 24);
  ctx.fillStyle = hexA(glowCol, 0.5 * clamp(shutter * 1.5)); ctx.fillRect(0, 811, W, 1.6);
  const spill = ctx.createRadialGradient(960, 820, 0, 960, 820, 900); spill.addColorStop(0, hexA(glowCol, 0.10 * shutter)); spill.addColorStop(1, hexA(glowCol, 0));
  ctx.fillStyle = spill; ctx.fillRect(0, 812, W, H - 812);
  ctx.strokeStyle = 'rgba(150,180,220,0.06)'; ctx.lineWidth = 1; for (let x = 0; x < W; x += 160) { ctx.beginPath(); ctx.moveTo(x, 840); ctx.lineTo(x, H); ctx.stroke(); }
  ctx.restore();
}
// light ring that wraps the characters before AXIS "jumps" them to orbit
export function jumpRing(cx, cy, k, t) {
  if (k <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const rx = lerp(90, 520, easeInOut(k)), ry = lerp(18, 300, easeInOut(k));
  for (let j = 0; j < 3; j++) {
    ctx.strokeStyle = `rgba(127,243,255,${(0.7 - j * 0.2) * Math.min(1, k * 3)})`; ctx.lineWidth = 3 - j; ctx.shadowColor = EYE; ctx.shadowBlur = 20;
    ctx.beginPath(); ctx.ellipse(cx, cy, rx * (1 + j * 0.08), ry * (1 + j * 0.08), Math.sin(t * 3 + j) * 0.1, 0, Math.PI * 2); ctx.stroke(); }
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rx); g.addColorStop(0, `rgba(127,243,255,${0.18 * k})`); g.addColorStop(1, 'rgba(127,243,255,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

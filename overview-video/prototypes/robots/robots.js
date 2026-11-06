// Robot character library: each function returns an SVG string.
// Params: expr = 'neutral' | 'happy' | 'surprised' | 'sad' ; t = time in seconds ; blink = 0..1 (1 = closed)

const R = {};

R.defs = `
<defs>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="softglow" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur stdDeviation="12"/>
  </filter>
  <linearGradient id="pearl" x1="0" y1="0" x2="0.3" y2="1">
    <stop offset="0" stop-color="#ffffff"/><stop offset="0.55" stop-color="#e3e8f2"/><stop offset="1" stop-color="#b9c3d6"/>
  </linearGradient>
  <linearGradient id="visor" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1b2440"/><stop offset="1" stop-color="#05070f"/>
  </linearGradient>
  <linearGradient id="graphite" x1="0" y1="0" x2="0.4" y2="1">
    <stop offset="0" stop-color="#4a5262"/><stop offset="1" stop-color="#232833"/>
  </linearGradient>
  <linearGradient id="shell" x1="0" y1="0" x2="0.2" y2="1">
    <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cfd6e3"/>
  </linearGradient>
  <radialGradient id="sphere" cx="0.38" cy="0.32" r="0.75">
    <stop offset="0" stop-color="#ffffff"/><stop offset="0.6" stop-color="#e2e8f3"/><stop offset="1" stop-color="#a9b4c9"/>
  </radialGradient>
  <linearGradient id="yellow" x1="0" y1="0" x2="0.3" y2="1">
    <stop offset="0" stop-color="#f3c552"/><stop offset="1" stop-color="#c98f1f"/>
  </linearGradient>
</defs>`;

// Generic glowing eyes. kind: 'pill' (rounded rect) or 'round'
R.eyes = function (cx, cy, gap, w, h, expr, color, blink = 0, kind = 'pill') {
  const out = [];
  for (const s of [-1, 1]) {
    const x = cx + s * gap / 2;
    if (expr === 'happy') {
      const r = w / 2;
      out.push(`<path d="M ${x - r} ${cy + h * 0.25} Q ${x} ${cy - h * 0.75} ${x + r} ${cy + h * 0.25}" fill="none" stroke="${color}" stroke-width="${Math.max(4, h * 0.28)}" stroke-linecap="round" filter="url(#glow)"/>`);
      continue;
    }
    let ew = w, eh = h;
    if (expr === 'surprised') { ew = w * 1.3; eh = h * 1.5; }
    eh = Math.max(eh * (1 - blink), 3);
    if (expr === 'sad') {
      // eye with a drooping lid: outer side lower
      const top = cy - eh / 2, bot = cy + eh / 2;
      const inner = x - s * ew / 2, outer = x + s * ew / 2;
      const lidInner = top, lidOuter = top + eh * 0.45;
      out.push(`<path d="M ${inner} ${lidInner + 4} L ${outer} ${lidOuter} L ${outer} ${bot - 6} Q ${outer} ${bot} ${outer - s * 6} ${bot} L ${inner + s * 6} ${bot} Q ${inner} ${bot} ${inner} ${bot - 6} Z" fill="${color}" filter="url(#glow)"/>`);
      continue;
    }
    if (kind === 'round') {
      out.push(`<ellipse cx="${x}" cy="${cy}" rx="${ew / 2}" ry="${eh / 2}" fill="${color}" filter="url(#glow)"/>`);
    } else {
      out.push(`<rect x="${x - ew / 2}" y="${cy - eh / 2}" width="${ew}" height="${eh}" rx="${Math.min(ew, eh) / 2}" fill="${color}" filter="url(#glow)"/>`);
    }
  }
  return out.join('');
};

// ---------- A: AXIS — hovering AI, sleek, orbit ring ----------
R.axisHead = function (expr, t, blink) {
  const a = (t * 0.9) % (Math.PI * 2);
  const dx = Math.cos(a) * 118, dy = Math.sin(a) * 22;
  const front = Math.sin(a) > 0;
  const ring = `<g transform="rotate(-12)"><ellipse cx="0" cy="0" rx="118" ry="22" fill="none" stroke="#5ef2ff" stroke-width="2.5" opacity="0.55"/></g>`;
  const dot = `<g transform="rotate(-12)"><circle cx="${dx}" cy="${dy}" r="6" fill="#5ef2ff" filter="url(#glow)"/></g>`;
  return `
  ${front ? '' : dot}
  <rect x="-85" y="-70" width="170" height="140" rx="68" fill="url(#pearl)"/>
  <rect x="-68" y="-30" width="136" height="58" rx="29" fill="url(#visor)"/>
  <path d="M -56 -24 Q -20 -32 30 -26" stroke="#ffffff" stroke-opacity="0.18" stroke-width="5" fill="none" stroke-linecap="round"/>
  ${R.eyes(0, -1, 56, 26, 30, expr, '#5ef2ff', blink)}
  <circle cx="-87" cy="0" r="7" fill="#5ef2ff" opacity="0.8"/><circle cx="87" cy="0" r="7" fill="#5ef2ff" opacity="0.8"/>
  ${ring}
  ${front ? dot : ''}`;
};
R.axis = function (expr = 'neutral', t = 0, blink = 0) {
  const bob = Math.sin(t * 2) * 8;
  const pulse = 0.7 + 0.3 * Math.sin(t * 3);
  return `<g transform="translate(0 ${bob})">
    <ellipse cx="0" cy="${235 - bob}" rx="${70 - bob}" ry="12" fill="#000" opacity="0.35"/>
    <ellipse cx="0" cy="168" rx="40" ry="14" fill="#5ef2ff" opacity="${0.55 * pulse}" filter="url(#softglow)"/>
    <path d="M -78 20 Q -82 10 -70 8 L 70 8 Q 82 10 78 20 L 40 150 Q 36 160 26 160 L -26 160 Q -36 160 -40 150 Z" fill="url(#pearl)"/>
    <path d="M -50 40 L 50 40" stroke="#c4cddd" stroke-width="2"/>
    <circle cx="0" cy="80" r="24" fill="#0b1020"/>
    <circle cx="0" cy="80" r="15" fill="#5ef2ff" opacity="${pulse}" filter="url(#glow)"/>
    <circle cx="0" cy="80" r="24" fill="none" stroke="#5ef2ff" stroke-width="2" opacity="0.6"/>
    <g transform="translate(-118 ${70 + Math.sin(t * 2 + 1) * 6})"><rect x="-18" y="-30" width="36" height="60" rx="18" fill="url(#pearl)"/><circle cx="0" cy="-12" r="5" fill="#5ef2ff" filter="url(#glow)"/></g>
    <g transform="translate(118 ${70 + Math.sin(t * 2 + 2) * 6})"><rect x="-18" y="-30" width="36" height="60" rx="18" fill="url(#pearl)"/><circle cx="0" cy="-12" r="5" fill="#5ef2ff" filter="url(#glow)"/></g>
    <g transform="translate(0 -80)">${R.axisHead(expr, t, blink)}</g>
  </g>`;
};

// ---------- B: VEGA — advanced humanoid, graphite + white, amber eyes ----------
R.vegaHead = function (expr, t, blink) {
  return `
  <rect x="-62" y="-58" width="124" height="116" rx="44" fill="url(#shell)"/>
  <rect x="-50" y="-34" width="100" height="62" rx="24" fill="url(#visor)"/>
  ${R.eyes(0, -3, 44, 22, 22, expr, '#ffb347', blink, 'round')}
  <rect x="-70" y="-14" width="10" height="30" rx="5" fill="#ff8a3d"/><rect x="60" y="-14" width="10" height="30" rx="5" fill="#ff8a3d"/>
  <path d="M -30 -50 Q 0 -60 30 -50" stroke="#ffffff" stroke-width="4" opacity="0.7" fill="none" stroke-linecap="round"/>`;
};
R.vega = function (expr = 'neutral', t = 0, blink = 0) {
  const sway = Math.sin(t * 1.5) * 2;
  return `<g transform="rotate(${sway * 0.3})">
    <ellipse cx="0" cy="238" rx="80" ry="10" fill="#000" opacity="0.35"/>
    <rect x="-56" y="130" width="40" height="100" rx="16" fill="url(#graphite)"/>
    <rect x="16" y="130" width="40" height="100" rx="16" fill="url(#graphite)"/>
    <rect x="-60" y="175" width="48" height="12" rx="6" fill="#ff8a3d"/><rect x="12" y="175" width="48" height="12" rx="6" fill="#ff8a3d"/>
    <rect x="-64" y="222" width="52" height="18" rx="9" fill="url(#shell)"/><rect x="12" y="222" width="52" height="18" rx="9" fill="url(#shell)"/>
    <path d="M -86 -10 Q -90 -24 -72 -26 L 72 -26 Q 90 -24 86 -10 L 58 130 Q 54 142 40 142 L -40 142 Q -54 142 -58 130 Z" fill="url(#graphite)"/>
    <path d="M -64 -18 L 64 -18 L 46 70 Q 0 86 -46 70 Z" fill="url(#shell)"/>
    <path d="M 0 -10 L 0 60" stroke="#ff8a3d" stroke-width="4" stroke-linecap="round" filter="url(#glow)"/>
    <g transform="rotate(${8 + sway} -92 -12)"><rect x="-112" y="-20" width="36" height="150" rx="18" fill="url(#graphite)"/><rect x="-108" y="55" width="28" height="8" rx="4" fill="#ff8a3d"/><circle cx="-94" cy="140" r="20" fill="url(#shell)"/></g>
    <g transform="rotate(${-8 - sway} 92 -12)"><rect x="76" y="-20" width="36" height="150" rx="18" fill="url(#graphite)"/><rect x="80" y="55" width="28" height="8" rx="4" fill="#ff8a3d"/><circle cx="94" cy="140" r="20" fill="url(#shell)"/></g>
    <rect x="-16" y="-44" width="32" height="24" rx="8" fill="#232833"/>
    <g transform="translate(0 -100)">${R.vegaHead(expr, t, blink)}</g>
  </g>`;
};

// ---------- C: ORBI — spherical companion, screen face ----------
R.orbiHead = function (expr, t, blink) {
  return `
  <circle cx="0" cy="0" r="110" fill="url(#sphere)"/>
  <path d="M -108 22 Q 0 52 108 22" fill="none" stroke="#3d7bff" stroke-width="7"/>
  <rect x="-74" y="-52" width="148" height="78" rx="36" fill="url(#visor)"/>
  ${R.eyes(0, -14, 64, 30, 40, expr, '#7fd6ff', blink, 'round')}
  <line x1="0" y1="-110" x2="0" y2="-140" stroke="#a9b4c9" stroke-width="5" stroke-linecap="round"/>
  <circle cx="0" cy="-146" r="9" fill="#3d7bff" filter="url(#glow)"/>`;
};
R.orbi = function (expr = 'neutral', t = 0, blink = 0) {
  const bob = Math.sin(t * 2.2) * 10;
  const fin = Math.sin(t * 6) * 6;
  return `<g>
    <ellipse cx="0" cy="235" rx="${80 - bob}" ry="12" fill="#000" opacity="0.35"/>
    <g transform="translate(0 ${60 + bob})">
      <path d="M -108 10 L -150 ${-10 + fin} L -140 ${30 + fin} Z" fill="#3d7bff"/>
      <path d="M 108 10 L 150 ${-10 - fin} L 140 ${30 - fin} Z" fill="#3d7bff"/>
      ${R.orbiHead(expr, t, blink)}
      <ellipse cx="0" cy="122" rx="30" ry="8" fill="#7fd6ff" opacity="0.6" filter="url(#softglow)"/>
    </g>
  </g>`;
};

// ---------- D: RUSTY — retired maintenance robot (original idea) ----------
R.rustyHead = function (expr, t, blink) {
  return `
  <rect x="-80" y="-56" width="160" height="112" rx="14" fill="url(#yellow)"/>
  <path d="M -60 -40 l 22 6 M 40 30 l 18 -8 M -20 34 l 10 4" stroke="#8a5d10" stroke-width="3" stroke-linecap="round" opacity="0.7"/>
  <circle cx="-34" cy="-4" r="30" fill="#3a3a3a"/><circle cx="34" cy="-4" r="24" fill="#3a3a3a"/>
  <circle cx="-34" cy="-4" r="24" fill="#0b1020"/><circle cx="34" cy="-4" r="19" fill="#0b1020"/>
  ${R.eyes(0, -4, 68, 22, 22, expr, '#9dff8a', blink, 'round')}
  <circle cx="-70" cy="-46" r="4" fill="#8a5d10"/><circle cx="70" cy="-46" r="4" fill="#8a5d10"/><circle cx="-70" cy="46" r="4" fill="#8a5d10"/><circle cx="70" cy="46" r="4" fill="#8a5d10"/>
  <path d="M 50 -56 L 58 -96 L 80 -110" stroke="#6b6b6b" stroke-width="5" fill="none" stroke-linecap="round"/>
  <circle cx="80" cy="-110" r="7" fill="#ff5a4e"/>`;
};
R.rusty = function (expr = 'neutral', t = 0, blink = 0) {
  const tilt = Math.sin(t * 1.3) * 3;
  return `<g>
    <ellipse cx="0" cy="238" rx="100" ry="12" fill="#000" opacity="0.35"/>
    <rect x="-100" y="170" width="200" height="64" rx="32" fill="#3a3a3a"/>
    ${[-70, -35, 0, 35, 70].map(x => `<circle cx="${x}" cy="202" r="14" fill="#6b6b6b"/>`).join('')}
    <rect x="-78" y="10" width="156" height="164" rx="16" fill="url(#yellow)"/>
    <rect x="-50" y="40" width="100" height="56" rx="8" fill="#3a3a3a"/>
    <rect x="-40" y="50" width="22" height="10" rx="3" fill="#9dff8a" opacity="0.8"/><rect x="-12" y="50" width="22" height="10" rx="3" fill="#ff5a4e" opacity="0.8"/>
    <path d="M -64 120 l 30 8 M 30 140 l 24 -6" stroke="#8a5d10" stroke-width="3" stroke-linecap="round" opacity="0.6"/>
    <g transform="rotate(${tilt} -86 40)"><rect x="-110" y="30" width="30" height="110" rx="12" fill="#6b6b6b"/><path d="M -110 140 l -8 26 l 14 0 l 4 -12 l 6 12 l 14 0 l -8 -26 Z" fill="#9a9a9a"/></g>
    <g transform="rotate(${-tilt} 86 40)"><rect x="80" y="30" width="30" height="110" rx="12" fill="#6b6b6b"/><circle cx="95" cy="150" r="16" fill="#9a9a9a"/></g>
    <rect x="-14" y="-6" width="28" height="20" fill="#6b6b6b"/>
    <g transform="translate(0 -60) rotate(${tilt})">${R.rustyHead(expr, t, blink)}</g>
  </g>`;
};

R.list = [
  { key: 'axis', name: 'A · AXIS', sub: 'Hovering AI · sleek, futuristic', color: '#5ef2ff' },
  { key: 'vega', name: 'B · VEGA', sub: 'Advanced humanoid · strong, cool', color: '#ffb347' },
  { key: 'orbi', name: 'C · ORBI', sub: 'Smart companion · friendly', color: '#7fd6ff' },
  { key: 'rusty', name: 'D · RUSTY', sub: 'Retired repair bot · warm (first idea)', color: '#9dff8a' },
];

if (typeof module !== 'undefined') module.exports = R;

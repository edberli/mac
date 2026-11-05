#!/usr/bin/env python3
"""Paper-puppet comedy Short renderer (1080x1920, 12 fps animation, 30 fps encode).

Usage (always under the RAM cap):
  ~/bin/memcap -m 6G -- python3 render.py --stills 1.0,11.5 [--sheet]
  ~/bin/memcap -m 6G -- python3 render.py --eyes            # eye detection debug image
  ~/bin/memcap -m 6G -- python3 render.py                   # full render
"""
import argparse, json, math, os, subprocess, sys, time, zlib
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi
from scipy.io import wavfile

cv2.setNumThreads(2)

W, H = 1080, 1920
ANIM_FPS, OUT_FPS = 12, 30
EP = '/Volumes/core/AI-Workspace/Claude/mac/comedy-shorts/ep01_game_night'
BEATS = f'{EP}/beats.json'
ROOT = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy'
ASSETS = f'{ROOT}/assets'
AUDIO = f'{ROOT}/audio'
BUILD = f'{ROOT}/build'
OUT_MP4 = f'{BUILD}/game_night_v1.mp4'
SR = 44100

# Manual eye overrides (source-pixel coords): name -> [(cx, cy, rx, ry), (cx, cy, rx, ry)]
EYE_OVERRIDES = {}

FONT_BOLD = ('/System/Library/Fonts/Avenir Next.ttc', 0)      # Avenir Next Bold
FONT_HEAVY = ('/System/Library/Fonts/Avenir Next.ttc', 8)     # Avenir Next Heavy


def shash(*a):
    return zlib.crc32(repr(a).encode()) & 0xffffff


def font(spec, size):
    return ImageFont.truetype(spec[0], size, index=spec[1])


def smooth(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


# --------------------------------------------------------------------------------------
# image helpers
# --------------------------------------------------------------------------------------
def over(dst, layer, x, y):
    """dst uint8 HxWx3, layer premultiplied uint8 RGBA, top-left at (x, y) in dst."""
    h, w = layer.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    s = layer[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4].astype(np.uint16)
    d = dst[y0:y1, x0:x1].astype(np.uint16)
    out = s[..., :3].astype(np.uint16) + (d * (255 - a) + 127) // 255
    dst[y0:y1, x0:x1] = np.minimum(out, 255).astype(np.uint8)


def over_layer(base, spr, x, y):
    """premult RGBA over premult RGBA (in place on base)."""
    h, w = spr.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, base.shape[1]), min(y + h, base.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.uint16)
    d = base[y0:y1, x0:x1].astype(np.uint16)
    out = s + (d * (255 - s[..., 3:4]) + 127) // 255
    base[y0:y1, x0:x1] = np.minimum(out, 255).astype(np.uint8)


def premult(rgb, a):
    """rgb float 0..255 HxWx3, a float 0..1 -> uint8 premult RGBA"""
    out = np.empty(a.shape + (4,), np.uint8)
    out[..., :3] = np.clip(rgb * a[..., None], 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8)
    return out


def paper_texture(h, w, seed, amp=0.045):
    """multiplicative paper fibre grain map around 1.0"""
    r = np.random.default_rng(seed)
    n = r.standard_normal((h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(n, (0, 0), 0.7)
    f1 = cv2.GaussianBlur(r.standard_normal((h, w)).astype(np.float32), (0, 0), sigmaX=0.7, sigmaY=4.0)
    f2 = cv2.GaussianBlur(r.standard_normal((h, w)).astype(np.float32), (0, 0), sigmaX=4.0, sigmaY=0.7)
    t = fine / (fine.std() + 1e-6) * 0.5 + f1 / (f1.std() + 1e-6) * 0.6 + f2 / (f2.std() + 1e-6) * 0.6
    t = t / (t.std() + 1e-6)
    return 1.0 + amp * t


def wobble_poly(pts, amp, seed, closed=True):
    r = np.random.default_rng(seed)
    n = len(pts)
    noise = r.standard_normal((n, 2))
    k = np.ones(3) / 3
    noise[:, 0] = np.convolve(np.r_[noise[-1:, 0], noise[:, 0], noise[:1, 0]], k, 'valid')
    noise[:, 1] = np.convolve(np.r_[noise[-1:, 1], noise[:, 1], noise[:1, 1]], k, 'valid')
    return np.asarray(pts) + noise * amp


# --------------------------------------------------------------------------------------
# puppets: keying, eye detection
# --------------------------------------------------------------------------------------
class Puppet:
    """Keyed puppet at source resolution."""

    def __init__(self, name, eyes=True):
        self.name = name
        im = np.asarray(Image.open(f'{ASSETS}/{name}.png').convert('RGB')).astype(np.float32)
        self.rgb, self.alpha = self.key(im)
        ys, xs = np.where(self.alpha > 0.04)
        self.x0, self.x1, self.y0, self.y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        self.rgb = self.rgb[self.y0:self.y1, self.x0:self.x1]
        self.alpha = self.alpha[self.y0:self.y1, self.x0:self.x1]
        self.h, self.w = self.alpha.shape
        if not eyes:
            self.eyes, self.ex, self.ey, self.spacing, self.erx, self.ery, self.eyew, self.headw = (), self.w / 2, 0, 0, 0, 0, 0, self.w
            return
        self.eyes = self.detect_eyes()
        (ax, ay, arx, ary), (bx, by, brx, bry) = self.eyes
        self.ex, self.ey = (ax + bx) / 2, (ay + by) / 2           # head anchor (eye line mid)
        self.spacing = abs(bx - ax)
        self.erx, self.ery = (arx + brx) / 2, (ary + bry) / 2
        self.eyew = 2 * self.erx
        self.headw = self.measure_head()

    @staticmethod
    def key(im):
        corners = np.concatenate([im[:20, :20].reshape(-1, 3), im[:20, -20:].reshape(-1, 3),
                                  im[-20:, :20].reshape(-1, 3), im[-20:, -20:].reshape(-1, 3)])
        G = np.median(corners, axis=0)
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        dbg = G[1] - max(G[0], G[2])
        d = g - np.maximum(r, b)
        hi, lo = dbg * 0.78, dbg * 0.12
        a = np.clip((hi - d) / (hi - lo), 0, 1)
        a = np.clip((a - 0.04) / 0.92, 0, 1)
        # remove specks
        lab, n = ndi.label(a > 0.5)
        if n > 1:
            sizes = ndi.sum(np.ones_like(a), lab, range(1, n + 1))
            for i, s in enumerate(sizes):
                if s < 400:
                    a[lab == i + 1] = 0
        # unmix green from edge pixels
        safe = np.maximum(a, 0.05)[..., None]
        fg = (im - (1 - a)[..., None] * G) / safe
        fg = np.clip(fg, 0, 255)
        # replace silhouette-edge colour (within ~2px of transparency) with the nearest interior colour: kills green fringe
        interior = cv2.erode((a > 0.97).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        _, (iy, ix) = ndi.distance_transform_edt(~interior, return_indices=True)
        fg = fg[iy, ix]
        return fg, a

    def detect_eyes(self):
        if self.name in EYE_OVERRIDES:
            return EYE_OVERRIDES[self.name]
        rgb, a = self.rgb, self.alpha
        mn = rgb.min(axis=2)
        sat = rgb.max(axis=2) - mn
        white = (mn > 165) & (sat < 90) & (a > 0.9)
        white[int(self.h * 0.40):] = False
        lab, n = ndi.label(white)
        cands = []
        for i in range(1, n + 1):
            ys, xs = np.where(lab == i)
            area = len(xs)
            if area < 400:
                continue
            bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            fill = area / (bw * bh)
            if not (0.6 < fill < 0.9):
                continue
            cands.append((area, (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2, bw / 2, bh / 2))
        cands.sort(reverse=True)
        best = None
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                A, B = cands[i], cands[j]
                if abs(A[2] - B[2]) < 0.25 * max(A[4], B[4]) * 2 and 0.6 < A[0] / B[0] < 1.6:
                    best = (A, B)
                    break
            if best:
                break
        if best is None:
            raise RuntimeError(f'eye detection failed for {self.name}: {cands[:4]}; add EYE_OVERRIDES')
        e = sorted(best, key=lambda c: c[1])
        return tuple((c[1], c[2], c[3], c[4]) for c in e)

    def measure_head(self):
        row = int(round(self.ey))
        cols = self.alpha[row] > 0.5
        x = int(round(self.ex))
        l = r = x
        while l > 0 and cols[l - 1]:
            l -= 1
        while r < self.w - 1 and cols[r + 1]:
            r += 1
        return r - l + 1

    def debug(self):
        img = Image.fromarray(premult_over_gray(self.rgb, self.alpha))
        d = ImageDraw.Draw(img)
        for (cx, cy, rx, ry) in self.eyes:
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=(255, 0, 0), width=3)
            r = 0.32 * (rx + ry) / 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0))
        d.line([self.ex - self.headw / 2, self.ey, self.ex + self.headw / 2, self.ey], fill=(0, 0, 255), width=3)
        d.ellipse([self.ex - 6, self.ey - 6, self.ex + 6, self.ey + 6], fill=(0, 0, 255))
        my = self.ey + 1.1 * self.eyew
        d.ellipse([self.ex - 8, my - 8, self.ex + 8, my + 8], outline=(255, 0, 255), width=3)
        return img


def premult_over_gray(rgb, a, bg=(120, 120, 120)):
    out = rgb * a[..., None] + np.array(bg, np.float32) * (1 - a[..., None])
    return np.clip(out, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------------------
# mouth + pupil paper sprites
# --------------------------------------------------------------------------------------
SS = 4  # supersample


def shape_sprite(draw_fn, w, h, seed, shadow=(2, 3), pad=8):
    """draw_fn(draw, scale) draws on an 'L'/RGBA supersampled canvas; returns premult RGBA with grain + shadow."""
    cw, ch = int(w + 2 * pad), int(h + 2 * pad)
    big = Image.new('RGBA', (cw * SS, ch * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(big), SS, cw / 2, ch / 2)
    img = np.asarray(big.resize((cw, ch), Image.LANCZOS)).astype(np.float32)
    a = img[..., 3] / 255
    rgb = img[..., :3] / np.maximum(a[..., None], 1e-3)
    tex = paper_texture(ch, cw, seed, 0.07)
    rgb = np.clip(rgb * tex[..., None], 0, 255)
    fg = premult(rgb, a)
    sh = np.zeros((ch, cw), np.float32)
    M = np.float32([[1, 0, shadow[0]], [0, 1, shadow[1]]])
    sh = cv2.warpAffine(a, M, (cw, ch))
    sh = cv2.GaussianBlur(sh, (0, 0), 1.3) * 0.38
    shl = np.zeros((ch, cw, 4), np.uint8)
    shl[..., 3] = np.clip(sh * 255, 0, 255).astype(np.uint8)
    base = shl
    over_layer(base, fg, 0, 0)
    return base, pad


def make_mouth(shape, s, seed):
    """Return (premult sprite, anchor_xy) for mouth of eye spacing s (px). Anchor = centre of mouth in sprite."""
    DARK = (62, 30, 26, 255)
    RED = (104, 20, 30, 255)
    TEETH = (244, 232, 212, 255)
    TONGUE = (196, 84, 86, 255)
    rng = np.random.default_rng(seed)

    def poly(d, pts, col, sc, cx, cy, amp=0.6):
        p = wobble_poly(pts, amp, int(rng.integers(1 << 30)))
        d.polygon([((cx + x) * sc, (cy + y) * sc) for x, y in p], fill=col)

    def ellipse_pts(rx, ry, n=48, a0=0, a1=2 * math.pi):
        t = np.linspace(a0, a1, n, endpoint=False)
        return np.c_[rx * np.cos(t), ry * np.sin(t)]

    if shape == 'flat':
        w, h = 0.46 * s, max(4.0, 0.045 * s)
        pts = [(-w / 2, -h / 2), (0, -h / 2 - 0.3), (w / 2, -h / 2), (w / 2, h / 2), (0, h / 2 + 0.3), (-w / 2, h / 2)]
        pts = np.array(pts)
        def fn(d, sc, cx, cy):
            poly(d, pts, DARK, sc, cx, cy, 0.5)
        return shape_sprite(fn, w + 6, h + 6, seed)
    if shape == 'smile':
        w = 0.56 * s
        th = max(4.0, 0.05 * s)
        depth = 0.12 * s
        xs = np.linspace(-w / 2, w / 2, 24)
        top = np.c_[xs, depth * (1 - (2 * xs / w) ** 2)]
        low = top[::-1] + np.array([0, th])
        pts = np.vstack([top, low])
        def fn(d, sc, cx, cy):
            poly(d, pts, DARK, sc, cx, cy, 0.5)
        return shape_sprite(fn, w + 8, depth + th + 8, seed)
    if shape in ('grin', 'open_s', 'open_m', 'open_l', 'o'):
        if shape == 'grin':
            w, h = 0.72 * s, 0.40 * s
        elif shape == 'open_s':
            w, h = 0.36 * s, 0.17 * s
        elif shape == 'open_m':
            w, h = 0.46 * s, 0.28 * s
        elif shape == 'open_l':
            w, h = 0.56 * s, 0.44 * s
        else:
            w, h = 0.20 * s, 0.22 * s
        if shape == 'grin':
            n = 40
            xs = np.linspace(-w / 2, w / 2, n)
            top = np.c_[xs, np.full(n, -h / 2) + 0.03 * h * (1 - (2 * xs / w) ** 2)]
            t = np.linspace(0, math.pi, n)
            bot = np.c_[(w / 2) * np.cos(t), -h / 2 + h * np.sin(t)]
            pts = np.vstack([top, bot[1:-1]])
            tp = np.array([(-w / 2 + 0.03 * w, -h / 2 + 0.02 * h), (w / 2 - 0.03 * w, -h / 2 + 0.02 * h),
                           (w / 2 - 0.10 * w, -h / 2 + 0.27 * h), (-w / 2 + 0.10 * w, -h / 2 + 0.27 * h)])
            def fn(d, sc, cx, cy):
                poly(d, pts, RED, sc, cx, cy, 0.6)
                poly(d, tp, TEETH, sc, cx, cy, 0.3)
            return shape_sprite(fn, w + 8, h + 8, seed)
        # round-ish open mouths
        pts = ellipse_pts(w / 2, h / 2)
        def fn(d, sc, cx, cy):
            poly(d, pts, DARK if shape == 'o' else RED, sc, cx, cy, 0.7)
            if shape == 'open_l':
                tg = ellipse_pts(w * 0.26, h * 0.20, 28)
                tg[:, 1] += h * 0.22
                poly(d, tg, TONGUE, sc, cx, cy, 0.5)
            if shape == 'o':
                inner = ellipse_pts(w * 0.34, h * 0.34, 28)
                poly(d, inner, RED, sc, cx, cy, 0.3)
        return shape_sprite(fn, w + 8, h + 8, seed)
    raise ValueError(shape)


def make_pupil(r, seed=7):
    d = int(math.ceil(2 * r + 6))
    def fn(dr, sc, cx, cy):
        pts = np.c_[r * np.cos(np.linspace(0, 2 * math.pi, 36, endpoint=False)), r * np.sin(np.linspace(0, 2 * math.pi, 36, endpoint=False))]
        p = wobble_poly(pts, 0.25, seed)
        dr.polygon([((cx + x) * sc, (cy + y) * sc) for x, y in p], fill=(24, 18, 17, 255))
    spr, pad = shape_sprite(fn, 2 * r, 2 * r, seed, shadow=(1, 2), pad=5)
    return spr, spr.shape[1] / 2, spr.shape[0] / 2


# --------------------------------------------------------------------------------------
# scene layout
# --------------------------------------------------------------------------------------
PAD = 110
TABLE_BASE = 0.82   # spec says 0.88; at 0.88 the table sits entirely below the feet/caption (see report)
SHOTS = None  # loaded from beats.json


class Sprite:
    """A placed puppet: premult RGBA canvas (puppet + shadow), frame-space origin, eye anchors, pivot."""

    def __init__(self, role, pup, scale, X, Y, kind, shadow_off):
        self.role, self.pup, self.scale = role, pup, scale
        sw, sh = int(round(pup.w * scale)), int(round(pup.h * scale))
        rgb = cv2.resize(pup.rgb * pup.alpha[..., None], (sw, sh), interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
        al = cv2.resize(pup.alpha, (sw, sh), interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
        al = np.clip(al, 0, 1)
        rgb = rgb / np.maximum(al[..., None], 1e-3)
        rgb = np.clip(rgb, 0, 255)
        # sharpen slightly (upscaled puppets go soft) then fibre grain
        if scale > 1.05:
            blur = cv2.GaussianBlur(rgb, (0, 0), 1.6)
            rgb = np.clip(rgb + 0.6 * (rgb - blur), 0, 255)
        tex = paper_texture(sh, sw, shash(pup.name), 0.032 if scale > 1.05 else 0.02)
        rgb = np.clip(rgb * tex[..., None], 0, 255)
        cw, ch = sw + 2 * PAD, sh + 2 * PAD
        canvas = np.zeros((ch, cw, 4), np.uint8)
        canvas[PAD:PAD + sh, PAD:PAD + sw] = premult(rgb, al)
        # shadow
        sa = np.zeros((ch, cw), np.float32)
        sa[PAD:PAD + sh, PAD:PAD + sw] = al
        M = np.float32([[1, 0, shadow_off[0]], [0, 1, shadow_off[1]]])
        sa = cv2.warpAffine(sa, M, (cw, ch))
        sa = cv2.GaussianBlur(sa, (0, 0), 7) * 0.45
        layer = np.zeros((ch, cw, 4), np.uint8)
        layer[..., 3] = np.clip(sa * 255, 0, 255).astype(np.uint8)
        over_layer(layer, canvas, 0, 0)
        # geometry in canvas coords
        self.ex = PAD + (pup.ex) * scale
        self.ey = PAD + (pup.ey) * scale
        self.eyes = [(PAD + cx * scale, PAD + cy * scale, rx * scale, ry * scale) for (cx, cy, rx, ry) in pup.eyes]
        self.spacing = pup.spacing * scale
        self.eyew = pup.eyew * scale
        self.pivot = (PAD + sw / 2, PAD + sh)   # feet, canvas coords
        # frame-space origin of canvas
        self.ox = int(round(X - self.ex))
        self.oy = int(round(Y - self.ey))
        self.headw_px = pup.headw * scale
        self.fig_w, self.fig_h = sw, sh
        self.left_frame = self.ox + PAD
        self.canvas = layer
        # crop canvas to frame +- margin to save work
        m = 120
        x0 = max(0, -m - self.ox)
        y0 = max(0, -m - self.oy)
        x1 = min(cw, W + m - self.ox)
        y1 = min(ch, H + m - self.oy)
        if x1 > x0 and y1 > y0:
            self.canvas = layer[y0:y1, x0:x1].copy()
            self.cx0, self.cy0 = x0, y0
        else:
            self.cx0 = self.cy0 = 0
        self.ox += self.cx0
        self.oy += self.cy0
        # shift anchors into cropped coords
        self.ex -= self.cx0
        self.ey -= self.cy0
        self.eyes = [(cx - self.cx0, cy - self.cy0, rx, ry) for (cx, cy, rx, ry) in self.eyes]
        self.pivot = (self.pivot[0] - self.cx0, self.pivot[1] - self.cy0)
        self.mouth_cache = {}

    def mouth(self, shape):
        if shape not in self.mouth_cache:
            seed = shash(self.pup.name, shape)
            spr, pad = make_mouth(shape, self.spacing, seed)
            self.mouth_cache[shape] = (spr, spr.shape[1] / 2, spr.shape[0] / 2)
        return self.mouth_cache[shape]


PUPIL_CACHE = {}


def pupil_sprite(r):
    k = int(round(r * 2))
    if k not in PUPIL_CACHE:
        PUPIL_CACHE[k] = make_pupil(k / 2)
    return PUPIL_CACHE[k]


class Scene:
    def __init__(self, spec):
        self.spec = spec
        self.puppets = {}
        self.bgs = {}
        self.sprites = {}
        self.table = None
        self.title = None

    # ---- backgrounds
    def bg(self, name, crop):
        key = (name, crop)
        if key in self.bgs:
            return self.bgs[key]
        im = Image.open(f'{ASSETS}/{name}.png').convert('RGB')
        iw, ih = im.size
        if crop is None:
            blur = 0
            c = im
        else:
            fx0, fx1, fy0, fy1 = crop
            c = im.crop((int(fx0 * iw), int(fy0 * ih), int(fx1 * iw), int(fy1 * ih)))
            blur = 8
        c = c.resize((W + 8, H + 8), Image.LANCZOS)
        a = np.asarray(c)
        if blur:
            a = cv2.GaussianBlur(a, (0, 0), blur)
        self.bgs[key] = a
        return a

    def get_puppet(self, name):
        if name not in self.puppets:
            self.puppets[name] = Puppet(name, eyes=(name != 'table'))
        return self.puppets[name]


def layout_shot(scene, shot):
    """Returns dict with bg array and list of (role, Sprite) in draw order, plus table."""
    if shot in scene.sprites:
        return scene.sprites[shot]
    sp = scene.spec['shots'][shot]
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': []}
    cast = sp['cast']
    SOFA = (0.0, 0.62, 0.25, 0.87)
    CHAIR = (0.38, 1.0, 0.25, 0.87)
    if shot == 'wide':
        out['bg'] = scene.bg('bg_wide', None)
        xs = {'D': 0.16, 'K': 0.36, 'L': 0.62, 'T': 0.82}
        for role in ('D', 'K', 'L', 'T'):
            if role not in cast:
                continue
            pup = scene.get_puppet(cast[role])
            scale = 0.35 * H / pup.h
            feet = 0.72 * H
            Y = feet - pup.h * scale + pup.ey * scale
            out['sprites'].append((role, Sprite(role, pup, scale, xs[role] * W, Y, 'wide', (6, 8))))
        t = scene.get_puppet('table')  # keyed table, same keyer
        sc = 0.50 * W / t.w
        out['table'] = Sprite('table', t, sc, 0.5 * W, TABLE_BASE * H - t.h * sc + t.ey * sc, 'table', (6, 9)) if hasattr(t, 'ey') else None
        return scene.sprites.setdefault(shot, out)
    single = len(cast) == 1
    side_chair = any(c in ('L', 'T') for c in cast)
    crop = CHAIR if side_chair else SOFA
    out['bg'] = scene.bg('bg_chair' if side_chair else 'bg_sofa', crop)
    if single:
        role = list(cast)[0]
        pup = scene.get_puppet(cast[role])
        spec = (0.48 * W, 800, 680)
        out['sprites'].append((role, fit_sprite(role, pup, *spec, shadow=(10, 14), notes=out['notes'])))
    else:
        for role, X in zip(list(cast), (0.28 * W, 0.70 * W)):
            pup = scene.get_puppet(cast[role])
            out['sprites'].append((role, fit_sprite(role, pup, X, 760, 400, shadow=(10, 14), notes=out['notes'], max_shift=80)))
    scene.sprites[shot] = out
    return out


def fit_sprite(role, pup, X, Y, headw, shadow, notes, max_shift=None):
    scale = headw / pup.headw
    # keep raised arm / body edges in frame: left extent from head centre
    left_ext = (pup.ex - 0) * scale
    margin = 16
    right_lim = W - 130 - headw / 2 - 10
    if X - left_ext < margin:
        X2 = min(X + (margin - (X - left_ext)), max(X, right_lim), X + (max_shift if max_shift is not None else 1e9))
        if X2 - left_ext < margin:
            scale = (X2 - margin) / pup.ex
            notes.append(f'{role}/{pup.name}: shifted X {X:.0f}->{X2:.0f}, scale {headw / pup.headw:.3f}->{scale:.3f} (head {pup.headw * scale:.0f}px) to keep arm in frame')
        else:
            notes.append(f'{role}/{pup.name}: shifted X {X:.0f}->{X2:.0f} to keep arm in frame')
        X = X2
    return Sprite(role, pup, scale, X, Y, 'single', shadow)


# --------------------------------------------------------------------------------------
# audio / timeline
# --------------------------------------------------------------------------------------
def build_timeline(spec, manifest, quiet=False):
    os.makedirs(f'{BUILD}/audio_t', exist_ok=True)
    beats = spec['beats']
    tl = []
    t = 0.0
    wavs = {}
    for i, b in enumerate(beats):
        m = manifest[i] if i < len(manifest) else None
        entry = {'i': i, 'start': t, 'beat': b, 'audio': None}
        if 'hold' in b:
            dur = float(b['hold'])
        else:
            if m is None:
                raise RuntimeError(f'beat {i} speaks but has no audio')
            tempo = float(b.get('tempo', 1.0))
            src = f"{AUDIO}/{m['file']}"
            if abs(tempo - 1) > 1e-6:
                dst = f"{BUILD}/audio_t/{m['file'][:-4]}_t{tempo}.wav"
                if not os.path.exists(dst):
                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-filter:a', f'atempo={tempo}', '-ar', str(SR), '-ac', '1', dst], check=True)
                src = dst
            if src not in wavs:
                sr, d = wavfile.read(src)
                assert sr == SR, (src, sr)
                d = d.astype(np.float32) / 32768 if d.dtype == np.int16 else d.astype(np.float32)
                if d.ndim > 1:
                    d = d.mean(axis=1)
                wavs[src] = d
            d = wavs[src]
            adur = len(d) / SR
            dur = adur + float(b.get('after', 0))
            entry['audio'] = d
            entry['adur'] = adur
            entry['env'] = envelope(d)
        entry['dur'] = dur
        tl.append(entry)
        t += dur
    return tl, t


def envelope(d, hop=0.01, win=0.08):
    n = int(len(d) / (SR * hop)) + 1
    h = int(hop * SR)
    w = int(win * SR)
    pad = np.r_[np.zeros(w // 2, np.float32), d.astype(np.float32), np.zeros(w, np.float32)]
    sq = pad ** 2
    cs = np.r_[0, np.cumsum(sq, dtype=np.float64)]
    out = np.empty(n, np.float32)
    for k in range(n):
        a = k * h
        out[k] = math.sqrt((cs[min(a + w, len(cs) - 1)] - cs[min(a, len(cs) - 1)]) / w)
    ref = np.percentile(out[out > out.max() * 0.05], 90) if (out > out.max() * 0.05).any() else out.max() + 1e-6
    return out / max(ref, 1e-6)


def env_at(env, local):
    k = int(round(local * 100))
    k = max(0, min(len(env) - 1, k))
    return float(env[k])


# --------------------------------------------------------------------------------------
# frame renderer
# --------------------------------------------------------------------------------------
LOOK_X = {'center': 0.0, 'left': -0.5, 'right': 0.5, 'down': 0.0}
LOOK_Y = {'center': 0.0, 'left': 0.0, 'right': 0.0, 'down': 0.45}


class Renderer:
    def __init__(self, spec, tl):
        self.spec = spec
        self.tl = tl
        self.scene = Scene(spec)
        self.rest = spec['rest_mouth']
        self.captions = {}
        self.title = None
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.48) / (H / 2)) ** 2)
        self.vig = (1 - 0.34 * np.clip(r - 0.35, 0, None) ** 1.6)[..., None].astype(np.float32)
        self.tint = np.array([1.045, 1.0, 0.915], np.float32)
        self.starts = [e['start'] for e in tl]

    def beat_at(self, T):
        lo = 0
        for i, s in enumerate(self.starts):
            if s <= T + 1e-9:
                lo = i
        return lo

    # ---- captions
    def caption(self, i):
        if i in self.captions:
            return self.captions[i]
        text = self.tl[i]['beat'].get('text', '')
        maxw = 860 - 80
        size = 62
        while True:
            f = font(FONT_BOLD, size)
            words = text.split()
            lines, cur = [], ''
            for w_ in words:
                t = (cur + ' ' + w_).strip()
                if f.getlength(t) <= maxw:
                    cur = t
                else:
                    lines.append(cur)
                    cur = w_
            lines.append(cur)
            if len(lines) <= 2 or size < 40:
                break
            size -= 2
        lh = int(size * 1.18)
        tw = max(f.getlength(l) for l in lines)
        sw = int(min(860, tw + 80))
        sh = int(lh * len(lines) + 56)
        pad = 50
        cw, ch = sw + 2 * pad, sh + 2 * pad
        SSc = 2
        big = Image.new('RGBA', (cw * SSc, ch * SSc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        rng = np.random.default_rng(100 + i)
        # rough-edged strip polygon
        pts = []
        n = 22
        for k in range(n):
            pts.append((pad + sw * k / n, pad))
        for k in range(6):
            pts.append((pad + sw, pad + sh * k / 6))
        for k in range(n):
            pts.append((pad + sw - sw * k / n, pad + sh))
        for k in range(6):
            pts.append((pad, pad + sh - sh * k / 6))
        pts = wobble_poly(pts, 1.6, 100 + i)
        d.polygon([(x * SSc, y * SSc) for x, y in pts], fill=(243, 231, 203, 255))
        tgt = Image.new('RGBA', big.size, (0, 0, 0, 0))
        big = big.resize((cw, ch), Image.LANCZOS)
        a = np.asarray(big).astype(np.float32)
        al = a[..., 3] / 255
        tex = paper_texture(ch, cw, 300 + i, 0.03)
        rgb = np.clip(a[..., :3] * tex[..., None], 0, 255)
        # text
        timg = Image.fromarray(np.zeros((ch, cw), np.uint8))
        td = ImageDraw.Draw(timg)
        ty = pad + (sh - lh * len(lines)) / 2 + (lh - size) * 0.15
        for k, l in enumerate(lines):
            td.text((cw / 2, ty + k * lh + size / 2 + 2), l, font=f, fill=255, anchor='mm')
        tm = np.asarray(timg).astype(np.float32) / 255
        tm = cv2.GaussianBlur(tm, (0, 0), 0.4)
        ink = np.array([62, 38, 25], np.float32)
        rgb = rgb * (1 - tm[..., None]) + ink * tm[..., None] * (0.92 + 0.08 * tex[..., None])
        # rotate ~1 deg and add shadow
        ang = 1.0 if i % 2 == 0 else -1.0
        M = cv2.getRotationMatrix2D((cw / 2, ch / 2), ang, 1.0)
        lay = premult(rgb, al)
        lay = cv2.warpAffine(lay, M, (cw, ch), flags=cv2.INTER_LINEAR)
        sh_a = lay[..., 3].astype(np.float32) / 255
        sh_a = cv2.warpAffine(sh_a, np.float32([[1, 0, 5], [0, 1, 9]]), (cw, ch))
        sh_a = cv2.GaussianBlur(sh_a, (0, 0), 7) * 0.45
        base = np.zeros((ch, cw, 4), np.uint8)
        base[..., 3] = np.clip(sh_a * 255, 0, 255).astype(np.uint8)
        over_layer(base, lay, 0, 0)
        self.captions[i] = base
        return base

    # ---- title
    def make_title(self):
        if self.title is not None:
            return self.title
        bgc = np.array([58, 38, 27], np.float32)
        tex = paper_texture(H, W, 5, 0.05)
        bg = (bgc * tex[..., None])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        bg *= (1 - 0.3 * np.clip(r - 0.3, 0, None))[..., None]
        bg = np.clip(bg, 0, 255).astype(np.uint8)
        letters = []
        cols = [(243, 229, 196), (240, 222, 186), (246, 233, 204), (238, 220, 190)]
        rng = np.random.default_rng(11)
        rows = [('GAME', 740), ('NIGHT', 1080)]
        for word, cy in rows:
            size = 330 if word == 'GAME' else 300
            f = font(FONT_HEAVY, size)
            adv = [f.getlength(c) for c in word]
            tot = sum(adv) - 0 * (len(word) - 1)
            scl = 920 / tot
            if True:
                f = font(FONT_HEAVY, int(size * scl))
                adv = [f.getlength(c) for c in word]
                tot = sum(adv) - 0 * (len(word) - 1)
            x = W / 2 - tot / 2
            for k, c in enumerate(word):
                bw = int(adv[k] + 160)
                bh = int(f.size * 1.5)
                big = Image.new('L', (bw * 2, bh * 2), 0)
                ImageDraw.Draw(big).text((bw, bh), c, font=font(FONT_HEAVY, f.size * 2), fill=255, anchor='mm')
                m = np.asarray(big.resize((bw, bh), Image.LANCZOS)).astype(np.float32) / 255
                # cut-paper wobble
                r2 = np.random.default_rng(900 + len(letters))
                dx = cv2.GaussianBlur(r2.standard_normal((bh, bw)).astype(np.float32), (0, 0), 9) * 6
                dy = cv2.GaussianBlur(r2.standard_normal((bh, bw)).astype(np.float32), (0, 0), 9) * 6
                gx, gy = np.meshgrid(np.arange(bw, dtype=np.float32), np.arange(bh, dtype=np.float32))
                m = cv2.remap(m, gx + dx, gy + dy, cv2.INTER_LINEAR)
                m = np.clip((m - 0.5) * 6 + 0.5, 0, 1)  # crisp but uneven edge
                ang = float(rng.uniform(-7, 7))
                M = cv2.getRotationMatrix2D((bw / 2, bh / 2), ang, 1)
                m = cv2.warpAffine(m, M, (bw, bh))
                col = np.array(cols[len(letters) % 4], np.float32)
                tx = paper_texture(bh, bw, 700 + len(letters), 0.045)
                rgb = np.clip(col * tx[..., None], 0, 255)
                lay = premult(rgb, m)
                sh = cv2.warpAffine(m, np.float32([[1, 0, 9], [0, 1, 14]]), (bw, bh))
                sh = cv2.GaussianBlur(sh, (0, 0), 9) * 0.55
                base = np.zeros((bh, bw, 4), np.uint8)
                base[..., 3] = np.clip(sh * 255, 0, 255).astype(np.uint8)
                over_layer(base, lay, 0, 0)
                cx = x + adv[k] / 2
                cyy = cy + float(rng.uniform(-14, 14))
                letters.append((base, int(cx - bw / 2), int(cyy - bh / 2)))
                x += adv[k]
        self.title = (bg, letters)
        return self.title

    # ---- main per-frame render
    def frame(self, T, aidx):
        """T: time in seconds (state time, already snapped to animation grid / beat start); aidx: global anim frame idx."""
        bi = self.beat_at(T)
        e = self.tl[bi]
        b = e['beat']
        local = max(0.0, T - e['start'])
        hold = 'hold' in b
        spoken = not hold and e['audio'] is not None
        shot = b['shot']
        pair = aidx // 2
        rng_bg = np.random.default_rng(1000 + pair)
        if shot == 'title':
            bg, letters = self.make_title()
            fr = bg.copy()
            for li, (lay, x, y) in enumerate(letters):
                r = np.random.default_rng(5000 + pair * 17 + li)
                over(fr, lay, x + int(r.integers(-1, 2)), y + int(r.integers(-1, 2)))
            return self.grade(fr, aidx)
        lay = layout_shot(self.scene, shot)
        wx, wy = (int(v) for v in rng_bg.integers(-1, 2, size=2))
        fr = lay['bg'][4 + wy:4 + wy + H, 4 + wx:4 + wx + W].copy()
        p = smooth(local / e['dur']) if hold and e['dur'] > 0 else 0.0
        say = b.get('say') if spoken else None
        look = b.get('look', {})
        look_to = b.get('look_to', {})
        ps_to = b.get('pupil_scale_to', {})
        tilt_to = b.get('tilt_to', {})
        for role, spr in lay['sprites']:
            fr_layer = spr.canvas.copy()
            # ---- eyes
            lk = look.get(role, 'center')
            vx, vy = LOOK_X[lk], LOOK_Y[lk]
            if role in look_to:
                lt = look_to[role]
                vx = vx + (LOOK_X[lt] - vx) * p
                vy = vy + (LOOK_Y[lt] - vy) * p
            ps = 1.0 + (ps_to[role] - 1.0) * p if role in ps_to else 1.0
            for (cx, cy, rx, ry) in spr.eyes:
                r = 0.32 * (rx + ry) / 2 * ps
                psp, ax, ay = pupil_sprite(max(r, 2))
                px = cx + vx * rx
                py = cy + vy * ry
                over_layer(fr_layer, psp, int(round(px - ax)), int(round(py - ay)))
            # ---- mouth
            rest = self.rest[role]
            lev = 0.0
            if role == say:
                rest = b.get('mouth_rest', rest)
                n = env_at(e['env'], local + 0.04)
                n_prev = env_at(e['env'], max(0.0, local - 1 / ANIM_FPS + 0.04))
                lev = max(n, 0.45 * n_prev)
                # Dave's and Linda's blurted lines must look gleeful: an o-shaped mouth would kill the joke
                glee = role in ('D', 'L') and b.get('emotion') == 'happy'
                if b.get('take') == 'me' and n >= 0.05:
                    shape = 'grin'
                elif n < 0.16:
                    shape = rest
                elif glee:
                    shape = 'grin' if n < 0.85 else 'open_l'
                elif n < 0.5:
                    shape = 'open_s'
                elif n < 0.85:
                    shape = 'open_m'
                else:
                    shape = 'open_l'
            else:
                shape = rest
            ms, mx, my = spr.mouth(shape)
            mcx = spr.ex
            mcy = spr.ey + 1.1 * spr.eyew
            over_layer(fr_layer, ms, int(round(mcx - mx)), int(round(mcy - my)))
            # ---- motion
            r = np.random.default_rng(shash(role, pair))
            amp_p, amp_a = (0.5, 0.05) if hold else (1.5, 0.2)
            jx, jy = r.uniform(-amp_p, amp_p, 2)
            ja = r.uniform(-amp_a, amp_a)
            dy, ang = 0.0, 0.0
            if role == say:
                dy = -0.02 * H * min(1.0, lev)
                sgn = 1 if math.sin(aidx * 2.3 + 0.7) > 0 else -1
                ang = 1.5 * min(1.0, lev) * sgn
            if role in tilt_to:
                ang += tilt_to[role] * p
            M = cv2.getRotationMatrix2D(spr.pivot, ang + ja, 1.0)
            M[:, 2] += (jx, jy + dy)
            warped = cv2.warpAffine(fr_layer, M, (fr_layer.shape[1], fr_layer.shape[0]), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            over(fr, warped, spr.ox, spr.oy)
        if lay['table'] is not None:
            tsp = lay['table']
            r = np.random.default_rng(777 + pair)
            M = np.float32([[1, 0, r.uniform(-1.2, 1.2)], [0, 1, r.uniform(-1.2, 1.2)]])
            warped = cv2.warpAffine(tsp.canvas, M, (tsp.canvas.shape[1], tsp.canvas.shape[0]))
            over(fr, warped, tsp.ox, tsp.oy)
        if spoken and b.get('text'):
            cap = self.caption(bi)
            r = np.random.default_rng(321 + pair)
            ox, oy = (int(v) for v in r.integers(-1, 2, size=2))
            over(fr, cap, int(W / 2 - cap.shape[1] / 2) + ox, int(1420 - cap.shape[0] / 2) + oy)
        return self.grade(fr, aidx)

    def grade(self, fr, aidx):
        f = fr.astype(np.float32)
        f = f * self.tint
        f = (f - 128) * 1.04 + 128 + 3
        f *= self.vig
        rg = np.random.default_rng(900000 + aidx)
        g = rg.standard_normal((H, W)).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 0.6) * 8
        f += g[..., None]
        return np.clip(f, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------------------
# audio mix
# --------------------------------------------------------------------------------------
def wood_tick(sr=SR, seed=0, pitch=1.0):
    n = int(0.06 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    # bandpass-ish click: difference of smoothed noise
    nz = np.convolve(noise, np.ones(4) / 4, 'same') - np.convolve(noise, np.ones(24) / 24, 'same')
    body = np.sin(2 * np.pi * 1350 * pitch * t) * np.exp(-t / 0.006) + 0.6 * np.sin(2 * np.pi * 2180 * pitch * t) * np.exp(-t / 0.004)
    x = body + 0.7 * nz * np.exp(-t / 0.0025)
    x[:int(0.0004 * sr)] *= np.linspace(0, 1, int(0.0004 * sr))
    return (x / np.abs(x).max()).astype(np.float32)


def bell(sr=SR):
    n = int(1.4 * sr)
    t = np.arange(n) / sr
    parts = [(880, 1.0, 1.0), (2217, 0.5, 0.55), (3520, 0.35, 0.38), (4690, 0.2, 0.25), (1320, 0.25, 0.8)]
    x = np.zeros(n)
    for f, a, dec in parts:
        x += a * np.sin(2 * np.pi * f * t) * np.exp(-t / dec * 3.2)
    x *= np.minimum(1, t / 0.002)
    return (x / np.abs(x).max()).astype(np.float32)


def build_audio(tl, total, path):
    n = int((total + 0.5) * SR)
    mix = np.zeros(n, np.float32)
    # speech
    for e in tl:
        if e['audio'] is not None:
            s = int(e['start'] * SR)
            d = e['audio']
            mix[s:s + len(d)] += d
    # sfx times
    starts = {}
    first_tick = ding_tick = second_tick = stop_tick = None
    for e in tl:
        s = e['beat'].get('sfx')
        if s == 'tick_start':
            if first_tick is None:
                first_tick = e['start']
            else:
                second_tick = e['start']
        elif s == 'ding_end_tick':
            ding_tick = e['start']
        elif s == 'tick_stop':
            stop_tick = e['start']
    ticks = []
    for a, b_ in ((first_tick, ding_tick), (second_tick, stop_tick)):
        if a is None or b_ is None:
            continue
        t = a
        k = 0
        while t < b_ - 1e-6:
            ticks.append((t, k))
            t += 0.5
            k += 1
    def in_hold(t):
        for e in tl:
            if e['start'] <= t < e['start'] + e['dur']:
                return 'hold' in e['beat']
        return False
    tk = [wood_tick(seed=1, pitch=1.0), wood_tick(seed=2, pitch=0.82)]
    for t, k in ticks:
        g = 10 ** (-14 / 20) if in_hold(t) else 10 ** (-28 / 20)
        x = tk[k % 2] * g
        s = int(t * SR)
        mix[s:s + len(x)] += x[:max(0, min(len(x), n - s))]
    dings = [ding_tick] + [e['start'] for e in tl if e['beat'].get('sfx') == 'ding']
    bl = bell() * 10 ** (-9 / 20)
    for t in dings:
        if t is None:
            continue
        s = int(t * SR)
        mix[s:s + len(bl)] += bl[:max(0, min(len(bl), n - s))]
    # room tone: very faint low rumble + hiss
    rng = np.random.default_rng(3)
    rt = rng.standard_normal(n).astype(np.float32)
    rt = cv2.GaussianBlur(rt.reshape(1, -1), (0, 0), sigmaX=40).ravel()
    rt /= rt.std() + 1e-9
    hiss = rng.standard_normal(n).astype(np.float32)
    hiss = np.r_[0, np.diff(hiss)]
    hiss /= hiss.std() + 1e-9
    mix += rt * 10 ** (-52 / 20) + hiss * 10 ** (-62 / 20)
    mix = mix[:int(total * SR)]
    pk = np.abs(mix).max()
    if pk > 0.95:
        mix *= 0.95 / pk
    st = np.int16(np.clip(mix, -1, 1) * 32767)
    wavfile.write(path, SR, np.c_[st, st])
    return ticks, dings


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------
def snap_state(R, T):
    """Given output time T, return (state time, anim index) with exact cut at beat start."""
    aidx = int(math.floor(T * ANIM_FPS + 1e-6))
    ta = aidx / ANIM_FPS
    bi = R.beat_at(T)
    st = R.starts[bi]
    if ta < st:
        ta = st
    return ta, aidx, bi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stills', default=None)
    ap.add_argument('--sheet', action='store_true')
    ap.add_argument('--eyes', action='store_true')
    ap.add_argument('--out', default=OUT_MP4)
    ap.add_argument('--timeline-only', action='store_true')
    a = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)
    spec = json.load(open(BEATS))
    manifest = json.load(open(f'{AUDIO}/manifest.json'))
    tl, total = build_timeline(spec, manifest)
    print(f'{"idx":>3} {"start":>7} {"dur":>6} {"shot":<9} text')
    for e in tl:
        b = e['beat']
        print(f"{e['i']:>3} {e['start']:7.3f} {e['dur']:6.3f} {b['shot']:<9} {b.get('text', '(hold)')}")
    print(f'TOTAL {total:.3f} s' + ('  ** OVER 50 s **' if total > 50 else ''))
    if a.timeline_only:
        return
    R = Renderer(spec, tl)
    if a.eyes:
        names = sorted({n for s in spec['shots'].values() for n in s['cast'].values()})
        tiles = []
        for n in names:
            p = R.scene.get_puppet(n)
            im = p.debug()
            print(f'{n}: size {p.w}x{p.h} eyes {[tuple(round(v, 1) for v in e) for e in p.eyes]} headw {p.headw}')
            s = 620 / im.height
            tiles.append(im.resize((int(im.width * s), 620)))
        sheet = Image.new('RGB', (sum(t.width for t in tiles) + 10 * len(tiles), 620), (30, 30, 30))
        x = 0
        for t in tiles:
            sheet.paste(t, (x, 0))
            x += t.width + 10
        sheet.save(f'{BUILD}/eye_debug.png')
        print('wrote', f'{BUILD}/eye_debug.png')
        return
    if a.stills or a.sheet:
        os.makedirs(f'{BUILD}/stills', exist_ok=True)
        if a.stills:
            for ts in a.stills.split(','):
                T = float(ts)
                ta, aidx, bi = snap_state(R, T)
                fr = R.frame(ta, aidx)
                p = f'{BUILD}/stills/t{T:07.3f}.jpg'
                Image.fromarray(fr).save(p, quality=92)
                print('still', p, 'beat', bi)
            for nm, sp in [(s, 0) for s in spec['shots']]:
                lay = layout_shot(R.scene, nm) if nm != 'title' else None
                if lay:
                    for note in lay['notes']:
                        print('layout note:', nm, note)
        if a.sheet:
            thumbs = []
            tt = 0.5
            while tt < total:
                ta, aidx, bi = snap_state(R, tt)
                fr = R.frame(ta, aidx)
                im = Image.fromarray(fr).resize((216, 384), Image.LANCZOS)
                d = ImageDraw.Draw(im)
                d.rectangle([0, 0, 92, 18], fill=(0, 0, 0))
                d.text((3, 3), f't={tt:.1f} b{bi}', fill=(255, 255, 255))
                thumbs.append(im)
                tt += 1.0
            per = 20
            for k in range(0, len(thumbs), per):
                chunk = thumbs[k:k + per]
                cols = 10
                rows = (len(chunk) + cols - 1) // cols
                sh = Image.new('RGB', (cols * 220, rows * 388), (20, 20, 20))
                for j, im in enumerate(chunk):
                    sh.paste(im, ((j % cols) * 220, (j // cols) * 388))
                p = f'{BUILD}/stills/sheet_{k // per + 1}.jpg'
                sh.save(p, quality=90)
                print('sheet', p)
        return
    # ---- full render
    audio_path = f'{BUILD}/mix_raw.wav'
    ticks, dings = build_audio(tl, total, audio_path)
    print(f'ticks: {len(ticks)}; dings at {[round(d, 2) for d in dings if d is not None]}')
    nframes = int(round(total * OUT_FPS))
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(OUT_FPS), '-i', '-',
           '-i', audio_path, '-filter:a', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
           '-ar', '44100', '-movflags', '+faststart', '-shortest', a.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    last_key, last = None, None
    t0 = time.time()
    for n in range(nframes):
        T = n / OUT_FPS
        ta, aidx, bi = snap_state(R, T)
        key = (bi, round(ta * 1000), aidx)
        if key != last_key:
            last = R.frame(ta, aidx)
            last_key = key
        proc.stdin.write(last.tobytes())
        if n % 60 == 0:
            print(f'frame {n}/{nframes}  {time.time() - t0:.0f}s', flush=True)
    proc.stdin.close()
    rc = proc.wait()
    print('ffmpeg rc', rc, 'frames', nframes, 'elapsed', round(time.time() - t0))
    for note_shot in spec['shots']:
        if note_shot in R.scene.sprites:
            for note in R.scene.sprites[note_shot]['notes']:
                print('layout note:', note_shot, note)


if __name__ == '__main__':
    main()

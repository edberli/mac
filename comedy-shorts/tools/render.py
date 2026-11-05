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
SHORTS = '/Volumes/core/AI-Workspace/Claude/mac/comedy-shorts'
ROOT = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy'
BUILD = f'{ROOT}/build'
SR = 44100

# Per-episode configuration. Layout code for each episode lives in layout_ep01 / layout_ep02 below.
EPCFG = {
    'ep01_game_night': dict(assets=[f'{ROOT}/assets'], audio=f'{ROOT}/audio_v4', out=f'{BUILD}/game_night_v4.mp4'),
    'ep02_on_hold': dict(assets=[f'{ROOT}/assets_ep02', f'{ROOT}/assets'], audio=f'{ROOT}/audio_ep02', out=f'{BUILD}/on_hold_v1.mp4'),
    'ep03_apology': dict(assets=[f'{ROOT}/assets_ep03', f'{ROOT}/assets'], audio=f'{ROOT}/audio_ep03', out=f'{BUILD}/apology_v1.mp4'),
}
# set by configure()
EPNAME = 'ep01_game_night'
BEATS = AUDIO = OUT_MP4 = None
ASSET_DIRS = []


def configure(ep):
    global EPNAME, BEATS, AUDIO, OUT_MP4, ASSET_DIRS
    if ep not in EPCFG:
        raise SystemExit(f'unknown episode {ep}; known: {list(EPCFG)}')
    c = EPCFG[ep]
    EPNAME, BEATS, AUDIO, OUT_MP4, ASSET_DIRS = ep, f'{SHORTS}/{ep}/beats.json', c['audio'], c['out'], c['assets']


def asset_path(name):
    for d in ASSET_DIRS:
        p = f'{d}/{name}.png'
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f'{name}.png not in {ASSET_DIRS}')


configure('ep01_game_night')

# Manual eye overrides (source-pixel coords): name -> [(cx, cy, rx, ry), (cx, cy, rx, ry)]
# (full source-image coords, before the bbox crop)
EYE_OVERRIDES = {'russell': [(450, 435.5, 70, 50), (614.5, 387.5, 69, 52)],
                 'marcus': [(358, 368, 79, 79), (511, 325, 77, 77)],
                 'marcus_jump': [(410, 428, 74, 74), (547, 387, 74, 74)]}
# Hip line (source y inside the keyed, cropped puppet): waist of trousers / top of skirt / where the dress flares.
# This is the line that must rest on the seat cushion's top surface.
HIP = {'dave_down': 850, 'dave_up': 850, 'karen_card': 832, 'karen_nocard': 832, 'linda': 1004, 'tom': 862,
       'vince': 940, 'cop': 900}
# Per-puppet face extras (ep02): mouth centre below the eye line in eye-widths, mouth scale, skin oval cut in a mask.
FACE = {'vince': dict(mouth_dy=1.15, mouth_scale=0.8, oval=True),
        'cop': dict(mouth_dy=1.32, mouth_scale=0.62),
        'doris': dict(mouth_dy=1.05, mouth_scale=1.0)}

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
        im = np.asarray(Image.open(asset_path(name)).convert('RGB')).astype(np.float32)
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
        py_, px_ = int(self.ey + 0.85 * self.ery), int(self.ex)
        self.skin = np.median(self.rgb[py_ - 3:py_ + 4, px_ - 3:px_ + 4].reshape(-1, 3), axis=0)
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
            return tuple((cx - self.x0, cy - self.y0, rx, ry) for (cx, cy, rx, ry) in EYE_OVERRIDES[self.name])
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
        if self.name in HIP:
            d.line([0, HIP[self.name], self.w, HIP[self.name]], fill=(0, 255, 255), width=4)
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
    if shape == 'smirk':
        # small lopsided smile: left end lower, right end higher, tapered stroke
        w = 0.50 * s
        th = max(4.0, 0.05 * s)
        depth, tilt = 0.10 * s, 0.11 * s
        u = np.linspace(0, 1, 28)
        cy_ = depth * (1 - (2 * u - 1) ** 2) * 0.8 + tilt * (1 - u) ** 1.2
        tp = th * (0.25 + 0.75 * np.sin(np.pi * u) ** 0.5)
        xs = (u - 0.5) * w
        hh = depth + tilt + th
        off = -hh / 2
        pts = np.vstack([np.c_[xs, cy_ + off], np.c_[xs, cy_ + tp + off][::-1]])
        def fn(d, sc, cx, cy):
            poly(d, pts, DARK, sc, cx, cy, 0.4)
        return shape_sprite(fn, w + 8, hh + 8, seed)
    if shape == 'small_o':
        rx, ry = 0.085 * s, 0.10 * s
        pts = ellipse_pts(rx, ry, 32)
        def fn(d, sc, cx, cy):
            poly(d, pts, DARK, sc, cx, cy, 0.4)
        return shape_sprite(fn, 2 * rx + 8, 2 * ry + 8, seed)
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
SHOTS = None  # loaded from beats.json


def Y_frame_x(X, pup, scale, sx):
    return X + (sx - pup.ex) * scale


class Sprite:
    """A placed puppet: premult RGBA canvas (puppet + shadow), frame-space origin, eye anchors, pivot."""

    def __init__(self, role, pup, scale, X, Y, kind, shadow_off, pivot='hip'):
        self.role, self.pup, self.scale = role, pup, scale
        self.hip_y = None
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
        sa = cv2.GaussianBlur(sa, (0, 0), 5) * 0.45
        layer = np.zeros((ch, cw, 4), np.uint8)
        layer[..., 3] = np.clip(sa * 255, 0, 255).astype(np.uint8)
        over_layer(layer, canvas, 0, 0)
        # geometry in canvas coords
        self.ex = PAD + (pup.ex) * scale
        self.ey = PAD + (pup.ey) * scale
        self.eyes = [(PAD + cx * scale, PAD + cy * scale, rx * scale, ry * scale) for (cx, cy, rx, ry) in pup.eyes]
        self.spacing = pup.spacing * scale
        self.eyew = pup.eyew * scale
        self.feet_y = Y + (pup.h - pup.ey) * scale
        self.foot_cx = X + (pup.w / 2 - pup.ex) * scale
        if pup.name in HIP and pivot == 'hip':
            hy = HIP[pup.name]
            self.pivot = (PAD + pup.ex * scale, PAD + hy * scale)      # speaking motion rotates about the hips
            row = pup.alpha[max(0, hy - 30)] > 0.5
            xs_ = np.where(row)[0]
            self.hip_l = Y_frame_x(X, pup, scale, xs_.min())
            self.hip_r = Y_frame_x(X, pup, scale, xs_.max())
            self.hip_y = Y + (hy - pup.ey) * scale
            self.hip_y = Y + (hy - pup.ey) * scale
        else:
            self.pivot = (PAD + pup.ex * scale, PAD + sh)             # feet
            if pup.name in HIP:
                hy = HIP[pup.name]
                row = pup.alpha[max(0, hy - 30)] > 0.5
                xs_ = np.where(row)[0]
                self.hip_l = Y_frame_x(X, pup, scale, xs_.min())
                self.hip_r = Y_frame_x(X, pup, scale, xs_.max())
                self.hip_y = Y + (hy - pup.ey) * scale
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
            face = FACE.get(self.pup.name, {})
            spr, pad = make_mouth(shape, self.spacing * face.get('mouth_scale', 1.0), seed)
            self.mouth_cache[shape] = (spr, spr.shape[1] / 2, spr.shape[0] / 2)
        return self.mouth_cache[shape]

    def oval(self):
        """Skin-tone oval opening cut into a mask (Vince), always drawn under the mouth."""
        if getattr(self, '_oval', None) is None:
            s_ = self.spacing
            w_, h_ = 0.78 * s_, 0.42 * s_
            col = tuple(int(c) for c in self.pup.skin) + (255,)
            def fn(d, sc, cx, cy):
                d.ellipse([(cx - w_ / 2 - 1.5) * sc, (cy - h_ / 2 - 1.5) * sc, (cx + w_ / 2 + 1.5) * sc, (cy + h_ / 2 + 1.5) * sc], fill=(70, 45, 30, 255))
                d.ellipse([(cx - w_ / 2) * sc, (cy - h_ / 2 + 1.0) * sc, (cx + w_ / 2) * sc, (cy + h_ / 2) * sc], fill=col)
            spr, pad = shape_sprite(fn, w_ + 6, h_ + 6, shash(self.pup.name, 'oval'), shadow=(1, 2))
            self._oval = (spr, spr.shape[1] / 2, spr.shape[0] / 2)
        return self._oval


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
    def bg(self, name, crop=None):
        key = (name, crop)
        if key in self.bgs:
            return self.bgs[key]
        c = Image.open(asset_path(name)).convert('RGB').resize((W + 8, H + 8), Image.LANCZOS)
        a = np.asarray(c)
        self.bgs[key] = a
        return a

    def seat_plate(self, name, S, Yh, Xc, shadows):
        """Close furniture plate scaled about its seat line so that the seat top surface sits at frame y = Yh.
        S = seat top surface fraction of image height. shadows = [(x0, x1, ry)] contact shadows at the hips."""
        im = Image.open(asset_path(name)).convert('RGB')
        iw, ih = im.size
        k = max((Yh + 6) / (S * ih), (W + 10) / iw, (H + 10) / ih)
        pw, ph = int(round(iw * k)), int(round(ih * k))
        py = int(round(Yh - S * ih * k))
        px = int(round(Xc - iw / 2 * k))
        px = min(-5, max(px, W + 5 - pw))
        a = np.asarray(im.resize((pw, ph), Image.LANCZOS))
        arr = a[-4 - py:H + 4 - py, -4 - px:W + 4 - px]
        assert arr.shape[:2] == (H + 8, W + 8), (arr.shape, py, px, k)
        arr = cv2.GaussianBlur(arr, (0, 0), 2.5).astype(np.float32)
        yy, xx = np.mgrid[0:H + 8, 0:W + 8].astype(np.float32)
        m = np.zeros((H + 8, W + 8), np.float32)
        for (x0, x1, ry) in shadows:
            cx, cy = (x0 + x1) / 2 + 4, Yh + ry * 0.35 + 4
            rx = (x1 - x0) / 2 * 0.95
            m = np.maximum(m, np.clip(1 - (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2), 0, 1))
        m = cv2.GaussianBlur(m, (0, 0), 9)
        arr = arr * (1 - 0.55 * m[..., None] * np.array([0.9, 1.0, 1.0], np.float32))
        return np.clip(arr, 0, 255).astype(np.uint8), k

    def plate_fill(self, name, Xc, blur=2.5):
        """Plate scaled to fill the frame (top aligned), lightly blurred. Returns (arr, k, py)."""
        im = Image.open(asset_path(name)).convert('RGB')
        iw, ih = im.size
        k = max((W + 10) / iw, (H + 10) / ih)
        pw, ph = int(round(iw * k)), int(round(ih * k))
        py = -5
        px = int(round(Xc - iw / 2 * k))
        px = min(-5, max(px, W + 5 - pw))
        a = np.asarray(im.resize((pw, ph), Image.LANCZOS))
        arr = a[-4 - py:H + 4 - py, -4 - px:W + 4 - px]
        assert arr.shape[:2] == (H + 8, W + 8), arr.shape
        return cv2.GaussianBlur(arr, (0, 0), blur), k, py

    def get_puppet(self, name):
        if name not in self.puppets:
            self.puppets[name] = Puppet(name, eyes=(not name.startswith('table')))
        return self.puppets[name]


SEAT = {'sofa': ('bg_sofa_close', 0.597), 'chair': ('bg_chair_close', 0.612)}
# wide shot (bg_wide in 1080x1920 coordinates, read from the plate): seat-top line, head x, puppet scale
WIDE = {'D': ('sofa', 1132, 215, 0.34), 'K': ('sofa', 1132, 395, 0.33), 'L': ('chair', 1128, 715, 0.29), 'T': ('chair', 1128, 900, 0.35)}
TABLE_SURFACE_Y = 1280   # frame y of the table-top centre in the wide shot (visible above the caption)


def layout_ep01(scene, shot):
    """Returns dict with bg array and list of (role, Sprite) in draw order, plus table."""
    if shot in scene.sprites:
        return scene.sprites[shot]
    sp = scene.spec['shots'][shot]
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': []}
    cast = sp['cast']
    if shot == 'wide':
        shadows = []
        for role in ('D', 'K', 'L', 'T'):
            if role not in cast:
                continue
            pup = scene.get_puppet(cast[role])
            _, Yh, X, scale = WIDE[role]
            Y = Yh - (HIP[pup.name] - pup.ey) * scale
            spr = Sprite(role, pup, scale, X, Y, 'wide', (4, 5))
            out['sprites'].append((role, spr))
            shadows.append((spr.hip_l + 8, spr.hip_r - 8, 7))
        arr = scene.bg('bg_wide', None).astype(np.float32)
        yy, xx = np.mgrid[0:H + 8, 0:W + 8].astype(np.float32)
        m = np.zeros((H + 8, W + 8), np.float32)
        for (x0, x1, ry) in shadows:
            cx, cy = (x0 + x1) / 2 + 4, 1130 + 4 + 3
            m = np.maximum(m, np.clip(1 - (((xx - cx) / ((x1 - x0) / 2)) ** 2 + ((yy - cy) / ry) ** 2), 0, 1))
        m = cv2.GaussianBlur(m, (0, 0), 4)
        arr = arr * (1 - 0.5 * m[..., None])
        out['bg'] = np.clip(arr, 0, 255).astype(np.uint8)
        t = scene.get_puppet('table')
        sc = 0.50 * W / t.w
        out['table'] = Sprite('table', t, sc, 0.5 * W, TABLE_SURFACE_Y - 0.43 * t.h * sc, 'table', (5, 7))
        scene.sprites[shot] = out
        return out
    single = len(cast) == 1
    side_chair = any(c in ('L', 'T') for c in cast)
    plate, S = SEAT['chair' if side_chair else 'sofa']
    if single:
        role = list(cast)[0]
        pup = scene.get_puppet(cast[role])
        spr = fit_sprite(role, pup, 0.48 * W, 680, out['notes'], eye_y=800)
        out['sprites'].append((role, spr))
        Xc = spr.X
        shadows = [(spr.hip_l, spr.hip_r, 22)]
        Yh = spr.hip_y
    else:
        DUO_YH = 1260
        for role, X in zip(list(cast), (0.28 * W, 0.70 * W)):
            pup = scene.get_puppet(cast[role])
            out['sprites'].append((role, fit_sprite(role, pup, X, 420, out['notes'], hip_y=DUO_YH, max_shift=80)))
        shadows = [(r_[1].hip_l, r_[1].hip_r, 14) for r_ in out['sprites']]
        Xc, Yh = 0.5 * W, DUO_YH
    out['bg'], k = scene.seat_plate(plate, S, Yh, Xc, shadows)
    out['notes'].append(f'plate {plate} scale {k:.3f}, seat line y={Yh:.0f}')
    scene.sprites[shot] = out
    return out


def layout_shot(scene, shot):
    if shot in scene.sprites:
        return scene.sprites[shot]
    return {'ep02_on_hold': layout_ep02, 'ep03_apology': layout_ep03}.get(EPNAME, layout_ep01)(scene, shot)


def blob_shadows(arr, items, blur=6):
    """Darken arr (uint8 HxWx3, with 4 px margin) with soft ellipses: items = [(cx, cy, rx, ry, strength)] in frame coords."""
    a = arr.astype(np.float32)
    m = np.zeros(arr.shape[:2], np.float32)
    yy, xx = np.mgrid[0:arr.shape[0], 0:arr.shape[1]].astype(np.float32)
    for (cx, cy, rx, ry, st) in items:
        m = np.maximum(m, st * np.clip(1 - (((xx - cx - 4) / rx) ** 2 + ((yy - cy - 4) / ry) ** 2), 0, 1))
    m = cv2.GaussianBlur(m, (0, 0), blur)
    return np.clip(a * (1 - m[..., None]), 0, 255).astype(np.uint8)


BENCH_S = 0.646            # bg_bench_close: seat-top fraction of plate height (read from the plate)
TELLER_FG_NATIVE_Y = 1190  # bg_teller_close: y (native px) where the near red counter section begins
# wide bank (native 941x1671 plate -> frame x1.148): bench seat-top y~1070, counter x 586-941 y 935-1255
FY = 1920 / 1671.0
FX = 1080 / 941.0


def layout_ep02(scene, shot):
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': [], 'items': None}
    cast = scene.spec['shots'][shot]['cast']
    P = lambda r: scene.get_puppet(cast[r])
    if shot == 'v':
        spr = fit_sprite('V', P('V'), 0.46 * W, 640, out['notes'], eye_y=800, pivot='hip')
        out['sprites'].append(('V', spr))
        out['bg'], k, py = scene.plate_fill('bg_bank_close', 0.5 * W)
    elif shot == 'c':
        spr = fit_sprite('C', P('C'), 0.48 * W, 600, out['notes'], eye_y=800)
        out['sprites'].append(('C', spr))
        out['bg'], k = scene.seat_plate('bg_bench_close', BENCH_S, spr.hip_y, spr.X, [(spr.hip_l, spr.hip_r, 22)])
    elif shot == 'd':
        spr = fit_sprite('D', P('D'), 0.5 * W, 680, out['notes'], eye_y=800, arm_fit=False)
        out['sprites'].append(('D', spr))
        out['bg'], k, py = scene.plate_fill('bg_teller_close', 0.5 * W)
        yfg = int(round(TELLER_FG_NATIVE_Y * k + py))
        out['items'] = [('s', 'D', spr), ('fg', (0, yfg, W, H))]
        out['notes'].append(f'counter foreground crop from y={yfg}')
    elif shot == 'wide':
        seat = 1070 * FY
        seated = [('H1', 92, 0.27), ('H2', 240, 0.27), ('C', 392, 0.27)]
        items, shadows, bench = [], [], []
        for role, X, sc in seated:
            pup = P(role)
            Y = seat - (HIP[pup.name] - pup.ey) * sc
            spr = Sprite(role, pup, sc, X, Y, 'wide', (4, 5))
            bench.append((role, spr))
            shadows.append((spr.hip_l + 5, spr.hip_r - 5, 0, 0, 0))
            shadows[-1] = ((spr.hip_l + spr.hip_r) / 2, seat + 3, (spr.hip_r - spr.hip_l) / 2 * 0.95, 7, 0.5)
        pd = P('D')
        sd = 0.33
        dspr = Sprite('D', pd, sd, 880, 840, 'wide', (4, 5))
        vp = P('V')
        sv = 0.45
        feet = 1585
        vY = feet - (vp.h - vp.ey) * sv
        vspr = Sprite('V', vp, sv, 685, vY, 'wide', (6, 8), pivot='feet')
        shadows.append((vspr.foot_cx, feet - 6, 0.62 * vspr.fig_w / 2, 20, 0.6))
        arr = scene.bg('bg_bank_wide')
        out['bg'] = blob_shadows(arr, shadows, blur=5)
        fg = (int(586 * FX), int(935 * FY), W, int(1255 * FY))
        out['items'] = [('s', r, sp_) for r, sp_ in bench] + [('s', 'D', dspr), ('fg', fg), ('s', 'V', vspr)]
        out['sprites'] = [(r, sp_) for r, sp_ in bench] + [('D', dspr), ('V', vspr)]
        for r, sp_ in out['sprites']:
            out['notes'].append(f'{r}: head {sp_.pup.headw * sp_.scale:.0f}px, eye y {sp_.pup.ey * 0 + sp_.oy + sp_.ey:.0f}, feet y {sp_.feet_y:.0f}')
    else:
        raise KeyError(shot)
    out['notes'].append(f'{shot}: laid out')
    scene.sprites[shot] = out
    return out


def layout_ep03(scene, shot):
    """ep03: three men STAND on the floor in front of the sofa (close plate) / on the rug (wide plate)."""
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': [], 'items': None}
    cast = scene.spec['shots'][shot]['cast']
    P = lambda r: scene.get_puppet(cast[r])
    FLOOR = 1895           # close plate: floor line in front of the sofa (sofa legs end ~1610)

    def place(role, pup, s, X, feet):
        Y = feet - (pup.h - pup.ey) * s
        spr = Sprite(role, pup, s, X, Y, 'single', (6, 8), pivot='feet')
        out['sprites'].append((role, spr))
        out['notes'].append(f'{role}/{pup.name}: head {pup.headw * s:.0f}px, scale {s:.3f}, eye y {Y:.0f}, feet y {spr.feet_y:.0f}, bbox x {X - pup.ex * s:.0f}..{X + (pup.w - pup.ex) * s:.0f}')
        return spr

    if shot == 'wide':
        feet, s = 1405, 0.55
        arr = scene.bg('bg_party_wide')
        sh = []
        for role, X in (("M", 215), ("R", 620), ("N", 850)):
            spr = place(role, P(role), s, X, feet)
            sh.append((spr.foot_cx, feet - 4, 0.34 * spr.fig_w, 13, 0.55))
        out['bg'] = blob_shadows(arr, sh, blur=5)
        t = scene.get_puppet('table_cake')
        sc = 560 / t.w
        out['table'] = Sprite('table', t, sc, 0.5 * W, 1440 - t.h * sc, 'table', (5, 7))
        out['notes'].append(f'table {t.w * sc:.0f}x{t.h * sc:.0f} bottom y 1440 (legs under caption)')
    else:
        bg, k, py = scene.plate_fill('bg_party_close', 0.5 * W, blur=2.5)
        sh = []
        if shot in ('r', 'n'):
            role = list(cast)[0]
            pup = P(role)
            headw = 480 if shot == 'n' else 650      # ep03: Neil's solo shot is smaller, full head in frame
            out['sprites'].append((role, fit_sprite(role, pup, 0.5 * W, headw, out['notes'], eye_y=760, pivot='feet')))
        elif shot in ('m', 'm_jump'):
            pm, pj = scene.get_puppet('marcus'), scene.get_puppet('marcus_jump')
            s = min((W - 30) / pm.w, (W - 30) / pj.w)        # whole figure incl. selfie stick must stay in frame
            pup = pm if shot == 'm' else pj
            X = W / 2 - (pup.w / 2 - pup.ex) * s
            if shot == 'm':
                spr = place('M', pup, s, X, FLOOR)
                sh.append((spr.foot_cx, FLOOR - 10, 0.30 * spr.fig_w, 24, 0.55))
            else:
                ey_m = FLOOR - (pm.h - pm.ey) * s
                c_m = ey_m + (pm.h / 2 - pm.ey) * s          # standing body-centre y
                ey_j = c_m - 100 - (pj.h / 2 - pj.ey) * s     # body centre 100 px higher
                spr = Sprite('M', pup, s, X, ey_j, 'single', (6, 8), pivot='feet')
                out['sprites'].append(('M', spr))
                out['notes'].append(f'M/marcus_jump: scale {s:.3f}, head {pj.headw * s:.0f}px, eye y {ey_j:.0f}, feet y {spr.feet_y:.0f}, stick top y {ey_j - pj.ey * s:.0f}, bbox x {X - pj.ex * s:.0f}..{X + (pj.w - pj.ex) * s:.0f}')
                sh.append((X + 10, FLOOR - 55, 0.40 * spr.fig_w, 30, 0.70))
        else:   # rn
            pr, pn = P('R'), P('N')
            s = 0.90
            feet = 1800
            for role, pup, X in (('R', pr, 370), ('N', pn, 790)):
                spr = place(role, pup, s, X, feet)
                rx = 0.38 * spr.fig_w if role == 'R' else 0.32 * spr.fig_w
                sh.append((spr.foot_cx, feet - 8, rx, 20, 0.55))
        out['bg'] = blob_shadows(bg, sh, blur=8) if sh else bg
    out['notes'].append(f'{shot}: laid out')
    scene.sprites[shot] = out
    return out


def fit_sprite(role, pup, X, headw, notes, eye_y=None, hip_y=None, max_shift=None, arm_fit=True, pivot='hip'):
    scale = headw / pup.headw
    # keep raised arm / body edges in frame: left extent from head centre
    left_ext = pup.ex * scale
    margin = 16
    right_lim = W - 130 - headw / 2 - 10
    if arm_fit and X - left_ext < margin:
        X2 = min(X + (margin - (X - left_ext)), max(X, right_lim), X + (max_shift if max_shift is not None else 1e9))
        if X2 - left_ext < margin:
            scale = (X2 - margin) / pup.ex
            notes.append(f'{role}/{pup.name}: shifted X {X:.0f}->{X2:.0f}, scale {headw / pup.headw:.3f}->{scale:.3f} (head {pup.headw * scale:.0f}px) to keep arm in frame')
        else:
            notes.append(f'{role}/{pup.name}: shifted X {X:.0f}->{X2:.0f} to keep arm in frame')
        X = X2
    off = (HIP[pup.name] - pup.ey) * scale if pup.name in HIP else 0.0   # eye line -> hip line, frame px
    Y = eye_y if eye_y is not None else hip_y - off
    spr = Sprite(role, pup, scale, X, Y, 'single', (6, 8), pivot=pivot)
    spr.X = X
    notes.append(f'{role}/{pup.name}: head {pup.headw * scale:.0f}px, eye y {Y:.0f}, hip y {Y + off:.0f}')
    return spr


# --------------------------------------------------------------------------------------
# audio / timeline
# --------------------------------------------------------------------------------------
def phone_filter(d):
    """Telephone: band-pass 300-3400 Hz plus light compression."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, [300, 3400], btype='bandpass', fs=SR, output='sos')
    y = sosfilt(sos, d.astype(np.float64))
    pk = max(np.abs(y).max(), 1e-6)
    y = y / pk
    y = np.tanh(2.2 * y) / np.tanh(2.2)        # light compression / soft clip
    rms_in = math.sqrt(float((d ** 2).mean())) + 1e-9
    rms_out = math.sqrt(float((y ** 2).mean())) + 1e-9
    y *= rms_in / rms_out                       # keep the level the voice had
    return np.clip(y, -0.98, 0.98).astype(np.float32)


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
            src = f"{AUDIO}/{m['file']}"
            if src not in wavs:
                sr, d = wavfile.read(src)
                assert sr == SR, (src, sr)
                d = d.astype(np.float32) / 32768 if d.dtype == np.int16 else d.astype(np.float32)
                if d.ndim > 1:
                    d = d.mean(axis=1)
                wavs[src] = d
            d = wavs[src]
            env_src = d
            if spec['voices'].get(b.get('say'), {}).get('phone'):
                d = phone_filter(d)
            adur = len(d) / SR
            dur = adur + float(b.get('after', 0))
            entry['audio'] = d
            entry['adur'] = adur
            entry['env'] = envelope(env_src)
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
        def _fit(max_lines):
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
                if len(lines) <= max_lines or size < 40:
                    return size, lines
                size -= 2
        size, lines = _fit(2)
        if EPNAME == 'ep03_apology' and size < 48:
            size, lines = _fit(3)     # ep03 only: allow 3 lines rather than shrink a 2-line caption below 48 px
        f = font(FONT_BOLD, size)
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
        phone = self.spec['voices'].get(self.tl[i]['beat'].get('say'), {}).get('phone')
        d.polygon([(x * SSc, y * SSc) for x, y in pts], fill=(188, 225, 219, 255) if phone else (243, 231, 203, 255))
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
    def make_title(self, text='GAME NIGHT'):
        if not hasattr(self, '_titles'):
            self._titles = {}
        if text in self._titles:
            return self._titles[text]
        if text == 'GAME NIGHT':
            lines = ['GAME', 'NIGHT']
        elif text == 'FOUR HOURS LATER':
            lines = ['FOUR HOURS', 'LATER']
        else:
            lines = text.split(' ')
        bgc = np.array([58, 38, 27], np.float32)
        tex = paper_texture(H, W, 5, 0.05)
        bg = (bgc * tex[..., None])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        bg *= (1 - 0.3 * np.clip(r - 0.3, 0, None))[..., None]
        bg = np.clip(bg, 0, 255).astype(np.uint8)
        letters = []
        cols = [(243, 229, 196), (240, 222, 186), (246, 233, 204), (238, 220, 190)]
        rng = np.random.default_rng(11 if text == 'GAME NIGHT' else 11 + shash(text) % 1000)
        ys = [740, 1080] if len(lines) == 2 else [900]
        for word, cy in zip(lines, ys):
            size = 330 if len(word) <= 4 else 300
            f = font(FONT_HEAVY, size)
            adv = [f.getlength(c) for c in word]
            tot = sum(adv)
            scl = 920 / tot
            if EPNAME != 'ep01_game_night':
                scl = min(scl, 1.25)      # short words ("ON") must not blow up
            f = font(FONT_HEAVY, int(size * scl))
            adv = [f.getlength(c) for c in word]
            tot = sum(adv)
            x = W / 2 - tot / 2
            for k, c in enumerate(word):
                if c == ' ':
                    x += adv[k]
                    continue
                bw = int(adv[k] + 160)
                bh = int(f.size * 1.5)
                big = Image.new('L', (bw * 2, bh * 2), 0)
                ImageDraw.Draw(big).text((bw, bh), c, font=font(FONT_HEAVY, f.size * 2), fill=255, anchor='mm')
                m = np.asarray(big.resize((bw, bh), Image.LANCZOS)).astype(np.float32) / 255
                r2 = np.random.default_rng(900 + len(letters))
                dx = cv2.GaussianBlur(r2.standard_normal((bh, bw)).astype(np.float32), (0, 0), 9) * 6
                dy = cv2.GaussianBlur(r2.standard_normal((bh, bw)).astype(np.float32), (0, 0), 9) * 6
                gx, gy = np.meshgrid(np.arange(bw, dtype=np.float32), np.arange(bh, dtype=np.float32))
                m = cv2.remap(m, gx + dx, gy + dy, cv2.INTER_LINEAR)
                m = np.clip((m - 0.5) * 6 + 0.5, 0, 1)
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
        self._titles[text] = (bg, letters)
        return self._titles[text]

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
        if shot in ('title', 'card'):
            bg, letters = self.make_title(b.get('text', 'GAME NIGHT'))
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
        bgview = fr.copy()
        tilt = b.get('tilt', {})
        for item in (lay.get('items') or [('s', r_, s_) for r_, s_ in lay['sprites']]):
            if item[0] == 'fg':
                x0, y0, x1, y1 = item[1]
                fr[y0:y1, x0:x1] = bgview[y0:y1, x0:x1]
                continue
            role, spr = item[1], item[2]
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
            if hold and len(lay['sprites']) == 1:
                rest = b.get('mouth_rest', rest)
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
            face = FACE.get(spr.pup.name, {})
            mcx = spr.ex
            mcy = spr.ey + face.get('mouth_dy', 1.1) * spr.eyew
            if face.get('oval'):
                os_, ox_, oy_ = spr.oval()
                over_layer(fr_layer, os_, int(round(mcx - ox_)), int(round(mcy - oy_)))
            over_layer(fr_layer, ms, int(round(mcx - mx)), int(round(mcy - my)))
            # ---- motion
            r = np.random.default_rng(shash(role, pair))
            amp_p, amp_a = (0.5, 0.05) if hold else (1.5, 0.2)
            jx, jy = r.uniform(-amp_p, amp_p, 2)
            ja = r.uniform(-amp_a, amp_a)
            dy, ang = 0.0, 0.0
            if role == say:
                dy = -0.01 * H * min(1.0, lev)
                if shot == 'm_jump':
                    dy -= 62 * min(1.0, lev)      # hop: rises with loudness, lands in the quiet
                sgn = 1 if math.sin(aidx * 2.3 + 0.7) > 0 else -1
                ang = 1.5 * min(1.0, lev) * sgn
            if role in tilt_to:
                ang += tilt_to[role] * p
            if role in tilt:
                ang += tilt[role]
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


def door_knock(sr=SR):
    """Three firm low wooden knocks on a door."""
    rng = np.random.default_rng(41)
    out = np.zeros(int(1.0 * sr), np.float32)
    for k, t0 in enumerate((0.0, 0.27, 0.54)):
        n = int(0.22 * sr)
        t = np.arange(n) / sr
        body = (np.sin(2 * np.pi * 150 * t) * np.exp(-t / 0.045) + 0.6 * np.sin(2 * np.pi * 235 * t) * np.exp(-t / 0.03)
                + 0.35 * np.sin(2 * np.pi * 410 * t) * np.exp(-t / 0.015))
        nz = rng.standard_normal(n).astype(np.float32)
        nz = cv2.GaussianBlur(nz.reshape(1, -1), (0, 0), sigmaX=6).ravel()
        click = nz * np.exp(-t / 0.008) * 4.0
        x = (body + click).astype(np.float32)
        x[:40] *= np.linspace(0, 1, 40)
        x *= 0.9 * (1.0 if k < 2 else 0.95)
        i = int(t0 * sr)
        out[i:i + n] += x
    return out * 0.8


def hold_music_loop(sr=SR):
    """Cheesy, cheerful bossa-style hold music: 4 bars of C major (Cmaj7 - Am7 - Dm7 - G7) at 124 bpm."""
    bpm = 124
    beat = 60 / bpm
    bars = 4
    n = int(bars * 4 * beat * sr)
    out = np.zeros(n + sr)
    def mtof(m):
        return 440 * 2 ** ((m - 69) / 12)
    def add(t0, dur, freq, amp, kind):
        i0 = int(t0 * sr)
        L = int(min(dur * 1.0 + 0.25, 1.2) * sr)
        t = np.arange(L) / sr
        if kind == 'lead':        # plasticky square-ish lead with vibrato
            ph = 2 * np.pi * freq * t + 0.012 * np.sin(2 * np.pi * 5.5 * t) * (t > 0.12)
            x = np.sign(np.sin(ph)) * 0.35 + np.sin(ph) * 0.5 + np.sin(2 * ph) * 0.12
            env = np.minimum(1, t / 0.006) * np.exp(-np.maximum(t - dur * 0.7, 0) / 0.06) * (1 - 0.35 * np.clip(t / dur, 0, 1))
        elif kind == 'bass':
            x = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
            env = np.minimum(1, t / 0.004) * np.exp(-t / 0.28)
        else:                     # electric-piano stab
            x = np.sin(2 * np.pi * freq * t) + 0.45 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t / 0.08) + 0.15 * np.sin(2 * np.pi * freq * 3 * t)
            env = np.minimum(1, t / 0.003) * np.exp(-t / 0.18)
        seg = x * env * amp
        out[i0:i0 + L] += seg[:max(0, min(L, len(out) - i0))]
    chords = [(48, [64, 67, 71, 74]), (45, [60, 64, 67, 72]), (50, [62, 65, 69, 72]), (43, [62, 65, 67, 71])]
    for b, (root, notes) in enumerate(chords):
        base = b * 4 * beat
        for bt, pitch in ((0, root), (1.5, root + 7), (2, root), (3.5, root + 7)):
            add(base + bt * beat, 0.45 * beat * 2, mtof(pitch), 0.55, 'bass')
        for bt in (0.5, 1.5, 3):
            for nt in notes:
                add(base + bt * beat, 0.5 * beat, mtof(nt), 0.11, 'comp')
    mel = [
        (0, .5, 76), (.5, .5, 79), (1, 1, 84), (2, .5, 83), (2.5, .5, 81), (3, 1, 79),
        (4, .5, 81), (4.5, .5, 84), (5, 1, 88), (6, .5, 86), (6.5, .5, 84), (7, 1, 81),
        (8, .5, 77), (8.5, .5, 81), (9, 1, 86), (10, .5, 84), (10.5, .5, 83), (11, 1, 81),
        (12, .5, 79), (12.5, .5, 83), (13, .5, 86), (13.5, .5, 89), (14, 1, 88), (15, .5, 86), (15.5, .5, 79)]
    for bt, d, m in mel:
        add(bt * beat, d * beat * 0.9, mtof(m), 0.30, 'lead')
    rng = np.random.default_rng(21)
    for k in range(bars * 8):                      # shaker on the eighths
        t0 = k * beat / 2
        i0 = int(t0 * sr)
        L = int(0.05 * sr)
        nz = np.diff(rng.standard_normal(L + 1)) * np.exp(-np.arange(L) / (0.012 * sr))
        out[i0:i0 + L] += nz * (0.10 if k % 2 == 0 else 0.06)
    loop = out[:n].copy()
    loop[:200] *= np.linspace(0, 1, 200)
    loop /= math.sqrt(float((loop ** 2).mean())) + 1e-9
    return loop.astype(np.float32)             # unit RMS


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
        elif s == 'door_knock':
            k0 = int((e['start'] + e['adur']) * SR)
            kn = door_knock()
            mix[k0:k0 + len(kn)] += kn[:max(0, min(len(kn), n - k0))]
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
    # hold music (ep02): from music_start to music_stop_click, telephone band-passed
    m_start = next((e['start'] for e in tl if e['beat'].get('sfx') == 'music_start'), None)
    m_stop = next((e['start'] for e in tl if e['beat'].get('sfx') == 'music_stop_click'), None)
    if m_start is not None and m_stop is not None:
        i0, i1 = int(m_start * SR), int(m_stop * SR)
        loop = hold_music_loop()
        mus = np.tile(loop, (i1 - i0) // len(loop) + 2)[:i1 - i0]
        mus = phone_filter(mus)
        g = np.full(i1 - i0, 10 ** (-26 / 20), np.float32)
        for e in tl:
            if 'hold' in e['beat'] or e['beat']['shot'] in ('card', 'title'):
                a_, b_ = int((e['start'] - m_start) * SR), int((e['start'] + e['dur'] - m_start) * SR)
                g[max(a_, 0):max(min(b_, len(g)), 0)] = 10 ** (-15 / 20)
        k = int(0.06 * SR)
        g = np.convolve(np.pad(g, (k, k), mode='edge'), np.ones(k) / k, 'same')[k:-k]
        mix[i0:i1] += mus * g
        rngc = np.random.default_rng(5)                # small line click as the music is cut
        cl = np.zeros(int(0.02 * SR), np.float32)
        cl[:6] = [0.5, -0.35, 0.2, -0.1, 0.05, 0]
        cl += rngc.standard_normal(len(cl)).astype(np.float32) * np.exp(-np.arange(len(cl)) / (0.002 * SR)) * 0.08
        mix[i1:i1 + len(cl)] += cl * 0.6
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
    ap.add_argument('--ep', default='ep01_game_night')
    ap.add_argument('--out', default=None)
    ap.add_argument('--timeline-only', action='store_true')
    a = ap.parse_args()
    configure(a.ep)
    if a.out is None:
        a.out = OUT_MP4
    os.makedirs(BUILD, exist_ok=True)
    STILLS = f'{BUILD}/stills' if a.ep == 'ep01_game_night' else f'{BUILD}/stills_{a.ep}'
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
        sheet.save(f'{BUILD}/eye_debug_{a.ep}.png')
        print('wrote', f'{BUILD}/eye_debug_{a.ep}.png')
        return
    if a.stills or a.sheet:
        os.makedirs(STILLS, exist_ok=True)
        if a.stills:
            for ts in a.stills.split(','):
                T = float(ts)
                ta, aidx, bi = snap_state(R, T)
                fr = R.frame(ta, aidx)
                p = f'{STILLS}/t{T:07.3f}.jpg'
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
                p = f'{STILLS}/sheet_{k // per + 1}.jpg'
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

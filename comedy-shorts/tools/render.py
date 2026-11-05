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
    # ep06: new assets first, then the no-selfie-stick Marcus (assets_leads), then older plates (bg_sofa_close).
    # WW_EXTRA_ASSETS=dir1:dir2 appends fallback dirs (placeholder tests only; real assets always win).
    # end_tag: appended once after the body (concat, ep06 only), first end_tag_secs seconds of brand/end_tag.mp4.
    'ep06_grandfather_auto': dict(assets=[f'{ROOT}/assets_ep06', f'{ROOT}/assets_leads', f'{ROOT}/assets'], audio=f'{ROOT}/audio_ep06', out=f'{BUILD}/grandfather_v1_phone.mp4',
                                  end_tag=f'{SHORTS}/brand/end_tag.mp4', end_tag_secs=1.5),
    # ep07 (I Voted): same room / puppets as ep06. The end_tag beat in beats.json is a placeholder: it is dropped from the body
    # (skip_shots) and the real end card is concatenated once (end_tag), so the card is never doubled.
    'ep07_i_voted': dict(assets=[f'{ROOT}/assets_ep07', f'{ROOT}/assets_ep06', f'{ROOT}/assets_ep03', f'{ROOT}/assets_leads', f'{ROOT}/assets'],
                         audio=f'{ROOT}/audio_ep07', out=f'{BUILD}/ivoted_v1_phone.mp4',
                         end_tag=f'{SHORTS}/brand/end_tag.mp4', end_tag_secs=1.5, skip_shots=('end_tag',), limit=0.80),
}
# puppet-name aliases per episode (beats.json says 'russell', the ep06 seated Russell art is russell_s1)
PUPPET_ALIAS = {'ep07_i_voted': {'russell': 'russell_s1'}}
# set by configure()
EPNAME = 'ep01_game_night'
BEATS = AUDIO = OUT_MP4 = None
ASSET_DIRS = []


def configure(ep):
    global EPNAME, BEATS, AUDIO, OUT_MP4, ASSET_DIRS
    if ep not in EPCFG:
        raise SystemExit(f'unknown episode {ep}; known: {list(EPCFG)}')
    c = EPCFG[ep]
    EPNAME, BEATS, AUDIO, OUT_MP4, ASSET_DIRS = ep, f'{SHORTS}/{ep}/beats.json', c['audio'], c['out'], list(c['assets'])
    ASSET_DIRS += [d for d in os.environ.get('WW_EXTRA_ASSETS', '').split(':') if d]


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
# Per-episode overrides, looked up before the global tables so older episodes are untouched.
# ep06: Marcus without selfie stick; new jump image; new box / sofa puppets are auto-detected unless measured here.
EYE_OVERRIDES_EP = {
    'ep06_grandfather_auto': {'marcus_jump': [(438, 468, 72, 72), (575, 430, 72, 72)],
                              'marcus_box': [(468, 680, 62, 62), (587, 655, 58, 58)],
                              'neil_box': [(407, 367, 53, 28), (550, 356, 50, 24)]},
    'ep07_i_voted': {'marcus_door': [(436, 459, 62, 62), (557, 430, 59, 59)]},
}
# HIP_EP: absolute source y (inside the cropped puppet). HIP_FRAC_EP: fraction of the cropped puppet height (used until
# a puppet is measured; run `render.py --ep ep06_grandfather_auto --eyes` and read the cyan hip line, then pin it in HIP_EP).
# ep06 Russell hip (cropped coords) = top edge of the plaid blanket (lap) for all four stages, so the seat line and the
# position of the figure are identical in s1..s4 (v2: s1/s2 used to sit 64 px lower).
HIP_EP = {'ep06_grandfather_auto': {'russell_s1': 860, 'russell_s2': 860, 'russell_s3': 860, 'russell_s4': 860},
          'ep07_i_voted': {'russell_s1': 860}}
HIP_FRAC_EP = {
    # russell_s1..s4 (seated, cropped at the shins): hip = where the shirt hem meets the thighs, ~70% down. Others: same default until measured.
    'ep06_grandfather_auto': {n: 0.70 for n in ('russell_s1', 'russell_s2', 'russell_s3', 'russell_s4', 'marcus_box', 'neil_box',
                                                  'marcus_jump', 'marcus', 'russell', 'neil')},
}
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
FONT_DIDOT_BOLD = ('/System/Library/Fonts/Supplemental/Didot.ttc', 2)   # ep06 cover title (not the GTA face)


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
        self.hip = HIP_EP.get(EPNAME, {}).get(name)
        if self.hip is None and name in HIP_FRAC_EP.get(EPNAME, {}):
            self.hip = int(round(HIP_FRAC_EP[EPNAME][name] * self.h))
        if self.hip is None:
            self.hip = HIP.get(name)
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
        ov = EYE_OVERRIDES_EP.get(EPNAME, {}).get(self.name) or EYE_OVERRIDES.get(self.name)
        if ov:
            return tuple((cx - self.x0, cy - self.y0, rx, ry) for (cx, cy, rx, ry) in ov)
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
        # second pass (only when the strict one finds nothing, so existing puppets keep their detection): tilted heads
        for tol in (0.25, 0.45, 0.6):
            for i in range(len(cands)):
                for j in range(i + 1, len(cands)):
                    A, B = cands[i], cands[j]
                    if abs(A[2] - B[2]) < tol * max(A[4], B[4]) * 2 and 0.6 < A[0] / B[0] < 1.6:
                        best = (A, B)
                        break
                if best:
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
        if self.hip is not None:
            d.line([0, self.hip, self.w, self.hip], fill=(0, 255, 255), width=4)
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

    def __init__(self, role, pup, scale, X, Y, kind, shadow_off, pivot='hip', top_extra=0):
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
        if pup.hip is not None and pivot == 'hip':
            hy = pup.hip
            self.pivot = (PAD + pup.ex * scale, PAD + hy * scale)      # speaking motion rotates about the hips
            row = pup.alpha[max(0, hy - 30)] > 0.5
            xs_ = np.where(row)[0]
            self.hip_l = Y_frame_x(X, pup, scale, xs_.min())
            self.hip_r = Y_frame_x(X, pup, scale, xs_.max())
            self.hip_y = Y + (hy - pup.ey) * scale
            self.hip_y = Y + (hy - pup.ey) * scale
        else:
            self.pivot = (PAD + pup.ex * scale, PAD + sh)             # feet
            if pup.hip is not None:
                hy = pup.hip
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
        if top_extra:                                   # ep07 door jump: extra transparent rows above the canvas so the warped
            E = int(top_extra)                          # figure is not cut by a hard canvas edge while it flies in
            self.canvas = np.pad(self.canvas, ((E, 0), (0, 0), (0, 0)))
            self.oy -= E
            self.ey += E
            self.eyes = [(cx, cy + E, rx, ry) for (cx, cy, rx, ry) in self.eyes]
            self.pivot = (self.pivot[0], self.pivot[1] + E)
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


def _lid_sprite(rx, ry, skin, seed):
    """Closed eye: a skin-coloured lid covering the eye white, with a dark downward arc (like a sleeping eye)."""
    w_, h_ = 2 * rx * 1.04, 2 * ry * 1.04
    col = tuple(int(c) for c in skin) + (255,)
    ink = (62, 30, 26, 255)
    def fn(d, sc, cx, cy):
        d.ellipse([(cx - w_ / 2) * sc, (cy - h_ / 2) * sc, (cx + w_ / 2) * sc, (cy + h_ / 2) * sc], fill=col)
        lw = max(3.0, 0.11 * ry)
        for u in np.linspace(-0.62, 0.62, 40):
            x = cx + u * rx
            y = cy + 0.02 * ry + 0.36 * ry * (1 - (u / 0.62) ** 2) * 0.9
            rr = lw * (0.5 + 0.5 * (1 - abs(u / 0.62) ** 2))
            d.ellipse([(x - rr / 2) * sc, (y - rr / 2) * sc, (x + rr / 2) * sc, (y + rr / 2) * sc], fill=ink)
    spr, pad = shape_sprite(fn, w_ + 6, h_ + 6, seed, shadow=(1, 1), pad=5)
    return spr, spr.shape[1] / 2, spr.shape[0] / 2


def _sprite_lid(self, rx, ry):
    k = ('lid', int(rx), int(ry))
    if k not in self.mouth_cache:
        self.mouth_cache[k] = _lid_sprite(rx, ry, self.pup.skin, shash(self.pup.name, 'lid'))
    return self.mouth_cache[k]


Sprite.lid = _sprite_lid

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

    def plate_at(self, name, k, px, py, blur=2.5):
        """Plate scaled by k with its top-left corner at frame (px, py); must cover the frame. Returns (H+8, W+8, 3), 4 px margin."""
        im = Image.open(asset_path(name)).convert('RGB')
        iw, ih = im.size
        a = np.asarray(im.resize((int(round(iw * k)), int(round(ih * k))), Image.LANCZOS))
        ph, pw = a.shape[:2]
        assert px <= -4 and py <= -4 and px + pw >= W + 4 and py + ph >= H + 4, ('plate does not cover frame', name, k, px, py)
        arr = a[-4 - py:H + 4 - py, -4 - px:W + 4 - px]
        return cv2.GaussianBlur(np.ascontiguousarray(arr), (0, 0), blur)

    def cover_fill(self, name):
        """Full-screen plate: scaled to cover 1080x1920 (centre crop), no blur. Returns uint8 (H+8, W+8, 3)."""
        key = ('cover', name)
        if key in self.bgs:
            return self.bgs[key]
        im = Image.open(asset_path(name)).convert('RGB')
        iw, ih = im.size
        k = max((W + 8) / iw, (H + 8) / ih)
        pw, ph = int(math.ceil(iw * k)), int(math.ceil(ih * k))
        a = np.asarray(im.resize((pw, ph), Image.LANCZOS))
        x0, y0 = (pw - (W + 8)) // 2, (ph - (H + 8)) // 2
        a = np.ascontiguousarray(a[y0:y0 + H + 8, x0:x0 + W + 8])
        self.bgs[key] = a
        return a

    def blank_panel(self, name):
        """Find the flat dark charcoal panel of a cover collage (frame coords x0, y0, x1, y1); fall back to the lower middle."""
        key = ('blank', name)
        if key in self.bgs:
            return self.bgs[key]
        a = self.cover_fill(name)[4:4 + H, 4:4 + W]
        g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float32)
        m1 = cv2.blur(g, (15, 15))
        sd = np.sqrt(np.maximum(cv2.blur(g * g, (15, 15)) - m1 * m1, 0))
        mask = ((m1 > 28) & (m1 < 100) & (sd < 7)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((31, 31), np.uint8))
        lab, n = ndi.label(mask)
        best = None
        for i in range(1, n + 1):
            ys, xs = np.where(lab == i)
            area = len(xs)
            if ys.mean() < 0.4 * H or area < 0.02 * W * H:
                continue
            if best is None or area > best[0]:
                best = (area, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        rect = best[1:] if best else (int(0.30 * W), int(0.66 * H), int(0.70 * W), int(0.90 * H))
        self.bgs[key] = tuple(int(v) for v in rect)
        return self.bgs[key]

    def get_puppet(self, name):
        name = PUPPET_ALIAS.get(EPNAME, {}).get(name, name)
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
    return {'ep02_on_hold': layout_ep02, 'ep03_apology': layout_ep03, 'ep06_grandfather_auto': layout_ep06, 'ep07_i_voted': layout_ep07}.get(EPNAME, layout_ep01)(scene, shot)


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


# ep06 layout (v2, 2026-11-05): every character shot is in bg_living (one room).
# Russell: on the red sofa on the left of bg_living, figure 60 % of the frame height. The four stages share one scale and
# one anchor (puppet h = 1347 and eye line y = 322 in s1..s4), so the figure and the sofa do not move between cuts.
EP06_RUSSELL = dict(plate='bg_living', S=985 / 1672)     # S = cushion top (fraction of plate height)
EP06_RUSSELL_SCALE = 0.60 * H / 1347                     # source px -> frame px
EP06_RUSSELL_X = 310                                     # frame x of the eye-line centre (sofa centre; body stays inside the left edge)
EP06_RUSSELL_TOP = 405                                   # frame y of the top of the figure
EP06_RUSSELL_SEAT_Y = 1140                               # seat line (cushion top): lap of the figure sits here
# Marcus and Neil stand on the right-hand rug of bg_living, one scale for both. Plate zoom k with top-left at (px, py):
# the lamp and the green armchair are in frame, the rug is under the feet.
EP06_STAND_SCALE = 0.93                                  # source px -> frame px (Marcus 1435 px tall, Neil 1490 px)
EP06_STAND_TOP = 330                                     # top of the figure (box or hair) in frame y
EP06_STAND_X = 660                                       # frame x of the eye-line centre
EP06_STAND_PLATE = dict(k=1.82, px=-614, py=-550)


def layout_ep06(scene, shot):
    """ep06: full-screen fake-game plates (no cast) and single shots of puppets in bg_living: Russell seated, Marcus and Neil standing."""
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': [], 'items': None}
    sp = scene.spec['shots'][shot]
    if sp.get('fullscreen'):
        out['bg'] = scene.cover_fill(sp['bg'])
        out['notes'].append(f"{shot}: full-screen plate {sp['bg']}")
        scene.sprites[shot] = out
        return out
    role = list(sp['cast'])[0]
    pup = scene.get_puppet(sp['cast'][role])
    if role == 'R':
        plate, S = EP06_RUSSELL['plate'], EP06_RUSSELL['S']
        s = EP06_RUSSELL_SCALE
        spr = Sprite(role, pup, s, EP06_RUSSELL_X, EP06_RUSSELL_TOP + pup.ey * s, 'single', (6, 8), pivot='hip')
        out['sprites'].append((role, spr))
        out['bg'], k = scene.seat_plate(plate, S, EP06_RUSSELL_SEAT_Y, EP06_RUSSELL_X, [(spr.hip_l, spr.hip_r, 22)])
        out['notes'].append(f'{role}/{pup.name}: height {pup.h * s:.0f}px, hip y {spr.hip_y:.0f}, feet y {spr.feet_y:.0f}; plate {plate} scale {k:.3f}')
    else:
        s = EP06_STAND_SCALE
        spr = Sprite(role, pup, s, EP06_STAND_X, EP06_STAND_TOP + pup.ey * s, 'single', (6, 8), pivot='feet')
        out['sprites'].append((role, spr))
        p = EP06_STAND_PLATE
        out['bg'] = blob_shadows(scene.plate_at('bg_living', p['k'], p['px'], p['py']),
                                 [(spr.foot_cx, spr.feet_y - 6, 0.34 * spr.fig_w, 22, 0.55)], blur=6)
        out['notes'].append(f'{role}/{pup.name}: top {EP06_STAND_TOP}, head {pup.headw * s:.0f}px, feet y {spr.feet_y:.0f}')
    scene.sprites[shot] = out
    return out


# ep07 (I Voted): same room as ep06. Russell and the full-screen plates reuse layout_ep06. Marcus and Neil stand on the rug:
# one scale per character (Marcus head ~ 443 px like ep06, Neil height ~ ep06's), feet on the rug, figure kept inside the frame.
EP07_SCALE = {'M': 0.96, 'N': 0.90}
EP07_FEET = {'M': 1670, 'N': 1730}
EP07_DOOR = dict(scale=0.93, X=594, top=470)     # marcus_door: mid-air jump, small contact shadow far below


def layout_ep07(scene, shot):
    sp = scene.spec['shots'][shot]
    if sp.get('fullscreen') or list(sp['cast'])[0] == 'R':
        return layout_ep06(scene, shot)
    out = {'bg': None, 'sprites': [], 'table': None, 'notes': [], 'items': None}
    role = list(sp['cast'])[0]
    pup = scene.get_puppet(sp['cast'][role])
    if shot == 'marcus_door':
        d = EP07_DOOR
        s, X = d['scale'], d['X']
        Y = d['top'] + pup.ey * s
        spr = Sprite(role, pup, s, X, Y, 'single', (6, 8), pivot='feet', top_extra=340)
        shadow = (spr.foot_cx, 1664, 0.20 * spr.fig_w, 16, 0.32)
    else:
        s, feet = EP07_SCALE[role], EP07_FEET[role]
        X = 660.0
        X = min(X, W - 10 - (pup.w - pup.ex) * s)
        X = max(X, 10 + pup.ex * s)
        Y = feet - (pup.h - pup.ey) * s
        spr = Sprite(role, pup, s, X, Y, 'single', (6, 8), pivot='feet')
        shadow = (spr.foot_cx, feet - 6, 0.34 * spr.fig_w, 22, 0.55)
    out['sprites'].append((role, spr))
    p = EP06_STAND_PLATE
    bg0 = scene.plate_at('bg_living', p['k'], p['px'], p['py'])
    out['bg0'], out['shadow'] = bg0, shadow            # shadow is moved by hand while a puppet slides off
    out['bg'] = blob_shadows(bg0, [shadow], blur=6)
    out['notes'].append(f'{role}/{pup.name}: scale {s:.3f}, head {pup.headw * s:.0f}px, eye y {Y:.0f}, feet y {spr.feet_y:.0f}, '
                        f'bbox x {X - pup.ex * s:.0f}..{X + (pup.w - pup.ex) * s:.0f}')
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
    off = (pup.hip - pup.ey) * scale if pup.hip is not None else 0.0   # eye line -> hip line, frame px
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
        dur += float(b.get('slide_out', 0.0))     # ep07: the puppet slides off in this extra time after the line
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
# ep06 text art (Pillow; our own lettering, no GTA face)
# --------------------------------------------------------------------------------------
def _rgba_from_mask(mask, fill, outline_mask=None, outline=(0, 0, 0), shadow=(6, 9), shadow_a=0.55):
    """mask/outline_mask float 0..1 (HxW). Returns premult RGBA uint8: drop shadow, outline, fill."""
    h, w = mask.shape
    if outline_mask is None:
        outline_mask = mask
    base = np.zeros((h, w, 4), np.uint8)
    sh = cv2.warpAffine(outline_mask.astype(np.float32), np.float32([[1, 0, shadow[0]], [0, 1, shadow[1]]]), (w, h))
    base[..., 3] = np.clip(cv2.GaussianBlur(sh, (0, 0), 6) * shadow_a * 255, 0, 255).astype(np.uint8)
    over_layer(base, premult(np.broadcast_to(np.array(outline, np.float32), (h, w, 3)), np.clip(outline_mask, 0, 1)), 0, 0)
    f = np.asarray(fill, np.float32)
    f = np.broadcast_to(f, (h, w, 3)) if f.ndim == 1 else f
    over_layer(base, premult(f, np.clip(mask, 0, 1)), 0, 0)
    return base


def stamp_layer(rows, max_w, gap=0.08, ss=2, pad=60):
    """Stack heavy text rows [(text, font_spec, size, fill, outline_px)] centred; each row is shrunk to fit max_w.
    Returns premult RGBA (tight + pad)."""
    imgs = []
    for text, fspec, size, fill, ow in rows:
        f = font(fspec, int(size * ss))
        while f.getlength(text) > max_w * ss and size > 12:
            size *= 0.96
            f = font(fspec, int(size * ss))
        bb = f.getbbox(text, stroke_width=int(ow * ss))
        wpx, hpx = bb[2] - bb[0] + 4 * ss, bb[3] - bb[1] + 4 * ss
        m = Image.new('L', (wpx, hpx), 0)
        ImageDraw.Draw(m).text((2 * ss - bb[0], 2 * ss - bb[1]), text, font=f, fill=255)
        o = Image.new('L', (wpx, hpx), 0)
        ImageDraw.Draw(o).text((2 * ss - bb[0], 2 * ss - bb[1]), text, font=f, fill=255, stroke_width=int(ow * ss), stroke_fill=255)
        imgs.append((m.resize((wpx // ss, hpx // ss), Image.LANCZOS), o.resize((wpx // ss, hpx // ss), Image.LANCZOS), fill))
    tw = max(i[0].width for i in imgs) + 2 * pad
    th = int(sum(i[0].height * (1 + gap) for i in imgs)) + 2 * pad
    M = np.zeros((th, tw), np.float32)
    O = np.zeros((th, tw), np.float32)
    F = np.zeros((th, tw, 3), np.float32)
    y = pad
    for m, o, fill in imgs:
        x = (tw - m.width) // 2
        ma, oa = np.asarray(m).astype(np.float32) / 255, np.asarray(o).astype(np.float32) / 255
        sl = (slice(y, y + m.height), slice(x, x + m.width))
        F[sl] = np.where(ma[..., None] > M[sl][..., None], np.asarray(fill, np.float32), F[sl])
        M[sl] = np.maximum(M[sl], ma)
        O[sl] = np.maximum(O[sl], oa)
        y += int(m.height * (1 + gap))
    return _rgba_from_mask(M, F, O)


def fancy_f(size):
    """A display F that cannot be misread: Didot Bold F with a long swash on the top bar and a curl, drawn on a mask.
    Returns (mask float HxW, baseline_y, advance)."""
    ss = 3
    f = font(FONT_DIDOT_BOLD, int(size * ss))
    bb = f.getbbox('F')
    wpx, hpx = bb[2] - bb[0], bb[3] - bb[1]
    padx, pady = int(0.55 * wpx), int(0.35 * hpx)
    img = Image.new('L', (wpx + 2 * padx, hpx + 2 * pady), 0)
    d = ImageDraw.Draw(img)
    d.text((padx - bb[0], pady - bb[1]), 'F', font=f, fill=255)
    # swash: the top bar sweeps left in a curl and the arm ends in a ball
    lw = max(4, int(0.045 * hpx))
    top = pady + int(0.03 * hpx)
    x0 = padx
    pts = [(x0 - 0.50 * wpx, top + 0.20 * hpx), (x0 - 0.38 * wpx, top - 0.10 * hpx), (x0 - 0.10 * wpx, top - 0.02 * hpx), (x0 + 0.05 * wpx, top + 0.03 * hpx)]
    for t in np.linspace(0, 1, 60):
        a = (1 - t) ** 3 * np.array(pts[0]) + 3 * (1 - t) ** 2 * t * np.array(pts[1]) + 3 * (1 - t) * t ** 2 * np.array(pts[2]) + t ** 3 * np.array(pts[3])
        r = lw * (0.4 + 0.9 * t)
        d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=255)
    cx, cy = x0 - 0.50 * wpx, top + 0.20 * hpx
    d.ellipse([cx - 2.2 * lw, cy - 2.2 * lw, cx + 2.2 * lw, cy + 2.2 * lw], fill=255)
    bx, by = padx + wpx * 1.0, top + 0.02 * hpx
    d.ellipse([bx - 1.6 * lw, by - 1.6 * lw, bx + 1.6 * lw, by + 1.6 * lw], fill=255)
    mid = pady + int(0.50 * hpx)
    d.ellipse([padx + 0.80 * wpx - 1.5 * lw, mid - 1.5 * lw, padx + 0.80 * wpx + 1.5 * lw, mid + 1.5 * lw], fill=255)
    bbm = img.getbbox()
    img = img.crop(bbm).resize(((bbm[2] - bbm[0]) // ss, (bbm[3] - bbm[1]) // ss), Image.LANCZOS)
    return np.asarray(img).astype(np.float32) / 255


def title_layer(text, box_w, box_h):
    """Cover title: GRAND / <fancy F>ATHER / AUTO VI, each row justified to the panel width, gold with black outline."""
    words = text.split()
    top, mid, bot = words[0], words[1], ' '.join(words[2:])
    ss = 2
    base = 220

    def row_mask(t):
        f = font(FONT_DIDOT_BOLD, base * ss)
        bb = f.getbbox(t)
        m = Image.new('L', (bb[2] - bb[0] + 8, bb[3] - bb[1] + 8), 0)
        ImageDraw.Draw(m).text((4 - bb[0], 4 - bb[1]), t, font=f, fill=255)
        return np.asarray(m.resize((m.width // ss, m.height // ss), Image.LANCZOS)).astype(np.float32) / 255

    def fit_w(m, w):
        k = w / m.shape[1]
        return cv2.resize(m, (max(1, int(m.shape[1] * k)), max(1, int(m.shape[0] * k))), interpolation=cv2.INTER_AREA)

    fm = fancy_f(base * 1.55)                  # drop-cap F, taller than the rest of the row
    rm = row_mask(mid[1:])
    Hh = max(fm.shape[0], rm.shape[0])
    row2 = np.zeros((Hh, fm.shape[1] + rm.shape[1] + 10), np.float32)
    row2[Hh - fm.shape[0]:, :fm.shape[1]] = fm
    row2[Hh - rm.shape[0]:, fm.shape[1] + 10:] = np.maximum(row2[Hh - rm.shape[0]:, fm.shape[1] + 10:], rm)
    wt = box_w * 0.90
    r1, r2, r3 = fit_w(row_mask(top), wt), fit_w(row2, wt), fit_w(row_mask(bot), wt * 0.82)
    gap = int(0.05 * box_w)
    pad = 24
    tw = int(wt) + 2 * pad
    th = r1.shape[0] + r2.shape[0] + r3.shape[0] + 2 * gap + 2 * pad
    M = np.zeros((th, tw), np.float32)
    y = pad
    for r in (r1, r2, r3):
        x = (tw - r.shape[1]) // 2
        M[y:y + r.shape[0], x:x + r.shape[1]] = np.maximum(M[y:y + r.shape[0], x:x + r.shape[1]], r)
        y += r.shape[0] + gap
    ow = max(2, int(box_w * 0.012))
    O = cv2.dilate(M, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ow + 1, 2 * ow + 1)))
    yy = np.linspace(0, 1, th, dtype=np.float32)[:, None, None]
    fill = np.array((255, 226, 130), np.float32) * (1 - yy) + np.array((232, 140, 40), np.float32) * yy
    lay = _rgba_from_mask(M, np.broadcast_to(fill, (th, tw, 3)).copy(), O, shadow=(4, 6))
    s = min(1.0, box_w * 0.98 / tw, box_h * 0.98 / th)
    if s < 1.0:
        lay = cv2.resize(lay, (int(tw * s), int(th * s)), interpolation=cv2.INTER_AREA)
    return lay


EP06_BAND_CY = 1440   # ep06 cover: centre y of the title band (top half of the bottom row of the cover collage)


def title_band_layer(text, band_w=W, base=200):
    """ep06 cover title: one full-width dark band with two gold rows, GRAND FATHER / AUTO VI.
    The F of FATHER is the swash F (fancy_f). Each row is shrunk together so the top row spans ~90% of the width.
    Returns premult RGBA (band_h, band_w)."""
    words = text.split()                                   # GRAND FATHER AUTO VI
    ss = 2

    def row_mask(t):
        f = font(FONT_DIDOT_BOLD, base * ss)
        bb = f.getbbox(t)
        m = Image.new('L', (bb[2] - bb[0] + 8, bb[3] - bb[1] + 8), 0)
        ImageDraw.Draw(m).text((4 - bb[0], 4 - bb[1]), t, font=f, fill=255)
        return np.asarray(m.resize((m.width // ss, m.height // ss), Image.LANCZOS)).astype(np.float32) / 255

    p1, p2 = row_mask(words[0]), row_mask(words[1][1:])     # GRAND | ATHER
    fo = fancy_f(base)                                      # F of FATHER
    gap_w, f_gap = int(0.24 * base), -int(0.06 * base)     # v2: F and ATHER pulled together (was +0.05 * base)
    h1 = max(p1.shape[0], fo.shape[0], p2.shape[0])
    R1 = np.zeros((h1, p1.shape[1] + gap_w + fo.shape[1] + f_gap + p2.shape[1]), np.float32)

    def put(dst, m, x):                                     # bottom (baseline) aligned
        sl = (slice(h1 - m.shape[0], h1), slice(x, x + m.shape[1]))
        dst[sl] = np.maximum(dst[sl], m)

    x = 0
    put(R1, p1, x); x += p1.shape[1] + gap_w
    put(R1, fo, x); x += fo.shape[1] + f_gap
    put(R1, p2, x)
    R2 = row_mask(' '.join(words[2:]))                      # AUTO VI

    k = 0.90 * band_w / R1.shape[1]
    R1 = cv2.resize(R1, (int(round(R1.shape[1] * k)), int(round(R1.shape[0] * k))), interpolation=cv2.INTER_AREA)
    R2 = cv2.resize(R2, (int(round(R2.shape[1] * k)), int(round(R2.shape[0] * k))), interpolation=cv2.INTER_AREA)
    pad = int(0.20 * R1.shape[0])
    gap = int(0.22 * R1.shape[0])
    bh = pad + R1.shape[0] + gap + R2.shape[0] + pad
    M = np.zeros((bh, band_w), np.float32)
    y = pad
    for R in (R1, R2):
        x = (band_w - R.shape[1]) // 2
        M[y:y + R.shape[0], x:x + R.shape[1]] = np.maximum(M[y:y + R.shape[0], x:x + R.shape[1]], R)
        y += R.shape[0] + gap
    ow = max(2, int(band_w * 0.007))
    O = cv2.dilate(M, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ow + 1, 2 * ow + 1)))
    yy = np.linspace(0, 1, bh, dtype=np.float32)[:, None, None]
    fill = np.array((255, 226, 130), np.float32) * (1 - yy) + np.array((232, 140, 40), np.float32) * yy
    text_layer = _rgba_from_mask(M, np.broadcast_to(fill, (bh, band_w, 3)).copy(), O, shadow=(4, 6))
    band = np.zeros((bh, band_w, 4), np.uint8)
    band[..., :3] = (24, 15, 9)                             # dark cocoa band, premultiplied at alpha 236
    band[..., 3] = 236
    band[:6] = (255, 200, 90, 255)                          # gold rules on both edges
    band[-6:] = (255, 200, 90, 255)
    over_layer(band, text_layer, 0, 0)
    return band


def big_mark_layer(text, box_w, box_h, base=400):
    """Huge display lettering (Didot Bold, our own type, not the game face) scaled to fill box_w x box_h, pink-to-orange gradient.
    Returns premult RGBA."""
    ss = 2
    f = font(FONT_DIDOT_BOLD, base * ss)
    bb = f.getbbox(text)
    m = Image.new('L', (bb[2] - bb[0] + 8, bb[3] - bb[1] + 8), 0)
    ImageDraw.Draw(m).text((4 - bb[0], 4 - bb[1]), text, font=f, fill=255)
    M = np.asarray(m.resize((m.width // ss, m.height // ss), Image.LANCZOS)).astype(np.float32) / 255
    k = min(box_w / M.shape[1], box_h / M.shape[0])
    M = cv2.resize(M, (int(M.shape[1] * k), int(M.shape[0] * k)), interpolation=cv2.INTER_AREA)
    th, tw = M.shape
    ow = max(2, int(box_w * 0.008))
    O = cv2.dilate(M, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ow + 1, 2 * ow + 1)))
    yy = np.linspace(0, 1, th, dtype=np.float32)[:, None, None]
    fill = np.array((255, 120, 178), np.float32) * (1 - yy) + np.array((255, 158, 70), np.float32) * yy
    return _rgba_from_mask(M, np.broadcast_to(fill, (th, tw, 3)).copy(), O, shadow=(5, 7))


def broken_hip_layer():
    return stamp_layer([('BROKEN HIP', FONT_HEAVY, 190, (225, 32, 32), 11)], 900)


def mission_passed_layer():
    return stamp_layer([('MISSION PASSED', FONT_HEAVY, 150, (255, 208, 66), 9), ('+$0.12', FONT_HEAVY, 120, (150, 235, 130), 8)], 960, gap=0.18)


def bw(fr, dim=0.94):
    g = (fr[..., 0] * 0.299 + fr[..., 1] * 0.587 + fr[..., 2] * 0.114).astype(np.float32)
    g = (g - 128) * 1.12 + 128
    return np.repeat(np.clip(g * dim, 0, 255).astype(np.uint8)[..., None], 3, axis=2)


# --------------------------------------------------------------------------------------
# ep07 confetti: deterministic paper pieces, closed-form motion (burst + drag + flutter fall), drawn straight onto the frame
# --------------------------------------------------------------------------------------
CONFETTI_COLS = [(226, 57, 47), (247, 181, 41), (60, 168, 160), (238, 111, 150), (246, 236, 214), (70, 120, 200), (124, 184, 74)]
_CONFETTI = None


def confetti_params(n=380):
    rng = np.random.default_rng(77)
    P = []
    for i in range(n):
        src = i % 3
        if src == 0:                                   # centre pop
            x0, y0, ang, sp = W * 0.5 + rng.normal(0, 40), H * 0.40 + rng.normal(0, 60), rng.uniform(0, 2 * math.pi), rng.uniform(500, 3000)
        elif src == 1:                                 # left cannon
            x0, y0, ang, sp = -20.0, H * 0.93, -rng.uniform(0.55, 1.35), rng.uniform(1600, 3600)
        else:                                          # right cannon
            x0, y0, ang, sp = W + 20.0, H * 0.93, -math.pi + rng.uniform(0.55, 1.35), rng.uniform(1600, 3600)
        kind = rng.choice(['rect', 'streamer', 'dot'], p=[0.58, 0.17, 0.25])
        if kind == 'rect':
            w_, h_ = rng.uniform(22, 48), rng.uniform(12, 26)
        elif kind == 'streamer':
            w_, h_ = rng.uniform(8, 13), rng.uniform(70, 130)
        else:
            w_, h_ = rng.uniform(14, 22), 0
        P.append(dict(x0=x0, y0=y0, vx=math.cos(ang) * sp, vy=math.sin(ang) * sp, vt=rng.uniform(260, 460), kind=kind, w=w_, h=h_,
                      col=CONFETTI_COLS[int(rng.integers(len(CONFETTI_COLS)))], th=rng.uniform(0, 2 * math.pi), om=rng.uniform(-9, 9),
                      ph=rng.uniform(0, 2 * math.pi), ff=rng.uniform(2.5, 8.0), back=(i % 4 == 0)))
    return P


def draw_confetti(fr, t, back):
    global _CONFETTI
    if _CONFETTI is None:
        _CONFETTI = confetti_params()
    k = 2.4
    a = (1 - math.exp(-k * t)) / k
    for q in _CONFETTI:
        if q['back'] != back:
            continue
        x = q['x0'] + q['vx'] * a
        y = q['y0'] + q['vy'] * a + q['vt'] * (t - a)
        if x < -140 or x > W + 140 or y < -140 or y > H + 140:
            continue
        c = math.cos(q['ph'] + 2 * math.pi * q['ff'] * t)
        shade = 0.74 + 0.26 * abs(c)
        col = tuple(int(v * shade) for v in q['col'])
        if q['kind'] == 'dot':
            cv2.circle(fr, (int(round(x)), int(round(y))), max(2, int(q['w'] / 2 * (0.6 + 0.4 * abs(c)))), col, -1, cv2.LINE_AA)
            continue
        hw, hh = q['w'] / 2 * (0.25 + 0.75 * abs(c)), q['h'] / 2
        th = q['th'] + q['om'] * t
        ct, st = math.cos(th), math.sin(th)
        pts = np.array([[x + ct * px - st * py, y + st * px + ct * py] for px, py in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))])
        cv2.fillConvexPoly(fr, np.round(pts * 16).astype(np.int32), col, cv2.LINE_AA, 4)


# --------------------------------------------------------------------------------------
# frame renderer
# --------------------------------------------------------------------------------------
LOOK_X = {'center': 0.0, 'left': -0.5, 'right': 0.5, 'down': 0.0, 'eyes_down': 0.0, 'eyes_closed': 0.0}
LOOK_Y = {'center': 0.0, 'left': 0.0, 'right': 0.0, 'down': 0.45, 'eyes_down': 0.6, 'eyes_closed': 0.0}


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

    def variant(self, T):
        """Per-output-frame state that changes faster than the 12 fps animation grid (mid-beat cuts, overlays, push-in):
        (effective shot, overlay phase or -1, push bucket). Part of the frame cache key."""
        bi = self.beat_at(T)
        e = self.tl[bi]
        b = e['beat']
        lo = max(0.0, T - e['start'])
        shot = b['shot']
        for t_cut, s_cut in b.get('shot_at', []):
            if lo >= t_cut - 1e-9:
                shot = s_cut
        ov = -1
        if b.get('overlay') and lo >= b.get('overlay_from', 0.0) - 1e-9:
            ov = min(3, int((lo - b.get('overlay_from', 0.0)) * OUT_FPS + 1e-6))
        push = int(lo * OUT_FPS + 1e-6) if (b.get('push') or b.get('burst') or b.get('slide_out')) else 0
        return shot, ov, push

    def beat_at(self, T):
        lo = 0
        for i, s in enumerate(self.starts):
            if s <= T + 1e-9:
                lo = i
        return lo

    def caption_owner(self, bi):
        """Beat whose caption card is on screen during beat bi: its own spoken text, or the card carried on by cap_cont beats."""
        b = self.tl[bi]['beat']
        if 'hold' not in b and self.tl[bi]['audio'] is not None and b.get('text'):
            return bi
        j = bi
        while j > 0 and self.tl[j]['beat'].get('cap_cont'):
            j -= 1
            if self.tl[j]['beat'].get('text'):
                return j
        return None

    # ---- captions
    def cap_step(self, T):
        """ep07 Neil summary: index of the sub-caption on screen (beats with text_steps only; 0 otherwise). Part of the frame cache key."""
        bi = self.beat_at(T)
        steps = self.tl[bi]['beat'].get('text_steps')
        if not steps:
            return 0
        lo = max(0.0, T - self.tl[bi]['start'])
        k = 0
        for j, (t_, _) in enumerate(steps):
            if lo >= float(t_) - 1e-9:
                k = j
        return k

    def caption(self, i, text=None):
        key = i if text is None else (i, text)
        if key in self.captions:
            return self.captions[key]
        if text is None:
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
        self.captions[key] = base
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
    def frame(self, T, aidx, t_out=None):
        """T: time in seconds (state time, already snapped to animation grid / beat start); aidx: global anim frame idx.
        t_out: real output time (for mid-beat cuts, overlays and the push-in, which run at the full output rate)."""
        bi = self.beat_at(T)
        e = self.tl[bi]
        b = e['beat']
        local = max(0.0, T - e['start'])
        t_out = T if t_out is None else max(T, t_out)
        local_out = max(0.0, t_out - e['start'])
        hold = 'hold' in b
        spoken = not hold and e['audio'] is not None
        shot, ov_phase, _ = self.variant(t_out)
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
        slide_dx = 0.0
        if b.get('slide_out') and 'bg0' in lay:
            so = float(b['slide_out'])
            q = min(1.0, max(0.0, (local_out - (e['dur'] - so)) / so))
            slide_dx = 1250.0 * q ** 1.8
        bgarr = lay['bg']
        if slide_dx > 0:
            cx_, cy_, rx_, ry_, st_ = lay['shadow']
            bgarr = blob_shadows(lay['bg0'], [(cx_ + slide_dx, cy_, rx_, ry_, st_)], blur=6)
        fr = bgarr[4 + wy:4 + wy + H, 4 + wx:4 + wx + W].copy()
        burst_t = local_out + 0.35 if b.get('burst') else None
        head_box = None                                     # ep07 door: Marcus head ellipse in frame coords (set in the sprite loop)
        if burst_t is not None:
            draw_confetti(fr, burst_t, back=True)
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
                if lk == 'eyes_closed':                       # ep07: skin lid with a closed-eye arc over the eye
                    lsp, lax, lay_ = spr.lid(rx, ry)
                    over_layer(fr_layer, lsp, int(round(cx - lax)), int(round(cy - lay_)))
                    continue
                r = 0.32 * (rx + ry) / 2 * ps
                psp, ax, ay = pupil_sprite(max(r, 2))
                px = cx + vx * rx
                py = cy + vy * ry
                if lk == 'eyes_down':                         # keep the pupil inside the eye white
                    py = cy + min(vy * ry, max(0.0, ry - r))
                    if role == 'R':
                        px = cx + min(0.25 * rx, max(0.0, rx - r))      # Russell (left) looks down-right, toward the soda
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
            if not self.spec['shots'].get(shot, {}).get('no_mouth'):    # ep07 marcus_door: the art already has an open mouth
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
                if shot in ('m_jump', 'marcus_jump'):
                    dy -= 62 * min(1.0, lev)      # hop: rises with loudness, lands in the quiet
                sgn = 1 if math.sin(aidx * 2.3 + 0.7) > 0 else -1
                ang = 1.5 * min(1.0, lev) * sgn
            if b.get('nod'):
                dy += 14 * abs(math.sin(2 * math.pi * 1.5 * min(1.0, local / max(e['dur'], 1e-6))))
            if role in tilt_to:
                ang += tilt_to[role] * p
            if role in tilt:
                ang += tilt[role]
            ddx = 0.0
            if b.get('burst'):                                   # ep07 door: jumps in from the upper right, settles, then floats
                pe = min(1.0, local_out / 0.32)
                ee = 1 - (1 - pe) ** 3
                ddx = 380.0 * (1 - ee)
                dy += -300.0 * (1 - ee) - 16.0 * math.sin(2 * math.pi * 1.1 * local_out) * ee
                ang += 16.0 * (1 - ee)
            if slide_dx > 0:
                ddx += slide_dx
                ang += 3.0 * min(1.0, slide_dx / 300.0)
            M = cv2.getRotationMatrix2D(spr.pivot, ang + ja, 1.0)
            M[:, 2] += (jx + ddx, jy + dy)
            warped = cv2.warpAffine(fr_layer, M, (fr_layer.shape[1], fr_layer.shape[0]), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            if b.get('burst') and role == say:              # head centre (just below the eye line) and radii, moved with the jump
                hx_ = M[0, 0] * spr.ex + M[0, 1] * (spr.ey - 12) + M[0, 2]
                hy_ = M[1, 0] * spr.ex + M[1, 1] * (spr.ey - 12) + M[1, 2]
                head_box = (hx_ + spr.ox, hy_ + spr.oy, 0.72 * spr.headw_px, 0.66 * spr.headw_px)
            over(fr, warped, spr.ox, spr.oy)
        if lay['table'] is not None:
            tsp = lay['table']
            r = np.random.default_rng(777 + pair)
            M = np.float32([[1, 0, r.uniform(-1.2, 1.2)], [0, 1, r.uniform(-1.2, 1.2)]])
            warped = cv2.warpAffine(tsp.canvas, M, (tsp.canvas.shape[1], tsp.canvas.shape[0]))
            over(fr, warped, tsp.ox, tsp.oy)
        title = self.spec['shots'].get(shot, {}).get('title')
        if title and EPNAME == 'ep06_grandfather_auto':
            tb = self.title_band(title)                       # full-width band, centred on EP06_BAND_CY
            over(fr, tb, 0, EP06_BAND_CY - tb.shape[0] // 2)
            big = self.spec['shots'][shot].get('big_mark')
            if big:                                           # huge mark filling the black cell under the band
                x0, y0, x1, y1 = self.scene.blank_panel(self.spec['shots'][shot]['bg'])
                top = EP06_BAND_CY + tb.shape[0] // 2 + 12
                vi = self.big_mark_art(big, x1 - x0 - 16, y1 - 14 - top)
                over(fr, vi, x0 + (x1 - x0 - vi.shape[1]) // 2, top + (y1 - 14 - top - vi.shape[0]) // 2)
        elif title:
            x0, y0, x1, y1 = self.scene.blank_panel(self.spec['shots'][shot]['bg'])
            tl_ = self.title_art(title, x1 - x0, y1 - y0)
            over(fr, tl_, int((x0 + x1) / 2 - tl_.shape[1] / 2), int((y0 + y1) / 2 - tl_.shape[0] / 2))
        if burst_t is not None:
            pre_front = fr.copy() if (local_out < 1.3 and head_box is not None) else None
            draw_confetti(fr, burst_t, back=False)
            if pre_front is not None:                       # ep07 opener: no paper over Marcus's head (big eyes and mouth) for 0-1.3 s
                cx_, cy_, rx_, ry_ = head_box
                x0_, x1_ = max(0, int(cx_ - rx_ - 30)), min(W, int(cx_ + rx_ + 30))
                y0_, y1_ = max(0, int(cy_ - ry_ - 30)), min(H, int(cy_ + ry_ + 30))
                yy_, xx_ = np.mgrid[y0_:y1_, x0_:x1_].astype(np.float32)
                dd_ = np.sqrt(((xx_ - cx_) / rx_) ** 2 + ((yy_ - cy_) / ry_) ** 2)
                m_ = np.clip((1.0 - dd_) / 0.08, 0, 1)[..., None]      # soft edge, no hard cut on the paper
                fr[y0_:y1_, x0_:x1_] = (fr[y0_:y1_, x0_:x1_] * (1 - m_) + pre_front[y0_:y1_, x0_:x1_] * m_).astype(np.uint8)
        if b.get('push') and lay['sprites']:
            spr0 = lay['sprites'][0][1]
            z = 1.0 + 0.38 * smooth(local_out / max(e['dur'], 1e-6))
            Mz = cv2.getRotationMatrix2D((spr0.ox + spr0.ex, spr0.oy + spr0.ey), 0, z)
            fr = cv2.warpAffine(fr, Mz, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        owner = self.caption_owner(bi)
        if owner is not None:
            steps = b.get('text_steps') if owner == bi else None
            if steps:                                       # ep07 Neil summary: one card per sentence, switched on the audio
                k_ = 0
                for j_, (t_, _) in enumerate(steps):
                    if local_out >= float(t_) - 1e-9:
                        k_ = j_
                cap = self.caption(owner, steps[k_][1])
            else:
                cap = self.caption(owner)
            r = np.random.default_rng(321 + pair)
            ox, oy = (int(v) for v in r.integers(-1, 2, size=2))
            over(fr, cap, int(W / 2 - cap.shape[1] / 2) + ox, int(1420 - cap.shape[0] / 2) + oy)
        fr = self.grade(fr, aidx)
        if ov_phase >= 0:
            fr = self.overlay(fr, b['overlay'], ov_phase)
        return fr

    def title_art(self, text, w, h):
        if not hasattr(self, '_title_art'):
            self._title_art = {}
        k = (text, w, h)
        if k not in self._title_art:
            self._title_art[k] = title_layer(text, w, h)
        return self._title_art[k]

    def big_mark_art(self, text, w, h):
        if not hasattr(self, '_big_mark'):
            self._big_mark = {}
        k = (text, w, h)
        if k not in self._big_mark:
            self._big_mark[k] = big_mark_layer(text, w, h)
        return self._big_mark[k]

    def title_band(self, text):
        if not hasattr(self, '_title_band'):
            self._title_band = {}
        if text not in self._title_band:
            self._title_band[text] = title_band_layer(text)
        return self._title_band[text]

    def overlay(self, fr, name, phase):
        """Post-grade overlays (ep06): broken_hip = black and white frame + big red text; mission_passed = gold text."""
        if not hasattr(self, '_ov_art'):
            self._ov_art = {}
        if name == 'broken_hip':
            fr = bw(fr)
            cy = int(H * 0.44)
        elif name == 'mission_passed':
            f = fr.astype(np.float32)
            yy = np.arange(H, dtype=np.float32)[:, None, None]
            band = np.clip(1 - np.abs(yy - H * 0.44) / (H * 0.2), 0, 1) * 0.42
            fr = np.clip(f * (1 - band), 0, 255).astype(np.uint8)
            cy = int(H * 0.44)
        else:
            raise ValueError(name)
        if name not in self._ov_art:
            self._ov_art[name] = broken_hip_layer() if name == 'broken_hip' else mission_passed_layer()
        art = self._ov_art[name]
        z = (1.22, 1.10, 1.04, 1.0)[phase]
        if z != 1.0:
            art = cv2.resize(art, (int(art.shape[1] * z), int(art.shape[0] * z)), interpolation=cv2.INTER_LINEAR)
        ang = -3.0 if name == 'broken_hip' else 0.0
        if ang:
            Mr = cv2.getRotationMatrix2D((art.shape[1] / 2, art.shape[0] / 2), ang, 1.0)
            art = cv2.warpAffine(art, Mr, (art.shape[1], art.shape[0]))
        over(fr, art, int(W / 2 - art.shape[1] / 2), int(cy - art.shape[0] / 2))
        return fr

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


def sfx_hit(sr=SR):
    """Cane on a hip: low thump (pitch drop) + short wooden crack. Original synthesis."""
    n = int(0.45 * sr)
    t = np.arange(n) / sr
    f = 45 + 110 * np.exp(-t / 0.05)
    thump = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.11) * 0.85
    rng = np.random.default_rng(11)
    crack = rng.standard_normal(n)
    crack = crack - np.convolve(crack, np.ones(6) / 6, 'same')
    crack = crack * np.exp(-t / 0.012) * 0.55
    wood = np.sin(2 * np.pi * 640 * t) * np.exp(-t / 0.03) * 0.25
    y = thump + crack + wood
    y[:int(0.002 * sr)] *= np.linspace(0, 1, int(0.002 * sr))
    return (y / max(1e-6, np.abs(y).max()) * 0.8).astype(np.float32)


def sfx_mission_pass(sr=SR):
    """Very short original 'level done' flourish: four quick rising plucks, the last one rings."""
    total = 0.75
    y = np.zeros(int(total * sr), np.float32)
    for k, (fq, t0, dur, amp) in enumerate([(523.25, 0.0, 0.16, 0.5), (659.25, 0.08, 0.16, 0.5), (783.99, 0.16, 0.18, 0.55), (1046.5, 0.25, 0.45, 0.7)]):
        n = int(dur * sr)
        t = np.arange(n) / sr
        env = np.minimum(t / 0.004, 1) * np.exp(-t / (dur * 0.45))
        w = np.sin(2 * np.pi * fq * t) + 0.35 * np.sin(2 * np.pi * 2 * fq * t) + 0.12 * np.sin(2 * np.pi * 3 * fq * t)
        s0 = int(t0 * sr)
        y[s0:s0 + n] += (w * env * amp * 0.45).astype(np.float32)[:len(y) - s0]
    return (y / max(1e-6, np.abs(y).max()) * 0.5).astype(np.float32)


def sfx_bleep(sr=SR, dur=0.35):
    """Censor bleep: 1 kHz sine."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    y = np.sin(2 * np.pi * 1000 * t) * 0.15
    k = int(0.005 * sr)
    y[:k] *= np.linspace(0, 1, k)
    y[-k:] *= np.linspace(1, 0, k)
    return y.astype(np.float32)


def sfx_door_burst(sr=SR):
    """ep07 opener, original synthesis: a door slam (pitch-dropping thump + wood crack + one small bounce), a party-popper pop with a
    streamer hiss, and a crowd cheer (22 detuned saw voices through vowel formants + a scatter of claps). 1.5 s."""
    from scipy.signal import butter, sosfilt
    n = int(1.5 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(21)
    f = 38 + 125 * np.exp(-t / 0.045)
    slam = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.16) * 0.9
    cr = rng.standard_normal(n)
    cr = cr - np.convolve(cr, np.ones(8) / 8, 'same')
    slam += cr * np.exp(-t / 0.014) * 0.7
    slam += (np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.05) + 0.5 * np.sin(2 * np.pi * 310 * t) * np.exp(-t / 0.03)) * 0.45
    k2 = int(0.12 * sr)
    bounce = np.zeros(n)
    tt = t[:n - k2]
    bounce[k2:] = (np.sin(2 * np.pi * 70 * tt) * np.exp(-tt / 0.08) * 0.35 + cr[:n - k2] * np.exp(-tt / 0.01) * 0.3)
    slam += bounce
    y = slam * 0.62
    pop = rng.standard_normal(n)
    pop = sosfilt(butter(2, [1500, 5500], btype='bandpass', fs=sr, output='sos'), pop)
    k3 = int(0.05 * sr)
    pe = np.zeros(n)
    pe[k3:] = np.exp(-t[:n - k3] / 0.03)
    y += pop * pe * 0.5
    hiss = sosfilt(butter(2, 3500, btype='highpass', fs=sr, output='sos'), rng.standard_normal(n))
    he = np.zeros(n)
    he[k3:] = np.minimum(1, t[:n - k3] / 0.03) * np.exp(-t[:n - k3] / 0.22)
    y += hiss * he * 0.07
    crowd = np.zeros(n)
    for _ in range(22):
        f0 = rng.uniform(150, 420)
        d0 = rng.uniform(0.08, 0.30)
        vib = 1 + 0.02 * np.sin(2 * np.pi * rng.uniform(4.5, 6.5) * t + rng.uniform(0, 6))
        ph = 2 * np.pi * np.cumsum(f0 * vib) / sr
        v = sum(np.sin(h * ph) / h for h in range(1, 14))
        env = np.clip((t - d0) / 0.10, 0, 1) * np.clip((1.45 - t) / 0.35, 0, 1) * (1 + 0.15 * np.sin(2 * np.pi * rng.uniform(3, 7) * t))
        crowd += v * env
    crowd = (sosfilt(butter(2, [450, 1000], btype='bandpass', fs=sr, output='sos'), crowd)
             + 0.6 * sosfilt(butter(2, [1000, 2600], btype='bandpass', fs=sr, output='sos'), crowd))
    crowd /= max(1e-6, np.abs(crowd).max())
    y += crowd * 0.2
    clap = np.zeros(n)
    for _ in range(36):
        i0 = int(rng.uniform(0.25, 1.3) * sr)
        m = int(0.02 * sr)
        c_ = rng.standard_normal(m) * np.exp(-np.arange(m) / (0.004 * sr))
        clap[i0:i0 + m] += c_[:max(0, min(m, n - i0))] * rng.uniform(0.3, 1.0)
    clap = sosfilt(butter(2, [1200, 4500], btype='bandpass', fs=sr, output='sos'), clap)
    y += clap * 0.12
    y[:int(0.0015 * sr)] *= np.linspace(0, 1, int(0.0015 * sr))
    return (y / max(1e-6, np.abs(y).max()) * 0.6).astype(np.float32)


def sfx_whoosh(sr=SR, dur=0.3):
    """Short paper-slide whoosh: band-passed noise whose centre rises, fast fade."""
    from scipy.signal import butter, sosfilt
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = np.random.default_rng(31).standard_normal(n)
    out = np.zeros(n)
    for lo, hi, g in ((300, 900, 1.0), (900, 2600, 0.8), (2600, 6000, 0.5)):
        out += sosfilt(butter(2, [lo, hi], btype='bandpass', fs=sr, output='sos'), x) * g
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return (out * env / max(1e-6, np.abs(out * env).max()) * 0.25).astype(np.float32)


SYNTH_SFX = {'hit': sfx_hit, 'mission_pass': sfx_mission_pass, 'bleep': sfx_bleep, 'door_burst': sfx_door_burst}


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
    # synthesised one-shots (ep06): placed at beat start + sfx_at
    for e in tl:
        nm = e['beat'].get('sfx')
        if nm in SYNTH_SFX:
            x = SYNTH_SFX[nm]()
            s0 = int((e['start'] + float(e['beat'].get('sfx_at', 0.0))) * SR)
            mix[s0:s0 + len(x)] += x[:max(0, min(len(x), n - s0))]
    # ep07: paper whoosh under the slide-off
    for e in tl:
        so = float(e['beat'].get('slide_out', 0.0))
        if so > 0 and e['audio'] is not None:
            x = sfx_whoosh(dur=so)
            s0 = int((e['start'] + e['dur'] - so) * SR)
            mix[s0:s0 + len(x)] += x[:max(0, min(len(x), n - s0))]
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


LIMIT_LIN = 0.86    # linear sample-peak ceiling before the AAC encode (checked with ebur128 true peak after)


def append_end_tag(body, tag, out, secs, limit=None):
    """Concatenate the end card once after the body (ep06). Both inputs are normalised to 1080x1920, 30 fps, 44.1 kHz stereo."""
    fc = (f'[1:v]trim=duration={secs},setpts=PTS-STARTPTS,fps={OUT_FPS},scale={W}:{H},setsar=1,format=yuv420p[v1];'
          f'[1:a]atrim=duration={secs},asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=stereo[a1];'
          '[0:v]setpts=PTS-STARTPTS,format=yuv420p[v0];'
          '[0:a]asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=stereo[a0];'
          '[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][ac];'
          f'[ac]alimiter=limit={limit or LIMIT_LIN}:attack=3:release=40:level=disabled[a]')   # final limiter (ep06 v3, ep07): true peak <= -1 dBTP
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', body, '-i', tag, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
           '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
           '-ar', '44100', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)


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
    skip = EPCFG[a.ep].get('skip_shots', ())
    if skip:                                           # drop placeholder beats (ep07 end_tag: the real card is concatenated once)
        keep = [i for i, b_ in enumerate(spec['beats']) if b_['shot'] not in skip]
        spec['beats'] = [spec['beats'][i] for i in keep]
        manifest = [manifest[i] if i < len(manifest) else None for i in keep]
        spec['shots'] = {k_: v_ for k_, v_ in spec['shots'].items() if k_ not in skip}
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
        names = sorted({n for s in spec['shots'].values() for n in s.get('cast', {}).values()})
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
                fr = R.frame(ta, aidx, t_out=T)
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
    end_tag = EPCFG[a.ep].get('end_tag')                  # ep06: body first, then the end card concatenated once
    body = f'{BUILD}/{a.ep}_body.mp4' if end_tag else a.out
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(OUT_FPS), '-i', '-',
           '-i', audio_path, '-filter:a', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
           '-ar', '44100', '-movflags', '+faststart', '-shortest', body]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    last_key, last = None, None
    t0 = time.time()
    for n in range(nframes):
        T = n / OUT_FPS
        ta, aidx, bi = snap_state(R, T)
        key = (bi, round(ta * 1000), aidx, R.variant(T), R.cap_step(T))
        if key != last_key:
            last = R.frame(ta, aidx, t_out=T)
            last_key = key
        proc.stdin.write(last.tobytes())
        if n % 60 == 0:
            print(f'frame {n}/{nframes}  {time.time() - t0:.0f}s', flush=True)
    proc.stdin.close()
    rc = proc.wait()
    print('ffmpeg rc', rc, 'frames', nframes, 'elapsed', round(time.time() - t0))
    if end_tag:
        if rc != 0:
            raise SystemExit('body render failed; end tag not appended')
        append_end_tag(body, end_tag, a.out, EPCFG[a.ep]['end_tag_secs'], EPCFG[a.ep].get('limit'))
        print('end tag appended once:', end_tag, f"{EPCFG[a.ep]['end_tag_secs']} s", '->', a.out)
    for note_shot in spec['shots']:
        if note_shot in R.scene.sprites:
            for note in R.scene.sprites[note_shot]['notes']:
                print('layout note:', note_shot, note)


if __name__ == '__main__':
    main()

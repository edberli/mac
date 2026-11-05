#!/usr/bin/env python3
"""GF v3: lighten ONLY the skin of assets_ep06/marcus_box.png so its mean skin colour matches assets_leads/marcus.png.
Shirt, DVD box, shorts, shoes, hair, headband, eye discs and the green background are untouched.
Old art is kept as marcus_box_dark.png (never overwritten). Run: python3 fix_marcus_box.py [--debug]
"""
import sys, os, shutil
import numpy as np, cv2
from PIL import Image

ROOT = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy'
SRC = f'{ROOT}/assets_ep06/marcus_box.png'
DARK = f'{ROOT}/assets_ep06/marcus_box_dark.png'
REF = f'{ROOT}/assets_leads/marcus.png'


def sm_t(f, sigma=2.5):
    sm = cv2.GaussianBlur(f, (0, 0), sigma)
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    return sm, (g - b) / np.maximum(r - b, 1), (g - np.maximum(r, b)) > 25


def ref_skin_mean():
    f = np.asarray(Image.open(REF).convert('RGB')).astype(np.float32)
    sm, t, green = sm_t(f)
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    m = (t > 0.2) & (t < 0.45) & (r > 140) & (r < 235) & (g < 125) & (b < 65) & (r - b > 80) & ~green
    m[900:] = False                       # face, neck, arms, fists (above the shorts)
    m = cv2.erode(m.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    return f[m].mean(0), int(m.sum())


def box_skin_mask(f):
    """Soft skin mask (float 0..1) of marcus_box. Colour test on a blurred copy (hue ratio t separates skin from shirt/shorts/hair),
    then spatial rules: no DVD cover, shorts patches only inside the two leg tubes."""
    h, w = f.shape[:2]
    sm, t, green = sm_t(f)
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    m = (t > 0.10) & (t < 0.225) & (r > 70) & (r < 215) & (r - b > 60) & ~green
    # DVD box: cover art sits at x 300..690, y < 445; only the two fists (x<372 / x>655) are skin there
    dvd = np.zeros((h, w), bool)
    dvd[:445, 300:690] = True
    dvd[320:445, :372] = False
    dvd[320:445, 655:] = False
    m &= ~dvd
    # shorts zone: the shorts have almost the same brown; inside it keep only the leg tubes (polygons from the 2x crop at (150,1050))
    zone = np.zeros((h, w), np.uint8)
    cv2.rectangle(zone, (262, 1095), (735, 1330), 1, -1)
    legs = np.zeros((h, w), np.uint8)
    for poly in ([(185, 285), (310, 215), (345, 235), (435, 350), (430, 385), (345, 405), (245, 450), (215, 420)],
                 [(1005, 350), (1100, 330), (1230, 450), (1245, 540), (1160, 590), (1085, 570), (975, 470)]):
        pts = np.array([(150 + x / 2, 1050 + y / 2) for x, y in poly], np.int32)
        cv2.fillPoly(legs, [pts], 1)
    m &= ~((zone > 0) & (legs == 0))
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 600:
            m[lab == i] = 0
    # edge rim: grow 6 px over pixels that are brown-orange skin shade (not green, not shirt red, not cream, not dark hair)
    rr, gg, bb = f[..., 0], f[..., 1], f[..., 2]
    eligible = (rr > 60) & (gg < 0.50 * rr) & (gg > 0.22 * rr) & (bb < 0.36 * rr) & (gg > bb)
    grown = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))).astype(bool)
    grown &= eligible | m.astype(bool)
    grown &= ~dvd
    grown &= ~((zone > 0) & (legs == 0))
    soft = cv2.GaussianBlur(grown.astype(np.float32), (0, 0), 1.2)
    return np.clip(soft * 1.0, 0, 1), grown


def main():
    debug = '--debug' in sys.argv
    if not os.path.exists(DARK):
        shutil.copy2(SRC, DARK)            # keep the original once
    f = np.asarray(Image.open(DARK).convert('RGB')).astype(np.float32)
    ref, nref = ref_skin_mean()
    soft, hard = box_skin_mask(f)
    core = cv2.erode(hard.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    before = f[core].mean(0)
    # per-channel gain (keeps the felt texture); solve so the mean after clipping hits the reference mean
    gain = ref / before
    for _ in range(12):
        after = np.clip(f[core] * gain, 0, 255).mean(0)
        gain = gain * ref / after
    new = np.clip(f * gain, 0, 255)
    out = f * (1 - soft[..., None]) + new * soft[..., None]
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(SRC)
    after = out.astype(np.float32)[core].mean(0)
    print('ref marcus.png skin mean RGB (n=%d): %s' % (nref, np.round(ref, 1).tolist()))
    print('marcus_box skin mean RGB before: %s  after: %s  (n=%d px)' % (np.round(before, 1).tolist(), np.round(after, 1).tolist(), int(core.sum())))
    print('gain per channel', np.round(gain, 3).tolist())
    # untouched check: pixels with mask 0 identical
    untouched = soft < 1e-4
    print('pixels with mask 0 changed:', int((np.abs(out.astype(int) - f.astype(int)).max(2)[untouched] > 0).sum()))
    ov = np.asarray(Image.open(DARK).convert('RGB')).copy()
    ov[hard] = (0, 255, 255)
    ref_im = Image.open(REF).convert('RGB')
    sheet = Image.new('RGB', (3 * 512, 768))
    for i, im in enumerate([ref_im, Image.open(DARK).convert('RGB'), Image.fromarray(out)]):
        sheet.paste(im.resize((512, 768), Image.LANCZOS), (i * 512, 0))
    sheet.save(f'{ROOT}/build/gf3_marcus_box.jpg', quality=92)
    if debug:
        Image.fromarray(ov).resize((683, 1024)).save(f'{ROOT}/build/iv/gf3_mask.jpg', quality=88)


if __name__ == '__main__':
    main()

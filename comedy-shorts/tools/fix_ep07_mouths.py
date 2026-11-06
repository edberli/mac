#!/usr/bin/env python3
"""ep07: paint out the smile drawn on marcus_bag.png / marcus_sticker.png with skin colour, keeping the felt grain
(smooth skin colour from the surrounding skin + high-pass grain copied from skin just below the mouth, feathered edge).
Originals are kept once as <name>_mouthed.png; the render then draws its own mouth. Run: python3 fix_ep07_mouths.py"""
import os, shutil
import numpy as np, cv2
from PIL import Image

D = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/assets_ep07'
BOX = (445, 336, 612, 440)      # x0, y0, x1, y1 around the drawn smile (same place in both images)
SHIFT = 92                      # donor grain comes from this many px below


def fix(name):
    src, keep = f'{D}/{name}.png', f'{D}/{name}_mouthed.png'
    if not os.path.exists(keep):
        shutil.copy2(src, keep)
    f = np.asarray(Image.open(keep).convert('RGB')).astype(np.float32)
    x0, y0, x1, y1 = BOX
    reg = f[y0:y1, x0:x1]
    med = np.median(reg.reshape(-1, 3), axis=0)
    d = np.linalg.norm(cv2.GaussianBlur(reg, (0, 0), 1.0) - med, axis=2)
    m = ((d > 38) & (reg[..., 2] < 110)).astype(np.uint8)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) & (reg[..., 2] < 110).astype(np.uint8)
    ok = ((1 - m) * (reg[..., 2] < 110)).astype(np.float32)
    # smooth skin base: normalised convolution of the non-mouth pixels
    num = cv2.GaussianBlur(reg * ok[..., None], (0, 0), 14)
    den = cv2.GaussianBlur(ok, (0, 0), 14)[..., None]
    base = num / np.maximum(den, 1e-3)
    # grain donor: high-pass of skin SHIFT px lower
    don = f[y0 + SHIFT:y1 + SHIFT, x0:x1]
    grain = don - cv2.GaussianBlur(don, (0, 0), 3.0)
    fill = base + grain
    soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 2.0)[..., None]
    soft = np.clip(soft * 1.6, 0, 1)
    out = f.copy()
    out[y0:y1, x0:x1] = reg * (1 - soft) + fill * soft
    Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(src)
    print(name, 'mouth px', int(m.sum()), 'skin median', med.round(0).tolist())


for n in ('marcus_bag', 'marcus_sticker'):
    fix(n)

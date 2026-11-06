#!/usr/bin/env python3
"""ep07: write I ATE IT ALL on the beige band of assets_ep07/sticker_close.png (Pillow, our own lettering).
Plain art kept once as sticker_close_plain.png. The full-screen crop maps src y to frame y = K*src - 4 (K = 1928/1536),
so the lettering is placed from frame targets: both lines inside the beige band, lowest glyph edge at frame y <= 1596
(Shorts UI covers the bottom), chicken feet untouched. Visible width after the crop is src x 98..926, each line within 760 px.
"""
import os, shutil
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

D = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/assets_ep07'
FONT = ('/System/Library/Fonts/Avenir Next.ttc', 8)      # Avenir Next Heavy
LINES = ['I ATE', 'IT ALL']
MAXW = 760
K = 1928 / 1536                  # full-screen cover scale: 1024x1536 plate to 1286x1928, then crop to 1080x1920
TOP_FRAME, BOT_FRAME = 1385, 1596    # lettering block limits in frame px (band starts at frame y ~1372)
GAP = 0.22                       # line gap as a fraction of cap height


def main():
    src, keep = f'{D}/sticker_close.png', f'{D}/sticker_close_plain.png'
    if not os.path.exists(keep):
        shutil.copy2(src, keep)
    im = Image.open(keep).convert('RGB')
    f0 = np.asarray(im).astype(np.float32)
    h, w = f0.shape[:2]
    def cap_of(sz):
        f = ImageFont.truetype(FONT[0], sz, index=FONT[1])
        return -f.getbbox('H', anchor='ls')[1]
    size = 150
    while True:
        cap = cap_of(size)
        block_frame = K * (2 * cap + GAP * cap)
        fnt = ImageFont.truetype(FONT[0], size, index=FONT[1])
        if max(fnt.getlength(t) for t in LINES) <= MAXW and block_frame <= BOT_FRAME - TOP_FRAME:
            break
        size -= 1
    # baselines from frame targets (line 2 has no descenders, so its baseline is the lowest edge)
    base2_src = (BOT_FRAME + 4) / K
    base1_src = base2_src - (cap + GAP * cap)
    centres = [(LINES[0], base1_src), (LINES[1], base2_src)]
    SS = 3
    big = ImageFont.truetype(FONT[0], size * SS, index=FONT[1])
    mask = Image.new('L', (w * SS, h * SS), 0)
    d = ImageDraw.Draw(mask)
    for t, by in centres:
        d.text((w * SS / 2, by * SS), t, font=big, fill=255, anchor='ms')
    m = np.asarray(mask.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255
    rng = np.random.default_rng(5)
    g = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 0.8)
    tex = 1 + 0.05 * g / g.std()
    ink = np.array([78, 42, 24], np.float32)
    sh = cv2.warpAffine(m, np.float32([[1, 0, 5], [0, 1, 7]]), (w, h))
    sh = cv2.GaussianBlur(sh, (0, 0), 4) * 0.35
    out = f0 * (1 - sh[..., None]) + 0.0 * sh[..., None]
    out = out * (1 - m[..., None]) + ink * tex[..., None] * m[..., None]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(src)
    print('sticker_close lettered, font size', size, 'cap px src', round(cap, 1), 'baselines src', round(base1_src, 1), round(base2_src, 1))


main()

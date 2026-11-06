#!/usr/bin/env python3
"""Measure displacement between two green-screen figures: bbox, rightmost hand tip, top of head, eye-oval centroid."""
import sys
import numpy as np
from PIL import Image

def load(p):
    im = np.array(Image.open(p).convert('RGB')).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    fg = ~((g - np.maximum(r, b) > 70) & (g > 150))
    return im, fg

def stats(p):
    im, fg = load(p)
    ys, xs = np.where(fg)
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    # hand tip: mean y of the rightmost 15 columns of the figure
    tip_y = ys[xs >= right - 15].mean()
    # head x-centre: foreground columns in the top 12% of figure height
    h = bot - top
    band = fg[top:top + int(h * 0.12)]
    hx = np.where(band.any(0))[0].mean()
    # eye ovals: near-white/cream pixels in the top 40% (excludes pure white hair >245 all channels)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    cream = (r > 225) & (g > 205) & (b > 180) & (r - b > 8) & (r - b < 60)
    cream[top + int(h * 0.4):] = False
    ey, ex = np.where(cream)
    eye = (ex.mean(), ey.mean()) if len(ex) > 200 else (float('nan'),) * 2
    return dict(bbox=(left, top, right, bot), tip=(right, round(tip_y, 1)), head_top=(round(hx, 1), top), eye=tuple(round(v, 1) for v in eye))

a, b = stats(sys.argv[1]), stats(sys.argv[2])
for k in a:
    print(k, a[k], b[k])
print('hand tip dx,dy', b['tip'][0] - a['tip'][0], round(b['tip'][1] - a['tip'][1], 1))
print('head top x shift', round(b['head_top'][0] - a['head_top'][0], 1), 'feet bottom dy', b['bbox'][3] - a['bbox'][3])
print('eye centroid dx,dy', round(b['eye'][0] - a['eye'][0], 1), round(b['eye'][1] - a['eye'][1], 1))

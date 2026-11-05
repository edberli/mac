#!/usr/bin/env python3
"""ep09: measure the blank PULL sign board (4 corners) and the door face on each background plate (source pixels, Pillow + numpy + cv2 contour)."""
import sys, json
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi
A = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/assets_ep09/'


def quad_of(mask):
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    k = int(np.argmax(sizes)) + 1
    m = (lab == k).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    for eps in np.linspace(0.01, 0.08, 30) * cv2.arcLength(c, True):
        ap = cv2.approxPolyDP(c, eps, True)
        if len(ap) == 4:
            break
    pts = ap.reshape(-1, 2).astype(float)
    # order: tl, tr, br, bl
    s = pts.sum(1); d = pts[:, 0] - pts[:, 1]
    return [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]], int(sizes.max())


out = {}
MANUAL = {   # swung-open leaf: read off a 1:1 crop with a coordinate grid (auto-detect merges the leaf with the floor shadow)
    'bg_hall_open': dict(door=[[808, 350], [938, 212], [938, 1115], [806, 1030]], sign=[[812, 442], [922, 374], [920, 563], [813, 605]]),
    # old hall / lot: dim light defeats the colour threshold, so these are read off 1:1 grid crops as well
    'bg_hall_old': dict(door=[[550, 325], [937, 207], [937, 1155], [550, 1030]], sign=[[575, 418], [905, 368], [907, 590], [577, 605]]),
    'bg_lot': dict(door=[[495, 435], [802, 372], [805, 1120], [495, 1072]], sign=[[517, 535], [780, 492], [782, 660], [517, 680]])}
for name in sys.argv[1:] or ['bg_hall', 'bg_hall_open', 'bg_hall_old', 'bg_lot']:
    if name in MANUAL:
        out[name] = MANUAL[name]; print(name, 'manual', out[name]); continue
    im = np.asarray(Image.open(A + name + '.png').convert('RGB')).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # door face: terracotta brown (r high, b low, r-g big); sign board: pale cream on the door (inside the door's bounding box)
    brown = (r - b > 70) & (r > 110) & (r < 215) & (g < 130) & (r - g > 40)
    if name == 'bg_hall_open':
        brown[:, :800] = False                     # only the swung-open leaf on the right (the floor shadow is brown too)
        brown[1100:] = False
    q_door, a_door = quad_of(brown)
    dx0, dx1 = int(min(p[0] for p in q_door)), int(max(p[0] for p in q_door))
    dy0, dy1 = int(min(p[1] for p in q_door)), int(max(p[1] for p in q_door))
    poly = np.zeros(r.shape, np.uint8)
    cv2.fillPoly(poly, [np.array(q_door, np.int32)], 1)
    poly = cv2.erode(poly, np.ones((15, 15), np.uint8)).astype(bool)      # keep inside the door leaf, away from its edge
    cm = (g > 148) & (r > 200) & poly                                       # the bright board; the leaf itself is darker terracotta
    # keep only blobs of a plausible size
    q_sign, a_sign = quad_of(cm)
    out[name] = dict(door=[[round(float(x), 1) for x in p] for p in q_door], sign=[[round(float(x), 1) for x in p] for p in q_sign])
    print(name, json.dumps(out[name]), a_door, a_sign)
json.dump(out, open('/Volumes/core/AI-Workspace/Claude/mac-work/comedy/build/ep09_work/quads.json', 'w'))

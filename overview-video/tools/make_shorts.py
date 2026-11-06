#!/usr/bin/env python3
"""Cut EP01 into vertical 1080x1920 English Shorts with burned-in captions and a headline.

usage: python3 tools/make_shorts.py [short_id ...]
Source build/ep01_full_v2.mp4 already has captions burned in near the bottom, so the crop stops at y=CROP_H.
Output: publish/shorts/<id>.mp4 and publish/shorts/<id>.captions.json
"""
import json, os, re, subprocess, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'build', 'ep01_full_v2.mp4')
SRT = os.path.join(ROOT, 'publish', 'ep01.en.srt')
OUT = os.path.join(ROOT, 'publish', 'shorts')
FPS, W, H = 30, 1080, 1920
CROP_H = 915            # burned-in captions start around y=923
PANEL_CY = 840
FEATHER = 70
CAP_TOP, CAP_W, CAP_SIZE = 1365, 840, 62
HEAD_CY, HEAD_W, HEAD_MAX = 215, 920, 92
BLACK = '/System/Library/Fonts/Supplemental/Arial Black.ttf'
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

# per srt line: chunks as display text, or (display, spoken) when digits replace spoken words
CHUNKS = {
    1: ["Wait... where's the Great Wall?"],
    2: ["With your eyes?", "You'll never find it."],
    3: ["But everyone says it's the one thing humans built", "that you can see from space."],
    10: ["I can't see it.", "Not even close."],
    11: [("The wall is only about 6 meters wide.", "The wall is only about six meters wide."),
         ("From 400 kilometers,", "From four hundred kilometers,"),
         "that's like trying to spot a pencil", "from half a kilometer away."],
    12: ["Then why does everyone say you can?"],
    13: [("The claim was already written down in 1754.", "The claim was already written down in seventeen fifty-four."),
         ("The first human reached space in 1961.", "The first human reached space in nineteen sixty-one.")],
    14: [("People repeated it for 200 years", "People repeated it for two hundred years"), "before anyone could check."],
    15: ["So what can you actually see from up here?"],
    16: [("This station circles the Earth every 90 minutes.", "This station circles the Earth every ninety minutes."),
         ("16 sunrises a day.", "Sixteen sunrises a day."), "Watch the night side."],
    17: ["Whoa... those lights."],
    18: ["Cities.", "Most borders are invisible from here.", "A few are lit up with floodlights,", "and those you can see."],
    19: ["Up here, a border only shows up", "if someone switches the lights on."],
    20: ["And that green glow?"],
    21: ["An aurora.", "And those flashes in the clouds are thunderstorms.", "You're looking down on them."],
    31: [("In 2021, an actor", "In twenty twenty-one, an actor"), "who played a starship captain for decades",
         "finally flew to space,", ("at 90 years old.", "at ninety years old.")],
    32: ["Afterwards, he said", "what he felt most wasn't joy.", "It was grief."],
    33: ["Grief? Why?"],
    34: ["Below him was everything.", "Above him, nothing but black."],
}


# End of "Everyone's wrong." on the source timeline. Measured from the loudness of the mix:
# speech stops at about 13.25 s and the next word starts at about 14.2 s, music continues under both.
INTRO_CUT = 13.55


# keyframes: (source time, crop width, crop centre x, ease seconds; 0 = snap on a scene cut)
def shorts():
    cut = INTRO_CUT
    return {
        'short1_great_wall': dict(
            head=['THE GREAT WALL', 'FROM SPACE?'],
            lines=[1, 2, 3, 'wrong', 10, 11, 12, 13, 14],
            segs=[dict(s=0.35, e=cut, kf=[(0.35, 1000, 940, 0), (6.68, 1500, 960, 0)]),
                  dict(s=47.45, e=74.55, kf=[(47.45, 1000, 940, 0), (50.6, 1600, 1040, .7), (59.5, 1000, 940, .6), (61.7, 1500, 960, .7)])]),
        'short2_age_90': dict(
            head=['SPACE AT AGE 90', "HE DIDN'T FEEL JOY"],
            lines=[31, 32, 33, 34],
            segs=[dict(s=163.66, e=186.75, kf=[(163.66, 1300, 1000, 0), (178.11, 1100, 960, 0)])]),
        'short3_what_you_see': dict(
            head=['WHAT YOU REALLY', 'SEE FROM SPACE'],
            lines=[15, 16, 17, 18, 19, 20, 21],
            segs=[dict(s=74.6, e=108.85, kf=[(74.6, 1000, 940, 0), (84.2, 1250, 960, 1.2)])]),
    }, cut


def parse_srt():
    txt = open(SRT, encoding='utf-8').read().strip()
    def sec(x):
        h, m, r = x.split(':'); s, ms = r.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    out = {}
    for b in re.split(r'\n\s*\n', txt):
        p = b.splitlines()
        a, z = p[1].split(' --> ')
        out[int(p[0])] = (sec(a), sec(z))
    return out


def weight(text):
    return len(text) + 6 * len(re.findall(r'[.?!](?:\s|$)', text)) + 3 * text.count(',') + 8 * text.count('...')


def split_line(a, z, chunks):
    items = [(c, c) if isinstance(c, str) else c for c in chunks]
    total = sum(weight(s) for _, s in items)
    t, res = a, []
    for disp, spoken in items:
        d = (z - a) * weight(spoken) / total
        res.append((t, t + d, disp))
        t += d
    return res


def to_out(t, segs):
    """Map a source time to the output timeline, clamped to the kept segments."""
    off = 0.0
    for sg in segs:
        n = round((sg['e'] - sg['s']) * FPS) / FPS
        if t < sg['s']:
            return off
        if t <= sg['s'] + n:
            return off + t - sg['s']
        off += n
    return off


def caption_track(cfg, srt, cut):
    track = []
    for ln in cfg['lines']:
        if ln == 'wrong':
            parts = [(srt[4][0], cut, "Everyone's wrong.")]
        else:
            parts = split_line(*srt[ln], CHUNKS[ln])
        for a, z, disp in parts:
            track.append(dict(start=round(to_out(a, cfg['segs']), 3), end=round(to_out(z, cfg['segs']), 3), text=disp))
    return track


def wrap(draw, text, font, maxw):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    # even out two-line captions so the last line is not a single orphan word
    if len(lines) == 2 and len(lines[1].split()) == 1 and len(lines[0].split()) > 2:
        a = lines[0].split()
        lines = [' '.join(a[:-1]), a[-1] + ' ' + lines[1]]
    return lines


def text_layer(lines, font, cy=None, top=None, stroke=6, gap=1.2):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lh = int(font.size * gap)
    y = top if top is not None else int(cy - lh * len(lines) / 2)
    for l in lines:
        d.text((W / 2, y), l, font=font, anchor='ma', fill=(255, 255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += lh
    arr = np.asarray(img, dtype=np.float32)
    ys = np.where(arr[..., 3].max(axis=1) > 0)[0]
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    return y0, y1, arr[y0:y1, :, :3][..., ::-1].copy(), arr[y0:y1, :, 3:4] / 255.0


def blend(frame, layer):
    y0, y1, rgb, a = layer
    roi = frame[y0:y1].astype(np.float32)
    frame[y0:y1] = (roi * (1 - a) + rgb * a).astype(np.uint8)


def head_layer(lines):
    size = HEAD_MAX
    probe = ImageDraw.Draw(Image.new('L', (8, 8)))
    while size > 40 and max(probe.textlength(l, font=ImageFont.truetype(BLACK, size)) for l in lines) > HEAD_W:
        size -= 2
    return text_layer(lines, ImageFont.truetype(BLACK, size), cy=HEAD_CY, stroke=5, gap=1.16)


def crop_at(t, kf):
    k = max(i for i, x in enumerate(kf) if x[0] <= t + 1e-6)
    tk, w, cx, ease = kf[k]
    if k == 0 or ease == 0 or t >= tk + ease:
        return w, cx
    p = (t - tk) / ease
    p = p * p * (3 - 2 * p)
    _, w0, cx0, _ = kf[k - 1]
    return w0 + (w - w0) * p, cx0 + (cx - cx0) * p


MASKS = {}
def mask(h):
    if h not in MASKS:
        r = np.ones(h, dtype=np.float32)
        f = min(FEATHER, h // 4)
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        r[:f] = ramp; r[-f:] = ramp[::-1]
        MASKS[h] = r[:, None, None]
    return MASKS[h]


GRAD_IS_TOP = (np.arange(H) < PANEL_CY)[:, None, None]
GRAD_DIM = np.where(np.arange(H) < PANEL_CY, 0.35 + 0.65 * np.arange(H) / PANEL_CY, 1 - 0.65 * (np.arange(H) - PANEL_CY) / (H - PANEL_CY)).astype(np.float32)[:, None, None]


def compose(src, t, kf):
    # plain vertical gradient from the panel's own top and bottom edge colours, so no shapes ghost behind the text
    top = src[:12].reshape(-1, 3).mean(axis=0, dtype=np.float32)
    bot = src[CROP_H - 12:CROP_H].reshape(-1, 3).mean(axis=0, dtype=np.float32)
    frame = np.ones((H, W, 3), np.float32) * (np.where(GRAD_IS_TOP, top, bot) * GRAD_DIM)
    w, cx = crop_at(t, kf)
    w = int(round(w)) // 2 * 2
    x0 = int(np.clip(round(cx - w / 2), 0, 1920 - w))
    h = int(round(CROP_H * W / w))
    fg = cv2.resize(src[0:CROP_H, x0:x0 + w], (W, h), interpolation=cv2.INTER_CUBIC if w < W else cv2.INTER_AREA).astype(np.float32)
    y0 = PANEL_CY - h // 2
    m = mask(h)
    frame[y0:y0 + h] = frame[y0:y0 + h] * (1 - m) + fg * m
    return frame.clip(0, 255).astype(np.uint8)


def build_audio(cfg, path):
    parts, labels = [], []
    for i, sg in enumerate(cfg['segs']):
        n = round((sg['e'] - sg['s']) * FPS) / FPS
        parts.append(f"[0:a]atrim=start={sg['s']}:duration={n},asetpts=PTS-STARTPTS,afade=in:d=0.05,afade=out:st={n - 0.05}:d=0.05[a{i}]")
        labels.append(f'[a{i}]')
    total = sum(round((s['e'] - s['s']) * FPS) / FPS for s in cfg['segs'])
    fc = ';'.join(parts) + ';' + ''.join(labels) + f'concat=n={len(labels)}:v=0:a=1,afade=out:st={total - 0.25}:d=0.25[a]'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-filter_complex', fc, '-map', '[a]', '-vn', '-ar', '44100', '-ac', '2', path], check=True)
    return total


def render(name, cfg, srt, cut):
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, name + '.mp4')
    wav = out + '.wav'
    total = build_audio(cfg, wav)
    track = caption_track(cfg, srt, cut)
    json.dump(dict(head=cfg['head'], duration=round(total, 3), captions=track), open(os.path.join(OUT, name + '.captions.json'), 'w'), indent=1, ensure_ascii=False)
    font = ImageFont.truetype(BOLD, CAP_SIZE)
    probe = ImageDraw.Draw(Image.new('L', (8, 8)))
    layers = [(c['start'], c['end'], text_layer(wrap(probe, c['text'], font, CAP_W), font, top=CAP_TOP, stroke=6)) for c in track]
    head = head_layer(cfg['head'])
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', wav,
                            '-c:v', 'libx264', '-crf', '20', '-preset', 'medium', '-threads', '4', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', out], stdin=subprocess.PIPE)
    n_out = 0
    for sg in cfg['segs']:
        n = round((sg['e'] - sg['s']) * FPS)
        dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(sg['s']), '-i', SRC, '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-threads', '2', '-'], stdout=subprocess.PIPE)
        for i in range(n):
            raw = dec.stdout.read(1920 * 1080 * 3)
            if len(raw) < 1920 * 1080 * 3:
                sys.exit(f'{name}: source ran out at segment frame {i}/{n}')
            src = np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3)
            frame = compose(src, sg['s'] + i / FPS, sg['kf'])
            blend(frame, head)
            t = n_out / FPS
            for a, z, lay in layers:
                if a <= t < z:
                    blend(frame, lay)
                    break
            if t > total - 0.25:
                frame = (frame * max(0.0, (total - t) / 0.25)).astype(np.uint8)
            enc.stdin.write(frame.tobytes())
            n_out += 1
        dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    os.remove(wav)
    print(name, 'frames', n_out, 'duration', round(total, 2), 'size', os.path.getsize(out), flush=True)


def main():
    all_shorts, cut = shorts()
    print('intro cut at', round(cut, 3), flush=True)
    srt = parse_srt()
    for name in sys.argv[1:] or list(all_shorts):
        render(name, all_shorts[name], srt, cut)


if __name__ == '__main__':
    main()

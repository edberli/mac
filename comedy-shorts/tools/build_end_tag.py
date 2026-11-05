"""Build brand/end_tag.mp4: 2.0 s, 1080x1920, 30 fps end card.

Animation: card cover-scaled to frame, 12 fps stepped frames.
Punch-in 108% -> 100% over first 0.35 s (ease-out-back, small overshoot),
then +/-2 px jitter, offset changes every 2 animation frames.
Audio: reused from the previous end_tag.mp4 (already -14.0 LUFS).
Usage: python3 build_end_tag.py <card.png> <audio.wav> <out.mp4> <workdir>
"""
import math, os, subprocess, sys
from PIL import Image

W, H, FPS_ANIM, FPS_OUT, DUR = 1080, 1920, 12, 30, 2.0
PUNCH = 0.35
JITTER = [(2, -1), (-2, 1), (1, 2), (-1, -2), (2, 2), (-2, -1), (1, -2), (-1, 1), (0, 2), (-2, 0)]

def ease_out_back(p, c1=1.2):
    c3 = c1 + 1
    u = p - 1
    return 1 + c3 * u ** 3 + c1 * u ** 2

def scale_at(t):
    if t >= PUNCH:
        return 1.0
    return 1.08 - 0.08 * ease_out_back(t / PUNCH)

def main():
    card_path, audio_path, out_path, work = sys.argv[1:5]
    os.makedirs(work, exist_ok=True)
    card = Image.open(card_path).convert("RGB")
    # cover-scale to 1080x1920
    s = max(W / card.width, H / card.height)
    cw, ch = math.ceil(card.width * s), math.ceil(card.height * s)
    cover = card.resize((cw, ch), Image.LANCZOS)
    left, top = (cw - W) // 2, (ch - H) // 2
    cover = cover.crop((left, top, left + W, top + H))
    # background fill = mean of the four corner patches (dark brown paper)
    px = [cover.crop(b).resize((1, 1), Image.BOX).getpixel((0, 0))
          for b in [(0, 0, 40, 40), (W - 40, 0, W, 40), (0, H - 40, 40, H), (W - 40, H - 40, W, H)]]
    bg = tuple(sum(p[i] for p in px) // 4 for i in range(3))
    n = int(DUR * FPS_ANIM)
    for i in range(n):
        t = i / FPS_ANIM
        sc = scale_at(t)
        dx = dy = 0
        if t >= PUNCH:
            dx, dy = JITTER[((i - 5) // 2) % len(JITTER)]
        fw, fh = round(W * sc), round(H * sc)
        frame = Image.new("RGB", (W, H), bg)
        scaled = cover.resize((fw, fh), Image.LANCZOS)
        frame.paste(scaled, ((W - fw) // 2 + dx, (H - fh) // 2 + dy))
        frame.save(os.path.join(work, f"f_{i:03d}.png"))
    tmp = os.path.join(work, "end_tag_tmp.mp4")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-framerate", str(FPS_ANIM), "-i", os.path.join(work, "f_%03d.png"),
        "-i", audio_path,
        "-vf", f"fps={FPS_OUT},format=yuv420p",
        "-map", "0:v", "-map", "1:a", "-t", str(DUR),
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out_path)

if __name__ == "__main__":
    main()

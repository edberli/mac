"""Turn a script (beats) + synthesized audio into a frame timeline.

usage: python3 tools/timeline.py script/ep01_intro.json build/ep01_intro
Writes build/<ep>/timeline.json with line timings, scene marks and
per-frame speech envelopes (used to animate talking).
"""
import json, os, sys, wave
import numpy as np

FPS = 30


def load(path):
    w = wave.open(path)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if w.getnchannels() > 1:
        a = a.reshape(-1, w.getnchannels()).mean(1)
    return a, w.getframerate()


def main(script_path, out_dir):
    sc = json.load(open(script_path))
    t, n, lines, marks = 0.0, 0, [], {}
    for b in sc['beats']:
        if 'mark' in b:
            marks[b['mark']] = round(t, 3)
        elif 'pause' in b:
            t += b['pause']
        elif 'say' in b:
            a, sr = load(os.path.join(out_dir, 'audio', f'l{n:02d}.wav'))
            d = len(a) / sr
            lines.append(dict(i=n, sp=b['say'], text=b['text'], start=round(t, 3), end=round(t + d, 3)))
            t += d
            n += 1
    end = marks.get('end', t)
    nf = int(np.ceil(end * FPS))
    env = {k: np.zeros(nf) for k in sc['voices']}
    for ln in lines:
        a, sr = load(os.path.join(out_dir, 'audio', f'l{ln["i"]:02d}.wav'))
        hop = sr // FPS
        for f in range(len(a) // hop):
            fi = int(round(ln['start'] * FPS)) + f
            if fi < nf:
                env[ln['sp']][fi] = max(env[ln['sp']][fi], float(np.sqrt((a[f * hop:(f + 1) * hop] ** 2).mean())))
    for k in env:
        m = env[k].max() or 1
        env[k] = np.minimum(env[k] / m * 1.6, 1)
    json.dump(dict(fps=FPS, frames=nf, lines=lines, scenes=marks, sfx=sc.get('sfx', []),
                   env={k: [round(float(x), 3) for x in v] for k, v in env.items()}),
              open(os.path.join(out_dir, 'timeline.json'), 'w'))
    for l in lines:
        print(f"{l['start']:7.2f}-{l['end']:7.2f} {l['sp']} {l['text']}")
    print('marks:', marks, 'frames:', nf)


if __name__ == '__main__':
    main(*sys.argv[1:3])

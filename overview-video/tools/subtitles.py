"""Build YouTube subtitle files (SRT) for the joined episode from the segment timelines.

usage: python3 tools/subtitles.py ep01 ep01_intro ep01_main
Writes publish/<ep>.en.srt, publish/<ep>.zh-Hans.srt, publish/<ep>.zh-Hant.srt and publish/<ep>.chapters.json.
Inserted clips (script "inserts") shift later lines; each segment starts where the previous one ends.
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, '.pydeps'))


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True, check=True).stdout)


def ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def main(ep, *segs):
    zh = json.load(open(os.path.join(ROOT, 'script', f'{ep}_zh.json')))
    from opencc import OpenCC
    s2t = OpenCC('s2tw')
    cues, marks, offset = [], {}, 0.0
    for seg in segs:
        tl = json.load(open(os.path.join(ROOT, 'build', seg, 'timeline.json')))
        sc = json.load(open(os.path.join(ROOT, 'script', f'{seg}.json')))
        ins = [(tl['scenes'][i['at']], dur(os.path.join(ROOT, i['file']))) for i in sc.get('inserts', [])]
        shift = lambda t: t + sum(d for at, d in ins if t >= at - 1e-6)
        for k, v in tl['scenes'].items():
            marks[f'{seg}.{k}'] = offset + shift(v)
        for ln in tl['lines']:
            cues.append((offset + shift(ln['start']), offset + shift(ln['end']) + 0.15, ln['text'], zh[seg][ln['i']]))
        offset += tl['frames'] / tl['fps'] + sum(d for _, d in ins)
    os.makedirs(os.path.join(ROOT, 'publish'), exist_ok=True)
    for lang, pick in [('en', lambda c: c[2]), ('zh-Hans', lambda c: c[3]), ('zh-Hant', lambda c: s2t.convert(c[3]))]:
        with open(os.path.join(ROOT, 'publish', f'{ep}.{lang}.srt'), 'w', encoding='utf-8') as f:
            for n, c in enumerate(cues, 1):
                f.write(f'{n}\n{ts(c[0])} --> {ts(c[1])}\n{pick(c)}\n\n')
    json.dump({k: round(v, 2) for k, v in marks.items()}, open(os.path.join(ROOT, 'publish', f'{ep}.marks.json'), 'w'), indent=1)
    print(f'{len(cues)} cues, total {offset:.2f}s')


if __name__ == '__main__':
    main(*sys.argv[1:])

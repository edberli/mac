"""Mix voice lines + placeholder ambience / sound effects into one track.

usage: python3 tools/mix.py build/ep01_intro
Writes build/<ep>/mix.wav (loudness-normalised to -16 LUFS).
The pad / hit / whoosh are simple synthesized placeholders, not music.
"""
import json, os, subprocess, sys


def main(out_dir):
    tl = json.load(open(os.path.join(out_dir, 'timeline.json')))
    end = tl['scenes'].get('end') or tl['frames'] / tl['fps']
    M = tl['scenes']
    inputs, chains, labels = [], [], []
    count = lambda: sum(1 for a in inputs if a == '-i')  # number of ffmpeg inputs so far
    for ln in tl['lines']:
        k = count()
        inputs += ['-i', os.path.join(out_dir, 'audio', f"l{ln['i']:02d}.wav")]
        ms = int(ln['start'] * 1000)
        chains.append(f'[{k}]adelay={ms}|{ms}[v{k}]')
        labels.append(f'[v{k}]')
    nv = len(labels)
    chains.append(''.join(labels) + f'amix=inputs={nv}:normalize=0[vox]')
    fx_labels = []
    for j, s in enumerate(tl.get('sfx', [])):
        k = count()
        if s['type'] == 'pad':
            a, b = M[s['from']], M[s['to']]
            d = b - a
            for f in (55, 82.4, 110):
                inputs += ['-f', 'lavfi', '-i', f'sine=f={f}:d={d}:sample_rate=44100']
            chains.append(f'[{k}][{k+1}][{k+2}]amix=inputs=3,tremolo=f=0.12:d=0.35,lowpass=f=400,'
                          f'afade=t=in:d=2,afade=t=out:st={max(d-1.5,0)}:d=1.5,volume=0.9,adelay={int(a*1000)}|{int(a*1000)}[fx{j}]')
        elif s['type'] == 'hit':
            a = M[s['at']]
            inputs += ['-f', 'lavfi', '-i', 'sine=f=48:d=2.2:sample_rate=44100', '-f', 'lavfi', '-i', 'anoisesrc=c=brown:d=2.2:r=44100:a=0.6']
            chains.append(f'[{k}][{k+1}]amix=inputs=2,lowpass=f=180,afade=t=in:d=0.01,afade=t=out:st=0.05:d=2.1,volume=2.2,'
                          f'adelay={int(a*1000)}|{int(a*1000)}[fx{j}]')
        elif s['type'] == 'whoosh':
            a, d = M[s['at']], s['dur']
            inputs += ['-f', 'lavfi', '-i', f'anoisesrc=c=pink:d={d+0.4}:r=44100:a=0.5']
            chains.append(f'[{k}]lowpass=f=900,highpass=f=80,afade=t=in:d={d*0.7},afade=t=out:st={d*0.8}:d={d*0.3+0.4},volume=0.55,'
                          f'adelay={int(a*1000)}|{int(a*1000)}[fx{j}]')
        fx_labels.append(f'[fx{j}]')
    chains.append('[vox]' + ''.join(fx_labels) + f'amix=inputs={1+len(fx_labels)}:normalize=0,atrim=0:{end},'
                  'aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11[out]')
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(chains), '-map', '[out]', '-ar', '44100',
           os.path.join(out_dir, 'mix.wav')]
    subprocess.run(cmd, check=True)
    print('mix.wav written')


if __name__ == '__main__':
    main(sys.argv[1])

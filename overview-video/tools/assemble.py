"""Splice pre-made clips (e.g. the channel intro) into a rendered segment.

usage: python3 tools/assemble.py script/ep01_intro.json build/ep01_intro
Reads "inserts" from the script, e.g.
  {"file": "assets/brand/wait-what-intro-5s.mp4", "at": "paris", "gain_db": 11}
and cuts build/<ep>/<ep>.mp4 at each scene mark, inserting the clip there.
Output: build/<ep>/<ep>_final.mp4 (1920x1080, 30 fps, AAC 44.1 kHz stereo).
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(script_path, out_dir):
    sc = json.load(open(script_path))
    tl = json.load(open(os.path.join(out_dir, 'timeline.json')))
    ep = os.path.basename(out_dir.rstrip('/'))
    src = os.path.join(out_dir, f'{ep}.mp4')
    inserts = sorted(sc.get('inserts', []), key=lambda i: tl['scenes'][i['at']])
    fps = tl['fps']
    cuts = [round(tl['scenes'][i['at']] * fps) for i in inserts]  # cut on exact frames
    inputs = ['-i', src]
    for ins in inserts:
        inputs += ['-i', os.path.join(ROOT, ins['file'])]
    chains, order, prev = [], [], 0
    for k, (ins, cut) in enumerate(zip(inserts, cuts)):
        chains.append(f'[0:v]trim=start_frame={prev}:end_frame={cut},setpts=PTS-STARTPTS[mv{k}]')
        chains.append(f'[0:a]atrim=start={prev / fps}:end={cut / fps},asetpts=PTS-STARTPTS[ma{k}]')
        chains.append(f'[{k + 1}:v]fps={fps},scale=1920:1080,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[iv{k}]')
        chains.append(f'[{k + 1}:a]aresample=44100,aformat=channel_layouts=stereo,volume={ins.get("gain_db", 0)}dB,asetpts=PTS-STARTPTS[ia{k}]')
        order += [f'[mv{k}][ma{k}]', f'[iv{k}][ia{k}]']
        prev = cut
    n = len(inserts)
    chains.append(f'[0:v]trim=start_frame={prev},setpts=PTS-STARTPTS[mv{n}]')
    chains.append(f'[0:a]atrim=start={prev / fps},asetpts=PTS-STARTPTS[ma{n}]')
    order.append(f'[mv{n}][ma{n}]')
    chains.append(''.join(order) + f'concat=n={len(order)}:v=1:a=1[v][a]')
    out = os.path.join(out_dir, f'{ep}_final.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(chains), '-map', '[v]', '-map', '[a]',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'slow', '-r', str(fps),
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', out], check=True)
    print('wrote', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])

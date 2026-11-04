"""Make a second-language audio track for a finished episode (for YouTube "multi-language audio").

The picture stays exactly as it is: every translated line is placed in the SAME time slot as the
English line (time-stretched 0.8x-1.25x if needed), mixed with the same ambience/effects, and the
channel intro is spliced in at the same point. Result: one audio file as long as the video.

usage:
  python3 tools/dub.py ep01 zh --human "Chinese (Mandarin)_Straightforward_Boy" --axis "Chinese (Mandarin)_Sincere_Adult"
  python3 tools/dub.py ep01 zh --samples ...      # only the first 4 lines of each segment, to audition voices
  python3 tools/dub.py ep01 zh --reuse ...        # skip synthesis, reuse build/<seg>/dub_<lang>/raw/*.wav

Inputs : script/<ep>_<lang>.json            translated lines per segment (same order as the English beats)
         script/<seg>.json                  speakers, emotions, inserts (channel intro)
         script/timelines/<seg>.json        timing of the published English cut
Output : publish/<ep>.audio.<lang>.m4a      upload in YouTube Studio > Subtitles/Languages > Audio track
Needs  : MINIMAX_API_KEY in the environment (see tools/tts_minimax.py), ffmpeg.
"""
import argparse, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mix as MIX  # noqa: E402


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True, check=True).stdout)


def run(*a):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep'); ap.add_argument('lang')
    ap.add_argument('--human', required=True); ap.add_argument('--axis', required=True)
    ap.add_argument('--axis-fx', default='robot', help="post effect for AXIS: robot (current EN choice) | robot_light | ai | ''")
    ap.add_argument('--samples', action='store_true'); ap.add_argument('--reuse', action='store_true')
    a = ap.parse_args()
    tr = json.load(open(os.path.join(ROOT, 'script', f'{a.ep}_{a.lang}.json')))
    voices = {'H': {'minimax': a.human, 'minimax_fx': ''}, 'A': {'minimax': a.axis, 'minimax_fx': a.axis_fx}}
    if not a.reuse:
        import tts_minimax as TTS
    parts = []
    for seg, lines in tr.items():
        sc = json.load(open(os.path.join(ROOT, 'script', f'{seg}.json')))
        tl_path = os.path.join(ROOT, 'script', 'timelines', f'{seg}.json')
        tl = json.load(open(tl_path))
        emo = [b.get('emotion') for b in sc['beats'] if 'say' in b]
        out = os.path.join(ROOT, 'build', seg, f'dub_{a.lang}')
        os.makedirs(os.path.join(out, 'raw'), exist_ok=True); os.makedirs(os.path.join(out, 'audio'), exist_ok=True)
        todo = tl['lines'][:4] if a.samples else tl['lines']
        for ln in todo:
            raw = os.path.join(out, 'raw', f"l{ln['i']:02d}.wav")
            if not a.reuse:
                TTS.synth(lines[ln['i']], voices[ln['sp']], emo[ln['i']], raw)
            slot = ln['end'] - ln['start']
            nxt = next((l['start'] for l in tl['lines'] if l['start'] > ln['start']), ln['end'] + 1.5)
            room = nxt - ln['start'] - 0.1          # its slot plus the pause before the next line
            d = dur(raw)
            tempo = min(max(d / room, 1.0), 1.25) if d > room else 1.0
            if d / tempo > room + 0.05:
                print(f"  ! {seg} l{ln['i']:02d} still {d / tempo - room:.2f}s too long - shorten the translation")
            run('-i', raw, '-af', f'atempo={tempo:.4f}', '-ac', '1', '-ar', '44100', os.path.join(out, 'audio', f"l{ln['i']:02d}.wav"))
            print(f"{seg} l{ln['i']:02d} {ln['sp']} {d:5.2f}s / room {room:5.2f}s tempo {tempo:.2f}  {lines[ln['i']][:24]}")
        if a.samples:
            continue
        MIX.main(out, audio_dir=os.path.join(out, 'audio'), out_name='mix.wav', timeline=tl_path)
        # splice inserted clips' audio (e.g. channel intro) at their scene marks, like tools/assemble.py does for video
        cur, prev = os.path.join(out, 'mix.wav'), 0.0
        for k, ins in enumerate(sorted(sc.get('inserts', []), key=lambda i: tl['scenes'][i['at']])):
            at = round(tl['scenes'][ins['at']] * tl['fps']) / tl['fps']
            p1, p2 = os.path.join(out, f'p{k}a.wav'), os.path.join(out, f'p{k}b.wav')
            run('-i', cur, '-af', f'atrim={prev}:{at},asetpts=PTS-STARTPTS', '-ar', '44100', '-ac', '2', p1)
            run('-i', os.path.join(ROOT, ins['file']), '-vn', '-af', f"aresample=44100,volume={ins.get('gain_db', 0)}dB", '-ac', '2', p2)
            parts += [p1, p2]; prev = at
        tail = os.path.join(out, 'tail.wav')
        run('-i', cur, '-af', f'atrim={prev},asetpts=PTS-STARTPTS', '-ar', '44100', '-ac', '2', tail)
        parts.append(tail)
    if a.samples:
        print('samples in build/<seg>/dub_%s/audio - listen, then run again without --samples' % a.lang); return
    lst = os.path.join(ROOT, 'build', f'{a.ep}_dub_{a.lang}.txt')
    open(lst, 'w').writelines(f"file '{p}'\n" for p in parts)
    dst = os.path.join(ROOT, 'publish', f'{a.ep}.audio.{a.lang}.m4a')
    run('-f', 'concat', '-safe', '0', '-i', lst, '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', dst)
    print('wrote', dst, f'{dur(dst):.2f}s')


if __name__ == '__main__':
    main()

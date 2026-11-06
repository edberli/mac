"""Fit new voice recordings into an existing timeline so the frames need no re-render.

usage: python3 tools/fit_audio.py build/ep01_main <new_audio_dir>
For each line in build/<ep>/timeline.json, takes <new_audio_dir>/lNN.wav (or .mp3/.m4a),
time-stretches it to the original slot length (tempo limited to 0.8x-1.25x so it stays natural)
and writes build/<ep>/audio/lNN.wav. Then run tools/mix.py and re-encode as usual.
"""
import json, os, subprocess, sys


def dur(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                capture_output=True, text=True, check=True).stdout)


def main(out_dir, new_dir):
    tl = json.load(open(os.path.join(out_dir, 'timeline.json')))
    for ln in tl['lines']:
        src = next((os.path.join(new_dir, f"l{ln['i']:02d}{ext}") for ext in ('.wav', '.mp3', '.m4a')
                    if os.path.exists(os.path.join(new_dir, f"l{ln['i']:02d}{ext}"))), None)
        if not src:
            sys.exit(f"missing l{ln['i']:02d} in {new_dir}")
        slot = ln['end'] - ln['start']
        tempo = min(max(dur(src) / slot, 0.8), 1.25)
        out = os.path.join(out_dir, 'audio', f"l{ln['i']:02d}.wav")
        if os.path.abspath(src) == os.path.abspath(out):
            tmp = out + '.src.wav'; os.replace(src, tmp); src = tmp
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', f'atempo={tempo:.4f}', '-ac', '1', '-ar', '44100', out], check=True)
        print(f"l{ln['i']:02d} slot {slot:5.2f}s tempo {tempo:.2f}")


if __name__ == '__main__':
    main(*sys.argv[1:3])

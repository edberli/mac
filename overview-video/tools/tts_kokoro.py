"""Natural-sounding placeholder voices with Kokoro (Apache-2.0, runs offline on CPU).

usage: python3 tools/tts_kokoro.py script/ep01_main.json build/ep01_main
Voices come from the script's "voices" entries: {"kokoro": "am_michael", "speed": 1.0, "fx": "human" | "ai"}.
Writes build/<ep>/audio/lNN.wav (44.1 kHz), same layout as tools/tts.py.
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, '.pydeps-kokoro'))
import soundfile as sf  # noqa: E402
from kokoro_onnx import Kokoro  # noqa: E402

FX = {
    'human': 'aresample=44100,highpass=f=70,acompressor=threshold=-18dB:ratio=3',
    # AXIS: natural voice with a light digital sheen (not the old pitched-down robot)
    'ai': 'aresample=44100,chorus=0.7:0.9:18:0.22:0.25:2,highpass=f=90,acompressor=threshold=-18dB:ratio=3',
}


def synth(k, text, voice, speed, fx, out):
    audio, sr = k.create(text, voice=voice, speed=speed, lang='en-us' if voice[0] == 'a' else 'en-gb')
    raw = out.replace('.wav', '_raw.wav')
    sf.write(raw, audio, sr)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', FX[fx], '-ar', '44100', out], check=True)


def main(script_path, out_dir):
    sc = json.load(open(script_path))
    k = Kokoro(os.path.join(ROOT, '.voices/kokoro/kokoro-v1.0.onnx'), os.path.join(ROOT, '.voices/kokoro/voices-v1.0.bin'))
    os.makedirs(os.path.join(out_dir, 'audio'), exist_ok=True)
    n = 0
    for b in sc['beats']:
        if 'say' in b:
            v = sc['voices'][b['say']]
            synth(k, b['text'], v['kokoro'], v.get('speed', 1.0), v.get('kfx', 'human'), os.path.join(out_dir, 'audio', f'l{n:02d}.wav'))
            n += 1
    print(f'{n} lines synthesized')


if __name__ == '__main__':
    main(*sys.argv[1:3])

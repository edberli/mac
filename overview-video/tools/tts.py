"""Synthesize every spoken line of a script with Piper (offline TTS).

usage: python3 tools/tts.py script/ep01_intro.json build/ep01_intro
Writes build/<ep>/audio/lNN.wav (44.1 kHz) with the voice effect applied.
These are PLACEHOLDER voices; final narration will be recorded by a person.
"""
import json, os, subprocess, sys, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, '.pydeps'))
from piper import PiperVoice  # noqa: E402
from piper.config import SynthesisConfig  # noqa: E402

FX = {
    'robot': 'asetrate=22050*0.96,aresample=44100,aecho=0.8:0.6:7:0.3,highpass=f=110,acompressor',
    'human': 'aresample=44100,acompressor',
}


def main(script_path, out_dir):
    sc = json.load(open(script_path))
    audio = os.path.join(out_dir, 'audio')
    os.makedirs(audio, exist_ok=True)
    voices = {k: PiperVoice.load(os.path.join(ROOT, '.voices', v['model'] + '.onnx')) for k, v in sc['voices'].items()}
    n = 0
    for b in sc['beats']:
        if 'say' not in b:
            continue
        raw = os.path.join(audio, f'l{n:02d}_raw.wav')
        with wave.open(raw, 'wb') as w:
            voices[b['say']].synthesize_wav(b['text'], w, syn_config=SynthesisConfig(length_scale=1.0))
        fx = FX[sc['voices'][b['say']]['fx']]
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', fx, '-ar', '44100', os.path.join(audio, f'l{n:02d}.wav')], check=True)
        n += 1
    print(f'{n} lines synthesized')


if __name__ == '__main__':
    main(*sys.argv[1:3])

#!/usr/bin/env python3
"""Synthesize every spoken beat of a sketch with MiniMax, trimmed of silence.

The key comes from the environment only:
  MINIMAX_API_KEY="$(security find-generic-password -s minimax-coding-plan-key -w)" MINIMAX_BASE=https://api.minimaxi.com python3 tts.py beats.json out_dir

Beats sharing the same role and "take" reuse one recording, so a repeated line is delivered identically.
"""
import json, os, subprocess, sys, urllib.request

BASE = os.environ.get('MINIMAX_BASE', 'https://api.minimaxi.com').rstrip('/')
MODEL = os.environ.get('MINIMAX_MODEL', 'speech-02-hd')
TRIM = 'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.01,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse'


def synth(text, voice, speed, emotion, out):
    settings = {'voice_id': voice, 'speed': speed}
    if emotion:
        settings['emotion'] = emotion
    body = {'model': MODEL, 'text': text, 'stream': False, 'voice_setting': settings,
            'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3', 'channel': 1}}
    req = urllib.request.Request(BASE + '/v1/t2a_v2', data=json.dumps(body).encode(), headers={
        'Authorization': 'Bearer ' + os.environ['MINIMAX_API_KEY'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    status = res.get('base_resp', {})
    if status.get('status_code', 0) != 0:
        sys.exit(f"MiniMax error {status.get('status_code')}: {status.get('status_msg')}")
    mp3 = out + '.mp3'
    with open(mp3, 'wb') as f:
        f.write(bytes.fromhex(res['data']['audio']))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp3, '-af', TRIM, '-ac', '1', '-ar', '44100', out], check=True)
    os.remove(mp3)


def main(script, out_dir):
    sc = json.load(open(script))
    os.makedirs(out_dir, exist_ok=True)
    manifest, made = [], {}
    for i, b in enumerate(sc['beats']):
        if 'say' not in b:
            manifest.append(None)
            continue
        key = (b['say'], b['take']) if 'take' in b else i
        if key not in made:
            path = os.path.join(out_dir, f'l{i:02d}.wav')
            v = sc['voices'][b['say']]
            if not os.path.exists(path):
                synth(b.get('tts_text', b['text']), v['minimax'], b.get('speed', v.get('speed', 1.0)), b.get('emotion'), path)
            made[key] = path
        dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', made[key]]))
        manifest.append({'file': os.path.basename(made[key]), 'dur': round(dur, 3)})
        print(i, b['say'], round(dur, 2), b['text'], flush=True)
    json.dump(manifest, open(os.path.join(out_dir, 'manifest.json'), 'w'), indent=1)
    print('total speech', round(sum(m['dur'] for m in manifest if m), 2), 'calls', len(made))


if __name__ == '__main__':
    main(*sys.argv[1:3])

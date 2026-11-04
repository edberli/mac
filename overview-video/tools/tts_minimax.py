"""Expressive voices with the MiniMax text-to-speech API (uses YOUR MiniMax account).

The key is read from the environment, never from the repository:
  export MINIMAX_API_KEY=...            # required
  export MINIMAX_GROUP_ID=...           # only if your account shows a Group ID
  export MINIMAX_BASE=https://api.minimax.io   # China accounts: https://api.minimaxi.com
  export MINIMAX_MODEL=speech-02-hd     # optional

usage:
  python3 tools/tts_minimax.py --list                                   # list system voice IDs
  python3 tools/tts_minimax.py script/ep01_main.json build/ep01_main    # synthesize all lines
Voices come from the script's "voices": {"A": {"minimax": "<voice_id>", "speed": 1.0, ...}}.
A beat may carry "emotion": happy | sad | angry | fearful | disgusted | surprised | neutral.
Writes build/<ep>/audio/lNN.wav (44.1 kHz mono), same layout as the other TTS tools.
"""
import json, os, subprocess, sys, urllib.request

BASE = os.environ.get('MINIMAX_BASE', 'https://api.minimax.io').rstrip('/')
MODEL = os.environ.get('MINIMAX_MODEL', 'speech-02-hd')


def call(path, body):
    key = os.environ.get('MINIMAX_API_KEY')
    if not key:
        sys.exit('MINIMAX_API_KEY is not set')
    url = BASE + path + (f"?GroupId={os.environ['MINIMAX_GROUP_ID']}" if os.environ.get('MINIMAX_GROUP_ID') else '')
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    st = res.get('base_resp', {})
    if st.get('status_code', 0) != 0:
        sys.exit(f"MiniMax error {st.get('status_code')}: {st.get('status_msg')}")
    return res


def synth(text, v, emotion, out):
    vs = {'voice_id': v['minimax'], 'speed': v.get('speed', 1.0), 'vol': v.get('vol', 1.0), 'pitch': v.get('pitch', 0)}
    if emotion:
        vs['emotion'] = emotion
    res = call('/v1/t2a_v2', {'model': MODEL, 'text': text, 'stream': False, 'voice_setting': vs,
                              'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3', 'channel': 1}})
    mp3 = out.replace('.wav', '.mp3')
    with open(mp3, 'wb') as f:
        f.write(bytes.fromhex(res['data']['audio']))
    fx = 'aresample=44100' + (',chorus=0.7:0.9:18:0.22:0.25:2' if v.get('minimax_fx', 'ai' if v.get('fx') == 'robot' else '') == 'ai' else '')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp3, '-af', fx, '-ac', '1', '-ar', '44100', out], check=True)


def main(args):
    if args and args[0] == '--list':
        res = call('/v1/get_voice', {'voice_type': 'system'})
        for v in res.get('system_voice', []):
            print(v.get('voice_id'), '|', v.get('voice_name'), '|', (v.get('description') or [''])[0] if isinstance(v.get('description'), list) else v.get('description'))
        return
    script_path, out_dir = args[:2]
    sc = json.load(open(script_path))
    os.makedirs(os.path.join(out_dir, 'audio'), exist_ok=True)
    n = 0
    for b in sc['beats']:
        if 'say' in b:
            synth(b['text'], sc['voices'][b['say']], b.get('emotion'), os.path.join(out_dir, 'audio', f'l{n:02d}.wav'))
            print(f'l{n:02d} {b["say"]}: {b["text"][:50]}')
            n += 1
    print(f'{n} lines synthesized')


if __name__ == '__main__':
    main(sys.argv[1:])

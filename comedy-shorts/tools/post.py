#!/usr/bin/env python3
"""Upload a Short to the WaitWhat channel and publish it. Records the video id as soon as it exists, so it can never upload twice; only re-publishes after that."""
import json, os, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_shorts as y
import yt_short_finish as f

FILE, TITLE, DESC = sys.argv[1:4]
y.STATE = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/posted.json'

# Chrome's default YouTube account is not WaitWhat's, so every Studio URL names the account explicitly
_call = y.call


def call(action, args, *a, **k):
    if action == 'navigate' and 'studio.youtube.com' in args.get('url', ''):
        args = dict(args, url=args['url'] + ('&' if '?' in args['url'] else '?') + 'authuser=3')
    return _call(action, args, *a, **k)


y.call = call


def main():
    done = json.load(open(y.STATE)) if os.path.exists(y.STATE) else {}
    if FILE not in done:
        try:
            y.post(FILE, TITLE, DESC)
        except SystemExit as e:
            print('post stopped:', e, flush=True)
    done = json.load(open(y.STATE)) if os.path.exists(y.STATE) else {}
    if FILE not in done:
        sys.exit('no video id recorded; nothing was uploaded as far as this script knows')
    vid = done[FILE]
    print('video', vid, flush=True)
    # earlier Shorts only went public once YouTube had processed them for a few minutes
    for attempt in range(4):
        info = y.read_back(vid)
        print('READBACK', attempt, json.dumps(info, ensure_ascii=False), flush=True)
        if info.get('oembed_status') == 200:
            return
        time.sleep(90)
        f.main(vid)
    sys.exit(f'{vid} still not public after 4 attempts')


if __name__ == '__main__':
    try:
        main()
    finally:
        print('tabs left', y.close_all(), flush=True)

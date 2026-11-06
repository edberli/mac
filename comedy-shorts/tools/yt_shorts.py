#!/usr/bin/env python3
"""Upload the EP01 Shorts to the WaitWhat channel and publish them. Stops at the first surprise; never retries a finished upload."""
import base64, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
import yt_upload1 as u

u.SESSION = 'waitwhat-shorts'
call, js, dump, wait = u.call, u.js, u.dump, u.wait
ROOT = '/Volumes/core/AI-Workspace/Claude/mac/overview-video/publish'
STATE = '/Volumes/core/AI-Workspace/Claude/mac-work/shorts/posted.json'
GUARD = '/Volumes/core/claude-work/bin/agent-browser-guard.py'
md = open(os.path.join(ROOT, 'ep01_shorts.md'), encoding='utf-8').read()
JOBS = re.findall(r'## \d\. `shorts/([\w.]+\.mp4)`.*?Title: (.*?)\n\nDescription: (.*?)\n', md, re.S)
CHUNK = 4_500_000


def guard():
    r = subprocess.run(['python3', GUARD, '--check'], capture_output=True, text=True)
    if r.returncode != 0 or not json.loads(r.stdout).get('allowed'):
        sys.exit('browser guard refused: ' + r.stdout[:300])


def set_box(sel, text):
    return js("""(()=>{const e=document.querySelector(%s);if(!e)return 'missing';e.focus();e.innerText=%s;
      e.dispatchEvent(new InputEvent('input',{bubbles:true,composed:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();
      return e.innerText})()""" % (json.dumps(sel), json.dumps(text)))


def click(sel):
    return js("(()=>{const b=document.querySelector(%s);if(!b)return 'missing';(b.querySelector('button')||b).click();return 'ok'})()" % json.dumps(sel))


def enabled(sel):
    return f"(()=>{{const b=document.querySelector('{sel}');return b&&b.getAttribute('aria-disabled')!=='true'&&!b.hasAttribute('disabled')&&!(b.querySelector('button')||{{}}).disabled}})()"


def inject(path, title):
    js('window.__f=[];1')
    n = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            r = js("(()=>{const b=atob('%s');const a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);window.__f.push(a);return window.__f.length})()" % base64.b64encode(b).decode())
            n += 1
            if r != n:
                sys.exit('chunk transfer failed')
    # the file name becomes the default title, so a wrong title box cannot leave a raw file name public
    name = re.sub(r'[\\/:*?"<>|]', '', title) + '.mp4'
    r = js("(()=>{const f=new File(window.__f,%s,{type:'video/mp4'});const i=document.querySelector('ytcp-uploads-file-picker input[type=file]')||document.querySelector('input[type=file][name=Filedata]');const d=new DataTransfer();d.items.add(f);i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}));window.__f=null;return f.size})()" % json.dumps(name))
    if r != os.path.getsize(path):
        sys.exit(f'size mismatch {r}')


def post(fname, title, desc):
    guard()
    call('navigate', {'url': f'https://studio.youtube.com/channel/{u.CHANNEL}/videos/upload?d=ud', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
    if not wait("document.querySelector('ytcp-uploads-file-picker input[type=file]')||document.querySelector('input[type=file][name=Filedata]')", 60, 'picker'):
        sys.exit('no upload picker')
    channel = js("(document.querySelector('ytcp-navigation-drawer #entity-name, #entity-name')||{}).innerText||''")
    print('channel', repr(channel), flush=True)
    if 'WaitWhat' not in str(channel):
        sys.exit('wrong channel')
    inject(os.path.join(ROOT, 'shorts', fname), title)
    if not wait("document.querySelector('#title-textarea #textbox')", 120, 'details'):
        sys.exit('details form missing')
    time.sleep(3)
    print('title box', repr(set_box('#title-textarea #textbox', title)), flush=True)
    print('desc box', repr(set_box('#description-textarea #textbox', desc)), flush=True)
    print('kids', js("(()=>{const r=document.querySelector('tp-yt-paper-radio-button[name=\"VIDEO_MADE_FOR_KIDS_NOT_MFK\"]');if(!r)return 'missing';r.click();return r.getAttribute('aria-checked')})()"), flush=True)
    time.sleep(2)
    link = ''
    t = time.time()
    while not link and time.time() - t < 240:
        link = js("(document.querySelector('.video-url-fadeable a, ytcp-video-info a')||{}).href||''") or ''
        time.sleep(3)
    print('link', link, flush=True)
    m = re.search(r'(?:youtu\.be/|shorts/|v=)([\w-]{11})', link)
    if not m:
        dump('no link')
        sys.exit('no video id')
    vid = m.group(1)
    # recorded before publishing, so a later failure can never cause a second upload
    done = json.load(open(STATE)) if os.path.exists(STATE) else {}
    done[fname] = vid
    json.dump(done, open(STATE, 'w'), indent=1)
    for step in range(3):
        if not wait(enabled('#next-button'), 180, f'next {step}'):
            sys.exit(f'next button stuck at step {step}')
        print('next', step, click('#next-button'), flush=True)
        time.sleep(3)
    if not wait("document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]')", 30, 'visibility'):
        sys.exit('visibility step missing')
    print('public', js("(()=>{const r=document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]');r.click();return r.getAttribute('aria-checked')})()"), flush=True)
    time.sleep(2)
    if js("document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]').getAttribute('aria-checked')") != 'true':
        sys.exit('public radio not selected')
    if not wait(enabled('#done-button'), 420, 'done'):
        sys.exit('publish button stuck')
    # publish is enabled before the bytes finish, and leaving the page then kills the upload, as happened to a 66 MB file
    label = "(document.querySelector('ytcp-video-upload-progress .progress-label, .progress-label')||{}).innerText||''"
    t = time.time()
    while not re.search('上載完成|處理', str(js(label))):
        if time.time() - t > 1200:
            sys.exit('upload did not finish within 20 minutes: ' + str(js(label)))
        print('uploading', js(label), flush=True)
        time.sleep(20)
    print('progress', js(label), flush=True)
    print('done', click('#done-button'), flush=True)
    # leaving the page straight after the click leaves the video a draft, so give the save time to finish
    time.sleep(30)
    dump('published')
    call('navigate', {'url': f'https://studio.youtube.com/video/{vid}/edit', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
    wait("document.querySelector('#title-textarea #textbox')", 60, 'edit')
    time.sleep(3)
    if '草稿' in str(js("(document.body.innerText||'').slice(0,120)")):
        # the upload wizard's first publish has stayed a draft on every Short so far; publishing from the reopened draft works
        print(vid, 'still a draft, publishing from the reopened draft', flush=True)
        import yt_short_finish
        yt_short_finish.main(vid)
        if '草稿' in str(js("(document.body.innerText||'').slice(0,120)")):
            sys.exit(f'{vid} is still a draft after the second publish')
    return vid


def read_back(vid):
    guard()
    call('navigate', {'url': f'https://studio.youtube.com/video/{vid}/edit', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
    wait("document.querySelector('#title-textarea #textbox')", 60, 'edit')
    time.sleep(3)
    info = dict(
        title=js("(document.querySelector('#title-textarea #textbox')||{}).innerText||''"),
        desc=js("(document.querySelector('#description-textarea #textbox')||{}).innerText||''"),
        visibility=js("(document.querySelector('ytcp-video-metadata-visibility')||{}).innerText||''"),
    )
    code = 0
    for _ in range(8):
        try:
            q = urllib.parse.quote(f'https://www.youtube.com/shorts/{vid}', safe='')
            with urllib.request.urlopen(f'https://www.youtube.com/oembed?format=json&url={q}', timeout=20) as r:
                code = r.status
                info['oembed'] = json.load(r).get('title')
                break
        except Exception as e:
            code = str(e)
            time.sleep(15)
    info['oembed_status'] = code
    return info


def close_all():
    for t in (call('list_tabs', {}).get('data') or {}).get('tabs', []):
        call('close_tab', {'tabId': t['tabId']})
    return call('list_tabs', {}).get('data')


def main():
    print('jobs', [j[0] for j in JOBS], flush=True)
    if len(JOBS) != 3:
        sys.exit('expected 3 jobs')
    done = json.load(open(STATE)) if os.path.exists(STATE) else {}
    try:
        for fname, title, desc in JOBS:
            if fname in done:
                print('skip, already posted', fname, flush=True)
                continue
            done[fname] = post(fname, title, desc)
            json.dump(done, open(STATE, 'w'), indent=1)
            print('POSTED', fname, done[fname], flush=True)
        for fname, vid in done.items():
            print('READBACK', fname, vid, json.dumps(read_back(vid), ensure_ascii=False), flush=True)
    finally:
        print('tabs left', close_all(), flush=True)


if __name__ == '__main__':
    main()

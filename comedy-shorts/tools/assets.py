#!/usr/bin/env python3
"""Generate the sketch's paper backgrounds and puppets through the logged-in ChatGPT web session, one new chat per image. Skips finished images; stops on any login, limit or verification prompt."""
import base64, json, os, re, subprocess, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_upload1 as u

u.SESSION = 'waitwhat-assets'
call, js = u.call, u.js
HERE = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/'
OUT = HERE + 'assets/'
REF = HERE + 'style/frame_a.png'
GUARD = '/Volumes/core/claude-work/bin/agent-browser-guard.py'
MEMORY = '/Users/winstonli/.claude/projects/-Volumes-core-claude-work/memory/chatgpt-use-project-not-sidebar.md'

STYLE = 'Use the attached image as the exact style reference: the same real hand-cut construction paper with fine fibres, slightly uneven scissor edges and a warm palette of muted mustard, brick red, dusty teal, cream and brown. It should read as paper card rather than fuzzy felt.'
FACE = 'Same character design as the reference. The two big eyes are plain white paper ovals with NO pupils at all. There is NO mouth: the skin below the eyes is completely blank. Do not draw a nose.'
KEY = 'Flat, even, completely solid pure green background (#00FF00) with nothing else in the image: no shadow on the background, no floor, no furniture, no text. The whole figure is visible with a clear green margin all round. Vertical image.'
BG = 'No people or animals. No text. Warm table-lamp light, soft vignette, slight film grain, shallow depth of field, photographed like a small physical diorama. Vertical 9:16 image.'


def puppet(desc):
    return f'{STYLE}\n\nCreate one single flat paper puppet, facing the camera in a seated pose with bent legs hanging down: {desc}. {FACE}\n\n{KEY}'


ITEMS = [
    ('bg_sofa_close', REF, f'{STYLE}\n\nCreate a straight-on, close front view of the red paper sofa from the reference, completely empty, filling the entire width of the frame with both arms at the left and right edges. The top of the seat cushion is a clear horizontal line at about 62% of the image height, with the back cushions above it and the front of the sofa below it, down to the floor at about 88%. Only the top 20% shows the mustard wall and the bottom of the curtained window. {BG}'),
    ('bg_chair_close', REF, f'{STYLE}\n\nCreate a straight-on, close front view of the teal paper two-seat armchair from the reference, completely empty, filling the entire width of the frame with both arms at the left and right edges. The top of the seat cushion is a clear horizontal line at about 62% of the image height, with the back cushions above it and the front of the chair below it, down to the floor at about 88%. Only the top 20% shows the mustard wall and the base of the glowing lamp. {BG}'),
    ('bg_wide', REF, f'{STYLE}\n\nCreate the same living room as the reference but completely empty: the red paper sofa on the left, the teal paper armchair wide enough for two on the right, floor lamp between them, curtained night window, framed picture and red rug. Leave the lower middle of the frame clear. {BG}'),
    ('bg_sofa', REF, f'{STYLE}\n\nCreate a close view of the back of the same red paper sofa filling the lower two thirds, with the curtained night window behind it on the left and the mustard wall on the right, softly out of focus. {BG}'),
    ('bg_chair', REF, f'{STYLE}\n\nCreate a close view of the back of the same teal paper armchair filling the lower two thirds, with the glowing lamp behind it on the left and the framed picture on the mustard wall on the right, softly out of focus. {BG}'),
    ('table', REF, f'{STYLE}\n\nCreate only the round brown paper coffee table from the reference with its two glasses of red wine, viewed from the front. {KEY}'),
    ('dave_down', REF, puppet('the man on the left of the reference, with spiky brown hair, a teal jumper and dark brown trousers, both arms resting at his sides')),
    ('dave_up', OUT + 'dave_down.png', puppet('exactly this same man from the attached image, unchanged in every way except that his right arm is raised straight up with an open hand, ready for a high five')),
    ('karen_nocard', OUT + 'karen_card.png', puppet('exactly this same woman from the attached image, unchanged in every way except that she holds no card and her hands rest in her lap')),
    # the group reference produced several figures per image, so these use a single-figure reference
    ('karen_card', OUT + 'karen_nocard.png', puppet('exactly this same woman from the attached image, unchanged in every way except that she holds one small white paper card in front of her chest with both hands. Show only this ONE figure, large, filling the frame')),
    ('linda', OUT + 'karen_nocard.png', puppet('a different woman drawn in exactly the same size, proportions and paper style as the attached figure, with reddish-brown hair in a neat bun and a brick red dress, holding up a small paper hourglass timer in one hand. Show only this ONE figure, large, filling the frame')),
    ('tom', OUT + 'dave_down.png', puppet('a different man drawn in exactly the same size, proportions and paper style as the attached figure, with short neat brown hair, a cream collared shirt and dark brown trousers, hands on his knees. Show only this ONE figure, large, filling the frame')),
]
GENS = "[...document.querySelectorAll('main img')].filter(i=>/^(生成圖片|Generated image)/.test(i.alt||''))"
BOX = "document.querySelector('.ProseMirror[contenteditable=\"true\"], #prompt-textarea')"
SEND = "document.querySelector('button[aria-label=\"傳送\"], button[aria-label=\"Send prompt\"], [data-testid=\"send-button\"], #composer-submit-button')"


def guard():
    r = subprocess.run(['python3', GUARD, '--check'], capture_output=True, text=True)
    if r.returncode != 0 or not json.loads(r.stdout).get('allowed'):
        sys.exit('browser guard refused: ' + r.stdout[:300])


def attach(path):
    b64 = base64.b64encode(open(path, 'rb').read()).decode()
    return js("""(()=>{const inp=[...document.querySelectorAll('input[type=file]')].find(i=>/image/.test(i.accept||''))||document.querySelector('input[type=file]');if(!inp)return 'no input';
      const bin=atob('%s');const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
      const dt=new DataTransfer();dt.items.add(new File([u],'reference.png',{type:'image/png'}));inp.files=dt.files;inp.dispatchEvent(new Event('change',{bubbles:true}));return 'ok'})()""" % b64)


def make(url, name, ref, prompt):
    guard()
    call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat Assets'})
    for _ in range(30):
        if js('!!' + BOX):
            break
        time.sleep(2)
    time.sleep(3)
    if js("/登入|Log in|額度|limit|unusual|驗證/i.test((document.querySelector('[role=\"dialog\"]')||{}).innerText||'')"):
        sys.exit('login, limit or verification prompt')
    print(name, 'attach', attach(ref), flush=True)
    time.sleep(8)
    # the composer keeps earlier unsent text as a draft, so replace everything in it rather than appending
    typed = js("(()=>{const e=%s;e.focus();document.execCommand('selectAll');document.execCommand('insertText',false,%s);return e.innerText.length})()" % (BOX, json.dumps(prompt)))
    print(name, 'typed', typed, 'of', len(prompt), flush=True)
    if abs(int(typed or 0) - len(prompt)) > 40:
        sys.exit(f'{name}: composer text does not match the prompt')
    for _ in range(40):
        time.sleep(1.5)
        if js("(()=>{const b=%s;if(b&&!b.disabled){b.click();return true}return false})()" % SEND):
            break
    else:
        sys.exit(f'{name}: could not send')
    start = time.time()
    while time.time() - start < 420:
        time.sleep(8)
        guard()
        if int(js(GENS + '.length') or 0) > 0 and not js("!!document.querySelector('[data-testid=\"stop-button\"]')"):
            data = js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
            open(OUT + name + '.png', 'wb').write(base64.b64decode(data.split(',', 1)[1]))
            print(name, 'saved', os.path.getsize(OUT + name + '.png'), round(time.time() - start), 's', flush=True)
            return
    print(name, 'page', str(js("(document.querySelector('main').innerText||'').slice(-300)")), flush=True)
    sys.exit(f'{name}: no image within 420 seconds')


def main():
    os.makedirs(OUT, exist_ok=True)
    url = re.findall(r'https://chatgpt\.com/g/[\w./-]+', open(MEMORY, encoding='utf-8').read())[0]
    for name, ref, prompt in ITEMS:
        if os.path.exists(OUT + name + '.png'):
            print(name, 'already done', flush=True)
            continue
        make(url, name, ref, prompt)


if __name__ == '__main__':
    try:
        main()
    finally:
        for t in (call('list_tabs', {}).get('data') or {}).get('tabs', []):
            call('close_tab', {'tabId': t['tabId']})
        print('tabs left', call('list_tabs', {}).get('data'), flush=True)

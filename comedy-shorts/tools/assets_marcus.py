#!/usr/bin/env python3
"""New Marcus with empty hands (no selfie stick, phone or any prop): marcus.png and marcus_jump.png.

ONE new chat inside the ChatGPT project 'Wait What', Extra High mode (checked before every send, never Pro).
Outputs the same green-key RGB format as assets_ep03/marcus*.png, which render.py keys itself.
Does not overwrite the old assets_ep03 files. Stops on any login, limit or verification prompt.
"""
import base64, json, os, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.u.SESSION = 'waitwhat-marcus'
OUT = a.HERE + 'assets_leads/'
OLD = a.HERE + 'assets_ep03/'
PROJECT = 'https://chatgpt.com/g/g-p-6aec8d01cc44819187bccb1828549b23/project'

SAME = ('Use the attached image as the exact reference for the character and the paper craft: the same original hand-cut paper man, '
        'the same face, the same warm dark brown paper skin, the same two big plain white paper oval eyes with NO pupils, NO mouth and no nose, '
        'the same short black curly hair, the same cream headband, the same red and yellow sports jersey, the same brown shorts with yellow stripes, '
        'cream socks and cream sneakers, the same fine paper fibres and scissor edges. He is an original fictional character, not any real person or existing cartoon.')
HANDS = ('HIS HANDS ARE COMPLETELY EMPTY. There is no selfie stick, no phone, no microphone and no object of any kind anywhere in the image. '
         'Both arms are complete, each ending in a full paper hand with five clear fingers.')
KEY = ('Flat, even, completely solid pure green background (#00FF00) with nothing else in the image: no shadow on the background, no floor, no text. '
       'The whole figure is visible with a clear green margin all round. Vertical 2:3 image, the same canvas size as the reference.')

ITEMS = [
    ('marcus', OLD + 'marcus.png',
     f'{SAME}\n\nRedraw exactly this same man in exactly the same standing pose, at exactly the same size and in exactly the same position in the frame, '
     f'with the same bent knees and the feet in exactly the same places. Only ONE thing changes: the raised right arm. Instead of holding a phone on a stick, '
     f'that arm is thrown up and out with a clenched fist punched high in the air, full of loud explosive energy. The left arm keeps its flexed fist. {HANDS}\n\n{KEY}'),
    ('marcus_jump', OLD + 'marcus_jump.png',
     f'Now, in this same conversation, make the second pose. {SAME}\n\nUse this new attached image as the pose and layout reference: the same man leaping in mid-air with both legs kicked out wide and both arms flung wide, '
     f'at exactly the same size and in exactly the same position in the frame, the feet in the same places. Keep the new empty-handed version of him from your last image: '
     f'the right arm that held the phone on a stick now ends in an open, empty, spread-fingered hand, just like his left hand. {HANDS}\n\n{KEY}'),
]
GENS = a.GENS


def guard():
    a.guard()


def mode_ok():
    # read only the mode chip (not the prompt): the zh UI shows the effort as 極高 (= Extra High)
    txt = a.js("(()=>{const f=document.querySelector('form');return [...f.querySelectorAll('button,[role=button]')].map(b=>(b.getAttribute('aria-label')||'')+' '+(b.innerText||'')).join(' | ')})()") or ''
    print('mode chip:', txt.replace('\n', ' ')[:160], flush=True)
    return ('極高' in txt or 'Extra High' in txt) and not any(k in txt for k in ('Pro', '專業'))


def send(prompt, attach):
    guard()
    print('attach', a.attach(attach), flush=True)
    time.sleep(8)
    typed = a.js("(()=>{const e=%s;e.focus();document.execCommand('selectAll');document.execCommand('insertText',false,%s);return e.innerText.length})()" % (a.BOX, json.dumps(prompt)))
    print('typed', typed, 'of', len(prompt), flush=True)
    if abs(int(typed or 0) - len(prompt)) > 40:
        sys.exit('composer text does not match the prompt')
    if not mode_ok():
        sys.exit('mode is not Extra High: refusing to send')
    for _ in range(40):
        time.sleep(1.5)
        if a.js("(()=>{const b=%s;if(b&&!b.disabled){b.click();return true}return false})()" % a.SEND):
            return
    sys.exit('could not send')


def main():
    os.makedirs(OUT, exist_ok=True)
    guard()
    a.call('navigate', {'url': PROJECT, 'newTab': False, 'group_title': 'WaitWhat Marcus'})
    for _ in range(30):
        if a.js('!!' + a.BOX):
            break
        time.sleep(2)
    time.sleep(3)
    if a.js("/登入|Log in|額度|limit|unusual|驗證/i.test((document.querySelector('[role=\"dialog\"]')||{}).innerText||'')"):
        sys.exit('login, limit or verification prompt')
    for name, ref, prompt in ITEMS:
        if os.path.exists(OUT + name + '.png'):
            print(name, 'already done', flush=True)
            continue
        n0 = int(a.js(GENS + '.length') or 0)
        send(prompt, ref)
        start = time.time()
        while time.time() - start < 600:
            time.sleep(8)
            guard()
            if int(a.js(GENS + '.length') or 0) > n0 and not a.js("!!document.querySelector('[data-testid=\"stop-button\"]')"):
                data = a.js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
                open(OUT + name + '.png', 'wb').write(base64.b64decode(data.split(',', 1)[1]))
                print(name, 'saved', os.path.getsize(OUT + name + '.png'), round(time.time() - start), 's', flush=True)
                break
        else:
            print('page', str(a.js("(document.querySelector('main').innerText||'').slice(-300)")), flush=True)
            sys.exit(f'{name}: no image within 600 seconds')
        time.sleep(4)
    print('chat url', a.js('location.href'), flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

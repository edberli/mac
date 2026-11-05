#!/usr/bin/env python3
"""Generate the channel's icon, logo, banner and end card in ONE ChatGPT conversation. Skips nothing silently; stops on any prompt."""
import base64, json, os, re, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

OUT = a.HERE + 'brand/'
REF = a.HERE + 'cast_test/trio_a.png'
BASE = 'Same paper craft, same three characters as the attached image, warm lamp light, visible fibres, soft shadows between paper layers. The energetic man never holds a phone or selfie stick in any of these images: his hands are empty. Spelling must be exactly as written. No other text, no logos of other brands.'
ITEMS = [
    ('icon', f'{BASE}\n\nCreate a square YouTube channel icon: only the head of the chubby man from the attached image, very large, centred, filling most of the frame, with a shocked face: huge white eyes, tiny black pupils, one eyebrow flying up, a small round mouth. Plain mustard paper background. It must read clearly at very small size. No text at all.'),
    ('logo', f'{BASE}\n\nNow create the channel logo, in the same conversation and the same style: big chunky cut-paper letters spelling exactly WAIT WHAT? on one line, each letter slightly wonky and a different size, cream and mustard with a thin dark brown edge, a bit of tape on two letters. Plain solid pure green background (#00FF00), no shadows on the background. Wide landscape image, no characters.'),
    ('banner', f'{BASE}\n\nNow create a YouTube channel banner, in the same style, very wide landscape: a warm paper living room with a red sofa stretching across the frame. All three characters stand in the exact centre of the image, close together: the chubby man smirking with arms crossed, the energetic man mid-jump with empty hands, the tall tired man looking sideways at them. To their right, but still within the central third of the image, the words WAIT WHAT? in the same cut-paper letters. Keep all characters and letters inside the central 60% of the width and the central 30% of the height; the far left and right are just room, curtains and paper balloons.'),
    ('end_card', f'{BASE}\n\nNow create a vertical 9:16 channel end card, in the same style: big wonky cut-paper letters spelling exactly WAIT WHAT? stacked on two lines on dark brown paper, with visible tape. The chubby man peeks over the top of the letter W with a shocked face, and the energetic man jumps beside the question mark.'),
]
GENS = a.GENS


def send(prompt, attach=None):
    if attach:
        print('attach', a.attach(attach), flush=True)
        time.sleep(8)
    typed = a.js("(()=>{const e=%s;e.focus();document.execCommand('selectAll');document.execCommand('insertText',false,%s);return e.innerText.length})()" % (a.BOX, json.dumps(prompt)))
    print('typed', typed, 'of', len(prompt), flush=True)
    if abs(int(typed or 0) - len(prompt)) > 40:
        sys.exit('composer text does not match the prompt')
    for _ in range(40):
        time.sleep(1.5)
        if a.js("(()=>{const b=%s;if(b&&!b.disabled){b.click();return true}return false})()" % a.SEND):
            return
    sys.exit('could not send')


def main():
    os.makedirs(OUT, exist_ok=True)
    url = re.findall(r'https://chatgpt\.com/g/[\w./-]+', open(a.MEMORY, encoding='utf-8').read())[0]
    a.guard()
    a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat Brand'})
    for _ in range(30):
        if a.js('!!' + a.BOX):
            break
        time.sleep(2)
    time.sleep(3)
    for i, (name, prompt) in enumerate(ITEMS):
        n0 = int(a.js(GENS + '.length') or 0)
        send(prompt, REF if i == 0 else None)
        start = time.time()
        while time.time() - start < 420:
            time.sleep(8)
            a.guard()
            if int(a.js(GENS + '.length') or 0) > n0 and not a.js("!!document.querySelector('[data-testid=\"stop-button\"]')"):
                data = a.js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
                open(OUT + name + '.png', 'wb').write(base64.b64decode(data.split(',', 1)[1]))
                print(name, 'saved', os.path.getsize(OUT + name + '.png'), round(time.time() - start), 's', flush=True)
                break
        else:
            print('page', str(a.js("(document.querySelector('main').innerText||'').slice(-300)")), flush=True)
            sys.exit(f'{name}: no image within 420 seconds')
        time.sleep(4)
    print('chat url', a.js('location.href'), flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

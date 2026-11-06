#!/usr/bin/env python3
"""EP07 'I Voted' image assets, all in ONE new chat inside the ChatGPT project 'Wait What'.

Usage: assets_ep07.py NAME [NAME ...] [--redo] [--note "extra instruction"]
Extra High mode is checked before every send (never Pro). Saved to assets_ep07/NAME.png as raw ChatGPT output.
--redo moves the existing file to assets_ep07/rejected/ first, and --note appends a correction to the prompt.
The conversation URL is kept in assets_ep07/.chat_url so every later image goes into the same chat.
Stops on any login, limit or verification prompt. Closes only the tabs this run opened, never pre-existing ones.
"""
import base64, json, os, shutil, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.u.SESSION = 'waitwhat-ep07'
H = a.HERE
OUT = H + 'assets_ep07/'
STATE = OUT + '.chat_url'
PROJECT = 'https://chatgpt.com/g/g-p-6aec8d01cc44819187bccb1828549b23/project'
LEADS = H + 'assets_leads/'
STYLE_REF = H + 'style/frame_a.png'

PAPER = ('The same real hand-cut construction paper craft as the Game Night paper puppets: fine paper fibres, slightly uneven scissor edges, '
         'muted palette of mustard, brick red, dusty teal, cream and brown, photographed like a tiny physical diorama, paper card not felt.')
NOTEXT = ('ABSOLUTELY NO text anywhere: no letters, no numbers, no words, no signs with writing, no logos, no brand names. '
          'Any sign, label, cup, bag or sticker is left blank.')
ORIG = 'Everything is an original fictional design: no real person, no existing cartoon, no video game logo, font or character. No racial stereotypes.'
NOSELF = 'NO selfie stick, NO phone, NO microphone, NO camera anywhere in the picture.'
KEY_GREEN = ('Flat, even, completely solid pure green background (#00FF00) with nothing else in the background: no shadow on the background, '
             'no floor, no props on the background, no text. The whole figure is visible with a clear green margin all round, nothing cropped. '
             'Vertical 2:3 image, 1024x1536.')
MARCUS = ('Image 1 is the exact character reference: the same original hand-cut paper boy Marcus with the same warm dark brown paper skin, '
          'the same short black curly hair, the same cream headband, the same red and yellow sports tank top with yellow trim, '
          'the same brown shorts with yellow stripes, and the same cream socks and sneakers. '
          'His two big eyes are plain white paper ovals with NO pupils. ' + ORIG)
PROPS = ('The paper bag is a crumpled brown paper takeaway bag with several round oily grease stains on it, held by its folded top. '
         'The drink is a giant paper soft-drink cup, tall and very large, cream coloured with a red band, a black plastic dome lid and a bendy straw sticking out of the lid. '
         'Both are plain, with NO logo and NO writing on them. ')
HANDS = 'Both arms are complete and both hands are full paper hands with five clearly separate fingers, nothing hidden and nothing cut off.'

ITEMS = {
    'marcus_door': ([LEADS + 'marcus.png'],
                    f'{PAPER}\n\n{MARCUS}\n\n'
                    f'Draw him leaping in mid-air through a doorway, bursting in with both feet kicked out in front and his whole body in a wild jump, bursting with excitement. '
                    f'In his LEFT hand he holds the greasy paper bag up high, and in his RIGHT hand he holds the giant drink cup up high. {PROPS}'
                    f'His mouth is wide open in a huge shout, drawn as one big dark red paper shape, eyes wide. {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY_GREEN}'),
    'marcus_bag': ([LEADS + 'marcus.png', OUT + 'marcus_door.png'],
                   f'{PAPER}\n\n{MARCUS}\n\n'
                   f'Image 2 shows the exact bag and the exact drink cup: use it only for those two props. '
                   f'Redraw Marcus standing on both feet in the same footing as image 1 (legs apart, sneakers turned out, same size and same place in the frame). '
                   f'He holds the greasy paper bag in his left hand and the giant drink cup in his right hand, both lifted in front of his chest so that both are fully visible. '
                   f'He is proud and smug: chest out, chin up, a small confident closed smile drawn as one simple dark paper curve, eyes still plain white ovals with no pupils. '
                   f'{PROPS}{HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY_GREEN}'),
    'marcus_sticker': ([LEADS + 'marcus.png', OUT + 'marcus_bag.png'],
                       f'{PAPER}\n\n{MARCUS}\n\n'
                       f'Image 2 shows the exact greasy paper bag: use it only for that prop. '
                       f'Redraw Marcus standing on both feet in the same footing as image 1. The greasy paper bag is clamped tightly under his LEFT arm, pinned against his side. '
                       f'His RIGHT hand points one finger proudly at a round sticker stuck on the middle of his red tank top, over his chest. '
                       f'The sticker is a plain round white paper sticker with a thin cream border and NOTHING drawn or written on it: a completely blank white circle. '
                       f'He looks very pleased with himself, chin up, a small smug smile drawn as one simple dark paper curve, eyes still plain white ovals with no pupils. '
                       f'No drink cup in this picture. {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY_GREEN}'),
    'sticker_close': ([STYLE_REF],
                      f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\n'
                      f'Create a full-screen close-up photo of a flat paper table surface: the whole frame is cream and brown paper card with faint paper fibres and soft warm lighting. '
                      f'There is NO green anywhere in the picture. In the centre sits one round paper sticker, about 60% of the frame width, with a thick white die-cut border, '
                      f'showing a cheerful cartoon chicken with a big round body and a small comb, raising one wing high up in a happy cheer, in mustard, brick red and cream paper. '
                      f'The sticker lies on the paper table with a soft shadow. The lower quarter of the frame is a plain, empty, flat area of cream paper, completely blank, left for text to be added later. '
                      f'{NOTEXT} No letters, no numbers, no words and no logos anywhere on the sticker or the table. Vertical 2:3 image, 1024x1536.'),
}
GENS = a.GENS


def mode_ok():
    txt = a.js("(()=>{const f=document.querySelector('form');return [...f.querySelectorAll('button,[role=button]')].map(b=>(b.getAttribute('aria-label')||'')+' '+(b.innerText||'')).join(' | ')})()") or ''
    print('mode chip:', txt.replace('\n', ' ')[:200], flush=True)
    return ('極高' in txt or 'Extra High' in txt) and not any(k in txt for k in ('Pro', '專業')), txt


def attach_many(paths):
    parts = []
    for i, p in enumerate(paths):
        parts.append("{n:'ref%d.png',b:'%s'}" % (i + 1, base64.b64encode(open(p, 'rb').read()).decode()))
    code = """(()=>{const inp=[...document.querySelectorAll('input[type=file]')].find(i=>/image/.test(i.accept||''))||document.querySelector('input[type=file]');if(!inp)return 'no input';
      const dt=new DataTransfer();for(const o of [%s]){const bin=atob(o.b);const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);dt.items.add(new File([u],o.n,{type:'image/png'}))}
      inp.files=dt.files;inp.dispatchEvent(new Event('change',{bubbles:true}));return 'ok '+dt.files.length})()""" % ','.join(parts)
    return a.js(code)


def clear_attachments():
    # the composer can keep attachments from an earlier send, so remove every chip before attaching this run's references
    for _ in range(6):
        n = a.js("(()=>{const bs=[...document.querySelectorAll('button')].filter(b=>/^(移除|Remove)\\s/.test(b.getAttribute('aria-label')||''));bs.forEach(b=>b.click());return bs.length})()") or 0
        if not n:
            return
        time.sleep(1)


def send(prompt, refs):
    a.guard()
    clear_attachments()
    print('attach', attach_many(refs), flush=True)
    time.sleep(9)
    typed = a.js("(()=>{const e=%s;e.focus();document.execCommand('selectAll');document.execCommand('insertText',false,%s);return e.innerText.length})()" % (a.BOX, json.dumps(prompt)))
    print('typed', typed, 'of', len(prompt), flush=True)
    if abs(int(typed or 0) - len(prompt)) > 60:
        sys.exit('composer text does not match the prompt')
    ok, txt = mode_ok()
    if not ok:
        sys.exit('mode is not Extra High: refusing to send')
    for _ in range(40):
        time.sleep(1.5)
        if a.js("(()=>{const b=%s;if(b&&!b.disabled){b.click();return true}return false})()" % a.SEND):
            return
    sys.exit('could not send')


def one(name, note, redo):
    refs, prompt = ITEMS[name]
    if note:
        prompt += '\n\nCORRECTION for this attempt (most important): ' + note
    dest = OUT + name + '.png'
    if os.path.exists(dest):
        if not redo:
            print(name, 'already done', flush=True)
            return
        os.makedirs(OUT + 'rejected', exist_ok=True)
        k = 1
        while os.path.exists(OUT + f'rejected/{name}_v{k}.png'):
            k += 1
        shutil.move(dest, OUT + f'rejected/{name}_v{k}.png')
    for r in refs:
        if not os.path.exists(r):
            sys.exit('missing reference ' + r)
    a.guard()
    url = open(STATE).read().strip() if os.path.exists(STATE) else PROJECT
    if not tab_ids():
        # the daemon has no tab for this session yet, so open the target page first
        a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat EP07'})
    cur = a.js('location.href') or ''
    if not (url != PROJECT and url.split('/c/')[-1] in cur and a.js('!!' + a.BOX)):
        a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat EP07'})
    for _ in range(30):
        if a.js('!!' + a.BOX):
            break
        time.sleep(2)
    time.sleep(5)
    if a.js("/登入|Log in|額度|limit|unusual|驗證/i.test((document.querySelector('[role=\"dialog\"]')||{}).innerText||'')"):
        sys.exit('login, limit or verification prompt')
    time.sleep(4)
    # count-based detection: image src URLs can change on re-render, so comparing URLs wrongly treats old images as new
    before_n = int(a.js(GENS + '.length') or 0)
    send(prompt, refs)
    start = time.time()
    idle = 0
    while time.time() - start < 600:
        time.sleep(8)
        a.guard()
        n = int(a.js(GENS + '.length') or 0)
        new = n > before_n
        busy = a.js("!!document.querySelector('[data-testid=\"stop-button\"]')")
        if new and not busy:
            data = a.js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
            raw = base64.b64decode(data.split(',', 1)[1])
            import hashlib
            digest = hashlib.sha256(raw).hexdigest()
            for f in os.listdir(OUT):
                if f.endswith('.png') and hashlib.sha256(open(OUT + f, 'rb').read()).hexdigest() == digest:
                    sys.exit(f'{name}: fetched image duplicates {f}, not saving')
            open(dest, 'wb').write(raw)
            print(name, 'saved', os.path.getsize(dest), round(time.time() - start), 's', flush=True)
            href = a.js('location.href')
            if '/c/' in (href or ''):
                open(STATE, 'w').write(href)
            print('chat url', href, flush=True)
            return
        idle = 0 if busy else idle + 1
        if idle >= 12 and not new:
            break
    print('page', str(a.js("(document.querySelector('main').innerText||'').slice(-400)")), flush=True)
    sys.exit(f'{name}: no image')


def tab_ids():
    return {t['tabId'] for t in ((a.call('list_tabs', {}).get('data') or {}).get('tabs', []))}


def main():
    args = sys.argv[1:]
    redo = '--redo' in args
    note = ''
    if '--note' in args:
        i = args.index('--note')
        note = args[i + 1]
        args = args[:i] + args[i + 2:]
    names = [x for x in args if not x.startswith('--')]
    os.makedirs(OUT, exist_ok=True)
    for nm in names:
        one(nm, note, redo)
        time.sleep(3)


if __name__ == '__main__':
    PRE = tab_ids()
    print('tabs before run', sorted(PRE), flush=True)
    try:
        main()
    finally:
        # close only tabs this run opened; tabs that existed before the run are never touched
        for tid in tab_ids() - PRE:
            a.call('close_tab', {'tabId': tid})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

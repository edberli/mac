#!/usr/bin/env python3
"""EP09 'It Says Pull' image assets, all in ONE new chat inside the ChatGPT project 'Wait What'.

Usage: assets_ep09.py NAME [NAME ...] [--redo] [--note "extra instruction"] [--keep]
Extra High mode ("推理強度 極高") is checked before every send (never Pro). Saved to assets_ep09/NAME.png as raw ChatGPT output.
--redo moves the existing file to assets_ep09/rejected/ first, and --note appends a correction to the prompt.
The conversation URL is kept in assets_ep09/.chat_url so every later image goes into the same chat.
Sends are at least 60 seconds apart (also across runs, via assets_ep09/.last_send).
Stops on any login, limit or verification prompt. Closes only the tabs this run opened, never pre-existing ones.

Page changes handled (2026-11-06): the composer is a role=textbox / ProseMirror with aria-label 「問 ChatGPT」 (no #prompt-textarea),
no data-message-author-role. Images are detected by COUNT of large non-attachment images in <main> (never by URL), and the wait
is long (up to 20 minutes), because images sometimes arrive minutes late.
"""
import base64, hashlib, json, os, re, shutil, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.u.SESSION = 'waitwhat-ep09'
H = a.HERE
OUT = H + 'assets_ep09/'
STATE = OUT + '.chat_url'
LAST = OUT + '.last_send'
PROJECT = 'https://chatgpt.com/g/g-p-6aec8d01cc44819187bccb1828549b23/project'
LEADS, EP03, EP06 = H + 'assets_leads/', H + 'assets_ep03/', H + 'assets_ep06/'
STYLE_REF = H + 'style/frame_a.png'
GAP = 60          # seconds between two sends
MAX_WAIT = 2700   # seconds to wait for one image before reporting no image

PAPER = ('The same real hand-cut construction paper craft as the Game Night paper puppets: fine paper fibres, slightly uneven scissor edges, '
         'muted palette of mustard, brick red, dusty teal, cream and brown, photographed like a tiny physical diorama, paper card not felt.')
NOTEXT = ('ABSOLUTELY NO text anywhere: no letters, no numbers, no words, no signs with writing, no logos, no brand names, no symbols that look like letters. '
          'Any sign or label is left completely blank.')
ORIG = 'Everything is an original fictional design: no real person, no existing cartoon, no logo, font or character. No racial stereotypes.'
NOGORE = 'Family-friendly: no blood, no wounds, no birth scene, nothing graphic.'
NOSELF = 'NO selfie stick, NO phone, NO microphone, NO camera anywhere in the picture.'
DIRECT = 'Generate the image right now, directly. Do not ask questions, do not reply with a plan or a description, just produce the picture.'
KEY = ('Flat, even, completely solid pure green background (#00FF00) with nothing else in the background: no shadow on the background, no floor, '
       'no wall, no door, no props, no text. The whole figure is visible from the top of the head to the soles of the shoes, with a clear green margin all round, nothing cropped. '
       'Vertical 2:3 image, 1024x1536.')
FACE = ('The two big eyes are plain white paper ovals with NO pupils. There is NO mouth, not even a closed one: the skin below the eyes is completely blank. Do not draw a nose.')
HANDS = 'Both arms are complete and both hands are full paper hands with five clearly separate fingers, nothing hidden and nothing cut off.'
BGFMT = 'Vertical 2:3 image, 1024x1536. Warm soft light, slight paper grain. No people, no animals, no text.'

RUSSELL = ('Image 1 is the exact character reference: the same original hand-cut paper man named Russell, with the same spiky brown paper hair, the same warm peach paper skin, '
           'the same round head, round belly and body proportions, the same teal short-sleeved t-shirt, the same dark brown trousers and dark brown shoes, the same paper style. ' + ORIG)
MARCUS = ('Image 1 is the exact character reference: the same original hand-cut paper boy Marcus with the same warm dark brown paper skin, '
          'the same short black curly hair, the same cream headband, the same red and yellow sports tank top with yellow trim, '
          'the same brown shorts with yellow stripes, and the same cream socks and sneakers. His two big eyes are plain white paper ovals with NO pupils. ' + ORIG)
NEIL = ('Image 1 is the exact character reference: the same original hand-cut paper man Neil with the same neat dark hair, round dark-rimmed glasses over his white oval eyes, '
        'cream shirt with brown tie and brown trousers, brown shoes, same long thin figure, same paper style. ' + ORIG)

PUSH = ('Three-quarter side view, his body facing the RIGHT of the frame, leaning forward from the hips at about 25 degrees, both arms stretched straight forward to the right at chest height '
        'with both palms pressed flat on an INVISIBLE vertical surface, each hand a full paper hand with five fingers spread flat. '
        'His head is turned toward the camera so the face looks out at the viewer. The back leg is straight and braced, the front leg bent, both shoes flat on the ground. '
        'There is NO door, NO wall and NO object anywhere: only the green background and the figure. ')
SAME = ('Image 1 is the exact reference. Redraw exactly the same pose, at exactly the same size and in exactly the same position in the frame: '
        'the same head position and angle, the same eye position, the same arms and the same hands in the same places, the same legs and feet. Nothing moves by even a few pixels. ')

DOOR = ('The door is one big closed hospital door in warm brown paper with a cream paper frame and a plain round paper handle, turned slightly so its plane angles toward the camera. '
        'Across the middle of the door sits one very large, flat, completely blank cream rectangular sign plate, about two thirds of the door width and one fifth of the door height, '
        'clean and easy to see even on a phone screen. ')

ITEMS = {
    'bg_hall': ([STYLE_REF],
                f'{DIRECT}\n\nUse the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\n'
                f'Create a hospital corridor in warm paper: cream paper walls with a dusty teal stripe, mustard paper floor tiles, plain round paper ceiling lights, a few plain doors far down the corridor, all warm and friendly. '
                f'On the RIGHT side of the frame stands one big door, filling about half the frame height and a third of the width. {DOOR}'
                f'In front of the door the floor is a clear, empty, open area wide enough for a person to stand there, with nothing on it. The left part of the frame shows the corridor receding. '
                f'No beds, no equipment, no cross symbols. {NOTEXT} {ORIG} {NOGORE}\n\n{BGFMT}'),
    'bg_hall_open': ([OUT + 'bg_hall.png'],
                     f'{DIRECT}\n\n{PAPER}\n\nThe attached image is the exact scene. Draw the very same corridor with the SAME camera, the same composition, the same walls, floor, lights, door frame and door position, with ONE change: '
                     f'the door has just been opened from the inside and is now wide open, its leaf swung back toward the right edge of the frame, so the doorway is clear. The large blank cream sign plate is still visible on the open door leaf. '
                     f'Through the open doorway we see a bright, warm, glowing empty room, soft golden light spilling out onto the corridor floor. There is NOBODY in the room and nobody in the doorway, and no furniture or beds visible. '
                     f'The floor in front of the doorway stays clear. {NOTEXT} {ORIG} {NOGORE}\n\n{BGFMT}'),
    'bg_hall_old': ([OUT + 'bg_hall.png'],
                    f'{DIRECT}\n\n{PAPER}\n\nThe attached image is the exact scene. Draw the very same corridor with the SAME camera, composition and door position, aged by eighteen years: '
                    f'the walls are faded, pale and bleached, the teal stripe washed out, the floor dull and scuffed, the light a little dimmer and yellower. The door is worn and tired, its brown paint faded, scratched and chipped at the edges. '
                    f'Exactly TWO worn, rubbed-pale hand marks, side by side at chest height on the lower-middle of the door below the sign, each the shape of a flat open palm with five fingers, as if two hands pushed there for years. '
                    f'The large blank cream sign plate is still there, as big and blank as before. The floor in front of the door stays clear and empty. {NOTEXT} {ORIG} {NOGORE}\n\n{BGFMT}'),
    'bg_lot': ([OUT + 'bg_hall.png', STYLE_REF],
               f'{DIRECT}\n\nImage 1 shows only the exact door to reuse (ignore the corridor around it); image 2 is only the style reference for the hand-cut paper craft. {PAPER}\n\n'
               f'Create a vast empty piece of wasteland: flat bare ground of dusty beige and grey paper, a huge pale cloudy paper sky taking up more than half the frame, a distant low horizon. '
               f'There is NO building anywhere, no wall, no ceiling, no floor tiles. Far away on the horizon only a lone construction crane and a few low heaps of rubble, tiny and grey, so the place feels abandoned and desolate. '
               f'In the exact middle of the frame, the SAME door as in image 1 stands completely alone, held in its cream door frame, free-standing with NOTHING on either side of it, no walls and no building behind it, turned slightly so it angles toward the camera. '
               f'The same very large, flat, completely blank cream sign plate is on the door, clean and easy to see on a phone. The ground in front of the door is clear and empty. {NOTEXT} {ORIG}\n\n{BGFMT}'),
    'russell_push': ([EP06 + 'russell_s1.png'],
                     f'{DIRECT}\n\n{PAPER}\n\n{RUSSELL}\n\nDraw him standing and pushing hard. {PUSH}'
                     f'Face: wide open determined white oval eyes with flat level brows, a stubborn, proud, unmovable stare. {FACE} {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY}'),
    'russell_push_old': ([OUT + 'russell_push.png'],
                         f'{DIRECT}\n\n{PAPER}\n\n{SAME}ONLY these things change, because eighteen years have passed: his hair is now white and thin, he has a very long white paper beard hanging down over his chin and chest, '
                         f'and his teal t-shirt and brown trousers are old, faded and worn with a few small patches. His skin is slightly more weathered. Same body, same belly, same shoes. {FACE.replace("There is NO mouth, not even a closed one: the skin below the eyes is completely blank.", "There is NO mouth drawn; the white beard simply covers the lower face.")} {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY}'),
    'marcus_push': ([LEADS + 'marcus.png'],
                    f'{DIRECT}\n\n{PAPER}\n\n{MARCUS}\n\nDraw him standing and pushing with all his might, with the same energy and enthusiasm. {PUSH}'
                    f'Face: wide white oval eyes with raised excited brows. He is giving it everything. NO props at all. {FACE} {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY}'),
    'marcus_push_old': ([OUT + 'marcus_push.png'],
                        f'{DIRECT}\n\n{PAPER}\n\n{SAME}ONLY these things change, because he is now extremely old: his curly hair is now white, the headband is now plain white, he is much thinner with narrow shoulders and thin arms and legs, '
                        f'his tank top and shorts hang loose, faded and baggy, and his skin looks weathered. Still the exact same pose and pushing hands. His eyes are tired white ovals with no pupils. {FACE} {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY}'),
    'neil_old': ([EP03 + 'neil.png'],
                 f'{DIRECT}\n\n{PAPER}\n\n{NEIL}\n\nDraw him much older: white hair, a slightly hunched back, standing in place, leaning on a plain wooden walking cane held in one hand, the other hand hanging at his side. '
                 f'He looks tired and worn out: heavy drooping eyelids on his white oval eyes behind the glasses, lowered brows, sagging shoulders. A few faint thin wrinkle lines. The shirt and tie are a little rumpled and faded. '
                 f'Both hands are complete paper hands with clear fingers. {FACE} Same figure proportions as in image 1, whole figure visible. {NOTEXT}\n\n{KEY}'),
    'neil_point': ([EP03 + 'neil.png'],
                   f'{DIRECT}\n\n{PAPER}\n\n{NEIL}\n\nDraw him young as in image 1 (same dark hair, no white hair), standing leaning forward, out of breath after running. '
                   f'His arm on the RIGHT side of the frame is stretched out straight toward the right edge of the frame with the hand making a clear pointing gesture: a full paper hand with the index finger extended straight and the other four fingers curled. '
                   f'His other hand is pressed flat on his own knee as he bends over, panting, back bent, knees slightly bent. His head is raised and turned toward the right, eyes wide open behind the glasses. '
                   f'{FACE} {HANDS} {NOTEXT}\n\n{KEY}'),
    'nurse': ([EP03 + 'neil.png'],
              f'{DIRECT}\n\n{PAPER}\n\nImage 1 shows only the paper style, the figure proportions and the blank-faced eyes (ignore the man). {ORIG}\n\n'
              f'Draw a NEW, original, friendly hospital nurse, a woman with warm tan paper skin and dark brown hair in a neat bun, wearing pale mint scrubs, a small plain blank white nurse cap and white shoes. Kind, welcoming face: raised friendly brows over her white oval eyes. '
              f'Standing, her body in three-quarter view toward the right. In one arm she cradles against her chest a soft folded PINK towel bundle, completely wrapped so that NO baby face and NO baby features are visible, it just looks like a pink bundle. '
              f'Her other arm is raised toward the UPPER RIGHT of the frame with the hand flat as if holding open a door at head height (no door drawn). {FACE} {HANDS} {NOSELF} {NOGORE}\n\n{NOTEXT}\n\n{KEY}'),
    'daughter': ([EP06 + 'russell_s1.png'],
                 f'{DIRECT}\n\n{PAPER}\n\nImage 1 is only a family-likeness reference (ignore the pose and clothes). {ORIG}\n\n'
                 f'Draw a NEW original eighteen-year-old girl, the daughter of the man in image 1, with a slight family resemblance: short spiky, pointed brown paper hair, a round peach paper face. '
                 f'She wears a brick red hoodie, dusty blue jeans, cream sneakers and a teal backpack on her shoulders. She is walking in side view, body in profile facing the LEFT of the frame, mid-stride, one foot forward, one hand holding the backpack strap and the other arm swinging naturally. '
                 f'Her head is turned slightly toward the camera with a flat, bored, expressionless look: half-lowered eyelids over her white oval eyes, level brows. {FACE} {HANDS} {NOSELF}\n\n{NOTEXT}\n\n{KEY}'),
}
GENS = ("[...document.querySelectorAll('main img')].filter(i=>i.naturalWidth>=600&&!i.closest('form')&&!/附件|上傳|Uploaded|upload|attachment/i.test(i.alt||'')&&!/^chrome-extension/.test(i.src))")
BOX = ("(document.querySelector('form .ProseMirror[contenteditable=\"true\"]')||document.querySelector('form [role=\"textbox\"]')||"
       "document.querySelector('.ProseMirror[contenteditable=\"true\"]')||document.querySelector('[role=\"textbox\"][contenteditable=\"true\"]')||document.querySelector('#prompt-textarea'))")
SEND = ("(document.querySelector('form button[aria-label=\"傳送\"], form button[aria-label=\"傳送提示\"], form button[aria-label=\"Send prompt\"], "
        "[data-testid=\"send-button\"], #composer-submit-button'))")
NEWIMG = ("(()=>{const im=[...document.querySelectorAll('main img')];const att=im.filter(i=>/附件|attachment/i.test(i.alt||''));"
          "const gen=im.filter(i=>i.naturalWidth>=600&&!i.closest('form')&&!/附件|上傳|Uploaded|upload|attachment/i.test(i.alt||'')&&!/^chrome-extension/.test(i.src));"
          "if(!gen.length)return false;if(!att.length)return true;"
          "return !!(att.at(-1).compareDocumentPosition(gen.at(-1))&Node.DOCUMENT_POSITION_FOLLOWING)})()")
BUSY = ("!!(document.querySelector('[data-testid=\"stop-button\"], button[aria-label*=\"停止\"], button[aria-label*=\"Stop\"]'))")


def mode_ok():
    txt = a.js("(()=>{const f=document.querySelector('form');return [...f.querySelectorAll('button,[role=button]')].map(b=>(b.getAttribute('aria-label')||'')+' '+(b.innerText||'')).join(' | ')})()") or ''
    print('mode chip:', txt.replace('\n', ' ')[:200], flush=True)
    ok = ('極高' in txt or 'Extra High' in txt) and not re.search(r'\bPro\b|專業', txt)
    return ok, txt


def attach_many(paths):
    parts = []
    for i, p in enumerate(paths):
        parts.append("{n:'ref%d.png',b:'%s'}" % (i + 1, base64.b64encode(open(p, 'rb').read()).decode()))
    code = """(()=>{const ins=[...document.querySelectorAll('input[type=file]')].filter(i=>/image/.test(i.accept||''));
      const inp=ins.find(i=>i.multiple)||ins[0]||document.querySelector('input[type=file]');if(!inp)return 'no input';
      const dt=new DataTransfer();for(const o of [%s]){const bin=atob(o.b);const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);dt.items.add(new File([u],o.n,{type:'image/png'}))}
      inp.files=dt.files;inp.dispatchEvent(new Event('change',{bubbles:true}));return 'ok '+dt.files.length})()""" % ','.join(parts)
    return a.js(code)


def chips():
    return int(a.js("[...document.querySelectorAll('button')].filter(b=>/^(移除|Remove)\\s/.test(b.getAttribute('aria-label')||'')).length") or 0)


def clear_attachments():
    # the composer can keep attachments from an earlier send, so remove every chip before attaching this run's references
    for _ in range(8):
        n = a.js("(()=>{const bs=[...document.querySelectorAll('button')].filter(b=>/^(移除|Remove)\\s/.test(b.getAttribute('aria-label')||''));bs.forEach(b=>b.click());return bs.length})()") or 0
        if not n:
            return
        time.sleep(1.5)


def wait_gap():
    if os.path.exists(LAST):
        try:
            last = float(open(LAST).read().strip())
        except ValueError:
            last = 0
        left = GAP + 3 - (time.time() - last)
        if left > 0:
            print('waiting', round(left), 's for the 60 s send gap', flush=True)
            time.sleep(left)


def send(prompt, refs):
    a.guard()
    clear_attachments()
    print('chips after clear', chips(), flush=True)
    print('attach', attach_many(refs), flush=True)
    for _ in range(30):
        time.sleep(1.5)
        if chips() >= len(refs):
            break
    time.sleep(3)
    nchip = chips()
    print('chips after attach', nchip, 'expected', len(refs), flush=True)
    if nchip != len(refs):
        sys.exit('attachment count mismatch: refusing to send')
    typed = a.js("(()=>{const e=%s;e.focus();document.execCommand('selectAll');document.execCommand('insertText',false,%s);return e.innerText.length})()" % (a.BOX if False else BOX, json.dumps(prompt)))
    print('typed', typed, 'of', len(prompt), flush=True)
    if abs(int(typed or 0) - len(prompt)) > 60:
        sys.exit('composer text does not match the prompt')
    ok, txt = mode_ok()
    if not ok:
        sys.exit('mode is not Extra High: refusing to send')
    wait_gap()
    a.guard()
    ok, txt = mode_ok()   # check again right before the click
    if not ok:
        sys.exit('mode is not Extra High: refusing to send')
    for _ in range(40):
        time.sleep(1.5)
        if a.js("(()=>{const b=%s;if(b&&!b.disabled){b.click();return true}return false})()" % SEND):
            open(LAST, 'w').write(str(time.time()))
            return
    sys.exit('could not send')


def tab_ids():
    return {t['tabId'] for t in ((a.call('list_tabs', {}).get('data') or {}).get('tabs', []))}


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
        a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat EP09'})
    cur = a.js('location.href') or ''
    if not (url != PROJECT and url.split('/c/')[-1] in cur and a.js('!!' + BOX)):
        a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat EP09'})
    for _ in range(30):
        if a.js('!!' + BOX):
            break
        time.sleep(2)
    time.sleep(5)
    if a.js("/登入|Log in|額度|limit|unusual|驗證/i.test((document.querySelector('[role=\"dialog\"]')||{}).innerText||'')"):
        sys.exit('login, limit or verification prompt')
    time.sleep(4)
    # count-based detection: image URLs can change on re-render, so never compare URLs
    before_n = int(a.js(GENS + '.length') or 0)
    print('large images before send:', before_n, 'newest-after-attachment:', a.js(NEWIMG), flush=True)
    send(prompt, refs)
    start = time.time()
    stable = 0
    last_log = 0
    while time.time() - start < MAX_WAIT:
        time.sleep(8)
        a.guard()
        # DOM-order detection: the newest generated image must come AFTER the newest attachment (the one just sent).
        # Counting images is unreliable because ChatGPT virtualises old turns and the count can go down.
        n = int(bool(a.js(NEWIMG)))
        busy = bool(a.js(BUSY))
        if time.time() - last_log > 60:
            last_log = time.time()
            print(f'  {round(time.time() - start)}s new_image={n} busy={busy}', flush=True)
        if n and not busy:
            stable += 1
        else:
            stable = 0
        if stable >= 2:
            data = a.js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
            raw = base64.b64decode(data.split(',', 1)[1])
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
    print('page', str(a.js("(document.querySelector('main').innerText||'').slice(-400)")), flush=True)
    print('imgs', str(a.js("JSON.stringify([...document.querySelectorAll('main img')].map(i=>[i.alt,i.naturalWidth]))"))[:600], flush=True)
    sys.exit(f'{name}: no image after {MAX_WAIT}s')


def main():
    args = sys.argv[1:]
    redo = '--redo' in args
    note = ''
    if '--note' in args:
        i = args.index('--note')
        note = args[i + 1]
        args = args[:i] + args[i + 2:]
    names = [x for x in args if not x.startswith('--')]
    for nm in names:
        if nm not in ITEMS:
            sys.exit('unknown name ' + nm)
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
        if '--keep' not in sys.argv:
            for tid in tab_ids() - PRE:
                a.call('close_tab', {'tabId': tid})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

#!/usr/bin/env python3
"""EP06 'Grand Father Auto' image assets, all in ONE new chat inside the ChatGPT project 'Wait What'.

Usage: assets_ep06.py NAME [NAME ...] [--redo] [--note "extra instruction"]
Extra High mode is checked before every send (never Pro). Saved to assets_ep06/NAME.png as raw ChatGPT output.
--redo moves the existing file to assets_ep06/rejected/ first, and --note appends a correction to the prompt.
The conversation URL is kept in assets_ep06/.chat_url so every later image goes into the same chat.
Stops on any login, limit or verification prompt. Closes its own tab at the end and lists tabs.
"""
import base64, json, os, shutil, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.u.SESSION = 'waitwhat-ep06'
H = a.HERE
OUT = H + 'assets_ep06/'
STATE = OUT + '.chat_url'
PROJECT = 'https://chatgpt.com/g/g-p-6aec8d01cc44819187bccb1828549b23/project'
LEADS, EP03, EP01 = H + 'assets_leads/', H + 'assets_ep03/', H + 'assets/'
STYLE_REF = H + 'style/frame_a.png'

PAPER = ('The same real hand-cut construction paper craft as the Game Night paper puppets: fine paper fibres, slightly uneven scissor edges, '
         'muted palette of mustard, brick red, dusty teal, cream and brown, photographed like a tiny physical diorama, paper card not felt.')
NOTEXT = 'ABSOLUTELY NO text anywhere: no letters, no numbers, no words, no signs with writing, no logos. Any sign or label is left blank.'
ORIG = 'Everything is an original fictional design: no real person, no existing cartoon, no video game logo, font or character. No racial stereotypes.'
KEY = ('Flat, even, completely solid pure green background (#00FF00) with nothing else in the image: no shadow on the background, no floor, no furniture, no text. '
       'The whole figure is visible with a clear green margin all round, nothing cropped. Vertical 2:3 image, 1024x1536.')
FACE = ('The two big eyes are plain white paper ovals with NO pupils. There is NO mouth: the skin below the eyes is blank. Do not draw a nose.')

RUSSELL = ('Image 1 is the exact character reference: the same original hand-cut paper man named Russell, with the same spiky brown paper hair, the same warm peach paper skin, '
           'the same round head and body proportions, the same dark brown trousers and the same paper style. ' + ORIG)
POSE = ('Seated posture as if on an invisible seat, shown facing the camera, with NO chair, NO sofa, NO armchair, NO cushion and no furniture of any kind drawn (the green background shows right up to his bottom and legs): upright torso, thighs pointing forward and shown short and rounded, lower legs hanging straight down, '
        'his bottom sits flat at the very bottom of the body with NO gap between the torso and the thighs, he is NOT floating and NOT crouching (image 2 shows the seated body construction only: ignore its person). '
        'Both hands hold a small grey paper video game controller in front of his belly, each hand a full paper hand with clearly separate fingers on the controller, thumbs on the sticks. '
        'Face: heavy half-closed flat eyelids across the top of each white oval and flat level brows, a completely dead, bored, unimpressed stare. ' + FACE)
SAME = ('Image 1 is the exact reference. Redraw exactly the same character in exactly the same pose, at exactly the same size and in exactly the same position in the frame: '
        'identical head, hair, eyes, brows, body, arms, hands on the controller and legs. Nothing moves by even a few pixels. ')

ITEMS = {
    'russell_s1': ([EP03 + 'russell.png', EP01 + 'dave_down.png'],
                   f'{PAPER}\n\n{RUSSELL}\n\nDraw him wearing a plain teal short-sleeved t-shirt over his round belly, dark brown trousers and dark brown shoes. {POSE}\n\n{NOTEXT}\n\n{KEY}'),
    'russell_s2': ([OUT + 'russell_s1.png'],
                   f'{PAPER}\n\n{SAME}ONLY ONE thing is added: an old man\'s chunky knitted brown cardigan with cream buttons, worn over the same teal t-shirt, sleeves covering his forearms down to the wrists. Everything else stays identical, the hands still hold the same controller. {FACE}\n\n{NOTEXT}\n\n{KEY}'),
    'russell_s3': ([OUT + 'russell_s2.png'],
                   f'{PAPER}\n\n{SAME}ONLY TWO things are added: a pair of round reading glasses with thin dark frames sitting low on his face over the eyes, and a folded tartan paper blanket lying across his lap and knees (red, mustard and cream checks), with the controller still visible in his hands above it. Everything else, including the cardigan, stays identical. {FACE}\n\n{NOTEXT}\n\n{KEY}'),
    'russell_s4': ([OUT + 'russell_s3.png'],
                   f'{PAPER}\n\n{SAME}ONLY ONE thing is added: a cream paper teacup on a saucer, with a thin curl of steam, placed on a small side shelf at the lower right of the frame beside his right elbow, not held by him. Everything else, including the glasses, blanket and cardigan, stays identical. {FACE}\n\n{NOTEXT}\n\n{KEY}'),
    'marcus_box': ([LEADS + 'marcus_jump.png'],
                   f'{PAPER}\n\nUse the attached image as the exact reference for the character: the same original hand-cut paper man Marcus with the same warm dark brown paper skin, two big plain white paper oval eyes with NO pupils, NO mouth, no nose, the same short black curly hair, cream headband, red and yellow sports jersey, brown shorts with yellow stripes, cream socks and sneakers. {ORIG}\n\n'
                   f'Redraw him leaping in mid-air in a similar jump pose, knees bent and feet kicked up, with both arms thrown straight up and both hands gripping ONE video game box high above his head, bursting with excitement. Both arms are complete, each ending in a full paper hand with five clear fingers on the box. NO selfie stick, NO phone, NO microphone. '
                   f'The game box is a rectangular paper game case held up with its front facing the camera, front art a colourful paper collage of a sunset street with tiny paper elderly people, thick black border, and the box has completely blank areas where a title would be. {NOTEXT}\n\n{KEY}'),
    'neil_box': ([EP03 + 'neil.png', OUT + 'marcus_box.png'],
                 f'{PAPER}\n\nImage 1 is the exact character reference: the same original hand-cut paper man Neil with the same neat dark hair, round dark-rimmed glasses over his white oval eyes, cream shirt with brown tie and brown trousers, same paper style. Image 2 shows the exact game box he holds (only the box matters: ignore the jumping boy). {ORIG}\n\n'
                 f'Draw Neil standing, holding that same game box in both hands in front of his chest, tilted slightly toward himself as he reads it. Both hands are complete paper hands with clear fingers. He looks very tired and resigned: heavy drooping eyelids on his white oval eyes behind the glasses, brows lowered, shoulders sagging. {FACE} Same size and figure proportions as in image 1. {NOTEXT}\n\n{KEY}'),
    'game_street_a': ([STYLE_REF],
                      f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\nCreate a full-screen video game screenshot in third-person view from behind an elderly man: a paper-cut sunset suburban street in orange, red and purple paper layers with a huge low paper sun, paper houses and a paper parked car. In the foreground we see the back of a hunched elderly hero with white hair pushing a metal walking frame, '
                      f'lifting a wooden cane high over his head with one hand. In front of him, a few steps away, another elderly man in a beige coat faces him. Cinematic game camera, strong depth, slightly low angle, big dramatic sky. No HUD, no health bar. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
    'game_street_b': ([OUT + 'game_street_a.png'],
                      f'{PAPER}\n\nThe attached image is the exact scene. Draw the very next frame with the SAME composition, the same camera, the same street, sunset and paper layers: the cane has just hit. The elderly man in the beige coat in front is blasted backwards through the air in a cartoon way, arms and legs flailing, glasses flying off, hat flying off, tiny cartoon impact star and speed lines at the point of contact; the hero in the foreground still stands with his walking frame and his cane swung forward. '
                      f'Funny, comic, family-friendly violence: no blood, no wounds, nothing gory. No HUD. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
    'game_trailer': ([STYLE_REF],
                     f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\nCreate a full-screen video game screenshot, third-person action camera, low dramatic angle: a paper-cut trailer park at golden hour, rows of cream and teal paper caravans, power lines, a paper water tower. '
                     f'In the foreground a fierce elderly grandmother with grey curly hair, a floral housecoat and slippers swings a big red handbag with both hands like a baseball bat at a pink plastic flamingo garden ornament which is flying off its stick; her pose is huge, heroic and full of attitude, motion arcs and dust puffs around her. No HUD. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
    'game_bank': ([STYLE_REF],
                  f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\nCreate a full-screen video game screenshot, third-person view from slightly behind an elderly man: a paper-cut bank interior with beige marble columns and a long teller counter with brass bars. The old man in the foreground in a flat cap and cardigan hands a small passbook across the counter to a bored teller. '
                  f'Behind him a very long, perfectly orderly queue of elderly people with walking sticks and handbags stretches back to the door, all patient and sombre. Dull, dignified, solemn lighting, grand and quiet like an epic mission. Paper clocks on the wall have no numbers. No HUD. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
    'game_pharmacy': ([STYLE_REF],
                      f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\nCreate a full-screen video game screenshot, third-person view from slightly behind an elderly man in a flat cap with a walking stick: a paper-cut pharmacy interior at the counter, shelves of coloured pill bottles and boxes, a green paper cross symbol glowing above the counter, a pharmacist behind the counter. '
                      f'A glowing yellow circular objective marker lies on the floor in front of the counter where the old man stands, with a soft vertical beam of light rising from it, exactly like a mission location in an open-world game. No HUD, no minimap. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
    'cover': ([STYLE_REF],
              f'Use the attached image only as the style reference for the hand-cut paper craft (ignore its content). {PAPER}\n\nCreate a video game box-cover collage: a 3x3 grid of rectangular panels separated by thick black borders, packed edge to edge, vertical 2:3. Eight panels each show one expressive hand-cut paper elderly man or woman in dramatic action, in bold saturated sunset colours: '
              f'(1) an old man racing a mobility scooter at crazy speed with motion lines, (2) an old man raising a wooden cane in a heroic pose, (3) an old man on a walking frame leaping over a ring of paper flames, (4) an old woman holding up a pair of dentures in triumph, (5) an old woman swinging a handbag, (6) an old man holding a giant pill organiser box, (7) an old woman in a hat pointing a rolled umbrella like a weapon, (8) an old man in a cardigan driving a tiny car. '
              f'The ninth panel is the centre of the lower half: a completely empty, flat, plain dark charcoal paper area with thick black border, with NOTHING in it, left blank for a title to be added later. It must look at a glance like a blockbuster open-world game cover, loud and explosive. {ORIG}\n\n{NOTEXT}\n\nVertical 2:3 image, 1024x1536.'),
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


def send(prompt, refs):
    a.guard()
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
    cur = a.js('location.href') or ''
    if not (url != PROJECT and url.split('/c/')[-1] in cur and a.js('!!' + a.BOX)):
        a.call('navigate', {'url': url, 'newTab': False, 'group_title': 'WaitWhat EP06'})
    for _ in range(30):
        if a.js('!!' + a.BOX):
            break
        time.sleep(2)
    time.sleep(5)
    if a.js("/登入|Log in|額度|limit|unusual|驗證/i.test((document.querySelector('[role=\"dialog\"]')||{}).innerText||'')"):
        sys.exit('login, limit or verification prompt')
    time.sleep(4)
    before = a.js(GENS + '.map(i=>i.src)') or []
    send(prompt, refs)
    start = time.time()
    idle = 0
    while time.time() - start < 600:
        time.sleep(8)
        a.guard()
        cur_srcs = a.js(GENS + '.map(i=>i.src)') or []
        new = [x for x in cur_srcs if x not in before]
        n = len(new)
        n0 = 0
        busy = a.js("!!document.querySelector('[data-testid=\"stop-button\"]')")
        if n > n0 and not busy:
            data = a.js("(async()=>{const g=%s;const r=await fetch(g.at(-1).src);const b=await r.blob();return await new Promise(o=>{const f=new FileReader();f.onload=()=>o(f.result);f.readAsDataURL(b)})})()" % GENS)
            open(dest, 'wb').write(base64.b64decode(data.split(',', 1)[1]))
            print(name, 'saved', os.path.getsize(dest), round(time.time() - start), 's', flush=True)
            href = a.js('location.href')
            if '/c/' in (href or ''):
                open(STATE, 'w').write(href)
            print('chat url', href, flush=True)
            return
        idle = 0 if busy else idle + 1
        if idle >= 12 and n <= n0:
            break
    print('page', str(a.js("(document.querySelector('main').innerText||'').slice(-400)")), flush=True)
    sys.exit(f'{name}: no image')


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
    try:
        main()
    finally:
      if '--keep' not in sys.argv:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
      print('tabs', a.call('list_tabs', {}).get('data'), flush=True)
      if 0:
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

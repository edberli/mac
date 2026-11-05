#!/usr/bin/env python3
"""The three leads together in the original Game Night paper style."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a
import assets_duo2 as d

a.OUT = a.HERE + 'cast_test/'
TRIO = """Create a comedy trio of three adult male friends, all original fictional characters, not based on any real person or existing cartoon.
1. CENTRE: a chubby, smug, mean-spirited, self-important man with a big round belly in a teal jumper, spiky brown hair, arms crossed, chin up, one eyebrow raised, and a nasty little know-it-all smirk. He has no hat and no red clothing.
2. LEFT: a very hyperactive young Black man, drawn with exactly the same simple face construction as the others (same round head, same white eyes, same small paper mouth, warm dark brown paper skin, no exaggerated lips or facial features, no stereotype). He is mid-jump, arms flung out, with a huge wide-open joyful mouth, a bright red and yellow made-up sports jersey with no logo or number, a white headband, short black hair.
3. RIGHT: a tall, thin, tired, sensible man with a long oval head, neat black hair, round glasses around his white eyes, a cream shirt with a slightly crooked tie, and a flat exhausted mouth, looking sideways at the other two."""
LAY = 'Layout, vertical 9:16: top two thirds, the three full figure on a plain warm mustard paper wall with clear contrasting silhouettes. Bottom third: three matching close-up faces in a row showing each one mid-reaction: the chubby one sneering, the energetic one screaming, the tall one closing his eyes in despair. No text, no logos.'
a.ITEMS = [('trio_a', a.REF, f'{d.STYLE}\n\n{TRIO}\n\n{LAY}')]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

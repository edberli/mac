#!/usr/bin/env python3
"""A chubby lead and a Black lead in the original Game Night paper style, drawn with equal dignity."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'cast_test/'
STYLE = 'Use the attached image as the exact style reference and keep it unchanged: warm hand-cut paper, the same round heads with almost no neck, large white paper oval eyes with black dot pupils, a separate glued-on paper mouth, simple bodies, muted mustard, brick red, dusty teal and brown palette, soft shadows and warm light.'
LAY = 'Layout, vertical 9:16, two rows on a plain warm mustard paper wall. Top row: the two men standing side by side in everyday clothes, facing the camera, with funny contrasting expressions. Bottom row: the same two men, with exactly the same faces and body shapes, dressed as a sketch-comedy duo playing other roles: left pair as two police officers, right pair as two chefs. They must be instantly recognisable as the same two guys in costume. No text, no logos, no existing cartoon characters.'
FAT = 'Man 1 is a lovable chubby guy: the same face design as the man on the left of the reference with spiky brown hair, a big confident open grin, and a big round belly fully covered by his teal jumper. He looks funny and charming, and his weight is not mocked.'
RESPECT = 'Man 2 is a Black man drawn with exactly the same simple face construction as every other character in this style: the same round head, the same white eyes and the same small glued-on paper mouth, with warm dark brown paper skin. No exaggerated lips or facial features and no stereotype of any kind: he must look as appealing and dignified as anyone else.'

a.ITEMS = [
    ('duo_c', a.REF, f'{STYLE}\n\nCreate a comedy duo of two male friends. {FAT} {RESPECT} He is tall and slim, with a neat short black flat-top haircut, a mustard hoodie and a calm, unimpressed flat mouth with one raised eyebrow. {LAY}'),
    ('duo_d', a.REF, f'{STYLE}\n\nCreate a comedy duo of two male friends. {FAT} {RESPECT} He is about average height, with short black curly hair, round glasses around his white eyes, a smart brick red cardigan over a cream shirt and a small sceptical smile. {LAY}'),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

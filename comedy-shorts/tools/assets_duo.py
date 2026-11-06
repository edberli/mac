#!/usr/bin/env python3
"""Two male leads in the original Game Night paper style, shown in costumes as sketch actors."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'cast_test/'
STYLE = 'Use the attached image as the exact style reference and keep it unchanged: warm hand-cut paper, the same round heads with almost no neck, large white paper oval eyes with black dot pupils, a separate glued-on paper mouth, simple bodies, muted mustard, brick red, dusty teal and brown palette, soft shadows and warm light.'
LAY = 'Layout, vertical 9:16, two rows on a plain warm mustard paper wall. Top row: the two men standing side by side in everyday clothes, facing the camera, with funny contrasting expressions. Bottom row: the same two men, with exactly the same faces and body shapes, dressed as a sketch-comedy duo playing other roles: left pair as two police officers, right pair as two chefs. They must be instantly recognisable as the same two guys in costume. No text, no logos, no existing cartoon characters.'
DAVE = 'Man 1 is exactly the man on the left of the reference: spiky brown hair, teal jumper, dark brown trousers, a big confident open grin.'

a.ITEMS = [
    ('duo_a', a.REF, f'{STYLE}\n\nCreate a comedy duo of two male friends. {DAVE} Man 2 is much taller and thinner than man 1, with a neat black side parting, a long oval head, a cream shirt and a calm, deadpan flat mouth. {LAY}'),
    ('duo_b', a.REF, f'{STYLE}\n\nCreate a comedy duo of two male friends. {DAVE} Man 2 is shorter and wider than man 1, bald with a big dark moustache and round glasses around his white eyes, a brick red jumper and a worried little mouth. {LAY}'),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

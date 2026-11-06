#!/usr/bin/env python3
"""Cast test built from what successful comedy cartoon channels share: huge heads, small bodies, simple faces, loud colour, one signature feature."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'cast_test/'
MATERIAL = 'Use the attached image only as the reference for the material: real hand-cut construction paper with fibres, scissor edges and soft shadows between layers. Ignore its characters, palette and dim lighting. Use bright, even, cheerful light.'
RULES = 'Design rules for all characters: the head is huge, about half of the total figure height, on a small simple body with short arms and legs. All three are about the same height. The face is extremely simple: big white paper eyes with tiny black dot pupils, separate thick paper eyebrows and one big mouth shape, with no nose or just a tiny one. Each has one instantly recognisable signature feature. Likeable, ordinary and funny, never scary or gross: no wrinkles, warts or bare skin.'
CAST = '1. DAVE: a tilted bright red baseball cap, a gap in his front teeth, a yellow T-shirt.\n2. KAREN: a huge round black afro-puff of hair like a big ball, flat straight eyebrows, a bright purple jumper.\n3. DORIS: a tall bright pink beehive hairdo, big round black glasses, a turquoise cardigan.'
LAYOUT = 'Layout, vertical 9:16: top row, the three standing side by side with their normal faces (Dave grinning smugly, Karen unimpressed, Doris sour). Bottom row, the same three, head and shoulders only, with extreme comedy expressions: Dave screaming with a giant open mouth and tiny pupils, Karen with one raised eyebrow and a sideways glare, Doris shocked with her mouth a huge O. Plain flat background. No text, no logos, no existing cartoon characters; these are original designs.'

a.ITEMS = [
    ('cast_d', a.REF, f'{MATERIAL}\n\nCreate a comedy trio. {RULES} Every paper shape has a bold black paper outline around it, like a thick cut border, so the figures pop at tiny sizes. Very saturated colours on a pale sky blue paper background.\n{CAST}\n\n{LAYOUT}'),
    ('cast_e', a.REF, f'{MATERIAL}\n\nCreate a comedy trio. {RULES} No outlines: shapes are separated only by colour and shadow, in the style of simple kids-show cut paper. Very saturated primary colours on a pale cream paper background.\n{CAST}\n\n{LAYOUT}'),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

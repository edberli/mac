#!/usr/bin/env python3
"""Generate the bank backgrounds and new puppets for On Hold through ChatGPT. Reuses the assets.py machinery."""
import sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

OLD = a.OUT
a.OUT = a.HERE + 'assets_ep02/'
STYLE = 'Use the attached image as the exact style reference for the paper craft: the same real hand-cut construction paper with fine fibres, slightly uneven scissor edges, flat simple shapes and the same warm light. Use a palette of muted teal, cream, mustard, brick red and warm grey.'
BG = a.BG
ROOM = 'the inside of a small old-fashioned bank made of paper: cream walls, a big round clock, a paper poster of a piggy bank, and a round steel vault door'
a.STYLE = STYLE
FACE = a.FACE
KEY = a.KEY
PUP = OLD + 'dave_down.png'


def fig(desc):
    return f'{STYLE}\n\nCreate one single flat paper puppet in exactly the same size, proportions and paper style as the attached figure: {desc}. Show only this ONE figure, large, filling the frame. {FACE}\n\n{KEY}'


a.ITEMS = [
    ('bg_bank_wide', a.REF, f'{STYLE}\n\nCreate {ROOM}, completely empty and viewed straight on. A long wooden bench against the wall on the left half of the frame, with its seat top at about 60% of the image height. The right third has a wooden teller counter seen from the front, with open space behind it. Tiled floor. {BG}'),
    ('bg_bank_close', a.REF, f'{STYLE}\n\nCreate {ROOM}, with the clock in the upper left and the vault door on the right, straight on, softly out of focus, with a tiled floor filling the bottom 15% of the image. Completely empty. {BG}'),
    ('bg_teller_close', a.REF, f'{STYLE}\n\nCreate the back wall of a bank teller booth made of paper, straight on: cream wall, a shelf of paper folders, a small brass bell and a calendar, softly out of focus. Completely empty. {BG}'),
    ('bg_bench_close', a.REF, f'{STYLE}\n\nCreate a straight-on close view of a long empty wooden paper bench against a cream bank wall, filling the entire width of the frame. The top of the seat is a clear horizontal line at about 62% of the image height, with the tiled floor at about 85%. A paper poster of a piggy bank on the wall behind it, softly out of focus. {BG}'),
    ('counter', a.REF, f'{STYLE}\n\nCreate only a wide wooden paper bank counter seen from the front, with a thin brass rail on top, filling the full width of the image and the lower half of its height. {KEY}'),
    ('vince', PUP, fig('a bank robber standing, legs straight, in a black balaclava ski mask whose wide oval opening shows the bare skin face and the two eyes, a black and white striped jumper and dark trousers. One hand holds a red paper telephone receiver with a curly cord to the side of his head. The other hand holds a brown paper money sack marked with a dollar sign')),
    ('doris', a.OUT + 'vince.png', fig('an elderly female bank teller seen from the waist up, with a neat grey hair bun, a teal cardigan, a name badge, and round thin paper glasses that frame the two white eyes')),
    ('cop', PUP, fig('a police officer in a full dark blue uniform with a peaked police cap, a badge and a moustache cut from brown paper, seated with bent legs hanging down. One hand holds a black paper mobile phone to the side of his head and the other rests on his knee')),
]

if __name__ == '__main__':
    import os
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

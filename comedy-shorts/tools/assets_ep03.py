#!/usr/bin/env python3
"""Riggable puppets for the three leads and the birthday-party plates for episode 3."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'assets_ep03/'
TRIO = a.HERE + 'cast_test/trio_a.png'
OLD = a.HERE + 'assets/'
STYLE = 'Use the attached image as the exact style reference: the same hand-cut paper, shapes, proportions and warm palette.'
FACE = 'The two big eyes are plain white paper ovals with NO pupils. There is NO mouth: the skin below the eyes is completely blank, and there is no nose. Keep the eyebrows as separate paper pieces only if stated.'
KEY = a.KEY


def fig(desc):
    return f'{STYLE}\n\nCreate one single flat paper puppet, standing, facing the camera, full figure: {desc}. Show only this ONE figure, large, filling the frame. {FACE}\n\n{KEY}'


BG = 'No people or animals. No text anywhere. Warm table-lamp light, soft vignette, slight film grain, shallow depth of field, photographed like a small physical diorama. Vertical 9:16 image.'
PARTY = 'Decorated for a sad little birthday party with a paper garland of triangular flags and a few paper balloons on the wall.'
a.ITEMS = [
    ('bg_party_close', OLD + 'bg_sofa_close.png', f'{STYLE}\n\nCreate exactly this same empty red paper sofa and room from the attached image, unchanged. {PARTY} {BG}'),
    ('bg_party_wide', OLD + 'bg_wide.png', f'{STYLE}\n\nCreate exactly this same empty living room from the attached image, unchanged. {PARTY} {BG}'),
    ('table_cake', OLD + 'table.png', f'{STYLE}\n\nCreate this same round brown paper coffee table, with on it a paper plate holding only crumbs and one burnt-out candle, and no wine glasses. {KEY}'),
    ('russell', TRIO, fig('the chubby man in the centre of the attached image, unchanged: big round belly in a teal jumper, spiky brown hair, arms crossed, chin slightly up. One eyebrow raised higher than the other, cut from brown paper. A small smear of cream frosting on his jumper')),
    ('neil', TRIO, fig('the tall thin man on the right of the attached image, unchanged: long oval head, neat black hair, thin round glasses frames around his white eyes, a cream shirt, a slightly crooked tie, dark trousers, arms at his sides')),
    ('marcus', TRIO, fig('the energetic young Black man on the left of the attached image, unchanged, with warm dark brown paper skin and the same simple face construction as the others, standing with knees bent, white headband, short black hair, a red and yellow made-up sports jersey with no logo or number, shorts, sneakers. One hand holds up a phone on a selfie stick and the other is a fist')),
    ('marcus_jump', a.OUT + 'marcus.png', fig('exactly this same man from the attached image, unchanged, now leaping in mid-air with legs kicked out and both arms flung wide, still holding the phone on a selfie stick in one hand')),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

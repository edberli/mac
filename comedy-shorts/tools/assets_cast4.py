#!/usr/bin/env python3
"""Six genuinely different character directions for the same comedy trio."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'cast_test/'
ROLES = 'The same comedy trio in every design: a smug over-confident fool, grinning (left); an unimpressed deadpan woman (middle); a sour, tiny, seen-it-all elderly woman (right).'
END = 'Standing side by side, full figure, large in a vertical 9:16 image, bright and appealing, instantly funny. Each must be recognisable from silhouette alone. Never scary or gross. No text, no logos, no existing cartoon characters; these are original designs.'
MAT = 'Use the attached image only as the reference for the handmade material quality: visible fibres, real edges and soft shadows. Ignore its characters and palette.'

a.ITEMS = [
    ('cast_f_beans', a.REF, f'{MAT}\n\n{ROLES}\nDesign: soft bean-shaped cut-paper blobs with no necks, tiny stubby limbs, tiny black dot eyes set far apart and one small expressive mouth. Each blob is a single bright colour: yellow, lilac, mint. {END} Pale pink paper background.'),
    ('cast_g_doodle', a.REF, f'{ROLES}\nDesign: scrappy hand-drawn black felt-tip doodles on lined notebook paper: big wobbly round heads, stick arms and legs, messy scribbled hair, huge expressive eyes, drawn quickly and confidently like a funny student cartoon, with only one or two splashes of marker colour. {END}'),
    ('cast_h_geometric', a.REF, f'{MAT}\n\n{ROLES}\nDesign: 1950s mid-century modern geometric cut paper: the fool is a tall triangle-shaped man, the woman a thin rectangle, the elderly woman a small circle; flat graphic shapes with thin legs, tiny faces with stylish minimal features, a limited palette of tomato red, teal, mustard and off-white. {END} Off-white paper background.'),
    ('cast_i_animals', a.REF, f'{MAT}\n\n{ROLES}\nDesign: office-worker animals in cut paper wearing human clothes: a chubby smug pug in a too-small shirt and tie, a tall bored flamingo-like heron in a blazer, and a tiny grumpy old tortoise with glasses in a cardigan. {END} Pale green paper background.'),
    ('cast_j_veg', a.REF, f'{MAT}\n\n{ROLES}\nDesign: vegetable people in cut paper with little arms and legs and big silly faces: the fool is a fat grinning potato with a tiny baseball cap, the woman a tall thin unimpressed carrot-like leek, and the elderly woman a tiny wrinkle-free grumpy onion with round glasses. {END} Pale yellow paper background.'),
    ('cast_k_googly', a.REF, f'{ROLES}\nDesign: handmade craft puppets photographed in close-up on a table: heads made from crumpled brown paper bags and coloured card, real plastic googly eyes of mismatched sizes, pipe-cleaner arms, a big felt mouth, wool hair, like a charming children\'s craft project gone wrong. {END} Plain bright blue paper backdrop.'),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

#!/usr/bin/env python3
"""Generate cast-redesign and end-tag test images through ChatGPT. Reuses the assets.py machinery."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a

a.OUT = a.HERE + 'cast_test/'
STYLE = 'Use the attached image only as the reference for the material and light: real hand-cut construction paper with visible fibres, uneven scissor edges, soft real shadows between layers, warm lamp light and slight film grain. The characters in the attached image are too cute and too similar. Replace them with the new designs below.'
SCENE = 'They stand side by side, full figure, in front of a plain mustard paper wall, on a brown paper floor, in a vertical 9:16 image. No text, no logos, no existing cartoon characters; these are original designs.'
CAST_A = 'a comedy trio with hilarious, instantly different silhouettes, ugly-cute and full of personality.\n1. DAVE: huge pear-shaped body, very tiny head, giant over-confident grin with big buck teeth, tiny legs, a too-small teal jumper.\n2. KAREN: extremely tall and thin, with a long giraffe neck, small dead fish eyes set close together, a flat unimpressed mouth, a mustard jumper and a brown bob haircut.\n3. DORIS: very short and wide, an old lady with enormous thick round glasses that magnify her eyes, a huge grey hair bun bigger than her head, a teal cardigan and a sour little mouth.'
CAST_B = 'a comedy trio pushed much further into grotesque-funny caricature, like an underground adult cartoon, but not disgusting: no slime, no blood, no body fluids.\n1. DAVE: a gigantic round belly, a pinhead with one crooked tooth, wonky eyes pointing in different directions, a comb-over of three hairs, tiny feet.\n2. KAREN: a skeletal tall woman with a very long chin, heavy eyelids, a huge hooked nose and a thin line for a mouth, wearing a mustard jumper.\n3. DORIS: a tiny old lady shaped like a potato, with a giant wart, glasses so thick her eyes fill the lenses, one enormous hair bun, and a permanent scowl.'

a.ITEMS = [
    ('cast_c', a.OUT + 'cast_a.png', "Use the attached image as the reference for the paper craft and the three characters' silhouettes. Create a new version that is funny and friendly, never scary or gross: smooth clean paper skin with no warts, pimples, spots, wrinkles, bare belly or belly button. Soft rounded shapes and big silly expressions.\n1. DAVE: pear-shaped with a very tiny head, wearing a teal jumper that fully covers his big round tummy, a huge happy goofy grin with two big front teeth, eyebrows raised, tiny legs.\n2. KAREN: very tall and thin with a long neck, neat brown bob, simple round dot eyes with sleepy half-closed paper eyelids, a small flat unimpressed mouth, a normal small nose, a mustard jumper.\n3. DORIS: very short and round, huge round glasses, a giant grey hair bun, rosy cheeks, a small pursed mouth, a teal cardigan.\n\\nThey stand side by side, full figure, in front of a plain mustard paper wall on a brown paper floor. Warm, charming and comedic, suitable for all audiences. Vertical 9:16. No text, no logos, no existing cartoon characters."),
]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

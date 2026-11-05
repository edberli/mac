#!/usr/bin/env python3
"""The Black lead as an original hyperactive character: the energy of a loud live-streamer, not anyone's likeness."""
import os, sys
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work/comedy')
import assets as a
import assets_duo2 as d

a.OUT = a.HERE + 'cast_test/'
LAY = 'Layout, vertical 9:16, on a plain warm mustard paper wall. Top half: the two friends together, full figure, the chubby one standing still and calmly eating a sandwich while the other leaps in the air beside him. Bottom half: three head-and-shoulders close-ups of the energetic man only, with extreme expressions: screaming with joy, sudden shock with tiny pupils, and wild laughing. No text, no logos, no existing cartoon characters, no real person.'
HYPER = "Man 2 is an original fictional character, not based on the appearance of any real person. He is a very hyperactive young Black man with explosive, loud, unpredictable energy, like he is permanently live on camera: mid-jump, arms flung out, huge wide-open mouth, wild wide eyes, one eyebrow high. A bright red and yellow made-up sports jersey with no logo and no number, a white headband, short black hair, and a phone on a selfie stick in one hand."
a.ITEMS = [('duo_e', a.REF, f'{d.STYLE}\n\nCreate a comedy duo of two male friends. {d.FAT} {d.RESPECT} {HYPER} {LAY}')]

if __name__ == '__main__':
    os.makedirs(a.OUT, exist_ok=True)
    try:
        a.main()
    finally:
        for t in (a.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            a.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', a.call('list_tabs', {}).get('data'), flush=True)

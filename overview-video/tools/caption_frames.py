"""Print the frame numbers where a caption is on screen (only these change when captions are toggled).

usage: python3 tools/caption_frames.py build/ep01_main
"""
import json, math, os, sys
tl = json.load(open(os.path.join(sys.argv[1], 'timeline.json')))
fps, n = tl['fps'], tl['frames']
fr = set()
for ln in tl['lines']:   # same window as kit2d captions(): start-0.05 .. end+0.25
    for f in range(max(0, math.floor((ln['start'] - 0.05) * fps)), min(n, math.ceil((ln['end'] + 0.25) * fps) + 1)):
        fr.add(f)
print(','.join(map(str, sorted(fr))))

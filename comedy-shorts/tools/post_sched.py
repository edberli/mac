#!/usr/bin/env python3
"""Upload a Short and stop on the visibility step without publishing, leaving the tab open so it can be scheduled. Never selects Public."""
import json, os, re, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_shorts as y

FILE, TITLE, DESC = sys.argv[1:4]
STATE = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/posted.json'
done = json.load(open(STATE)) if os.path.exists(STATE) else {}
if FILE in done:
    sys.exit(f'already uploaded as {done[FILE]}')
y.guard()
y.call('navigate', {'url': f'https://studio.youtube.com/channel/{y.u.CHANNEL}/videos/upload?d=ud&authuser=3', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
if not y.wait("document.querySelector('ytcp-uploads-file-picker input[type=file]')||document.querySelector('input[type=file][name=Filedata]')", 60, 'picker'):
    sys.exit('no upload picker')
name = y.js("(document.querySelector('ytcp-navigation-drawer #entity-name, #entity-name')||{}).innerText||''")
print('channel', repr(name), flush=True)
if 'WaitWhat' not in str(name):
    sys.exit('wrong channel')
y.inject(FILE, TITLE)
if not y.wait("document.querySelector('#title-textarea #textbox')", 120, 'details'):
    sys.exit('details form missing')
time.sleep(3)
print('title', repr(y.set_box('#title-textarea #textbox', TITLE)), flush=True)
print('desc', repr(y.set_box('#description-textarea #textbox', DESC)), flush=True)
print('kids', y.js("(()=>{const r=document.querySelector('tp-yt-paper-radio-button[name=\"VIDEO_MADE_FOR_KIDS_NOT_MFK\"]');if(!r)return 'missing';r.click();return r.getAttribute('aria-checked')})()"), flush=True)
time.sleep(2)
link, t = '', time.time()
while not link and time.time() - t < 240:
    link = y.js("(document.querySelector('.video-url-fadeable a, ytcp-video-info a')||{}).href||''") or ''
    time.sleep(3)
print('link', link, flush=True)
m = re.search(r'(?:youtu\.be/|shorts/|v=)([\w-]{11})', link)
if not m:
    sys.exit('no video id')
done[FILE] = m.group(1)
json.dump(done, open(STATE, 'w'), indent=1)
for step in range(3):
    if not y.wait(y.enabled('#next-button'), 180, f'next {step}'):
        sys.exit(f'next stuck at {step}')
    print('next', step, y.click('#next-button'), flush=True)
    time.sleep(3)
label = "(document.querySelector('ytcp-video-upload-progress .progress-label, .progress-label')||{}).innerText||''"
t = time.time()
while not re.search('上載完成|處理', str(y.js(label))):
    if time.time() - t > 1200:
        sys.exit('upload did not finish')
    time.sleep(20)
print('progress', y.js(label), flush=True)
print('radios', y.js("JSON.stringify([...document.querySelectorAll('tp-yt-paper-radio-button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>[e.getAttribute('name'),e.innerText.trim().slice(0,12),e.getAttribute('aria-checked')]))"), flush=True)
print('sched', y.js("JSON.stringify([...document.querySelectorAll('ytcp-visibility-scheduler,#schedule-radio-button,#second-container,ytcp-datetime-picker,ytcp-date-picker,#datepicker-trigger,#time-of-day-container')].map(e=>[e.tagName,e.id,(e.innerText||'').replace(/\\s+/g,' ').slice(0,80)]))"), flush=True)
print('tabs', y.call('list_tabs', {}).get('data'), flush=True)

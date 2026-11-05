#!/usr/bin/env python3
"""Reopen a draft Short and schedule it for a given local date and time. Never selects Public; retries because the first attempts stay drafts."""
import sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_short_finish as f
y = f.y

VID, DATE, TIME = sys.argv[1:4]
PICK = 'ytcp-datetime-picker'


def is_draft():
    y.call('navigate', {'url': f'https://studio.youtube.com/video/{VID}/edit?authuser=3', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
    y.wait("document.querySelector('#title-textarea #textbox')", 60, 'edit')
    time.sleep(4)
    return '草稿' in str(y.js("(document.body.innerText||'').slice(0,120)"))


def attempt():
    print('edit draft', f.click_text('編輯草稿'), flush=True)
    y.wait("document.querySelector('#next-button')", 30, 'wizard')
    time.sleep(3)
    for step in range(3):
        if y.js("!!document.querySelector('#second-container-expand-button') && document.querySelector('#second-container-expand-button').getBoundingClientRect().width>0"):
            break
        y.wait(y.enabled('#next-button'), 120, f'next {step}')
        print('next', step, y.click('#next-button'), flush=True)
        time.sleep(3)
    print('expand', y.js("(()=>{const b=document.querySelector('#second-container-expand-button');if(!b)return 'none';b.click();return 'ok'})()"), flush=True)
    time.sleep(2)
    y.js("""(()=>{const i=document.querySelector('%s input');const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;i.focus();s.call(i,%r);i.dispatchEvent(new Event('input',{bubbles:true,composed:true}));i.dispatchEvent(new Event('change',{bubbles:true,composed:true}));i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,bubbles:true,composed:true}));i.blur();return 1})()""" % (PICK, TIME))
    time.sleep(2)
    text = str(y.js("(document.querySelector('%s')||{}).innerText" % PICK))
    value = str(y.js("(document.querySelector('%s input')||{}).value" % PICK))
    print('picker', text.replace('\n', ' ')[:70], '|', value, flush=True)
    if DATE not in text or value != TIME:
        sys.exit('schedule value wrong; not confirming')
    label = str(y.js("(document.querySelector('#done-button')||{}).innerText")).strip()
    print('done label', label, flush=True)
    if label != '排程':
        sys.exit('done button is not the schedule button; not clicking')
    y.wait(y.enabled('#done-button'), 300, 'done')
    print('done', y.click('#done-button'), flush=True)
    time.sleep(30)


def main():
    y.guard()
    for n in range(4):
        if not is_draft():
            print('NOT A DRAFT after', n, 'attempts', flush=True)
            print('list', y.js("(()=>{return document.body.innerText.replace(/\\s+/g,' ').slice(0,120)})()"), flush=True)
            return
        y.guard()
        attempt()
        time.sleep(60)
    sys.exit('still a draft after 4 attempts' if is_draft() else 'scheduled on the last attempt')


if __name__ == '__main__':
    try:
        main()
        y.call('navigate', {'url': f'https://studio.youtube.com/channel/{y.u.CHANNEL}/videos/short?authuser=3', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
        time.sleep(8)
        print('rows', y.js("[...document.querySelectorAll('ytcp-video-row')].slice(0,3).map(r=>r.innerText.replace(/\\s+/g,' ').slice(0,170))"), flush=True)
    finally:
        print('tabs', y.close_all(), flush=True)

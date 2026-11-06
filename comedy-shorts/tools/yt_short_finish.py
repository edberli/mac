#!/usr/bin/env python3
"""Reopen a draft Short, select Public, click publish, and print every visible dialog. Never confirms a warning unless given --confirm "<button text>"."""
import sys, time
import yt_shorts as y

VISIBLE = """[...document.querySelectorAll('ytcp-prechecks-warning-dialog,ytcp-video-share-dialog,ytcp-uploads-still-processing-dialog,ytcp-uploads-dialog,tp-yt-paper-dialog,ytcp-dialog,ytcp-confirmation-dialog')]
  .filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none'})
  .map(e=>e.tagName+': '+e.innerText.replace(/\\s+/g,' ').slice(0,900))"""


def dialogs(tag):
    print(f'[{tag}]', y.js(VISIBLE), flush=True)


def click_text(text):
    return y.js("(()=>{const b=[...document.querySelectorAll('button,ytcp-button,ytcp-button-shape,tp-yt-paper-button')].filter(e=>e.offsetParent!==null).find(e=>e.innerText.trim()===%s);if(!b)return 'missing';b.click();return 'ok'})()" % repr(text))


def main(vid):
    y.guard()
    y.call('navigate', {'url': f'https://studio.youtube.com/video/{vid}/edit', 'newTab': False, 'group_title': 'WaitWhat Shorts'})
    y.wait("document.querySelector('#title-textarea #textbox')", 60, 'edit')
    time.sleep(3)
    print('edit draft', click_text('編輯草稿'), flush=True)
    y.wait("document.querySelector('#next-button')", 30, 'wizard')
    time.sleep(3)
    dialogs('opened')
    for step in range(3):
        if y.js("!!document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]') && document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]').offsetParent!==null"):
            break
        y.wait(y.enabled('#next-button'), 120, f'next {step}')
        print('next', step, y.click('#next-button'), flush=True)
        time.sleep(3)
    print('public', y.js("(()=>{const r=document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]');if(!r)return 'missing';r.click();return r.getAttribute('aria-checked')})()"), flush=True)
    time.sleep(2)
    print('done enabled', y.js(y.enabled('#done-button')), flush=True)
    dialogs('before done')
    y.wait(y.enabled('#done-button'), 300, 'done')
    print('done', y.click('#done-button'), flush=True)
    for i in range(6):
        time.sleep(5)
        dialogs(f'after done {(i + 1) * 5}s')
    print('page', str(y.js("(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,200)")), flush=True)
    print('tabs', y.call('list_tabs', {}).get('data'), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])

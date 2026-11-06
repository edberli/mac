#!/usr/bin/env python3
"""Update the WaitWhat channel banner, picture and description in YouTube Studio, then publish. Stops rather than guesses if a dialog does not appear."""
import base64, json, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_shorts as y

CH = 'UCO4SWLY37jF46gBQYyWG_TQ'
BRAND = '/Volumes/core/AI-Workspace/Claude/mac/comedy-shorts/brand/'
DIALOG = "[...document.querySelectorAll('ytcp-dialog,tp-yt-paper-dialog,ytcp-image-cropper-dialog,ytcp-profile-image-editor')].filter(e=>e.offsetParent!==null||e.getBoundingClientRect().width>0)"


def inject(host, path, mime):
    b64 = base64.b64encode(open(path, 'rb').read()).decode()
    return y.js("""(()=>{const i=document.querySelector('%s input[type=file]');if(!i)return 'no input';
      const b=atob('%s');const u=new Uint8Array(b.length);for(let k=0;k<b.length;k++)u[k]=b.charCodeAt(k);
      const d=new DataTransfer();d.items.add(new File([u],'%s',{type:'%s'}));i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}));return u.length})()""" % (host, b64, path.split('/')[-1], mime))


def confirm_dialog(tag):
    for _ in range(25):
        time.sleep(2)
        ok = y.js("""(()=>{const b=[...document.querySelectorAll('ytcp-button, button')].filter(e=>e.getBoundingClientRect().width>0).find(e=>/^(完成|Done)$/.test((e.innerText||'').trim()));if(!b)return 'wait';if(b.getAttribute('aria-disabled')==='true'||b.hasAttribute('disabled'))return 'disabled';(b.querySelector('button')||b).click();return 'clicked'})()""")
        if ok == 'clicked':
            print(tag, 'dialog done', flush=True)
            time.sleep(4)
            return
    print(tag, 'visible buttons', y.js("JSON.stringify([...document.querySelectorAll('ytcp-button,button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>(e.innerText||'').trim().slice(0,12)).filter(Boolean))"), flush=True)
    print(tag, 'dialogs', y.js("JSON.stringify([...document.querySelectorAll('ytcp-dialog,tp-yt-paper-dialog,[role=dialog]')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.tagName+':'+(e.innerText||'').replace(/\\s+/g,' ').slice(0,200)))"), flush=True)
    sys.exit(f'{tag}: crop dialog did not finish')


def main():
    y.guard()
    y.call('navigate', {'url': f'https://studio.youtube.com/channel/{CH}/editing/profile?authuser=3', 'newTab': False, 'group_title': 'WaitWhat Profile'})
    time.sleep(10)
    name = y.js("(document.querySelector('ytcp-navigation-drawer #entity-name, #entity-name')||{}).innerText||''")
    print('channel', repr(name), flush=True)
    if 'WaitWhat' not in str(name):
        sys.exit('wrong channel')
    print('banner', inject('ytcp-banner-upload', BRAND + 'banner_2560x1440.jpg', 'image/jpeg'), flush=True)
    confirm_dialog('banner')
    print('picture', inject('ytcp-profile-image-upload', BRAND + 'icon_800.png', 'image/png'), flush=True)
    confirm_dialog('picture')
    desc = open(BRAND + 'channel_description.md', encoding='utf-8').read().strip()
    print('desc', y.js("""(()=>{const e=document.querySelector('ytcp-channel-editing-profile-tab #textbox[contenteditable=true], #description-container #textbox, #textbox');if(!e)return 'missing';e.focus();e.innerText=%s;e.dispatchEvent(new InputEvent('input',{bubbles:true,composed:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();return e.innerText.length})()""" % json.dumps(desc)), 'of', len(desc), flush=True)
    time.sleep(3)
    for _ in range(20):
        r = y.js("(()=>{const b=document.querySelector('#publish-button');if(!b)return 'missing';if(b.getAttribute('aria-disabled')==='true'||b.hasAttribute('disabled'))return 'disabled';(b.querySelector('button')||b).click();return 'clicked'})()")
        if r == 'clicked':
            break
        time.sleep(3)
    print('publish', r, flush=True)
    time.sleep(15)
    print('after', str(y.js("[...document.querySelectorAll('tp-yt-paper-toast,ytcp-toast')].map(e=>e.innerText).join(' | ')")), flush=True)
    y.guard()
    y.call('navigate', {'url': 'https://www.youtube.com/@WaitWhatST?authuser=3', 'newTab': False, 'group_title': 'WaitWhat Profile'})
    time.sleep(10)
    print('public', str(y.js("(document.querySelector('yt-page-header-renderer, #page-header')||{innerText:''}).innerText.replace(/\\s+/g,' ').slice(0,400)")), flush=True)
    print('images', y.js("JSON.stringify([...document.querySelectorAll('yt-page-header-renderer img, #page-header img')].map(i=>i.src.slice(0,80)).slice(0,4))"), flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        print('tabs', y.close_all(), flush=True)

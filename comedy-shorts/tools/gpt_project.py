#!/usr/bin/env python3
"""Create the ChatGPT project 'Wait What' through the UI if it does not exist, and report what it found. Never prints tokens."""
import json, subprocess, sys, time
sys.path.insert(0, '/Volumes/core/AI-Workspace/Claude/mac-work')
import yt_upload1 as u

u.SESSION = 'waitwhat-project'
OUT = '/Volumes/core/AI-Workspace/Claude/mac-work/comedy/gpt_project.json'
GUARD = '/Volumes/core/claude-work/bin/agent-browser-guard.py'


def main():
    g = json.loads(subprocess.run(['python3', GUARD, '--check'], capture_output=True, text=True).stdout)
    if not g.get('allowed'):
        sys.exit('guard refused')
    u.call('navigate', {'url': 'https://chatgpt.com/', 'newTab': False, 'group_title': 'WaitWhat Project'})
    time.sleep(9)
    links = "[...document.querySelectorAll('nav a[href*=\"/g/g-p-\"][href$=\"/project\"]')].map(a=>[a.innerText.trim(),a.getAttribute('href')])"
    print('project links', u.js('JSON.stringify(%s.slice(0,30))' % links), flush=True)
    print('click new', u.js("""(()=>{const e=[...document.querySelectorAll('nav a, nav button, nav [role=button], nav div')].find(x=>/^(新增項目|新項目|新專案|新增專案|New project)$/.test((x.innerText||'').trim()));if(!e)return 'missing';e.click();return e.tagName})()"""), flush=True)
    time.sleep(3)
    print('dialog', str(u.js("(document.querySelector('[role=dialog]')||{}).innerText||''"))[:300], flush=True)
    print('typed', u.js("""(()=>{const i=document.querySelector('[role=dialog] input');if(!i)return 'no input';i.focus();document.execCommand('insertText',false,'Wait What');i.dispatchEvent(new Event('input',{bubbles:true}));return i.value})()"""), flush=True)
    time.sleep(2)
    print('create', u.js("""(()=>{const b=[...document.querySelectorAll('[role=dialog] button')].find(x=>/^(建立項目|建立專案|建立|Create project|Create)$/.test((x.innerText||'').trim()));if(!b)return 'missing';if(b.disabled)return 'disabled';b.click();return 'ok'})()"""), flush=True)
    time.sleep(8)
    url = u.js('location.href')
    print('url', url, flush=True)
    if '/g/g-p-' in str(url):
        json.dump({'url': url.split('?')[0]}, open(OUT, 'w'))


if __name__ == '__main__':
    try:
        main()
    finally:
        for t in (u.call('list_tabs', {}).get('data') or {}).get('tabs', []):
            u.call('close_tab', {'tabId': t['tabId']})
        print('tabs left', u.call('list_tabs', {}).get('data'), flush=True)

#!/usr/bin/env python3
"""Sum API usage of this session and its subagents per production phase, from the session transcripts. Windows are Singapore time on 2026-11-05."""
import glob, json, os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = '/Users/winstonli/.claude/projects/-Volumes-core-claude-work/904065d0-5d84-4aaa-8443-518533ee73b6'
SGT = timezone(timedelta(hours=8))
PHASES = [('Game Night', '15:13', '17:29'), ('On Hold', '17:29', '18:15'), ('Character tests', '18:15', '20:00'), ('Episode 3-5 so far', '20:00', '23:59')]


def at(hm):
    h, m = hm.split(':')
    return datetime(2026, 11, 5, int(h), int(m), tzinfo=SGT)


files = [ROOT + '.jsonl'] + glob.glob(ROOT + '/**/*.jsonl', recursive=True)
print('files', len(files))
seen, totals = set(), defaultdict(lambda: defaultdict(int))
for path in files:
    for line in open(path, encoding='utf-8', errors='ignore'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get('message') or {}
        use = msg.get('usage') if isinstance(msg, dict) else None
        if not use or not d.get('timestamp'):
            continue
        key = (msg.get('id'), d.get('requestId'))
        if key in seen:
            continue
        seen.add(key)
        t = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00'))
        for name, a, b in PHASES:
            if at(a) <= t < at(b):
                model = (msg.get('model') or '?').replace('claude-', '')
                row = totals[(name, model)]
                row['calls'] += 1
                row['input'] += use.get('input_tokens', 0)
                row['output'] += use.get('output_tokens', 0)
                row['cache_write'] += use.get('cache_creation_input_tokens', 0)
                row['cache_read'] += use.get('cache_read_input_tokens', 0)
print('phase | model | calls | input | output | cache_write | cache_read')
for (name, model), r in sorted(totals.items()):
    print(name, '|', model, '|', r['calls'], '|', r['input'], '|', r['output'], '|', r['cache_write'], '|', r['cache_read'])

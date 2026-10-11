#!/usr/bin/env python3
"""Generate an HTML file with the SAME approved dataset as data/league.json.
Read-only preview until a human commits BOTH HTML and JSON together.
"""
import argparse
import json
import pathlib
import re

DEFINITIONS=pathlib.Path(__file__).resolve().parents[1]/'reference'/'metric_definitions.json'
METRIC_PATTERN=re.compile(r'(<script id="metricdefs" type="application/json">)(.*?)(</script>)',re.S)

PATTERN=re.compile(r'(<script id="fantasydata" type="application/json">)(.*?)(</script>)',re.S)

def safe_json(data):
    return json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def sync(html,data):
    if data.get('completedThrough',0)<4 or len(data.get('teams',[]))!=10:raise ValueError('Incomplete approved dataset')
    match=PATTERN.search(html)
    if not match:raise ValueError('Missing embedded snapshot in HTML')
    old=json.loads(match.group(2))
    if int(data['completedThrough'])<int(old['completedThrough']):raise ValueError('Refusing backward fallback snapshot')
    for word in ('espn_s2','espn_swid','owner_name','manager_name','session_cookie'):
        if word in json.dumps(data).lower():raise ValueError('Potential sensitive field found in public data')
    updated=html[:match.start(2)]+safe_json(data)+html[match.end(2):]
    metrics=json.loads(DEFINITIONS.read_text(encoding='utf8'))
    m=METRIC_PATTERN.search(updated)
    if not m:raise ValueError('Missing shared metric definitions in HTML')
    return updated[:m.start(2)]+safe_json(metrics)+updated[m.end(2):]

def main():
    a=argparse.ArgumentParser();a.add_argument('--html',default='index.html');a.add_argument('--data',required=True);a.add_argument('--output',required=True);args=a.parse_args()
    original=pathlib.Path(args.html).read_text(encoding='utf8');data=json.loads(pathlib.Path(args.data).read_text(encoding='utf8'))
    updated=sync(original,data);out=pathlib.Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(updated,encoding='utf8')
    print(f'Prepared matching HTML fallback at Week {data["completedThrough"]}; live website untouched.')
if __name__=='__main__':main()
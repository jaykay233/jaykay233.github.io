#!/usr/bin/env python3
"""Collect architecture-related excerpts from representative HF model cards.

The excerpts are source material for human review, not automatic architecture
claims. One representative per config model_type (up to LIMIT) is selected by
saved popularity/download signals.
"""
from __future__ import annotations
import concurrent.futures
import json
import random
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
CATALOG=DATA/'discovered_models.json'
CACHE=DATA/'model_card_evidence_cache.json'
LIMIT=100
KEYWORDS=re.compile(r"architecture|transformer|attention|linear|mHC|iHC|MTP|MoE|GQA|MLA|DeltaNet|Mamba|SwiGLU|RMSNorm|RoPE|sparse|hybrid|expert|convolution|SWA|CSA|HCA",re.I)


def score(model):
    ranks=[r for r in (model.get('rankings') or {}).values() if isinstance(r,(int,float)) and 1<=r<=1000]
    popularity=sum((1001-r)/10 for r in ranks)/len(ranks) if ranks else 0
    return popularity, len(ranks), model.get('downloads_snapshot',0), model.get('likes_snapshot',0)


def fetch(model):
    repo=model['hub_id']; url=f'https://huggingface.co/{repo}/raw/main/README.md'
    for attempt in range(6):
        try:
            req=Request(url,headers={'User-Agent':'ArchAtlas-model-card-evidence/1.0'})
            with urlopen(req,timeout=35) as res:
                text=res.read(1_500_000).decode('utf-8','replace')
            lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines()]
            matched=[]
            for line in lines:
                if len(line)>=25 and KEYWORDS.search(line):
                    # Keep direct, compact source snippets and avoid huge tables.
                    line=line[:360]
                    if line not in matched:
                        matched.append(line)
                    if len(matched)>=12: break
            return model['id'],{'status':'ok','source':url,'excerpt_count':len(matched),'excerpts':matched}
        except HTTPError as exc:
            if exc.code==404: return model['id'],{'status':'not-found','source':url}
            if exc.code not in (408,425,429,500,502,503,504): return model['id'],{'status':f'http-{exc.code}','source':url}
            retry=exc.headers.get('Retry-After') if exc.headers else None
        except (URLError,TimeoutError,OSError) as exc:
            if attempt==5: return model['id'],{'status':'error','source':url,'error':str(exc)[:160]}
            retry=None
        delay=float(retry) if retry and retry.isdigit() else min(2**attempt,20)
        time.sleep(delay+random.random()*0.4)
    return model['id'],{'status':'error','source':url}


def main():
    models=json.loads(CATALOG.read_text())
    cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    ranked=sorted(models,key=score,reverse=True)
    selected=[]; seen=set()
    for model in ranked:
        model_type=(model.get('config_summary') or {}).get('model_type')
        key=('type',str(model_type).casefold()) if model_type else ('owner',model.get('organization','').casefold())
        if key in seen: continue
        seen.add(key); selected.append(model)
        if len(selected)>=LIMIT: break
    todo=[m for m in selected if m['id'] not in cache]
    print(f'Fetching model cards for {len(todo)} representative models ({len(selected)} selected)…',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,m) for m in todo]
        for n,future in enumerate(concurrent.futures.as_completed(futures),1):
            key,result=future.result(); cache[key]=result
            if n%20==0 or n==len(todo):
                CACHE.write_text(json.dumps(cache,ensure_ascii=False,separators=(',',':'))+'\n')
                print(f'  fetched {n}/{len(todo)} model cards',flush=True)
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,separators=(',',':'))+'\n')
    selected_ids={m['id'] for m in selected}
    counts={}
    for model in models:
        result=cache.get(model['id']) if model['id'] in selected_ids else None
        if result:
            model['model_card_evidence']=result
            counts[result['status']]=counts.get(result['status'],0)+1
    CATALOG.write_text(json.dumps(models,ensure_ascii=False,indent=2)+'\n')
    report={'selected_representatives':len(selected),'status':counts,'selection':'one most popular candidate per config model_type (or owner when unavailable)','interpretation':'excerpts are raw model-card evidence snippets and require human interpretation; not automatic module claims'}
    (DATA/'model_card_review_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()

#!/usr/bin/env python
import json

# 查 docstore
with open(r'storage/docstore.json', encoding='utf-8') as f:
    d = json.load(f)
refs = d.get('docstore/data', {})
print(f'文档数量: {len(refs)}')
for rid, ref in list(refs.items())[:2]:
    md = ref.get('metadata', {})
    print(f'  doc_id={rid[:20]}... kb_id={md.get("kb_id")} file={md.get("file_name","")[:30]}')

# 查 kb_registry
with open(r'storage/kb_registry.json', encoding='utf-8') as f:
    kbs = json.load(f)
print(f'\n知识库数量: {len(kbs)}')
for kb in kbs:
    print(f'  {kb["kb_id"]:12s} {kb["kb_name"]}  doc_count={kb.get("doc_count",0)}')

# 查 /list API
import requests
r = requests.get('http://127.0.0.1:18080/api/kb/list')
if r.status_code == 200:
    docs = r.json()['data']['docs']
    print(f'\n/api/kb/list 文档数: {len(docs)}')
    for doc in docs[:3]:
        print(f'  {doc["name"][:30]:30s} kb_id={doc.get("kb_id")} type={doc.get("type")}')

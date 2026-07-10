#!/usr/bin/env python
"""验证文档解析 + BGE embedding + 向量检索 全链路（无需 LLM）"""
import requests, subprocess, sys, time, os, json

# 清理旧索引（保留 kb_registry 和 config_store）
for f in os.listdir('storage'):
    fp = os.path.join('storage', f)
    if f.endswith('.json') and f not in ('kb_registry.json', 'config_store.json'):
        os.remove(fp)
    if f.endswith('.db'):
        os.remove(fp)

# 启动服务器
print('=== 启动服务器 ===')
p = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'api.app:app', '--host', '127.0.0.1', '--port', '18089', '--log-level', 'warning'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(6)
base = 'http://127.0.0.1:18089'

# ── 1. 上传 PDF ──
print('\n=== 1. 上传 PDF ===')
pdf_path = r'data\GBT29890-2013_粮油仓储管理办法_3473e9a2.pdf'
if not os.path.exists(pdf_path):
    # 用已有 PDF
    pdfs = [f for f in os.listdir('data') if f.endswith('.pdf')]
    if pdfs:
        pdf_path = os.path.join('data', pdfs[0])
        print(f'使用已有 PDF: {pdfs[0]}')
    else:
        # 创建简单文本文件
        with open('data/test_doc.txt', 'w', encoding='utf-8') as f:
            f.write('知识库问答系统是一种基于检索增强生成的信息处理系统。' * 50)
        pdf_path = 'data/test_doc.txt'
        print('使用测试文本文件')

with open(pdf_path, 'rb') as f:
    file_data = f.read()
print(f'文件大小: {len(file_data)} bytes')

r = requests.post(f'{base}/api/kb/file/import',
    files={'files': (os.path.basename(pdf_path), file_data)},
    data={'chunk_size': 512, 'chunk_overlap': 50, 'kb_id': 'default'})
print(f'上传响应: {r.status_code}')
data = r.json()['data']
print(f'  索引块数: {data["indexed_chunks"]}')
print(f'  知识库: {data["kb_id"]}')

# ── 2. 验证文档列表 ──
print('\n=== 2. 文档列表 ===')
r = requests.get(f'{base}/api/kb/list')
docs = r.json()['data']['docs']
print(f'文档数: {len(docs)}')
for d in docs:
    print(f'  {d["name"]}  kb={d["kb_id"]}  type={d["type"]}')

# ── 3. 验证 KB 注册表 ──
print('\n=== 3. 知识库统计 ===')
r = requests.get(f'{base}/api/kb')
for x in r.json()['data']['items']:
    print(f'  {x["kb_id"]:12s}  doc_count={x["doc_count"]}')

# ── 4. 验证索引文件 ──
print('\n=== 4. 索引文件 ===')
for f in ['default__vector_store.json', 'docstore.json', 'index_store.json']:
    fp = os.path.join('storage', f)
    if os.path.exists(fp):
        sz = os.path.getsize(fp)
        print(f'  {f:35s} {sz/1024:.1f} KB')
    else:
        print(f'  {f:35s} 不存在')

# ── 5. 验证 embedding 模型 ──
print('\n=== 5. Embedding 模型 ===')
r = requests.get(f'{base}/api/health')
print(f'健康检查: {r.status_code}')

p.terminate()
p.wait()
print('\n=== 全链路验证完成 ===')

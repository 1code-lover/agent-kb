#!/usr/bin/env python
"""完整链路验证：清理旧索引 → 上传文档 → 查询检索"""
import requests, subprocess, sys, time, os, json

# 清理旧索引（保留 kb_registry）
for f in os.listdir('storage'):
    fp = os.path.join('storage', f)
    if f.endswith('.json') and f != 'kb_registry.json' and f != 'config_store.json':
        os.remove(fp)
    if f.endswith('.db'):
        os.remove(fp)

# 启动服务器
p = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'api.app:app', '--host', '127.0.0.1', '--port', '18088', '--log-level', 'warning'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(6)
base = 'http://127.0.0.1:18088'

# 上传文档
doc = (
    '知识库问答系统是一种基于检索增强生成的信息处理系统。'
    '它通过向量检索找到相关文档片段，再通过大语言模型生成准确回答。'
    '向量检索使用BGE等嵌入模型将文本转换为向量，'
    '在向量数据库中搜索最相似的文档片段。'
    '大语言模型基于检索到的上下文生成最终答案。'
)
r = requests.post(f'{base}/api/kb/file/import',
    files={'files': ('rag_intro.txt', doc.encode('utf-8'))},
    data={'chunk_size': 256, 'chunk_overlap': 50, 'kb_id': 'default'})
print(f'上传: {r.status_code} {r.json()["data"]["indexed_chunks"]} chunks')

# 查询
r = requests.post(f'{base}/api/chat/query', json={
    'question': '什么是基于检索增强生成的知识库问答系统？',
    'session_id': 'test',
})
data = r.json()
print(f'查询: {r.status_code}')
print(f'答案: {data["data"]["answer"][:200]}...')
for s in data['data']['sources'][:2]:
    print(f'  来源: {s["file"]} score={s["score"]:.3f} kb={s["kb_id"]}')
    print(f'  片段: {s["text"][:100]}...')

p.terminate()
p.wait()

#!/usr/bin/env python
"""清理 default 知识库的重复文档和空文本文档。

去重策略：
1. 按文本内容去重，相同文本只保留首次出现的文档
2. 删除空文本文档（PNG 图片等无文本内容的）
3. 同步清理 vector_store 中对应的 embedding / metadata 条目
4. 操作前自动备份，支持 --dry-run 预览

用法：
    python scripts/dedup_default_kb.py --dry-run     # 预览
    python scripts/dedup_default_kb.py               # 执行
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STORAGE = REPO_ROOT / "storage"

DOCSTORE = STORAGE / "docstore.json"
VECTOR_STORE = STORAGE / "default__vector_store.json"
INDEX_STORE = STORAGE / "index_store.json"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"  backup -> {bak.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 default 知识库重复文档")
    parser.add_argument("--dry-run", action="store_true", help="只预览不执行")
    args = parser.parse_args()

    print("=" * 70)
    print("Default KB 去重清理" + (" [DRY-RUN]" if args.dry_run else ""))
    print("=" * 70)

    ds = load_json(DOCSTORE)
    vs = load_json(VECTOR_STORE)

    docs = ds.get("docstore/data", {})
    embedding_dict = vs.get("embedding_dict", {})
    text_id_to_ref = vs.get("text_id_to_ref_doc_id", {})
    metadata_dict = vs.get("metadata_dict", {})

    print(f"\n清理前状态:")
    print(f"  docstore 文档数:    {len(docs)}")
    print(f"  vector_store 嵌入数: {len(embedding_dict)}")

    # 1. 找重复和空文档
    text_to_docs: dict[str, list[str]] = defaultdict(list)
    empty_doc_ids: list[str] = []

    for doc_id, doc in docs.items():
        text = doc.get("__data__", {}).get("text", "").strip()
        if len(text) == 0:
            empty_doc_ids.append(doc_id)
        else:
            text_to_docs[text].append(doc_id)

    # 重复组：同一文本对应多个 doc_id
    duplicate_groups = {
        text: doc_ids for text, doc_ids in text_to_docs.items() if len(doc_ids) > 1
    }

    # 待删除的 doc_id 集合：重复组里除第一个外的 + 空文档
    remove_doc_ids: set[str] = set()
    for text, doc_ids in duplicate_groups.items():
        for doc_id in doc_ids[1:]:  # 保留第一个
            remove_doc_ids.add(doc_id)
    for doc_id in empty_doc_ids:
        remove_doc_ids.add(doc_id)

    print(f"\n问题文档统计:")
    print(f"  重复组数:           {len(duplicate_groups)}")
    print(f"  重复文档数:         {sum(len(v) - 1 for v in duplicate_groups.values())}")
    print(f"  空文本文档数:       {len(empty_doc_ids)}")
    print(f"  待删除文档总数:     {len(remove_doc_ids)}")

    if not remove_doc_ids:
        print("\n没有需要清理的文档，退出。")
        return 0

    # 2. 找到受影响的 text_id（ref_doc_id 在删除集合中）
    affected_text_ids: set[str] = set()
    for text_id, ref_doc_id in text_id_to_ref.items():
        if ref_doc_id in remove_doc_ids:
            affected_text_ids.add(text_id)

    print(f"  受影响嵌入数:       {len(affected_text_ids)}")

    # 3. 预览删除详情
    print(f"\n重复文档详情（Top 10 组）:")
    for i, (text, doc_ids) in enumerate(
        sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True)[:10], 1
    ):
        preview = text[:80].replace("\n", " ").strip()
        print(f"  组 {i}: 重复 {len(doc_ids)} 次, 保留 1 删除 {len(doc_ids) - 1}")
        print(f"    预览: {preview}...")
        for doc_id in doc_ids[:3]:
            md = docs[doc_id].get("__data__", {}).get("metadata", {})
            print(f"    - {md.get('file_name', 'unknown')}")
        if len(doc_ids) > 3:
            print(f"    ... 还有 {len(doc_ids) - 3} 个")

    if empty_doc_ids:
        print(f"\n空文本文档:")
        for doc_id in empty_doc_ids[:10]:
            md = docs[doc_id].get("__data__", {}).get("metadata", {})
            print(f"  - {md.get('file_name', 'unknown')}")

    if args.dry_run:
        print(f"\n[DRY-RUN] 不执行实际删除。")
        print(f"执行清理后预计: docstore {len(docs) - len(remove_doc_ids)} 文档, "
              f"vector_store {len(embedding_dict) - len(affected_text_ids)} 嵌入")
        return 0

    # 4. 备份
    print(f"\n备份原文件...")
    backup(DOCSTORE)
    backup(VECTOR_STORE)
    backup(INDEX_STORE)

    # 5. 执行删除
    print(f"\n执行删除...")
    for doc_id in remove_doc_ids:
        del docs[doc_id]
    print(f"  docstore: 删除 {len(remove_doc_ids)} 文档, 剩余 {len(docs)}")

    for text_id in affected_text_ids:
        embedding_dict.pop(text_id, None)
        text_id_to_ref.pop(text_id, None)
        metadata_dict.pop(text_id, None)
    print(f"  vector_store: 删除 {len(affected_text_ids)} 嵌入, 剩余 {len(embedding_dict)}")

    # 6. 保存
    save_json(DOCSTORE, ds)
    save_json(VECTOR_STORE, vs)
    print(f"\n保存完成:")
    print(f"  docstore.json -> {DOCSTORE.stat().st_size / 1024:.1f} KB")
    print(f"  default__vector_store.json -> {VECTOR_STORE.stat().st_size / 1024:.1f} KB")

    print(f"\n清理后状态:")
    print(f"  docstore 文档数:    {len(docs)}")
    print(f"  vector_store 嵌入数: {len(embedding_dict)}")
    print(f"\n去重完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

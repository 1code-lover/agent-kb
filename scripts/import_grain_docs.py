"""
批量导入 grain-knowledge-base docs/01-07+99 目录下的全部文档。
跳过 98-duplicates-to-review 和 README.md。
直接调用 kb_service.import_files，不依赖 HTTP 服务。
"""
import io
import sys
import time
import mimetypes
from pathlib import Path

# 确保项目根在 sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 导入前先初始化运行时（加载 config/env）
import config  # noqa: F401
from api.services import kb_service

KB_ID = "grain-knowledge-base"
DOCS_DIR = ROOT / "data" / "grain-knowledge-base" / "docs"
CHUNK_SIZE = 2048
CHUNK_OVERLAP = 512
BATCH_SIZE = 5  # 每批文件数，避免单次占用太多内存

# 要导入的子目录（按顺序）
INCLUDE_DIRS = [
    "01-standards-regulations",
    "02-storage-operations",
    "03-monitoring-analysis",
    "04-regulation-platform",
    "05-patents",
    "06-research-reports",
    "07-templates-samples",
    "99-other",
]

SKIP_NAMES = {"README.md", "readme.md"}


class FakeUploadFile:
    """最小化模拟 FastAPI UploadFile，满足 kb_service._prepare_pending_import_file 的访问需求。"""

    def __init__(self, path: Path, relative_path: str):
        self.filename = path.name
        self.content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._bytes = path.read_bytes()
        self.file = io.BytesIO(self._bytes)
        self._relative_path = relative_path

    def __repr__(self):
        return f"<FakeUploadFile {self.filename}>"


def collect_files() -> list[tuple[Path, str]]:
    """收集所有要导入的文件，返回 (绝对路径, 相对于 kb data 目录的路径) 列表。"""
    results = []
    for dir_name in INCLUDE_DIRS:
        sub = DOCS_DIR / dir_name
        if not sub.exists():
            print(f"[WARN] 目录不存在，跳过: {sub}")
            continue
        for f in sorted(sub.iterdir()):
            if not f.is_file():
                continue
            if f.name in SKIP_NAMES:
                continue
            # relative_path 相对于 kb data dir（grain-knowledge-base/），
            # 传给 preserve_tree 模式，保留 docs/subdir/filename 结构
            rel = f"docs/{dir_name}/{f.name}"
            results.append((f, rel))
    return results


def batched(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main():
    files_to_import = collect_files()
    total = len(files_to_import)
    print(f"待导入文件总数: {total}")
    print(f"KB: {KB_ID}  chunk_size={CHUNK_SIZE}  chunk_overlap={CHUNK_OVERLAP}")
    print("-" * 60)

    imported = 0
    failed = 0
    skipped = 0

    for batch_idx, batch in enumerate(batched(files_to_import, BATCH_SIZE)):
        fake_files = []
        rel_paths = []
        for fpath, rel in batch:
            size_mb = fpath.stat().st_size / 1024 / 1024
            print(f"  加载: {rel}  ({size_mb:.1f} MB)")
            fake_files.append(FakeUploadFile(fpath, rel))
            rel_paths.append(rel)

        t0 = time.perf_counter()
        try:
            result = kb_service.import_files(
                fake_files,
                CHUNK_SIZE,
                CHUNK_OVERLAP,
                kb_id=KB_ID,
                relative_paths=rel_paths,
                import_mode="preserve_tree",
            )
        except Exception as e:
            print(f"  [ERROR] 批次 {batch_idx + 1} 整体失败: {e}")
            failed += len(batch)
            continue

        elapsed = time.perf_counter() - t0
        file_results = result.get("file_results", [])
        # 优先用顶层汇总计数
        batch_ok = result.get("success_count", 0)
        batch_fail = result.get("failed_count", 0)
        batch_empty = result.get("empty_count", 0)

        for fr in file_results:
            status = fr.get("status", "?")
            fname = fr.get("name") or fr.get("filename") or fr.get("file_name", "?")
            chunks = fr.get("indexed_chunks", 0)
            msg = fr.get("message", "")
            if status == "success":
                print(f"  [OK]   {fname}  ({chunks} chunks)")
            elif status in ("skipped", "already_exists", "empty"):
                print(f"  [SKIP] {fname}  {msg}")
            else:
                print(f"  [FAIL] {fname}  {msg or status}")

        imported += batch_ok
        failed += batch_fail
        skipped += batch_empty

        print(f"  批次 {batch_idx + 1} 耗时 {elapsed:.1f}s")
        print()

    print("=" * 60)
    print(f"完成: 成功={imported}  跳过={skipped}  失败={failed}  总计={total}")


if __name__ == "__main__":
    main()

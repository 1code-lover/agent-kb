#!/usr/bin/env python3
"""
注释规范检查脚本。

职责：
- 检查 Python 文件是否包含模块 docstring；
- 检查 Python 文件中的函数是否包含 docstring；
- 检查 JS/JSX 文件是否包含文件头注释；
- 检查 JS/JSX 中命名函数是否存在紧邻的注释块。

使用方式：
- python scripts/check_commenting.py
- python scripts/check_commenting.py server webapp/src
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


DEFAULT_TARGETS = ("server", "webapp/src")
PY_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".jsx"}
SKIP_DIR_NAMES = {"node_modules", ".git", ".venv", "venv", "__pycache__"}


def iter_source_files(targets: Iterable[Path]) -> Iterable[Path]:
    """遍历目标目录下源码文件。"""
    for target in targets:
        if not target.exists():
            continue
        if target.is_file():
            if target.suffix in PY_EXTENSIONS | JS_EXTENSIONS:
                yield target
            continue

        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix in PY_EXTENSIONS | JS_EXTENSIONS:
                yield path


def check_python_file(path: Path) -> List[str]:
    """检查 Python 文件的模块/函数注释规范。"""
    issues: List[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"{path}: 语法错误，无法检查注释 - {exc}"]

    if ast.get_docstring(tree) is None:
        issues.append(f"{path}: 缺少模块级 docstring")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.get_docstring(node) is None:
                issues.append(f"{path}: 函数 `{node.name}` 缺少 docstring")
    return issues


def _has_js_header_comment(lines: List[str]) -> bool:
    """检查 JS 文件首个非空行是否为注释。"""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith("/**") or stripped.startswith("//")
    return False


def _function_candidates(lines: List[str]) -> List[Tuple[int, str]]:
    """提取需要检查注释的 JS 函数定义位置。"""
    candidates: List[Tuple[int, str]] = []
    patterns = (
        re.compile(r"^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)\s*\("),
        re.compile(r"^\s*export\s+function\s+([A-Za-z0-9_]+)\s*\("),
        re.compile(r"^\s*function\s+([A-Za-z0-9_]+)\s*\("),
        re.compile(r"^\s*async\s+function\s+([A-Za-z0-9_]+)\s*\("),
    )
    for idx, line in enumerate(lines):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                candidates.append((idx, match.group(1)))
                break
    return candidates


def _has_nearby_js_doc(lines: List[str], index: int) -> bool:
    """检查函数定义前方是否紧邻注释块。"""
    # 允许函数注释包含输入/输出等多行说明，因此放宽回溯窗口。
    start = max(0, index - 16)
    block = "\n".join(lines[start:index])
    return "/**" in block or "//" in block


def check_js_file(path: Path) -> List[str]:
    """检查 JS/JSX 文件的文件头与函数注释规范。"""
    issues: List[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    if not _has_js_header_comment(lines):
        issues.append(f"{path}: 缺少文件头注释")

    for idx, func_name in _function_candidates(lines):
        if not _has_nearby_js_doc(lines, idx):
            issues.append(f"{path}: 函数 `{func_name}` 缺少紧邻注释")
    return issues


def run_checks(target_paths: Iterable[str]) -> int:
    """执行所有注释规范检查并返回退出码。"""
    root = Path.cwd()
    targets = [root / item for item in target_paths]

    issues: List[str] = []
    for file_path in iter_source_files(targets):
        if file_path.suffix in PY_EXTENSIONS:
            issues.extend(check_python_file(file_path))
        elif file_path.suffix in JS_EXTENSIONS:
            issues.extend(check_js_file(file_path))

    if issues:
        print("注释规范检查未通过：")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("注释规范检查通过。")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or list(DEFAULT_TARGETS)
    raise SystemExit(run_checks(args))

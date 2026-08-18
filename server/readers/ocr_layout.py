"""OCR 版面块与连续表格合并。

该模块只处理纯数据结构，不依赖 OCR 引擎，便于稳定测试同页与跨页规则。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _cell_text(cell: Any) -> str:
    """读取单元格文本。"""
    if isinstance(cell, dict):
        return str(cell.get("text") or "").strip()
    return str(cell or "").strip()


def _row_texts(row: list[Any]) -> list[str]:
    """把 OCR 行转换为纯文本单元格。"""
    return [_cell_text(cell) for cell in row]


def _column_centers(rows: list[list[Any]]) -> list[float]:
    """计算每列的平均 x 中心。"""
    if not rows:
        return []
    column_count = len(rows[0])
    centers: list[float] = []
    for index in range(column_count):
        values = []
        for row in rows:
            if index >= len(row) or not isinstance(row[index], dict):
                continue
            value = row[index].get("x_center")
            if value is not None:
                values.append(float(value))
        centers.append(sum(values) / len(values) if values else float(index * 100))
    return centers


def _compatible_tables(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """判断两个表格块的列数和列中心是否可视为同一结构。"""
    left_centers = [float(value) for value in left.get("column_centers") or []]
    right_centers = [float(value) for value in right.get("column_centers") or []]
    if not left_centers or len(left_centers) != len(right_centers):
        return False
    if len(left_centers) == 1:
        return abs(left_centers[0] - right_centers[0]) <= 20.0
    span = max(max(left_centers) - min(left_centers), max(right_centers) - min(right_centers), 1.0)
    tolerance = max(16.0, span * 0.12)
    return all(abs(left - right) <= tolerance for left, right in zip(left_centers, right_centers))


def build_layout_blocks(rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """把 OCR 几何行分成表格块与普通段落块。"""
    blocks: list[dict[str, Any]] = []
    pending_table_rows: list[list[dict[str, Any]]] = []

    def flush_table_rows() -> None:
        """输出连续候选行；不足两行时按普通文本处理。"""
        nonlocal pending_table_rows
        if not pending_table_rows:
            return
        if len(pending_table_rows) >= 2:
            blocks.append(
                {
                    "type": "table",
                    "rows": [_row_texts(row) for row in pending_table_rows],
                    "column_centers": _column_centers(pending_table_rows),
                }
            )
        else:
            blocks.append({"type": "paragraph", "text": " ".join(_row_texts(pending_table_rows[0]))})
        pending_table_rows = []

    for row in rows:
        if len(row) >= 2:
            if pending_table_rows and len(row) != len(pending_table_rows[-1]):
                flush_table_rows()
            pending_table_rows.append(row)
            continue
        flush_table_rows()
        text = " ".join(_row_texts(row)).strip()
        if text:
            if blocks and blocks[-1].get("type") == "paragraph":
                blocks[-1]["text"] = f"{blocks[-1]['text']}\n{text}"
            else:
                blocks.append({"type": "paragraph", "text": text})
    flush_table_rows()
    return blocks


def _escape_cell(text: str) -> str:
    """转义 Markdown 表格单元格。"""
    return text.replace("|", r"\|").replace("\n", " ").strip()


def render_layout_blocks(blocks: list[dict[str, Any]]) -> str:
    """将布局块渲染为文本/Markdown。"""
    rendered: list[str] = []
    for block in blocks:
        if block.get("type") != "table":
            text = str(block.get("text") or "").strip()
            if text:
                rendered.append(text)
            continue
        rows = [[_escape_cell(_cell_text(cell)) for cell in row] for row in block.get("rows") or []]
        if not rows:
            continue
        lines = ["| " + " | ".join(row) + " |" for row in rows]
        if not block.get("continued_from_previous"):
            lines.insert(1, "| " + " | ".join("---" for _ in rows[0]) + " |")
        rendered.append("\n".join(lines))
    return "\n\n".join(rendered).strip()


def merge_continuous_table_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """合并同页相邻表格与页尾到下一页页首的连续表格。"""
    normalized = deepcopy(pages)
    original_table_count = sum(
        1 for page in normalized for block in page.get("blocks") or [] if block.get("type") == "table"
    )
    merged_count = 0
    continued_pages = 0
    removed_headers = 0

    for page in normalized:
        merged_blocks: list[dict[str, Any]] = []
        for block in page.get("blocks") or []:
            if (
                merged_blocks
                and block.get("type") == "table"
                and merged_blocks[-1].get("type") == "table"
                and _compatible_tables(merged_blocks[-1], block)
            ):
                merged_blocks[-1].setdefault("rows", []).extend(block.get("rows") or [])
                merged_count += 1
            else:
                merged_blocks.append(block)
        page["blocks"] = merged_blocks

    for index in range(1, len(normalized)):
        previous_blocks = normalized[index - 1].get("blocks") or []
        current_blocks = normalized[index].get("blocks") or []
        if not previous_blocks or not current_blocks:
            continue
        previous = previous_blocks[-1]
        current = current_blocks[0]
        if previous.get("type") != "table" or current.get("type") != "table":
            continue
        if not _compatible_tables(previous, current):
            continue
        current["continued_from_previous"] = True
        previous_rows = previous.get("rows") or []
        current_rows = current.get("rows") or []
        if previous_rows and current_rows and _row_texts(previous_rows[0]) == _row_texts(current_rows[0]):
            current["rows"] = current_rows[1:]
            removed_headers += 1
        continued_pages += 1
        merged_count += 1

    page_texts = []
    for page in normalized:
        body = render_layout_blocks(page.get("blocks") or [])
        if body:
            page_texts.append(f"[Page {int(page.get('page_number') or len(page_texts) + 1)}]\n{body}")

    remaining_tables = [
        block for page in normalized for block in page.get("blocks") or [] if block.get("type") == "table"
    ]
    table_rows = sum(len(block.get("rows") or []) for block in remaining_tables)
    table_columns = max((len((block.get("rows") or [[]])[0]) for block in remaining_tables if block.get("rows")), default=0)
    has_paragraph = any(
        block.get("type") == "paragraph" for page in normalized for block in page.get("blocks") or []
    )
    layout_mode = "mixed" if remaining_tables and has_paragraph else ("table" if remaining_tables else "geometry_lines")
    return {
        "text": "\n\n".join(page_texts),
        "pages": normalized,
        "diagnostics": {
            "layout_mode": layout_mode,
            "table_detected": bool(remaining_tables),
            "table_row_count": table_rows,
            "table_column_count": table_columns,
            "table_block_count": original_table_count,
            "merged_block_count": merged_count,
            "continued_page_count": continued_pages,
            "removed_repeated_header_count": removed_headers,
        },
    }


__all__ = ["build_layout_blocks", "merge_continuous_table_pages", "render_layout_blocks"]

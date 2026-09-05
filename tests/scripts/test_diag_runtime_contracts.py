"""诊断脚本运行时端口/base URL 合同测试。"""

from __future__ import annotations

import pytest

import scripts.diag_cross_domain_kb_eval as cross_eval
import scripts.diag_desktop_model_workflow as desktop_diag
import scripts.diag_extensionless_text_roundtrip as exttext_diag
import scripts.diag_image_ocr_roundtrip as image_diag
import scripts.diag_mixed_batch_roundtrip as mixed_diag
import scripts.diag_pdf_scan_roundtrip as pdf_scan_diag
import scripts.diag_pdf_text_roundtrip as pdf_text_diag
import scripts.diag_utf8_import_roundtrip as utf8_diag
import scripts.import_grain_kb_batches as grain_import
import scripts.run_grain_qa_eval as grain_eval


@pytest.mark.parametrize(
    ("label", "reader"),
    [
        ("cross-domain", lambda: cross_eval._build_arg_parser().parse_args([]).api_base),
        ("desktop-model", lambda: desktop_diag._parse_args([]).base_url),
        ("mixed-batch", lambda: mixed_diag._parse_args([]).base_url),
        ("utf8-import", lambda: utf8_diag._parse_args([]).base_url),
        ("image-ocr", lambda: image_diag._parse_args([]).base_url),
        ("pdf-text", lambda: pdf_text_diag._parse_args([]).base_url),
        ("pdf-scan", lambda: pdf_scan_diag._parse_args([]).base_url),
        ("extensionless", lambda: exttext_diag._parse_args([]).base_url),
        ("grain-import", lambda: grain_import.parse_args([]).api_base_url),
        ("grain-eval", lambda: grain_eval._build_arg_parser().parse_args([]).api_base),
    ],
)
def test_diag_scripts_prefer_kb_api_base_url_env(monkeypatch: pytest.MonkeyPatch, label: str, reader) -> None:
    """诊断脚本默认地址应优先读取 KB_API_BASE_URL。"""
    monkeypatch.setenv("KB_API_BASE_URL", "https://kb.example.com:18443/")
    monkeypatch.setenv("KB_API_PORT", "19090")

    assert reader() == "https://kb.example.com:18443", label


@pytest.mark.parametrize(
    ("label", "reader"),
    [
        ("cross-domain", lambda: cross_eval._build_arg_parser().parse_args([]).api_base),
        ("desktop-model", lambda: desktop_diag._parse_args([]).base_url),
        ("mixed-batch", lambda: mixed_diag._parse_args([]).base_url),
        ("utf8-import", lambda: utf8_diag._parse_args([]).base_url),
        ("image-ocr", lambda: image_diag._parse_args([]).base_url),
        ("pdf-text", lambda: pdf_text_diag._parse_args([]).base_url),
        ("pdf-scan", lambda: pdf_scan_diag._parse_args([]).base_url),
        ("extensionless", lambda: exttext_diag._parse_args([]).base_url),
        ("grain-import", lambda: grain_import.parse_args([]).api_base_url),
        ("grain-eval", lambda: grain_eval._build_arg_parser().parse_args([]).api_base),
    ],
)
def test_diag_scripts_fall_back_to_kb_api_port(monkeypatch: pytest.MonkeyPatch, label: str, reader) -> None:
    """未显式配置 base URL 时，诊断脚本应回退到统一端口契约。"""
    for key in (
        "KB_API_BASE_URL",
        "NORTHAGENT_API_BASE_URL",
        "THINKRAG_API_BASE_URL",
        "FOXGLOVE_API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KB_API_PORT", "19090")

    assert reader() == "http://127.0.0.1:19090", label


@pytest.mark.parametrize(
    ("label", "source_reader"),
    [
        ("cross-domain", lambda: cross_eval._build_arg_parser().format_help()),
        ("desktop-model", lambda: desktop_diag._parse_args.__code__.co_consts),
        ("mixed-batch", lambda: mixed_diag._parse_args.__code__.co_consts),
        ("utf8-import", lambda: utf8_diag._parse_args.__code__.co_consts),
        ("image-ocr", lambda: image_diag._parse_args.__code__.co_consts),
        ("pdf-text", lambda: pdf_text_diag._parse_args.__code__.co_consts),
        ("pdf-scan", lambda: pdf_scan_diag._parse_args.__code__.co_consts),
        ("extensionless", lambda: exttext_diag._parse_args.__code__.co_consts),
        ("grain-import", lambda: grain_import.parse_args.__code__.co_consts),
        ("grain-eval", lambda: grain_eval._build_arg_parser().format_help()),
    ],
)
def test_diag_scripts_document_kb_api_contract_in_cli_help_or_parser_source(label: str, source_reader) -> None:
    """CLI 帮助文案/解析器源码应明确 KB_API_BASE_URL / KB_API_PORT 契约。"""
    blob = str(source_reader())

    assert "KB_API_BASE_URL" in blob, label
    assert "KB_API_PORT" in blob, label
    assert "18080" in blob, label

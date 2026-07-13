# PDF OCR 解析与质量评估进展

## 背景

当前知识库文件导入需要支持扫描版 PDF。原有 `SimpleDirectoryReader` 对带文字层 PDF 可工作，但对扫描件或文字层质量较差的国标 PDF 解析结果不足，影响后续切分、向量化和 RAG 检索。

## 当前实现

### 解析链路

- `server/index.py` 在批量目录导入和上传文件导入时统一走 `_load_documents()`。
- 非 PDF 文件继续交给 `SimpleDirectoryReader`。
- PDF 文件交给 `server/readers/pdf_ocr.py` 中的 `PDFOCRReader`：
  1. 先使用 PyMuPDF 读取 PDF 文字层。
  2. 如果文字为空、过短、中文占比过低或疑似水印碎片，则判定为无有效文字层。
  3. 无有效文字层时回退 PaddleOCR，逐页渲染图片并识别文本。
  4. 将整本 PDF 文本合并为一个 LlamaIndex `Document`，保留 `file_name` 和 `file_path` 元数据。

### 依赖

`requirements.txt` 已新增：

- `pymupdf==1.28.0`
- `paddleocr==3.7.0`
- `paddlepaddle==3.2.2`

当前 Windows 本地验证使用系统 Python 3.12 环境运行；`.venv` 中尚未安装 PaddleOCR 相关依赖。

## 测试覆盖

### 功能正确性测试

文件：`tests/readers/test_pdf_ocr.py`

覆盖：

- 带有效文字层 PDF：直接使用 PyMuPDF，不触发 OCR。
- 空白 PDF：返回空文档列表，不抛异常。
- 真实扫描件 PDF：使用 `data/rice_standard_3885c3dc.pdf` 跑完整 PaddleOCR，并校验关键词召回。

常规快测命令：

```bash
python -m pytest tests/readers/test_pdf_ocr.py -q -m "not slow"
```

当前结果：

```text
2 passed, 1 deselected in 4.27s
```

真实 OCR 慢测命令：

```bash
python -m pytest tests/readers/test_pdf_ocr.py::test_scanned_pdf_falls_back_to_ocr_and_recalls_key_terms -q -s
```

当前结果：

```text
OCR 第 1/6 页 → 130 字
OCR 第 2/6 页 → 298 字
OCR 第 3/6 页 → 806 字
OCR 第 4/6 页 → 770 字
OCR 第 5/6 页 → 757 字
OCR 第 6/6 页 → 726 字
1 passed, 2 warnings in 725.37s (0:12:05)
```

### 解析质量评估

文件：`scripts/pdf_ocr_quality.py`

能力：

- 对 OCR 后文本按关键词列表统计召回情况。
- 输出命中词、未命中词、命中数、总词数、召回率、文本长度和文本预览。
- 支持将报告输出为 JSON 文件。

质量评估逻辑测试：`tests/readers/test_pdf_ocr_quality.py`

```bash
python -m pytest tests/readers/test_pdf_ocr_quality.py -q
```

当前结果：

```text
2 passed in 0.19s
```

真实样本评估命令：

```bash
python scripts/pdf_ocr_quality.py data/rice_standard_3885c3dc.pdf \
  --keywords 稻谷 出糙率 整精米率 水分 杂质 黄粒米 色泽 气味 \
  --output test_output/pdf_ocr_quality_rice_standard.json
```

当前评估结果：

```json
{
  "document_count": 1,
  "text_length": 3497,
  "keyword_recall": {
    "total": 8,
    "hit_count": 8,
    "miss_count": 0,
    "recall": 1.0
  }
}
```

## 使用建议

日常开发默认跑快测：

```bash
python -m pytest tests/readers/test_pdf_ocr.py tests/readers/test_pdf_ocr_quality.py -q -m "not slow"
```

需要验证真实 OCR 时单独跑慢测：

```bash
python -m pytest tests/readers/test_pdf_ocr.py -q -m slow -s
```

需要评估某个 PDF 的解析质量时：

```bash
python scripts/pdf_ocr_quality.py data/xxx.pdf \
  --keywords 关键词1 关键词2 关键词3 \
  --output test_output/xxx_quality.json
```

## 当前限制

- PaddleOCR 在 CPU 上跑整本扫描件耗时较长，当前 6 页样本约 12 分钟。
- 质量评估目前采用关键词召回率，适合判断 RAG 入库前的关键信息是否可检索；暂未覆盖字符准确率 CER、表格结构还原和版面顺序质量。
- PaddleOCR 日志在 Windows 终端中可能出现编码显示问题，但输出 JSON 文件内容为 UTF-8，可正常读取。

## 后续方向

- 为真实业务 PDF 建立关键词基准集，持续比较 OCR 版本或参数调整前后的召回率。
- 若需要缩短回归时间，可新增页数限制参数，将全量慢测和首页烟测分开。
- 后续如需要表格字段级质量评估，可扩展为“字段名 + 期望值”的召回检查。

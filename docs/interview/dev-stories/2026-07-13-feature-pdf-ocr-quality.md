# PDF 扫描件 OCR 解析与质量评估

## 基本信息
- 类型：feature
- 日期：2026-07-13
- 相关模块：知识库文件导入、PDF 读取器、OCR 质量评估
- 相关文件：`server/readers/pdf_ocr.py`、`server/index.py`、`scripts/pdf_ocr_quality.py`、`tests/readers/test_pdf_ocr.py`、`tests/readers/test_pdf_ocr_quality.py`、`docs/20260713-pdf-ocr-quality/20260713-pdf-ocr-quality-status.md`

## 需求背景

知识库需要导入国标类 PDF，但当前样本多数是扫描件或文字层质量很差的 PDF。只依赖 LlamaIndex 默认读取器时，文档可能只得到少量页眉、水印或乱码文本，后续切分、向量化和 RAG 检索都会受影响。因此需要在 PDF 入库阶段增加 OCR 回退能力，并提供一个能量化解析质量的验证方法。

## 设计与实现方案

我在 `server/readers/pdf_ocr.py` 中新增 `PDFOCRReader`，读取 PDF 时先用 PyMuPDF 提取文字层，再用中文占比、总字数、去重行数等启发式规则判断文本是否有效。如果文本为空、过短或疑似乱码/水印碎片，就把页面渲染成图片交给 PaddleOCR 逐页识别，最后合并为一个 LlamaIndex `Document`。

在 `server/index.py` 中新增 `_load_documents()`，让目录导入和上传文件导入都统一进入这条读取链路：PDF 走 `PDFOCRReader`，非 PDF 继续走 `SimpleDirectoryReader`。这样不会影响 DOCX/TXT 等已有格式，同时让扫描件 PDF 能进入后续的 ingestion pipeline。

为了避免只验证“能跑”，我又加了 `scripts/pdf_ocr_quality.py`，用关键词召回率评估 OCR 结果质量。脚本会输出文本长度、命中词、漏召回词和召回率，并支持写入 JSON 报告。

## 为什么选这个方案

优先 PyMuPDF、失败再 OCR，是为了兼顾速度和质量。带有效文字层的 PDF 直接读取成本很低；扫描件才启动 PaddleOCR，避免每个 PDF 都走重模型。把逻辑封装成独立 reader，而不是散落在上传接口里，也方便单测和后续替换 OCR 引擎。

质量评估选择关键词召回率，是因为当前目标是 RAG 入库可检索，不是排版还原或全文校对。对国标、制度、合同这类文件，关键术语和字段能不能被召回，比单纯字符准确率更贴近检索效果，而且标注成本低，可以快速扩展样本集。

## 其他方案与为什么没选

- 直接全量 PaddleOCR：实现简单，但对带文字层 PDF 也很慢，CPU 环境下不可接受。
- 只依赖 PyMuPDF 或默认 reader：无法覆盖扫描件，当前 `data/` 下真实国标样本已验证文字层不足。
- 直接做 CER 字符准确率：更精细，但需要人工标注标准答案，当前阶段成本过高，先用关键词召回做入库前质量门槛。

## 风险与权衡

PaddleOCR 在 CPU 上较慢，真实 6 页扫描件样本一次完整识别约 12 分钟，因此测试中把真实 OCR 用例标记为 `slow`，日常默认只跑非 slow 快测。OCR 输出质量也可能受图片分辨率、表格结构和版面顺序影响，目前只保证关键信息可召回，后续如果要做表格字段级检验，需要继续扩展质量评估脚本。

## 验证与结果

快测：

```bash
python -m pytest tests/readers/test_pdf_ocr.py tests/readers/test_pdf_ocr_quality.py -q -m "not slow"
```

结果：

```text
4 passed, 1 deselected in 4.32s
```

真实 OCR 慢测：

```bash
python -m pytest tests/readers/test_pdf_ocr.py::test_scanned_pdf_falls_back_to_ocr_and_recalls_key_terms -q -s
```

结果：

```text
OCR 第 1/6 页 → 130 字
OCR 第 2/6 页 → 298 字
OCR 第 3/6 页 → 806 字
OCR 第 4/6 页 → 770 字
OCR 第 5/6 页 → 757 字
OCR 第 6/6 页 → 726 字
1 passed, 2 warnings in 725.37s (0:12:05)
```

质量评估：

```bash
python scripts/pdf_ocr_quality.py data/rice_standard_3885c3dc.pdf \
  --keywords 稻谷 出糙率 整精米率 水分 杂质 黄粒米 色泽 气味 \
  --output test_output/pdf_ocr_quality_rice_standard.json
```

结果：8 个关键词全部命中，文本长度 3497，召回率 1.0。

## 面试表达版本

我在知识库导入链路里补了扫描件 PDF 的 OCR 回退能力。实现上不是所有 PDF 都直接 OCR，而是先用 PyMuPDF 提取文字层，再用中文占比和字数等规则判断是否有效；无效时才走 PaddleOCR，这样兼顾速度和兼容性。为了验证不只是“能跑”，我加了关键词召回评估脚本，用真实国标扫描件检查核心术语是否能被识别出来。最终 6 页样本能完整 OCR 入库，8 个业务关键词全部命中；同时把真实 OCR 测试标成 slow，避免日常回归被 12 分钟的 CPU OCR 拖慢。

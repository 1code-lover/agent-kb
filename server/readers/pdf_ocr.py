"""
PDF 文本提取器：优先 PyMuPDF 提取文字，无文字或文字太少时自动切 PaddleOCR。
"""
import os
import re
import numpy as np
from llama_index.core.readers.base import BasePydanticReader
from llama_index.core.schema import Document


class PDFOCRReader(BasePydanticReader):
    """PDF 读取器，支持扫描件 OCR 回退。"""

    is_remote: bool = False
    lang: str = 'ch'
    use_textline_orientation: bool = True
    ocr_kw: dict = {}

    def __init__(self, lang='ch', use_textline_orientation=True, **ocr_kw):
        super().__init__(lang=lang, use_textline_orientation=use_textline_orientation, ocr_kw=ocr_kw)
        self._ocr = None

    @classmethod
    def class_name(cls) -> str:
        return "PDFOCRReader"

    def _lazy_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang=self.lang,
                use_textline_orientation=self.use_textline_orientation,
                **self.ocr_kw,
            )
        return self._ocr

    @staticmethod
    def _text_is_garbled(text: str) -> bool:
        """判断 PyMuPDF 提取的文本是否有效（兼容中英文，避免短正文被误判为乱码）。"""
        text = text.strip()
        if not text:
            return True

        visible_chars = [char for char in text if not char.isspace()]
        visible_len = len(visible_chars)
        if visible_len == 0:
            return True

        cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        latin_chars = len(re.findall(r'[A-Za-z]', text))
        digit_chars = len(re.findall(r'\d', text))
        readable_ratio = (cjk_chars + latin_chars + digit_chars) / visible_len
        if readable_ratio < 0.3:
            return True

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        unique_lines = list(dict.fromkeys(lines))
        longest_line_length = max((len(line) for line in unique_lines), default=0)

        # 仅有极短碎片且行数很少时，仍视为无效文字层，避免页码/水印误判为正文。
        if len(unique_lines) <= 2 and visible_len < 30 and longest_line_length < 20:
            return True

        return False

    def _try_pymupdf(self, file_path):
        try:
            import fitz
            doc = fitz.open(file_path)
            num_pages = len(doc)
            text = ''
            for page in doc:
                text += page.get_text()
            doc.close()
            if text and text.strip() and not self._text_is_garbled(text):
                return text, True
        except Exception:
            pass
        return '', False

    def _ocr_pdf(self, file_path):
        try:
            import fitz
        except ImportError:
            raise ImportError("需要 PyMuPDF (fitz) 打开 PDF 文件")

        ocr = self._lazy_ocr()
        doc = fitz.open(file_path)
        pages_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if img_array.shape[2] == 4:
                img_array = img_array[:, :, :3]

            result = ocr.predict(img_array)
            page_text = ''
            for ocr_res in result:
                j = ocr_res.json
                texts = j.get('res', {}).get('rec_texts', [])
                page_text = '\n'.join(t.strip() for t in texts if t.strip())
            pages_text.append(page_text.strip())
            print(f'  OCR 第 {page_num + 1}/{len(doc)} 页 → {len(page_text)} 字')
        doc.close()
        return '\n\n'.join(pages_text)

    def load_data(self, file_path, **kwargs):
        text, ok = self._try_pymupdf(file_path)
        if ok:
            print(f'  PyMuPDF 提取 {os.path.basename(file_path)} → {len(text)} 字')
        else:
            print(f'  PDF 无有效文字层，启动 PaddleOCR: {os.path.basename(file_path)}')
            text = self._ocr_pdf(file_path)

        if not text.strip():
            return []

        doc = Document(
            text=text,
            metadata={
                'file_name': os.path.basename(file_path),
                'file_path': file_path,
            },
        )
        return [doc]

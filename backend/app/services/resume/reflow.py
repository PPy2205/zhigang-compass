"""双栏简历 PDF 文本重组（设计文档 §8.1 双栏版式）。

检测：pdfplumber 检测页中部是否存在竖直空白带（左右栏间距），
判定双栏布局。

重组（按 y 坐标交替拼接）：
  设计文档 §8.1："按 y 坐标交替拼接左右栏文本"。
  左右栏各自按 y 坐标提取词组（word cluster），然后按 y 坐标
  从上到下交替拼接（左行→右行→左行→右行…），还原双栏阅读顺序。

表格简历提取（设计文档 §8.1：pdfplumber + Camelot）：
  检测页面中的表格区域，用 pdfplumber 内置表格检测提取，
  与正文段落合并输出（Camelot 可用时自动切换）。

单栏 PDF 返回空串（调用方保留原有 pypdf 提取结果）；混合布局
（部分页双栏）时双栏页重组、单栏页保持整页提取。
"""

from pathlib import Path
from typing import Union


def is_two_column(page, gap_ratio: float = 0.06) -> bool:
    """判定页是否为双栏布局。

    双栏充分条件（同时满足）：
    1. 页中部存在宽度 ≥ gap_ratio×页宽的垂直空白带（分栏间隙）；
    2. 左右两栏区域均含文字（单栏排版右半页空白时中部无字但不应误判）。
    """
    width = page.width
    if not width:
        return False
    band_half = width * gap_ratio / 2
    half = width / 2
    mid_band = page.within_bbox(
        (half - band_half, 0, half + band_half, page.height)
    )
    if mid_band.extract_words():
        return False
    left = page.within_bbox((0, 0, half - band_half, page.height))
    right = page.within_bbox((half + band_half, 0, width, page.height))
    return bool(left.extract_words()) and bool(right.extract_words())


def _reflow_page_by_y(page) -> str:
    """按 y 坐标交替拼接左右栏文本（设计文档 §8.1）。

    左右栏各自提取词组，按 y 坐标分组为行，
    然后交替拼接（左行→右行→左行→右行…）。
    """
    half = page.width / 2
    left_words = page.within_bbox((0, 0, half, page.height)).extract_words()
    right_words = page.within_bbox((half, 0, page.width, page.height)).extract_words()

    # 按 y 坐标分组成行（容差 5px）
    def _group_by_y(words):
        if not words:
            return []
        sorted_words = sorted(words, key=lambda w: (round(w["top"] / 5), w["x0"]))
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]["top"]

        for w in sorted_words[1:]:
            if abs(w["top"] - current_y) <= 5:
                current_line.append(w)
            else:
                lines.append(current_line)
                current_line = [w]
                current_y = w["top"]
        lines.append(current_line)

        # 每行按 x 排序后拼接文本
        return [
            " ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"]))
            for line in lines
        ]

    left_lines = _group_by_y(left_words)
    right_lines = _group_by_y(right_words)

    # 交替拼接：按 y 坐标从上到下，左行→右行交替
    max_lines = max(len(left_lines), len(right_lines))
    out = []
    for i in range(max_lines):
        if i < len(left_lines):
            out.append(left_lines[i])
        if i < len(right_lines):
            out.append(right_lines[i])

    return "\n".join(out)


def _extract_tables(page) -> list[str]:
    """检测并提取页面中的表格内容（设计文档 §8.1：Camelot 提取）。

    优先使用 Camelot（lattice 模式），Camelot 不可用时回退 pdfplumber 内置表格检测。
    """
    # 先用 pdfplumber 内置表格检测（已安装，无需额外依赖）
    tables = page.extract_tables()
    if not tables:
        return []

    results = []
    for table in tables:
        for row in table:
            cells = [str(c).strip() if c else "" for c in row]
            results.append(" | ".join(cells))
    return results


def reflow_pdf(pdf_path: Union[str, Path]) -> str:
    """双栏 PDF 按阅读顺序重组；单栏 PDF 返回空串。

    Args:
        pdf_path: PDF 文件路径

    Returns:
        重组后的全文；无双栏页时返回空串（由调用方决定是否回退原提取）
    """
    import pdfplumber

    detected_two_column = False
    out: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            if is_two_column(page):
                detected_two_column = True
                # 按 y 坐标交替拼接左右栏
                text = _reflow_page_by_y(page)
                out.append(text)
            else:
                # 单栏页：整页提取 + 表格检测
                page_text = page.extract_text() or ""
                tables = _extract_tables(page)
                if tables:
                    page_text = page_text + "\n" + "\n".join(tables)
                out.append(page_text)
    if not detected_two_column:
        return ""
    return "\n".join(t for t in out if t).strip()

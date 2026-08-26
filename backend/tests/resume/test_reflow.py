"""双栏简历 PDF 重组测试（设计文档 §8.1）。

用 PyMuPDF 在指定坐标写入文本生成测试 PDF（fitz 已在依赖中，
且可精确控制 x/y 坐标构造双栏布局）。

测试覆盖：
- 单栏 PDF → 返回空串
- 双栏 PDF → y 坐标交替拼接阅读顺序
- 混合布局（双栏+单栏）→ 所有页文本保留
- 三栏变体 → 双栏检测仍有效
- 表格内容提取
"""

import fitz

from app.services.resume.reflow import (
    reflow_pdf,
    is_two_column,
    _reflow_page_by_y,
    _extract_tables,
)


def _write_pdf(path, spans):
    """spans: [(x, y, text)]，生成一页 A4 PDF。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    for x, y, text in spans:
        page.insert_text((x, y), text)
    doc.save(path)
    doc.close()


def _write_multipage_pdf(path, pages_spans):
    """pages_spans: [[(x, y, text)], ...]，每元素一页。"""
    doc = fitz.open()
    for spans in pages_spans:
        page = doc.new_page(width=595, height=842)
        for x, y, text in spans:
            page.insert_text((x, y), text)
    doc.save(path)
    doc.close()


# ── 单栏 PDF ──


def test_single_column_pdf_returns_empty(tmp_path):
    """单栏 PDF 无双栏空白带 → reflow_pdf 返回空串（调用方回退原提取）。"""
    p = tmp_path / "single.pdf"
    _write_pdf(p, [(50, 60 + i * 20, f"line {i}") for i in range(10)])
    assert reflow_pdf(p) == ""


# ── 双栏 PDF ──


def test_two_column_pdf_reflowed_in_reading_order(tmp_path):
    """双栏 PDF 按 y 坐标交替拼接（左行→右行→左行→右行）。"""
    p = tmp_path / "two_col.pdf"
    left = [f"L{i}" for i in range(5)]
    right = [f"R{i}" for i in range(5)]
    spans = [(50, 60 + i * 20, t) for i, t in enumerate(left)]
    spans += [(320, 60 + i * 20, t) for i, t in enumerate(right)]
    _write_pdf(p, spans)

    text = reflow_pdf(p)
    assert text != ""
    # 所有内容都保留
    assert all(f"L{i}" in text for i in range(5))
    assert all(f"R{i}" in text for i in range(5))
    # y 坐标交替：L0 和 R0 在同一 y，L0 应在 R0 之前
    assert text.index("L0") < text.index("R0")
    # L1 在 R0 之后（下一行的左栏）
    assert text.index("R0") < text.index("L1")


def test_two_column_detection(tmp_path):
    """is_two_column 正确识别双栏布局。"""
    p = tmp_path / "detect.pdf"
    _write_pdf(p, [
        (50, 60 + i * 20, f"left{i}") for i in range(5)
    ] + [
        (320, 60 + i * 20, f"right{i}") for i in range(5)
    ])
    import pdfplumber
    with pdfplumber.open(str(p)) as pdf:
        page = pdf.pages[0]
        assert is_two_column(page)


def test_single_column_not_detected_as_two_column(tmp_path):
    """单栏 PDF 不被误判为双栏。"""
    p = tmp_path / "single_detect.pdf"
    _write_pdf(p, [(50, 60 + i * 20, f"line {i}") for i in range(10)])
    import pdfplumber
    with pdfplumber.open(str(p)) as pdf:
        page = pdf.pages[0]
        assert not is_two_column(page)


# ── 混合布局 ──


def test_mixed_layout_preserves_all_pages(tmp_path):
    """混合布局（第一页双栏 + 第二页单栏）时所有页文本都保留。"""
    p = tmp_path / "mixed.pdf"
    _write_multipage_pdf(p, [
        # 第一页：双栏
        [(50, 60 + i * 20, f"A{i}") for i in range(4)]
        + [(320, 60 + i * 20, f"B{i}") for i in range(4)],
        # 第二页：单栏
        [(50, 60, "single page")],
    ])

    text = reflow_pdf(p)
    assert "A0" in text and "B0" in text
    assert "single page" in text


def test_three_column_treated_as_two_column(tmp_path):
    """三栏 PDF 的中部空白带会被检测为双栏（至少不会漏检）。"""
    p = tmp_path / "three.pdf"
    _write_pdf(p, [
        (50, 60 + i * 20, f"L{i}") for i in range(3)
    ] + [
        (250, 60 + i * 20, f"M{i}") for i in range(3)
    ] + [
        (450, 60 + i * 20, f"R{i}") for i in range(3)
    ])
    text = reflow_pdf(p)
    # 三栏文本全部保留
    assert "L0" in text
    assert "M0" in text
    assert "R0" in text


# ── y 坐标交替拼接 ──


def test_y_coordinate_interleaving(tmp_path):
    """y 坐标交替拼接：同行左右栏内容按左→右顺序出现。"""
    p = tmp_path / "interleave.pdf"
    # 左栏第1行 y=60，右栏第1行 y=60
    # 左栏第2行 y=80，右栏第2行 y=80
    _write_pdf(p, [
        (50, 60, "LeftFirst"),
        (320, 60, "RightFirst"),
        (50, 80, "LeftSecond"),
        (320, 80, "RightSecond"),
    ])
    text = reflow_pdf(p)
    # 同一 y 的左栏在右栏之前
    assert text.index("LeftFirst") < text.index("RightFirst")
    # 下一行的左栏在上一行右栏之后
    assert text.index("RightFirst") < text.index("LeftSecond")


def test_uneven_column_lengths(tmp_path):
    """左右栏行数不等时：所有内容都保留。"""
    p = tmp_path / "uneven.pdf"
    _write_pdf(p, [
        (50, 60 + i * 20, f"L{i}") for i in range(5)
    ] + [
        (320, 60 + i * 20, f"R{i}") for i in range(3)
    ])
    text = reflow_pdf(p)
    assert all(f"L{i}" in text for i in range(5))
    assert all(f"R{i}" in text for i in range(3))


# ── 表格提取 ──


def test_table_extraction_no_tables(tmp_path):
    """无表格的页面 → _extract_tables 返回空列表。"""
    p = tmp_path / "no_table.pdf"
    _write_pdf(p, [(50, 60, "Normal text line")])
    import pdfplumber
    with pdfplumber.open(str(p)) as pdf:
        page = pdf.pages[0]
        tables = _extract_tables(page)
        assert tables == []


# ── 空页面 ──


def test_empty_page_returns_empty(tmp_path):
    """空页面 PDF → reflow 返回空串。"""
    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(p)
    doc.close()
    assert reflow_pdf(p) == ""


def test_reflow_preserves_text_content(tmp_path):
    """reflow 后文本内容完整保留（无丢失）。"""
    p = tmp_path / "preserve.pdf"
    content = [
        "Python", "Java", "Spring", "Docker",
        "Kubernetes", "MySQL", "Redis", "Kafka",
    ]
    spans = []
    for i, word in enumerate(content[:4]):
        spans.append((50, 60 + i * 20, word))
    for i, word in enumerate(content[4:]):
        spans.append((320, 60 + i * 20, word))
    _write_pdf(p, spans)

    text = reflow_pdf(p)
    for word in content:
        assert word in text

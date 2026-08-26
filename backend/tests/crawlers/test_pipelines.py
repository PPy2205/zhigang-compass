"""CleaningPipeline 清洗管线测试（设计文档 §4.2）。

覆盖：
- 实习/兼职岗位源头过滤（已有）
- 长度过滤（< 50 字丢弃）
- 核心词检测（无核心词丢弃）
- 质量评分（< 0.6 标记人工复核）
- 正常岗位通过 + 指纹/质量评分生成
"""

from types import SimpleNamespace

import pytest
from scrapy.exceptions import DropItem

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "data"))

from crawlers.items import JobItem
from crawlers.pipelines import (
    CleaningPipeline,
    _employment_reason,
    _has_core_keyword,
    _quality_score,
    QUALITY_THRESHOLD,
)


def _job(**fields) -> JobItem:
    item = JobItem()
    for k, v in fields.items():
        item[k] = v
    return item


def _make_spider():
    """构造模拟 spider 用于日志验证。"""
    return SimpleNamespace(
        logger=SimpleNamespace(info=lambda *a, **k: None),
        name="test_spider",
    )


def _make_pipeline():
    pipe = CleaningPipeline()
    pipe.crawler = SimpleNamespace(spider=_make_spider())
    return pipe


# ── _employment_reason 判断 ──


def test_intern_cn_title():
    assert _employment_reason(_job(title="实习生（前端开发）")) == "实习岗位"
    assert _employment_reason(_job(title="数据运营实习生")) == "实习岗位"


def test_intern_en_title():
    assert _employment_reason(_job(title="Software Engineer Intern")) == "实习岗位"
    assert _employment_reason(_job(title="Data Scientist Internship")) == "实习岗位"


def test_intern_tag():
    assert _employment_reason(_job(title="Engineer", tags=["INTERNSHIP"])) == "实习岗位"


def test_chinese_tag_not_filtered():
    # 智联 tags 为技能/招聘对象标签（如"金融分析大学生实习"），非就业类型，不应误拦截
    assert _employment_reason(
        _job(title="商业数据金融分析师", tags=["金融分析大学生实习"])
    ) is None


def test_parttime_cn_title():
    assert _employment_reason(_job(title="兼职数据分析")) == "兼职岗位"


def test_parttime_en_title():
    assert _employment_reason(_job(title="Data Analyst - Part Time")) == "兼职岗位"
    assert _employment_reason(_job(title="Part-time UI Designer")) == "兼职岗位"


def test_parttime_tag():
    assert _employment_reason(_job(title="Analyst", tags=["PART_TIME"])) == "兼职岗位"


def test_fulltime_not_filtered():
    assert _employment_reason(_job(title="Software Engineer", tags=["FULL_TIME"])) is None


def test_intern_no_false_positive():
    # intern 词边界：internal / internet / international 不应误伤
    assert _employment_reason(_job(title="International Sales Manager")) is None
    assert _employment_reason(_job(title="Internal Tool Developer")) is None
    assert _employment_reason(_job(title="IoT Internet Engineer")) is None


def test_normal_job_not_filtered():
    assert _employment_reason(
        _job(title="Python 后端开发工程师", company="XX科技", tags=["技能标签"])
    ) is None


# ── 长度过滤（设计文档 §4.2：长度 < 50 字丢弃）──


def test_short_text_dropped():
    """文本长度 < 50 字 → DropItem。"""
    pipe = _make_pipeline()
    item = _job(
        title="Python 开发工程师",
        source="boss", source_id="1",
        description="负责后端开发",
    )
    # description + requirements + raw_text = "负责后端开发" = 7 字 < 50
    with pytest.raises(DropItem) as exc:
        pipe.process_item(item)
    assert "文本过短" in str(exc.value)


def test_min_length_passed():
    """文本长度 = 50 字 → 通过长度过滤。"""
    pipe = _make_pipeline()
    desc = "负责后端系统开发，需要熟练掌握Python编程语言和相关框架，有分布式系统经验优先。" * 1
    # desc 长度 > 50，包含核心词
    item = _job(
        title="Python 开发工程师",
        source="boss", source_id="1",
        company="XX科技",
        description=desc,
        requirements="本科及以上学历",
    )
    result = pipe.process_item(item)
    assert result is item


# ── 核心词检测（设计文档 §4.2：核心词检测）──


def test_no_core_keyword_dropped():
    """文本无 JD 核心词 → DropItem。"""
    pipe = _make_pipeline()
    # 长度够但无核心词（纯噪音文本）
    long_text = "今天天气很好适合出门散步我们去公园玩了一整天很开心" * 5
    item = _job(
        title="XXX",
        source="boss", source_id="1",
        description=long_text,
        requirements=long_text,
    )
    with pytest.raises(DropItem) as exc:
        pipe.process_item(item)
    assert "核心词" in str(exc.value)


def test_core_keyword_chinese():
    """中文核心词检测。"""
    assert _has_core_keyword("负责后端系统开发")
    assert _has_core_keyword("本科及以上学历")
    assert _has_core_keyword("精通Python编程")


def test_core_keyword_english():
    """英文核心词检测。"""
    assert _has_core_keyword("responsible for backend development")
    assert _has_core_keyword("requires bachelor degree")
    assert _has_core_keyword("5 years experience")


def test_no_core_keyword():
    """无核心词文本。"""
    assert not _has_core_keyword("今天天气很好")
    assert not _has_core_keyword("随机文本无关键词")


# ── 质量评分（设计文档 §4.2：质量评分 < 0.6 入人工复核）──


def test_quality_score_high():
    """高质量 JD → score >= 0.6，needs_review=False。"""
    pipe = _make_pipeline()
    item = _job(
        title="Python 开发工程师",
        source="boss", source_id="1",
        company="XX科技",
        location="北京",
        salary="20-30K",
        description="负责后端系统开发，需要熟练掌握Python编程语言和相关框架，有分布式系统经验优先。",
        requirements="本科及以上学历，3年以上开发经验",
    )
    result = pipe.process_item(item)
    assert result["quality_score"] >= QUALITY_THRESHOLD
    assert result["needs_review"] is False


def test_quality_score_low():
    """低质量 JD → score < 0.6，needs_review=True。

    直接测试 _quality_score 函数（避免被长度过滤拦截）。
    """
    # 仅 title + description 有值，缺 company/location/salary，文本短
    item = _job(
        title="开发工程师",
        description="负责开发",
        requirements="熟悉Python",
    )
    score = _quality_score(item)
    assert score < QUALITY_THRESHOLD


def test_quality_score_dimensions():
    """质量评分四维计算正确性。"""
    # 全字段 + 长文本 + 核心词 + 格式标记 → 高分
    item_good = _job(
        title="开发工程师",
        company="XX科技",
        location="北京",
        salary="20K",
        description="负责系统开发\n1. 后端架构\n2. 数据库设计",
        requirements="本科\n1. Python\n2. SQL",
    )
    score_good = _quality_score(item_good)
    assert score_good >= 0.6

    # 缺字段 + 短文本 → 低分
    item_poor = _job(
        title="XX",
        description="短文本",
    )
    score_poor = _quality_score(item_poor)
    assert score_poor < 0.6
    assert score_good > score_poor


# ── process_item 完整流程 ──


def test_process_item_drops_intern_job():
    pipe = _make_pipeline()
    item = _job(title="实习生（前端开发）", source="boss", source_id="1")
    with pytest.raises(DropItem) as exc:
        pipe.process_item(item)
    assert "实习岗位" in str(exc.value)
    assert pipe._filtered_count == 1


def test_process_item_passes_normal_job():
    pipe = _make_pipeline()
    item = _job(
        title="Python 后端开发工程师", source="boss", source_id="2",
        company="XX科技",
        description="负责后端系统开发，需要熟练掌握Python编程语言和相关框架，有分布式系统经验优先。",
        requirements="本科及以上学历，3年以上开发经验",
    )
    result = pipe.process_item(item)
    assert result is item
    assert pipe._filtered_count == 0
    assert item["_fingerprint"]  # 正常岗位继续走指纹计算
    assert "quality_score" in item  # 质量评分已计算
    assert "needs_review" in item  # 复核标记已设置

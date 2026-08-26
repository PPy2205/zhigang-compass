"""MinHash 近似去重兜底测试（设计文档 §4.2 去重）。

覆盖：
- 文本 shingle 切分
- MinHash 签名计算
- Jaccard 相似度估计
- 抄袭判定（≥ 0.85）
- 重复记录分组
"""

import pytest

from app.services.data_quality.minhash import (
    _text_shingles,
    minhash_signature,
    jaccard_similarity,
    is_plagiarism,
    find_duplicates,
    PLAGIARISM_THRESHOLD,
)


class TestShingles:
    """Shingle 切分测试。"""

    def test_chinese_shingles(self):
        """中文 3 字符滑窗。"""
        shingles = _text_shingles("精通Python开发")
        assert len(shingles) > 0
        # 精通P, 通Py, Pyt... 等中文+英文混合

    def test_english_shingles(self):
        """英文 2 词滑窗。"""
        shingles = _text_shingles("Python Java Spring Boot")
        assert len(shingles) > 0
        # "python java", "java spring", "spring boot"

    def test_empty_text(self):
        """空文本 → 空集合。"""
        assert _text_shingles("") == set()
        assert _text_shingles(None) == set()

    def test_short_text(self):
        """短文本 → 整文本作为单个 shingle。"""
        shingles = _text_shingles("精通")
        assert len(shingles) == 1


class TestMinHashSignature:
    """MinHash 签名测试。"""

    def test_signature_length(self):
        """签名长度 = num_perm。"""
        sig = minhash_signature("精通Python开发框架", num_perm=64)
        assert len(sig) == 64

    def test_same_text_same_signature(self):
        """相同文本 → 相同签名。"""
        text = "熟练掌握Python编程语言和相关框架"
        sig1 = minhash_signature(text)
        sig2 = minhash_signature(text)
        assert sig1 == sig2

    def test_empty_text_signature(self):
        """空文本 → 全 0 签名。"""
        sig = minhash_signature("")
        assert all(s == 0 for s in sig)


class TestJaccardSimilarity:
    """Jaccard 相似度测试。"""

    def test_identical_text(self):
        """完全相同文本 → 相似度 = 1.0。"""
        text = "熟练掌握Python编程语言和相关框架，有分布式系统经验"
        sig = minhash_signature(text)
        assert jaccard_similarity(sig, sig) == 1.0

    def test_similar_text(self):
        """高度相似文本 → 相似度 > 0.5。"""
        text_a = "熟练掌握Python编程语言和相关框架，有分布式系统经验"
        text_b = "熟练掌握Python编程语言和框架，有分布式系统经验"
        sig_a = minhash_signature(text_a)
        sig_b = minhash_signature(text_b)
        sim = jaccard_similarity(sig_a, sig_b)
        assert sim > 0.5

    def test_different_text(self):
        """完全不同文本 → 相似度低。"""
        text_a = "精通Java Spring Boot微服务开发"
        text_b = "负责前端React TypeScript开发"
        sig_a = minhash_signature(text_a)
        sig_b = minhash_signature(text_b)
        sim = jaccard_similarity(sig_a, sig_b)
        assert sim < 0.3

    def test_empty_signatures(self):
        """空签名 → 相似度 0。"""
        assert jaccard_similarity([], []) == 0.0
        assert jaccard_similarity([1, 2, 3], []) == 0.0


class TestPlagiarism:
    """抄袭判定测试。"""

    def test_plagiarism_detected(self):
        """高度相似文本 → 判定为抄袭。"""
        text_a = "熟练掌握Python编程语言，精通Django和Flask框架，有丰富的后端开发经验"
        text_b = "熟练掌握Python编程语言，精通Django和Flask框架，有丰富的后端开发经验"
        assert is_plagiarism(text_a, text_b)

    def test_no_plagiarism(self):
        """不相似文本 → 非抄袭。"""
        text_a = "精通Java Spring Boot微服务架构设计"
        text_b = "负责React前端开发，熟练使用ECharts数据可视化"
        assert not is_plagiarism(text_a, text_b)

    def test_custom_threshold(self):
        """自定义阈值。"""
        text_a = "熟练掌握Python编程语言和相关框架"
        text_b = "熟练掌握Python编程语言和框架"
        # 默认 0.85 可能不触发，降低阈值检测
        assert is_plagiarism(text_a, text_b, threshold=0.3)


class TestFindDuplicates:
    """重复记录分组测试。"""

    def test_find_duplicate_group(self):
        """找出抄袭组。"""
        records = [
            ("r1", "熟练掌握Python编程语言，精通Django框架，有丰富的后端开发经验"),
            ("r2", "熟练掌握Python编程语言，精通Django框架，有丰富的后端开发经验"),
            ("r3", "负责React前端开发，熟练使用TypeScript"),
            ("r4", "负责React前端开发，熟练使用TypeScript"),
        ]
        groups = find_duplicates(records)
        assert len(groups) >= 1
        # 每组至少 2 条
        for group in groups:
            assert len(group) >= 2

    def test_no_duplicates(self):
        """全部不同 → 无抄袭组。"""
        records = [
            ("r1", "精通Java Spring Boot微服务架构设计"),
            ("r2", "负责React前端开发使用TypeScript"),
            ("r3", "数据分析师，熟练SQL和Python数据分析"),
        ]
        groups = find_duplicates(records)
        assert len(groups) == 0

    def test_single_record(self):
        """单条记录 → 无抄袭组。"""
        records = [("r1", "精通Python开发")]
        groups = find_duplicates(records)
        assert len(groups) == 0

    def test_empty_records(self):
        """空列表 → 无抄袭组。"""
        groups = find_duplicates([])
        assert len(groups) == 0

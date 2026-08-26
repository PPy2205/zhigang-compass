"""Bradley-Terry 权重迭代单元测试（AL-M5-02，设计文档 9.3 节）。

覆盖 BT 对数似然计算、权重优化、反馈对收集、退化逻辑。
"""

import pytest

from app.services.matching.bradley_terry import (
    _EPS,  # noqa: private import for testing
    MIN_FEEDBACK_PAIRS,
    FeedbackPair,
    IterationResult,
    _extract_subscores,
    _grid_search_bt,
    bt_log_likelihood,
    collect_feedback_pairs_from_records,
    optimize_weights_bt,
)
from app.services.matching.weights import DEFAULT_WEIGHTS


# ─── BT 对数似然计算 ───────────────────────────────────────────

class TestBTLogLikelihood:
    """bt_log_likelihood 计算正确性。"""

    def test_perfect_separation(self):
        """winner 全满分、loser 全零分 → 似然接近 0（log(1) = 0）。"""
        pairs = [
            FeedbackPair(winner=(1.0, 1.0, 1.0), loser=(0.0, 0.0, 0.0))
        ]
        ll = bt_log_likelihood(DEFAULT_WEIGHTS, pairs)
        # S_w = 1.0, S_l ≈ 0 → log(1/1) ≈ 0
        assert ll == pytest.approx(0.0, abs=0.01)

    def test_identical_scores(self):
        """winner 和 loser 子分数相同 → 似然 = log(0.5) ≈ -0.693。"""
        pairs = [
            FeedbackPair(winner=(0.5, 0.5, 0.5), loser=(0.5, 0.5, 0.5))
        ]
        ll = bt_log_likelihood(DEFAULT_WEIGHTS, pairs)
        assert ll == pytest.approx(-0.693, abs=0.05)

    def test_multiple_pairs_sum(self):
        """多对的似然应为各对似然之和。"""
        pair1 = FeedbackPair(winner=(0.9, 0.8, 0.7), loser=(0.3, 0.2, 0.1))
        pair2 = FeedbackPair(winner=(0.8, 0.7, 0.6), loser=(0.4, 0.3, 0.2))
        ll_combined = bt_log_likelihood(DEFAULT_WEIGHTS, [pair1, pair2])
        ll1 = bt_log_likelihood(DEFAULT_WEIGHTS, [pair1])
        ll2 = bt_log_likelihood(DEFAULT_WEIGHTS, [pair2])
        assert ll_combined == pytest.approx(ll1 + ll2, abs=1e-10)

    def test_empty_pairs(self):
        """空对列表 → 似然 = 0。"""
        assert bt_log_likelihood(DEFAULT_WEIGHTS, []) == 0.0

    def test_zero_scores_no_crash(self):
        """双方分数均为 0 → 不崩溃（数值稳定）。"""
        pairs = [
            FeedbackPair(winner=(0.0, 0.0, 0.0), loser=(0.0, 0.0, 0.0))
        ]
        ll = bt_log_likelihood(DEFAULT_WEIGHTS, pairs)
        # 不应为 -inf
        assert ll > -1e6

    def test_higher_must_weight_increases_ll(self):
        """winner 的 must 分更高时，增大 w_must 应提升似然。"""
        pairs = [
            FeedbackPair(winner=(0.9, 0.5, 0.5), loser=(0.3, 0.5, 0.5))
        ]
        ll_low_must = bt_log_likelihood((0.4, 0.3, 0.3), pairs)
        ll_high_must = bt_log_likelihood((0.7, 0.15, 0.15), pairs)
        assert ll_high_must > ll_low_must


# ─── 权重优化 ──────────────────────────────────────────────────

class TestOptimizeWeights:
    """optimize_weights_bt 优化正确性。"""

    def test_synthetic_winner_higher_must(self):
        """合成数据 winner must 系统性更高 → 优化后 w_must 应增大。"""
        rng = __import__("random").Random(42)
        pairs = []
        for _ in range(50):
            pairs.append(FeedbackPair(
                winner=(rng.uniform(0.7, 1.0), rng.uniform(0.3, 0.7), rng.uniform(0.3, 0.7)),
                loser=(rng.uniform(0.1, 0.4), rng.uniform(0.3, 0.7), rng.uniform(0.3, 0.7)),
            ))
        old_ll = bt_log_likelihood(DEFAULT_WEIGHTS, pairs)
        new_w = optimize_weights_bt(pairs, initial_weights=DEFAULT_WEIGHTS)
        new_ll = bt_log_likelihood(new_w, pairs)
        # 优化后似然应提升
        assert new_ll >= old_ll - 1e-6
        # w_must 应增大（winner must 更高）
        assert new_w[0] >= DEFAULT_WEIGHTS[0] - 0.05

    def test_weights_sum_to_one(self):
        """优化后权重之和 = 1。"""
        pairs = [
            FeedbackPair(winner=(0.8, 0.6, 0.4), loser=(0.2, 0.3, 0.5)),
            FeedbackPair(winner=(0.9, 0.5, 0.7), loser=(0.1, 0.4, 0.2)),
        ]
        w = optimize_weights_bt(pairs)
        assert sum(w) == pytest.approx(1.0, abs=0.002)

    def test_weights_in_bounds(self):
        """权重在搜索边界内。"""
        pairs = [
            FeedbackPair(winner=(0.9, 0.8, 0.7), loser=(0.1, 0.2, 0.3)),
        ] * 10
        w = optimize_weights_bt(pairs)
        assert 0.4 <= w[0] <= 0.7 + 0.01
        assert 0.1 <= w[1] <= 0.3 + 0.01
        assert w[2] >= -0.01

    def test_grid_search_fallback(self):
        """网格搜索能找到合理解。"""
        pairs = [
            FeedbackPair(winner=(0.9, 0.5, 0.5), loser=(0.1, 0.5, 0.5)),
        ] * 5
        w = _grid_search_bt(pairs)
        assert sum(w) == pytest.approx(1.0, abs=0.01)
        # must 应偏高
        assert w[0] >= 0.6


# ─── 反馈对收集 ────────────────────────────────────────────────

class TestCollectFeedbackPairs:
    """collect_feedback_pairs_from_records 数据构建。"""

    def test_cross_result_pairs(self):
        """同一用户 👍 > 👎 构建跨结果对。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
            {"match_id": "m2", "score": -1, "user_id": "u1"},
        ]
        results = [
            {"match_id": "m1", "result": {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7}, "user_id": "u1"},
            {"match_id": "m2", "result": {"must_score": 0.3, "nice_score": 0.2, "exp_score": 0.1}, "user_id": "u1"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 1
        assert pairs[0].winner == (0.9, 0.8, 0.7)
        assert pairs[0].loser == (0.3, 0.2, 0.1)
        assert pairs[0].source == "cross_result"

    def test_within_recommend_pairs(self):
        """👍 recommend 结果中排名 1 > 排名 2 构建推荐内对。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
        ]
        results = [
            {"match_id": "m1", "result": {"items": [
                {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7},
                {"must_score": 0.5, "nice_score": 0.4, "exp_score": 0.3},
            ]}, "user_id": "u1"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 1
        assert pairs[0].winner == (0.9, 0.8, 0.7)
        assert pairs[0].loser == (0.5, 0.4, 0.3)
        assert pairs[0].source == "within_recommend"

    def test_different_users_no_cross_pairs(self):
        """不同用户的 👍 和 👎 不构成跨结果对。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
            {"match_id": "m2", "score": -1, "user_id": "u2"},
        ]
        results = [
            {"match_id": "m1", "result": {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7}, "user_id": "u1"},
            {"match_id": "m2", "result": {"must_score": 0.3, "nice_score": 0.2, "exp_score": 0.1}, "user_id": "u2"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 0

    def test_identical_scores_skipped(self):
        """完全相同的子分数对被跳过（无信息量）。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
            {"match_id": "m2", "score": -1, "user_id": "u1"},
        ]
        results = [
            {"match_id": "m1", "result": {"must_score": 0.5, "nice_score": 0.5, "exp_score": 0.5}, "user_id": "u1"},
            {"match_id": "m2", "result": {"must_score": 0.5, "nice_score": 0.5, "exp_score": 0.5}, "user_id": "u1"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 0

    def test_missing_result_skipped(self):
        """反馈对应的 match_id 在结果表中不存在 → 跳过。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
            {"match_id": "m_missing", "score": -1, "user_id": "u1"},
        ]
        results = [
            {"match_id": "m1", "result": {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7}, "user_id": "u1"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 0

    def test_multiple_users_multiple_pairs(self):
        """多用户各产生独立比较对。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
            {"match_id": "m2", "score": -1, "user_id": "u1"},
            {"match_id": "m3", "score": 1, "user_id": "u2"},
            {"match_id": "m4", "score": -1, "user_id": "u2"},
        ]
        results = [
            {"match_id": "m1", "result": {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7}, "user_id": "u1"},
            {"match_id": "m2", "result": {"must_score": 0.3, "nice_score": 0.2, "exp_score": 0.1}, "user_id": "u1"},
            {"match_id": "m3", "result": {"must_score": 0.8, "nice_score": 0.7, "exp_score": 0.6}, "user_id": "u2"},
            {"match_id": "m4", "result": {"must_score": 0.4, "nice_score": 0.3, "exp_score": 0.2}, "user_id": "u2"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 2
        assert all(p.source == "cross_result" for p in pairs)

    def test_recommend_with_single_item_no_within_pair(self):
        """recommend 结果仅 1 个岗位 → 不产生推荐内对。"""
        feedback = [
            {"match_id": "m1", "score": 1, "user_id": "u1"},
        ]
        results = [
            {"match_id": "m1", "result": {"items": [
                {"must_score": 0.9, "nice_score": 0.8, "exp_score": 0.7},
            ]}, "user_id": "u1"},
        ]
        pairs = collect_feedback_pairs_from_records(feedback, results)
        assert len(pairs) == 0

    def test_extract_subscores_recommend_format(self):
        """recommend 格式：从 items[0] 提取子分数。"""
        data = {"items": [
            {"must_score": 0.8, "nice_score": 0.6, "exp_score": 0.9},
            {"must_score": 0.3, "nice_score": 0.2, "exp_score": 0.1},
        ]}
        scores = _extract_subscores(data)
        assert scores == (0.8, 0.6, 0.9)

    def test_extract_subscores_compare_format(self):
        """compare 格式：直接从顶层提取子分数。"""
        data = {"must_score": 0.7, "nice_score": 0.5, "exp_score": 0.8}
        scores = _extract_subscores(data)
        assert scores == (0.7, 0.5, 0.8)

    def test_extract_subscores_empty(self):
        """空数据返回 None。"""
        assert _extract_subscores({}) is None
        assert _extract_subscores(None) is None


# ─── 端到端验证 ────────────────────────────────────────────────

class TestEndToEnd:
    """BT 权重迭代端到端验证。"""

    def test_full_pipeline_synthetic(self):
        """合成数据端到端：收集对 → 优化 → 验证似然提升。"""
        import random
        rng = random.Random(123)
        pairs = []
        for _ in range(50):
            pairs.append(FeedbackPair(
                winner=(rng.uniform(0.7, 1.0), rng.uniform(0.4, 0.8), rng.uniform(0.5, 0.9)),
                loser=(rng.uniform(0.1, 0.4), rng.uniform(0.2, 0.5), rng.uniform(0.2, 0.6)),
            ))

        old_ll = bt_log_likelihood(DEFAULT_WEIGHTS, pairs)
        new_w = optimize_weights_bt(pairs, initial_weights=DEFAULT_WEIGHTS)
        new_ll = bt_log_likelihood(new_w, pairs)

        # 似然应提升
        assert new_ll >= old_ll - 1e-6
        # 权重之和 = 1
        assert sum(new_w) == pytest.approx(1.0, abs=0.01)

    def test_iteration_result_dataclass(self):
        """IterationResult 数据类字段完整性。"""
        result = IterationResult(
            success=True,
            old_weights=(0.6, 0.2, 0.2),
            new_weights=(0.7, 0.15, 0.15),
            old_log_likelihood=-10.0,
            new_log_likelihood=-8.0,
            pair_count=50,
        )
        assert result.improvement == pytest.approx(2.0)
        assert result.success is True

    def test_fallback_result(self):
        """退化结果（success=False）不包含新权重。"""
        result = IterationResult(
            success=False,
            old_weights=(0.6, 0.2, 0.2),
            pair_count=5,
            fallback_reason="反馈对数不足（5 < 30）",
        )
        assert result.new_weights is None
        assert not result.success
        assert "不足" in result.fallback_reason

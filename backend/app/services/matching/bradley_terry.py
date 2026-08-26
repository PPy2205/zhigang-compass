"""Bradley-Terry 权重迭代（AL-M5-02，设计文档 9.3 节）。

M5 阶段基于用户 👍/👎 反馈的成对比较数据，用 Bradley-Terry 模型
迭代匹配权重 (w_must, w_nice, w_exp)，使评分排序更贴近用户偏好。

核心思路：
  用户对推荐结果给出 👍（满意）或 👎（不满意），同一用户的
  👍 结果 > 👎 结果构成成对比较。将匹配总分视为 BT "worth"参数：
      P(winner > loser) = S_w / (S_w + S_l)
  其中 S = w_must × must + w_nice × nice + w_exp × exp。
  最大化对数似然 L(w) = Σ log(S_w / (S_w + S_l)) 即得到最优权重。

数据不足时（反馈对数 < MIN_FEEDBACK_PAIRS）退化至 Optuna 静态权重
（设计文档 9.3："数据不足时退化至 Optuna 静态权重"）。
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from app.services.matching.weights import (
    DEFAULT_WEIGHTS,
    SIM_THRESHOLD_DEFAULT,
    _CONFIG_PATH,
    load_sim_threshold,
    load_weights,
)

logger = logging.getLogger(__name__)

# 反馈对数下限：低于此值视为数据不足，退化至 Optuna 静态权重
MIN_FEEDBACK_PAIRS = 30

# 数值稳定常数：防止 S_w 或 S_l 为 0 时 log(0) / 除零
_EPS = 1e-8

# 权重搜索边界（与 tune_match_weights.py Optuna 搜索空间一致）
_W_MUST_BOUNDS = (0.4, 0.7)
_W_NICE_BOUNDS = (0.1, 0.3)


@dataclass
class FeedbackPair:
    """一对反馈比较数据。

    Attributes:
        winner: (must_score, nice_score, exp_score) — 用户偏好的结果
        loser:  (must_score, nice_score, exp_score) — 用户不偏好的结果
        winner_match_id: 胜方 match_id（审计追溯）
        loser_match_id:  负方 match_id
        user_id: 提供反馈的用户（同一用户内的比较更可靠）
        source: 比较来源（cross_result=跨结果 / within_recommend=推荐内排序）
    """

    winner: tuple[float, float, float]
    loser: tuple[float, float, float]
    winner_match_id: str = ""
    loser_match_id: str = ""
    user_id: str = ""
    source: str = "cross_result"


@dataclass
class IterationResult:
    """权重迭代结果。"""

    success: bool
    old_weights: tuple[float, float, float]
    new_weights: tuple[float, float, float] | None = None
    old_log_likelihood: float = 0.0
    new_log_likelihood: float = 0.0
    pair_count: int = 0
    sim_threshold: float = SIM_THRESHOLD_DEFAULT
    fallback_reason: str = ""
    pairs: list[FeedbackPair] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        """对数似然提升量。"""
        return self.new_log_likelihood - self.old_log_likelihood


def _extract_subscores(result_data: dict) -> tuple[float, float, float] | None:
    """从匹配结果 JSON 中提取 (must, nice, exp) 子分数。

    支持两种存储格式：
    - recommend: {"items": [{must_score, nice_score, exp_score, ...}], "match_id": ...}
    - compare:   {must_score, nice_score, exp_score, ...}
    """
    if not result_data:
        return None
    items = result_data.get("items")
    if items and isinstance(items, list) and len(items) > 0:
        top = items[0]
    else:
        top = result_data
    try:
        return (
            float(top.get("must_score", 0.0)),
            float(top.get("nice_score", 0.0)),
            float(top.get("exp_score", 0.0)),
        )
    except (TypeError, ValueError):
        return None


def collect_feedback_pairs_from_records(
    feedback_rows: list[dict],
    result_rows: list[dict],
) -> list[FeedbackPair]:
    """从反馈与结果记录构建成对比较数据（纯计算，无 I/O 依赖）。

    Args:
        feedback_rows: [{"match_id": str, "score": int(1/-1), "user_id": str}]
        result_rows: [{"match_id": str, "result": dict, "user_id": str}]

    构建规则：
    1. 跨结果对（cross_result）：同一 user_id 下 👍 结果 > 👎 结果
    2. 推荐内对（within_recommend）：👍 recommend 结果中排名第 1 的岗位 > 排名第 2
    """
    result_map: dict[str, dict] = {
        r["match_id"]: r for r in result_rows if r.get("match_id")
    }

    # 按 user_id 分组反馈
    user_feedback: dict[str, list[dict]] = {}
    for fb in feedback_rows:
        uid = fb.get("user_id", "")
        mid = fb.get("match_id", "")
        if not mid:
            continue
        user_feedback.setdefault(uid, []).append(fb)

    pairs: list[FeedbackPair] = []

    for uid, fbs in user_feedback.items():
        positives = [fb for fb in fbs if fb.get("score") == 1]
        negatives = [fb for fb in fbs if fb.get("score") == -1]

        # 跨结果对：同一用户 👍 > 👎
        for pos in positives:
            pos_scores = _extract_subscores(result_map.get(pos["match_id"], {}).get("result", {}))
            if pos_scores is None:
                continue
            for neg in negatives:
                neg_scores = _extract_subscores(result_map.get(neg["match_id"], {}).get("result", {}))
                if neg_scores is None:
                    continue
                # 跳过完全相同的子分数（无信息量）
                if pos_scores == neg_scores:
                    continue
                pairs.append(FeedbackPair(
                    winner=pos_scores,
                    loser=neg_scores,
                    winner_match_id=pos["match_id"],
                    loser_match_id=neg["match_id"],
                    user_id=uid,
                    source="cross_result",
                ))

        # 推荐内对：👍 结果中排名第 1 > 第 2（用户认可排序）
        for pos in positives:
            data = result_map.get(pos["match_id"], {}).get("result", {})
            if not data or not isinstance(data.get("items"), list):
                continue
            items = data["items"]
            if len(items) < 2:
                continue
            top = _extract_subscores({"items": [items[0]]})
            second = _extract_subscores({"items": [items[1]]})
            if top is None or second is None or top == second:
                continue
            pairs.append(FeedbackPair(
                winner=top,
                loser=second,
                winner_match_id=pos["match_id"],
                loser_match_id=pos["match_id"],
                user_id=uid,
                source="within_recommend",
            ))

    return pairs


async def collect_feedback_pairs() -> list[FeedbackPair]:
    """从数据库收集反馈比较对（需运行中的 PostgreSQL）。

    查询 match_feedback + match_results 表，按 user_id 分组构建成对比较。
    """
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.business import MatchFeedbackRecord, MatchResultRecord

    async with async_session_factory() as session:
        fb_rows = (await session.execute(
            select(MatchFeedbackRecord.match_id, MatchFeedbackRecord.score)
        )).all()
        result_rows_q = (await session.execute(
            select(MatchResultRecord.match_id, MatchResultRecord.result, MatchResultRecord.user_id)
        )).all()

    feedback_list = [
        {"match_id": r[0], "score": r[1], "user_id": ""}
        for r in fb_rows
    ]
    # 补充 user_id：从 match_results 关联
    result_map = {r[0]: r[2] for r in result_rows_q}
    for fb in feedback_list:
        fb["user_id"] = result_map.get(fb["match_id"], "")

    result_list = [
        {"match_id": r[0], "result": r[1], "user_id": r[2]}
        for r in result_rows_q
    ]

    return collect_feedback_pairs_from_records(feedback_list, result_list)


def bt_log_likelihood(
    weights: tuple[float, float, float],
    pairs: list[FeedbackPair],
) -> float:
    """Bradley-Terry 对数似然。

    L(w) = Σ log(S_w / (S_w + S_l))

    其中 S = w_must × must + w_nice × nice + w_exp × exp。
    """
    w_must, w_nice, w_exp = weights
    total = 0.0
    for pair in pairs:
        s_w = (
            w_must * pair.winner[0]
            + w_nice * pair.winner[1]
            + w_exp * pair.winner[2]
        )
        s_l = (
            w_must * pair.loser[0]
            + w_nice * pair.loser[1]
            + w_exp * pair.loser[2]
        )
        # 数值稳定：防止 S_w + S_l = 0
        total += math.log((s_w + _EPS) / (s_w + s_l + _EPS))
    return total


def optimize_weights_bt(
    pairs: list[FeedbackPair],
    initial_weights: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    """用 scipy 优化 BT 对数似然，返回最优 (w_must, w_nice, w_exp)。

    约束：w_must + w_nice + w_exp = 1，各分量在搜索边界内。
    优化器不可用时退化为网格搜索（保证可用性）。
    """
    w0 = initial_weights or load_weights()
    lo_must, hi_must = _W_MUST_BOUNDS
    lo_nice, hi_nice = _W_NICE_BOUNDS

    def neg_ll(w: list[float]) -> float:
        w_must, w_nice = w
        w_exp = 1.0 - w_must - w_nice
        if w_exp < -1e-6:
            return 1e6
        return -bt_log_likelihood((w_must, w_nice, w_exp), pairs)

    try:
        from scipy.optimize import minimize

        # 归一化初始点至搜索边界内
        x0 = [
            min(max(w0[0], lo_must), hi_must),
            min(max(w0[1], lo_nice), hi_nice),
        ]

        result = minimize(
            neg_ll,
            x0,
            method="L-BFGS-B",
            bounds=[(lo_must, hi_must), (lo_nice, hi_nice)],
        )

        w_must = round(float(result.x[0]), 3)
        w_nice = round(float(result.x[1]), 3)
        w_exp = round(1.0 - w_must - w_nice, 3)
        if w_exp < 0:
            # 边界修正：w_exp 不应为负
            w_exp = 0.0
            w_nice = round(1.0 - w_must, 3)
        return (w_must, w_nice, w_exp)

    except ImportError:
        logger.warning("scipy 不可用，退化为网格搜索")
        return _grid_search_bt(pairs)


def _grid_search_bt(
    pairs: list[FeedbackPair],
) -> tuple[float, float, float]:
    """网格搜索 BT 最优权重（scipy 不可用时的降级方案）。"""
    lo_must, hi_must = _W_MUST_BOUNDS
    lo_nice, hi_nice = _W_NICE_BOUNDS
    step = 0.01

    best_ll = -math.inf
    best_w = DEFAULT_WEIGHTS

    w_must = lo_must
    while w_must <= hi_must + 1e-6:
        w_nice = lo_nice
        while w_nice <= hi_nice + 1e-6:
            w_exp = 1.0 - w_must - w_nice
            if w_exp < -1e-6:
                w_nice += step
                continue
            ll = bt_log_likelihood(
                (round(w_must, 3), round(w_nice, 3), round(w_exp, 3)), pairs
            )
            if ll > best_ll:
                best_ll = ll
                best_w = (round(w_must, 3), round(w_nice, 3), round(w_exp, 3))
            w_nice += step
        w_must += step

    return best_w


def write_weights_bt(
    weights: tuple[float, float, float],
    sim_threshold: float | None = None,
) -> None:
    """将 BT 迭代权重写入 configs/match_weights.json（幂等覆盖）。"""
    threshold = sim_threshold if sim_threshold is not None else load_sim_threshold()
    existing = {}
    if _CONFIG_PATH.exists():
        try:
            existing = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    out = {
        "w_must": weights[0],
        "w_nice": weights[1],
        "w_exp": weights[2],
        "sim_threshold": threshold,
        "_comment": existing.get(
            "_comment",
            "匹配权重（设计文档 9.3）。Bradley-Terry 反馈迭代覆盖此文件。",
        ),
    }
    _CONFIG_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


async def iterate_weights(
    min_pairs: int = MIN_FEEDBACK_PAIRS,
    dry_run: bool = False,
) -> IterationResult:
    """Bradley-Terry 权重迭代主入口（设计文档 9.3 M5 阶段）。

    流程：
    1. 从 match_feedback + match_results 收集成对比较数据
    2. 数据不足（< min_pairs）→ 退化至 Optuna 静态权重，返回 fallback
    3. 用 scipy 最大化 BT 对数似然，得到最优权重
    4. dry_run=False 时写入 configs/match_weights.json

    Args:
        min_pairs: 最少反馈对数，低于此值触发退化
        dry_run: True 时仅返回结果不写文件

    Returns:
        IterationResult: 迭代结果（含新旧权重、对数似然、对数等）
    """
    old_weights = load_weights()
    sim_threshold = load_sim_threshold()

    pairs = await collect_feedback_pairs()

    if len(pairs) < min_pairs:
        logger.info(
            "反馈对数 %d < %d，退化至 Optuna 静态权重",
            len(pairs), min_pairs,
        )
        return IterationResult(
            success=False,
            old_weights=old_weights,
            pair_count=len(pairs),
            sim_threshold=sim_threshold,
            fallback_reason=f"反馈对数不足（{len(pairs)} < {min_pairs}）",
            pairs=pairs,
        )

    old_ll = bt_log_likelihood(old_weights, pairs)
    new_weights = optimize_weights_bt(pairs, initial_weights=old_weights)
    new_ll = bt_log_likelihood(new_weights, pairs)

    if not dry_run:
        write_weights_bt(new_weights, sim_threshold)

    return IterationResult(
        success=True,
        old_weights=old_weights,
        new_weights=new_weights,
        old_log_likelihood=old_ll,
        new_log_likelihood=new_ll,
        pair_count=len(pairs),
        sim_threshold=sim_threshold,
        pairs=pairs,
    )

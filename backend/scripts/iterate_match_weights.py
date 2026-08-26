"""Bradley-Terry 权重迭代 CLI（AL-M5-02，设计文档 9.3 节）。

基于用户 👍/👎 反馈的成对比较数据，用 Bradley-Terry 模型迭代
匹配权重 (w_must, w_nice, w_exp)。数据不足时退化至 Optuna 静态权重。

用法：
    # 正式迭代：从数据库收集反馈 → 优化 → 写入 configs/match_weights.json
    uv run python scripts/iterate_match_weights.py

    # 预演模式：仅展示结果不写文件
    uv run python scripts/iterate_match_weights.py --dry-run

    # 合成数据测试：不依赖数据库，用合成反馈对验证管线
    uv run python scripts/iterate_match_weights.py --synthetic

    # 指定最少反馈对数阈值
    uv run python scripts/iterate_match_weights.py --min-pairs 20

先决条件：数据库中需有 match_feedback + match_results 记录（synthetic 模式除外）。
"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.matching.bradley_terry import (
    MIN_FEEDBACK_PAIRS,
    FeedbackPair,
    IterationResult,
    bt_log_likelihood,
    collect_feedback_pairs_from_records,
    iterate_weights,
    optimize_weights_bt,
    write_weights_bt,
)
from app.services.matching.weights import load_weights


def generate_synthetic_pairs(n: int = 50, seed: int = 42) -> list[FeedbackPair]:
    """生成合成反馈对用于管线测试。

    模拟真实分布：winner 的 must_score 系统性高于 loser，
    加入随机扰动使问题非平凡。
    """
    rng = random.Random(seed)
    pairs: list[FeedbackPair] = []
    for i in range(n):
        # winner 子分数偏高（模拟用户认可的匹配）
        w_must = rng.uniform(0.7, 1.0)
        w_nice = rng.uniform(0.5, 0.9)
        w_exp = rng.uniform(0.6, 1.0)
        # loser 子分数偏低（模拟用户不认可的匹配）
        l_must = rng.uniform(0.2, 0.6)
        l_nice = rng.uniform(0.1, 0.5)
        l_exp = rng.uniform(0.3, 0.7)
        pairs.append(FeedbackPair(
            winner=(round(w_must, 4), round(w_nice, 4), round(w_exp, 4)),
            loser=(round(l_must, 4), round(l_nice, 4), round(l_exp, 4)),
            winner_match_id=f"syn_pos_{i}",
            loser_match_id=f"syn_neg_{i}",
            user_id="synthetic_user",
            source="synthetic",
        ))
    return pairs


def run_synthetic(dry_run: bool) -> None:
    """合成数据模式：验证 BT 管线完整性。"""
    pairs = generate_synthetic_pairs()
    old_weights = load_weights()
    old_ll = bt_log_likelihood(old_weights, pairs)
    new_weights = optimize_weights_bt(pairs, initial_weights=old_weights)
    new_ll = bt_log_likelihood(new_weights, pairs)

    print("=" * 60)
    print("Bradley-Terry 权重迭代（合成数据测试）")
    print("=" * 60)
    print(f"合成反馈对数: {len(pairs)}")
    print(f"旧权重:       w_must={old_weights[0]:.3f}  w_nice={old_weights[1]:.3f}  w_exp={old_weights[2]:.3f}")
    print(f"旧对数似然:   {old_ll:.4f}")
    print(f"新权重:       w_must={new_weights[0]:.3f}  w_nice={new_weights[1]:.3f}  w_exp={new_weights[2]:.3f}")
    print(f"新对数似然:   {new_ll:.4f}")
    print(f"似然提升:     {new_ll - old_ll:+.4f}")

    if not dry_run:
        write_weights_bt(new_weights)
        print("\n[写入] configs/match_weights.json 已更新")
    else:
        print("\n[预演] --dry-run 未写入文件")

    # 验证：BT 模型应当增大 w_must（winner 的 must 系统性更高）
    if new_weights[0] > old_weights[0]:
        print(f"[验证] w_must 提升 {new_weights[0] - old_weights[0]:+.3f}（符合预期：winner must 更高）")
    else:
        print(f"[注意] w_must 下降 {new_weights[0] - old_weights[0]:+.3f}（合成数据噪声较大）")


async def run_real(args) -> None:
    """正式模式：从数据库收集反馈并迭代。"""
    result = await iterate_weights(
        min_pairs=args.min_pairs,
        dry_run=args.dry_run,
    )

    print("=" * 60)
    print("Bradley-Terry 权重迭代")
    print("=" * 60)
    print(f"反馈对数:     {result.pair_count}")

    if not result.success:
        print(f"\n[退化] {result.fallback_reason}")
        print(f"       当前权重保持不变: {result.old_weights}")
        print(f"       建议: 继续收集用户反馈，达到 {args.min_pairs} 对后重试")
        print(f"       或运行 scripts/tune_match_weights.py 使用 Optuna 静态调优")
        return

    print(f"旧权重:       w_must={result.old_weights[0]:.3f}  w_nice={result.old_weights[1]:.3f}  w_exp={result.old_weights[2]:.3f}")
    print(f"旧对数似然:   {result.old_log_likelihood:.4f}")
    if result.new_weights:
        print(f"新权重:       w_must={result.new_weights[0]:.3f}  w_nice={result.new_weights[1]:.3f}  w_exp={result.new_weights[2]:.3f}")
        print(f"新对数似然:   {result.new_log_likelihood:.4f}")
        print(f"似然提升:     {result.improvement:+.4f}")

    # 按来源统计对数
    by_source: dict[str, int] = {}
    for p in result.pairs:
        by_source[p.source] = by_source.get(p.source, 0) + 1
    print(f"\n对数来源分布:")
    for src, cnt in sorted(by_source.items()):
        print(f"  {src}: {cnt}")

    if not args.dry_run:
        print(f"\n[写入] configs/match_weights.json 已更新")
    else:
        print(f"\n[预演] --dry-run 未写入文件")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bradley-Terry 权重迭代（AL-M5-02）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预演模式：仅输出结果不写入 configs/match_weights.json",
    )
    parser.add_argument(
        "--synthetic", action="store_true",
        help="合成数据模式：不依赖数据库，用合成反馈对验证管线",
    )
    parser.add_argument(
        "--min-pairs", type=int, default=MIN_FEEDBACK_PAIRS,
        help=f"最少反馈对数阈值（默认 {MIN_FEEDBACK_PAIRS}，低于此退化至 Optuna）",
    )
    args = parser.parse_args()

    if args.synthetic:
        run_synthetic(args.dry_run)
    else:
        asyncio.run(run_real(args))


if __name__ == "__main__":
    main()

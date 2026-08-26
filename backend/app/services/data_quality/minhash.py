"""MinHash 近似去重兜底（设计文档 §4.2 去重）。

当 SimHash 对短文本判定不稳时（单 token 变化导致汉明距过大），
用 MinHash + Jaccard 相似度作为兜底去重手段。

设计文档 §4.2：SimHash 64-bit 近似去重（汉明距 ≤ 3）、MinHash 兜底，
抄袭（≥ 0.85）保留最新版本。
"""

import hashlib
from typing import Iterable

# Shingle 大小（中文按字符，英文按词）
_CN_SHINGLE_SIZE = 3
_EN_SHINGLE_SIZE = 2
# 哈希函数数量（128 足够覆盖 1000+ 条记录的近似去重）
_NUM_PERMUTATIONS = 128
# 抄袭判定阈值（设计文档 §4.2：≥ 0.85）
PLAGIARISM_THRESHOLD = 0.85


def _text_shingles(text: str) -> set[str]:
    """将文本切分为 shingle 集合。

    中文按 3 字符滑窗，英文按 2 词滑窗。
    文本短于 shingle 大小时回退为整文本单个 shingle。
    """
    if not text:
        return set()

    # 中文 shingle
    cn_chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    en_words = [w for w in text.split() if any(c.isascii() and c.isalpha() for c in w)]

    shingles: set[str] = set()
    if len(cn_chars) >= _CN_SHINGLE_SIZE:
        for i in range(len(cn_chars) - _CN_SHINGLE_SIZE + 1):
            shingles.add("".join(cn_chars[i : i + _CN_SHINGLE_SIZE]))
    elif cn_chars:
        shingles.add("".join(cn_chars))

    if len(en_words) >= _EN_SHINGLE_SIZE:
        for i in range(len(en_words) - _EN_SHINGLE_SIZE + 1):
            shingles.add(" ".join(en_words[i : i + _EN_SHINGLE_SIZE]).lower())
    elif en_words:
        shingles.add(en_words[0].lower())

    return shingles


def _hash_fn(s: str, seed: int) -> int:
    """带 seed 的哈希函数，模拟排列哈希。"""
    h = hashlib.md5(f"{seed}:{s}".encode()).hexdigest()
    return int(h[:16], 16)  # 64-bit


def minhash_signature(text: str, num_perm: int = _NUM_PERMUTATIONS) -> list[int]:
    """计算文本的 MinHash 签名（长度 num_perm）。

    对每个 permutation i，取所有 shingle 在 _hash_fn(s, i) 下的最小值。
    """
    shingles = _text_shingles(text)
    if not shingles:
        return [0] * num_perm

    signature = []
    for i in range(num_perm):
        min_hash = min(_hash_fn(s, i) for s in shingles)
        signature.append(min_hash)
    return signature


def jaccard_similarity(sig_a: list[int], sig_b: list[int]) -> float:
    """计算两个 MinHash 签名的 Jaccard 相似度估计值。"""
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def is_plagiarism(text_a: str, text_b: str, threshold: float = PLAGIARISM_THRESHOLD) -> bool:
    """判断两段文本是否构成抄袭（Jaccard ≥ threshold）。"""
    sig_a = minhash_signature(text_a)
    sig_b = minhash_signature(text_b)
    return jaccard_similarity(sig_a, sig_b) >= threshold


def find_duplicates(
    records: list[tuple[str, str]],
    threshold: float = PLAGIARISM_THRESHOLD,
) -> list[list[int]]:
    """找出记录列表中的抄袭组。

    Args:
        records: [(record_id, text), ...]
        threshold: 抄袭判定阈值

    Returns:
        抄袭组列表，每组为索引列表（指向 records 的下标）
    """
    if len(records) < 2:
        return []

    # 预计算所有签名
    sigs = [(i, minhash_signature(text)) for i, (_, text) in enumerate(records)]

    groups: list[list[int]] = []
    used: set[int] = set()

    for i, sig_i in sigs:
        if i in used:
            continue
        group = [i]
        for j, sig_j in sigs[i + 1 :]:
            if j in used:
                continue
            if jaccard_similarity(sig_i, sig_j) >= threshold:
                group.append(j)
                used.add(j)
        if len(group) > 1:
            used.add(i)
            groups.append(group)

    return groups

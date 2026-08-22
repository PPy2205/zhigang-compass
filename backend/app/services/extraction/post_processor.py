"""抽取结果后处理：熟练度前缀剥离 + 递归后缀清洗 + 白名单过滤 + 去重。

设计文档 §5.2/§5.3：中文后缀清洗（去除"系统/框架/技术/工程师"等 30+ 后缀）
+ 技能归一化（设计文档 §5.3：人工词典兜底 + 子串包含对齐）。
"""

import re
from app.services.extraction.schemas import JDExtractionResult, SkillExtracted
from app.services.extraction.dictionary import (
    SOFT_SKILL_WHITELIST,
    SKILL_STOPWORDS,
    SKILL_WHITELIST,
    SKILL_ALIAS,
    normalize_skill,
    _SKILL_WHITELIST_LOWER,
)

# 需去除的中文后缀（按长度降序排列，优先匹配长后缀）。
# 不含"服务"：剥除后产生碎片（"微服务"→"微"），且无合理剥除场景。
# T-08 补充："经验"/"经历"/"实践"等——BOSS 结构化标签常带后缀
# （如"微服务经验""机器学习经历"），递归剥除至白名单可匹配。
SUFFIXES = sorted([
    "工程师", "技术", "系统", "框架", "平台", "工具", "软件", "开发",
    "设计", "管理", "应用", "方案", "产品", "项目", "算法",
    "架构", "引擎", "组件", "中间件", "协议", "标准", "接口",
    # T-08 新增：经验/能力/知识等后缀（BOSS 标签 + LLM 输出常见）
    "经验", "经历", "实践", "能力", "知识", "原理",
    "工程", "体系", "体系结构", "程序", "语言",
], key=len, reverse=True)

_SKILL_SUFFIX_RE = re.compile(
    f"({'|'.join(re.escape(s) for s in SUFFIXES)})$"
)

# 熟练度前缀（JD/黄金集标签常带，如"熟悉SQL""了解Python Web"）。
# 剥除顺序：长前缀优先，避免"熟练掌握"只剥"熟练"后残留"掌握"。
_PROFICIENCY_PREFIXES = sorted([
    "熟练掌握", "深入了解", "深入理解", "深刻理解",
    "了解", "熟悉", "掌握", "精通", "熟练",
    "具备", "具有", "拥有", "有过", "做过",
], key=len, reverse=True)

_PROFICIENCY_PREFIX_RE = re.compile(
    f"^({'|'.join(re.escape(p) for p in _PROFICIENCY_PREFIXES)})"
)


def _strip_proficiency_prefix(name: str) -> str:
    """剥离熟练度前缀（"熟悉SQL"→"SQL"，"了解Python Web"→"Python Web"）。"""
    return _PROFICIENCY_PREFIX_RE.sub("", name).strip()


# 白名单小写集合 + 别名小写集合，用于子串包含对齐（T-08 §5.3 人工词典兜底）
_SKILL_WHITELIST_LOWER_SET: set[str] = {w.lower() for w in SKILL_WHITELIST}
_SKILL_ALIAS_LOWER: dict[str, str] = {k.lower(): v for k, v in SKILL_ALIAS.items()}


def _align_to_whitelist(name: str) -> str:
    """子串包含对齐：清洗后的技能名若为白名单词的子串或超串，则对齐到标准名。

    设计文档 §5.3 人工词典兜底的轻量实现（无需 SBERT）：
    - 精确匹配白名单 → 返回标准写法
    - 白名单词是输入的子串（"微服务架构" ⊃ "微服务"）→ 返回标准名
      ※ 仅对 len ≥ 3 的白名单词生效，避免 "AI"/"Go" 等短词误匹配
    - 输入是白名单词的前缀子串（"python web" starts with "Python"）→ 返回标准名
      ※ 同样要求输入长度 ≥ 3
    """
    low = name.lower()
    if low in _SKILL_WHITELIST_LOWER_SET:
        # 精确匹配 → 返回白名单标准写法
        return _SKILL_WHITELIST_LOWER.get(low, name)
    # 白名单词是输入的子串（输入更长）：取最长匹配
    best_match = ""
    best_std = name
    for skill in SKILL_WHITELIST:
        sl = skill.lower()
        if len(sl) >= 3 and sl in low and len(sl) > len(best_match):
            best_match = sl
            best_std = skill
    if best_match:
        return best_std
    # 输入是白名单词的前缀子串（输入更短，至少 3 字符）
    for skill in SKILL_WHITELIST:
        sl = skill.lower()
        if len(low) >= 3 and low == sl[:len(low)]:
            return skill
    return name


def clean_skill_name(name: str) -> str:
    """清洗技能名称：熟练度前缀剥离 + 递归后缀清洗 + 白名单子串对齐。

    设计文档 §5.2/§5.3：
    1. 软技能白名单整体跳过（"项目管理"不以"管理"为后缀退化）
    2. 剥离熟练度前缀（"熟悉SQL"→"SQL"，"了解Python"→"Python"）
    3. 递归剥除中文后缀（"微服务架构设计"→"微服务架构"→"微服务"）
    4. 子串对齐到白名单标准名（"react"→"React"，"微服务架构"→"微服务"）
    """
    if name in SOFT_SKILL_WHITELIST:
        return name

    # 1. 剥离熟练度前缀
    name = _strip_proficiency_prefix(name)

    # 2. 递归剥除后缀
    while True:
        new_name = _SKILL_SUFFIX_RE.sub("", name).strip()
        if new_name == name or not new_name:
            break
        name = new_name

    # 3. 子串对齐到白名单
    name = _align_to_whitelist(name)

    return name


def dedup_skills(skills: list[SkillExtracted]) -> list[SkillExtracted]:
    """按 name 去重（保留首次出现）。"""
    seen: set[str] = set()
    result = []
    for s in skills:
        key = s.name.lower()
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def post_process(result: JDExtractionResult) -> JDExtractionResult:
    """执行完整后处理管线：
    1. 别名归一化
    2. 后缀清洗
    3. 黑名单剔除（行业/业务领域词，防 LLM 幻觉技能入图）
    4. 去重
    """
    # skills 与 requirements 共用同一清洗规则：别名 → 后缀清洗 → 黑名单剔除
    def _clean(name: str) -> str:
        return clean_skill_name(normalize_skill(name))

    result.skills = [
        SkillExtracted(name=_clean(s.name), category=s.category, description=s.description)
        for s in result.skills
        if _clean(s.name) and _clean(s.name) not in SKILL_STOPWORDS
    ]
    result.skills = dedup_skills(result.skills)

    # 软技能：仅保留岗位本体白名单（LLM 越界输出在此拦截，防非白名单词入岗位本体）
    seen_soft: set[str] = set()
    cleaned_soft: list[str] = []
    for s in result.soft_skills:
        name = clean_skill_name(normalize_skill(s)).strip()
        if not name or name in seen_soft or name not in SOFT_SKILL_WHITELIST:
            continue
        seen_soft.add(name)
        cleaned_soft.append(name)
    result.soft_skills = cleaned_soft

    for tool in result.tools:
        tool.name = normalize_skill(tool.name)

    # requirements 与 skills 使用同一清洗规则（避免非标准技能名入图），
    # 并按 (技能, 必要性) 去重，与 skills 去重口径一致
    cleaned_reqs = []
    seen: set[tuple[str, str]] = set()
    for req in result.requirements:
        name = _clean(req.skill_name)
        if not name or name in SKILL_STOPWORDS:
            continue
        key = (name.lower(), req.necessity)
        if key in seen:
            continue
        seen.add(key)
        req.skill_name = name
        cleaned_reqs.append(req)
    result.requirements = cleaned_reqs

    return result

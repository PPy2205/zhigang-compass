"""抽取后处理单元测试（设计文档 §5.2/§5.3）。

覆盖熟练度前缀剥离、递归后缀清洗、白名单子串对齐、别名归一化、去重、requirements 与 skills 同规则。
"""

from app.services.extraction.post_processor import (
    clean_skill_name,
    dedup_skills,
    post_process,
)
from app.services.extraction.schemas import (
    JDExtractionResult,
    REQUIRESRelation,
    SkillExtracted,
)


class TestCleanSkillName:
    def test_removes_chinese_suffix(self):
        # 递归剥除：先剥"工程师"再剥"开发"，最终对齐到白名单标准名
        assert clean_skill_name("Python 开发工程师") == "Python"
        assert clean_skill_name("Docker 技术") == "Docker"
        assert clean_skill_name("数据平台") == "数据"

    def test_recursive_suffix_stripping(self):
        # T-08：递归剥除——"微服务架构设计" → "微服务架构" → "微服务"
        assert clean_skill_name("微服务架构设计") == "微服务"
        assert clean_skill_name("React 开发框架") == "React"

    def test_proficiency_prefix_stripped(self):
        # T-08：熟练度前缀剥离——"熟悉SQL" → "SQL"，"了解Python" → "Python"
        assert clean_skill_name("熟悉SQL") == "SQL"
        assert clean_skill_name("了解Python") == "Python"
        assert clean_skill_name("掌握Docker") == "Docker"
        assert clean_skill_name("精通Kubernetes") == "Kubernetes"

    def test_experience_suffix_stripped(self):
        # T-08：经验/经历后缀剥离——BOSS 标签"微服务经验" → "微服务"
        assert clean_skill_name("微服务经验") == "微服务"
        assert clean_skill_name("机器学习经历") == "机器学习"
        assert clean_skill_name("云计算经验") == "云计算"

    def test_whitelist_substring_alignment(self):
        # T-08：子串包含对齐——"linux开发/部署经验" 中 "Linux" 是子串
        assert clean_skill_name("linux开发/部署经验") == "Linux"
        # "python web" 中 "Python" 是前缀子串
        assert clean_skill_name("python web") == "Python"

    def test_no_suffix_unchanged(self):
        assert clean_skill_name("Python") == "Python"
        assert clean_skill_name("MySQL") == "MySQL"

    def test_empty_input(self):
        assert clean_skill_name("") == ""
        assert clean_skill_name("   ") == ""

    def test_soft_skill_preserved(self):
        # 软技能白名单整体跳过后缀清洗："项目管理"不以"管理"为后缀退化
        assert clean_skill_name("项目管理") == "项目管理"
        assert clean_skill_name("产品设计") == "产品设计"

    def test_microservice_suffix_preserved(self):
        # 微服务是完整技能词，不能被"服务"后缀剥成"微"（历史 bug 回归测试）
        assert clean_skill_name("微服务") == "微服务"
        assert clean_skill_name("微服务架构") == "微服务"
        assert clean_skill_name("云原生") == "云原生"


class TestDedupSkills:
    def test_case_insensitive_dedup_keeps_first(self):
        skills = [
            SkillExtracted(name="Python"),
            SkillExtracted(name="python"),
            SkillExtracted(name="Python"),
        ]
        names = [s.name for s in dedup_skills(skills)]
        assert names == ["Python"]


class TestPostProcess:
    def test_normalize_clean_dedup_full_pipeline(self):
        result = JDExtractionResult(
            position_name="",
            skills=[
                SkillExtracted(name="Docker 技术"),
                SkillExtracted(name="docker 技术"),
                SkillExtracted(name="Go"),
            ],
            requirements=[
                REQUIRESRelation(skill_name="Docker 技术", necessity="must"),
                REQUIRESRelation(skill_name="docker 技术", necessity="must"),
                REQUIRESRelation(skill_name="Go", necessity="nice"),
            ],
        )
        out = post_process(result)
        assert [s.name for s in out.skills] == ["Docker", "Go"]
        # requirements 与 skills 同规则清洗 + 按 (技能, 必要性) 去重
        assert [(r.skill_name, r.necessity) for r in out.requirements] == [
            ("Docker", "must"),
            ("Go", "nice"),
        ]

    def test_skill_and_requirement_same_rule(self):
        """requirements 中出现的技能名清洗后与 skills 同名（保证入图对齐）。"""
        result = JDExtractionResult(
            position_name="",
            skills=[SkillExtracted(name="Kubernetes 技术")],
            requirements=[REQUIRESRelation(skill_name="Kubernetes 技术", necessity="must")],
        )
        out = post_process(result)
        assert out.skills[0].name == out.requirements[0].skill_name == "Kubernetes"

    def test_soft_skills_filtered_to_whitelist(self):
        """soft_skills 仅保留岗位本体白名单 + 去重（LLM 越界输出在此拦截）。"""
        result = JDExtractionResult(
            position_name="",
            soft_skills=["团队协作", "沟通能力", "团队协作", "领导力", "体力好"],
        )
        out = post_process(result)
        assert out.soft_skills == ["团队协作", "沟通能力", "领导力"]

    def test_soft_skill_normalized_before_filter(self):
        """软技能经别名归一化后命中白名单（无别名则原样）。"""
        result = JDExtractionResult(position_name="", soft_skills=["团队协作"])
        out = post_process(result)
        assert out.soft_skills == ["团队协作"]

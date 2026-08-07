"""图谱模块扩展集成测试（TE-M4-01，设计文档 §11.3.9）。

覆盖 test_graph_integration.py 未覆盖的 graph 端点：
position 详情/skills/evidence/similar/skill 详情/algorithms/view。
基础设施不可达时由 conftest 统一 skip。
"""

import httpx
import pytest


def _get_skill_id(client: httpx.Client, auth_headers) -> str | None:
    """从全景图取一个真实技能节点 ID。"""
    pano = client.get(
        "/api/v1/graph/panorama", params={"limit": 100}, headers=auth_headers
    ).json()["data"]
    return next((n["id"] for n in pano["nodes"] if n["type"] == "skill"), None)


def _get_position_id(client: httpx.Client, auth_headers) -> str | None:
    """从全景图取一个真实岗位节点 ID。"""
    pano = client.get(
        "/api/v1/graph/panorama", params={"limit": 100}, headers=auth_headers
    ).json()["data"]
    return next((n["id"] for n in pano["nodes"] if n["type"] == "position"), None)


class TestGraphPosition:
    """岗位节点相关端点。"""

    def test_position_detail(self, client: httpx.Client, auth_headers):
        """岗位详情：must/nice 技能聚合。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        pos_id = _get_position_id(client, auth_headers)
        if not pos_id:
            pytest.skip("图谱无岗位节点")
        r = client.get(f"/api/v1/graph/position/{pos_id}", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "id" in data or "position_id" in data

    def test_position_skills(self, client: httpx.Client, auth_headers):
        """岗位技能列表（可按 necessity 过滤）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        pos_id = _get_position_id(client, auth_headers)
        if not pos_id:
            pytest.skip("图谱无岗位节点")
        r = client.get(f"/api/v1/graph/position/{pos_id}/skills", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestGraphSkill:
    """技能节点相关端点。"""

    def test_skill_detail(self, client: httpx.Client, auth_headers):
        """技能节点详情（关联计数）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        skill_id = _get_skill_id(client, auth_headers)
        if not skill_id:
            pytest.skip("图谱无技能节点")
        r = client.get(f"/api/v1/graph/skill/{skill_id}", headers=auth_headers)
        assert r.status_code == 200

    def test_skill_positions(self, client: httpx.Client, auth_headers):
        """技能反向查询岗位列表。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        skill_id = _get_skill_id(client, auth_headers)
        if not skill_id:
            pytest.skip("图谱无技能节点")
        r = client.get(f"/api/v1/graph/skill/{skill_id}/positions", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))

    def test_skill_evidence(self, client: httpx.Client, auth_headers):
        """技能证据列表（MENTIONED_IN Evidence）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        skill_id = _get_skill_id(client, auth_headers)
        if not skill_id:
            pytest.skip("图谱无技能节点")
        r = client.get(f"/api/v1/graph/skill/{skill_id}/evidence", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestGraphSimilar:
    """相似技能检索。"""

    def test_similar_skills(self, client: httpx.Client, auth_headers):
        """语义相似度 Top-K（需 SBERT，可能较慢）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(
            "/api/v1/graph/skill/similar",
            params={"q": "Python", "top_k": 5},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestGraphAlgorithms:
    """图算法端点。"""

    def test_pagerank(self, client: httpx.Client, auth_headers):
        """PageRank 技能重要性 Top-N。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(
            "/api/v1/graph/algorithms/pagerank",
            params={"top_n": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))

    def test_skill_clusters(self, client: httpx.Client, auth_headers):
        """Louvain 技能簇。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/graph/algorithms/skill-clusters", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestGraphViews:
    """视图切换端点。"""

    @pytest.mark.parametrize("view_type", ["panorama", "techStack", "level", "positionCenter"])
    def test_view_switch(self, client: httpx.Client, auth_headers, view_type):
        """四种视图均返回合法结构。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(f"/api/v1/graph/view/{view_type}", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "nodes" in data or "stats" in data

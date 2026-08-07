"""演化模块集成测试（TE-M4-01，设计文档 §11.3.9）。

覆盖 evolution 端点：diff/signals/versions 详情/trends/state-machine/watch。
大部分端点从 graph_versions 快照（PostgreSQL）读取，不依赖 Neo4j；
仅 test_position_evolution 调用 /graph/panorama 需 Neo4j。
PG+Redis 不可达时由 conftest 统一 skip。
"""

import httpx
import pytest


class TestEvolutionVersions:
    """版本列表与详情。"""

    def test_versions_list(self, client: httpx.Client, auth_headers):
        """版本列表分页结构合法（已有测试，此处补充详情）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/evolution/versions", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] >= 0

    def test_version_detail(self, client: httpx.Client, auth_headers):
        """版本详情：元信息 + 快照统计 + 节点列表。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        versions = client.get("/api/v1/evolution/versions", headers=auth_headers).json()["data"]
        if not versions["items"]:
            pytest.skip("无图谱版本快照")
        vid = versions["items"][0]["version_id"]
        r = client.get(f"/api/v1/evolution/versions/{vid}", headers=auth_headers)
        assert r.status_code == 200


class TestEvolutionDiff:
    """版本 Diff 对比。"""

    def test_diff_two_versions(self, client: httpx.Client, auth_headers):
        """两个版本快照 Diff 对比（需至少 2 个版本）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        versions = client.get("/api/v1/evolution/versions", headers=auth_headers).json()["data"]
        if len(versions["items"]) < 2:
            pytest.skip("不足 2 个版本快照，跳过 Diff 用例")
        v1 = versions["items"][0]["version_id"]
        v2 = versions["items"][1]["version_id"]
        r = client.get(
            "/api/v1/evolution/diff",
            params={"from_version": v2, "to_version": v1},
            headers=auth_headers,
        )
        assert r.status_code == 200


class TestEvolutionSignals:
    """新兴/衰退技能信号。"""

    def test_signals_top_n(self, client: httpx.Client, auth_headers):
        """Z-score 信号 Top-N。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(
            "/api/v1/evolution/signals",
            params={"top_n": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestEvolutionTrends:
    """技能频次趋势。"""

    def test_trends(self, client: httpx.Client, auth_headers):
        """技能频次趋势（从版本快照统计）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(
            "/api/v1/evolution/trends",
            params={"skill": "Python"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestEvolutionStateMachine:
    """岗位状态机总览。"""

    def test_state_machine(self, client: httpx.Client, auth_headers):
        """六态分布 + 最近流转记录。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/evolution/state-machine", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestEvolutionWatch:
    """观察池公开摘要。"""

    def test_watch(self, client: httpx.Client, auth_headers):
        """观察池摘要 + MLI 产业化拐点排名。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/evolution/watch", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], (list, dict))


class TestEvolutionPositionHistory:
    """岗位演化历史。"""

    def test_position_evolution(self, client: httpx.Client, auth_headers, neo4j_available):
        """岗位节点存在性与引用边数变化。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        if not neo4j_available:
            pytest.skip("Neo4j 不可达，跳过图谱依赖用例")
        # 取一个真实岗位 ID
        pano = client.get(
            "/api/v1/graph/panorama", params={"limit": 50}, headers=auth_headers
        ).json()["data"]
        pos_id = next((n["id"] for n in pano["nodes"] if n["type"] == "position"), None)
        if not pos_id:
            pytest.skip("图谱无岗位节点")
        r = client.get(f"/api/v1/evolution/position/{pos_id}/evolution", headers=auth_headers)
        assert r.status_code == 200

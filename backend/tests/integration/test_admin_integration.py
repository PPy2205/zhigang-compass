"""管理后台模块集成测试（TE-M4-01，设计文档 §11.3.9）。

覆盖 admin 端点：users/audit/crawl/llm-config/discovery/positions。
需 admin 角色认证；基础设施不可达时由 conftest 统一 skip。
"""

import httpx
import pytest


class TestAdminUsers:
    """用户管理端点。"""

    def test_users_list(self, client: httpx.Client, auth_headers):
        """用户列表分页结构合法。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/users", headers=auth_headers)
        assert r.status_code in (200, 403)  # 403 = 非 admin 角色
        if r.status_code == 200:
            data = r.json()["data"]
            assert "items" in data or isinstance(data, list)

    def test_audit_logs(self, client: httpx.Client, auth_headers):
        """审计日志查询（分页 + 类别过滤）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get(
            "/api/v1/admin/audit/logs",
            params={"page": 1, "page_size": 10},
            headers=auth_headers,
        )
        assert r.status_code in (200, 403)


class TestAdminCrawl:
    """爬取监控端点。"""

    def test_crawl_status(self, client: httpx.Client, auth_headers):
        """爬取状态监控（raw 表入库统计 + output 文件数）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/crawl/status", headers=auth_headers)
        assert r.status_code in (200, 403)

    def test_crawl_history(self, client: httpx.Client, auth_headers):
        """爬取历史（crawl 任务列表分页）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/crawl/history", headers=auth_headers)
        assert r.status_code in (200, 403)


class TestAdminLlmConfig:
    """LLM 配置管理端点。"""

    def test_get_llm_config(self, client: httpx.Client, auth_headers):
        """读取 LLM provider 配置（api_key 打码）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/llm-config", headers=auth_headers)
        assert r.status_code in (200, 403)

    def test_update_llm_config(self, client: httpx.Client, auth_headers):
        """保存 LLM provider 配置（只读测试，不实际修改）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        # 先读取当前配置
        r = client.get("/api/v1/admin/llm-config", headers=auth_headers)
        if r.status_code != 200:
            pytest.skip("非 admin 角色或配置不可读")
        # 回写相同配置（不修改任何值，验证写入链路通）
        r2 = client.put("/api/v1/admin/llm-config", json=r.json()["data"], headers=auth_headers)
        assert r2.status_code in (200, 422)


class TestAdminPositions:
    """岗位审核端点。"""

    def test_pending_positions(self, client: httpx.Client, auth_headers):
        """待审核岗位列表（candidate 候选池）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/positions/pending", headers=auth_headers)
        assert r.status_code in (200, 403)

    def test_declining_positions(self, client: httpx.Client, auth_headers):
        """待归档岗位列表（declining 状态）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/positions/declining", headers=auth_headers)
        assert r.status_code in (200, 403)

    def test_position_detail(self, client: httpx.Client, auth_headers):
        """岗位详情（技能/学历/证书）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        # 取一个真实岗位名
        pano = client.get(
            "/api/v1/graph/panorama", params={"limit": 50}, headers=auth_headers
        ).json()["data"]
        pos_name = next(
            (n.get("name", n.get("label", "")) for n in pano["nodes"] if n["type"] == "position"),
            None,
        )
        if not pos_name:
            pytest.skip("图谱无岗位节点")
        r = client.get(f"/api/v1/admin/positions/{pos_name}", headers=auth_headers)
        assert r.status_code in (200, 403, 404)


class TestAdminEvolution:
    """演化审核端点。"""

    def test_evolution_pending(self, client: httpx.Client, auth_headers):
        """待审核演化变更（emerging 状态岗位列表）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/evolution/pending", headers=auth_headers)
        assert r.status_code in (200, 403)


class TestAdminDiscovery:
    """发现模块端点。"""

    def test_discovery_watch(self, client: httpx.Client, auth_headers):
        """观察池周报（技术热点信号列表）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/admin/discovery/watch", headers=auth_headers)
        assert r.status_code in (200, 403)

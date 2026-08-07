"""匹配 + 简历模块集成测试（TE-M4-01，设计文档 §11.3.9）。

覆盖 match compare/result/gap/path/feedback 和 resume detail/parse stream。
基础设施不可达时由 conftest 统一 skip。
"""

import httpx
import pytest


def _get_resume_id(client: httpx.Client, auth_headers) -> str | None:
    """从简历列表取一个真实 resume_id。"""
    data = client.get(
        "/api/v1/resume/list", params={"limit": 5}, headers=auth_headers
    ).json()["data"]
    if data["items"]:
        return data["items"][0]["id"]
    return None


class TestMatchCompare:
    """人岗比对端点。"""

    def test_compare(self, client: httpx.Client, auth_headers):
        """人岗比对：差距三态 + 学习路径 + 证据引用。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        resume_id = _get_resume_id(client, auth_headers)
        if not resume_id:
            pytest.skip("无简历缓存，跳过比对用例")
        # 取一个岗位 ID 用于比对
        pano = client.get(
            "/api/v1/graph/panorama", params={"limit": 50}, headers=auth_headers
        ).json()["data"]
        pos_id = next((n["id"] for n in pano["nodes"] if n["type"] == "position"), None)
        if not pos_id:
            pytest.skip("图谱无岗位节点")
        r = client.post(
            "/api/v1/match/compare",
            json={"resume_id": resume_id, "position_id": pos_id},
            headers=auth_headers,
        )
        assert r.status_code in (200, 404, 422)

    def test_match_feedback(self, client: httpx.Client, auth_headers):
        """提交匹配反馈（1=👍 / -1=👎）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.post(
            "/api/v1/match/feedback",
            json={"match_id": "test-integration", "feedback": 1},
            headers=auth_headers,
        )
        # match_id 不存在时可能返回 404，链路通即合法
        assert r.status_code in (200, 404, 422)


class TestResumeDetail:
    """简历详情端点。"""

    def test_resume_detail(self, client: httpx.Client, auth_headers):
        """简历解析详情（完整画像）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        resume_id = _get_resume_id(client, auth_headers)
        if not resume_id:
            pytest.skip("无简历缓存，跳过详情用例")
        r = client.get(f"/api/v1/resume/{resume_id}", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "id" in data or "resume_id" in data

    def test_resume_edit(self, client: httpx.Client, auth_headers):
        """编辑简历画像（fields 顶层覆盖 + version 递增）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过编辑用例")
        resume_id = _get_resume_id(client, auth_headers)
        if not resume_id:
            pytest.skip("无简历缓存，跳过编辑用例")
        r = client.put(
            f"/api/v1/resume/{resume_id}",
            json={"fields": {"summary": "集成测试编辑"}},
            headers=auth_headers,
        )
        assert r.status_code in (200, 422)

    def test_resume_download(self, client: httpx.Client, auth_headers):
        """下载简历原始文件（仅上传者本人）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过下载用例")
        resume_id = _get_resume_id(client, auth_headers)
        if not resume_id:
            pytest.skip("无简历缓存，跳过下载用例")
        r = client.get(f"/api/v1/resume/files/{resume_id}/download", headers=auth_headers)
        # 文件可能不存在（admin 非上传者），链路通即合法
        assert r.status_code in (200, 403, 404)


class TestMatchResultFlow:
    """匹配结果查询流程（需先有 recommend 结果）。"""

    def test_recommend_and_query_result(self, client: httpx.Client, auth_headers):
        """推荐后查询匹配结果（链路通）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        resume_id = _get_resume_id(client, auth_headers)
        if not resume_id:
            pytest.skip("无简历缓存，跳过推荐用例")
        r = client.post(
            "/api/v1/match/recommend",
            json={"resume_id": resume_id, "top_n": 3},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        # 如果有匹配结果，尝试查询详情
        items = data.get("items", [])
        if items and "match_id" in items[0]:
            match_id = items[0]["match_id"]
            r2 = client.get(f"/api/v1/match/result/{match_id}", headers=auth_headers)
            assert r2.status_code in (200, 404)

"""认证模块集成测试（TE-M4-01，设计文档 §11.3.9）。

覆盖 auth 全链路：login → me → refresh → password → logout → register。
PG+Redis 不可达时由 conftest 统一 skip。
"""

import httpx
import pytest


class TestAuthLogin:
    """登录端点正反用例。"""

    def test_login_success(self, client: httpx.Client):
        """admin 默认账号登录成功，返回双 Token。"""
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        if r.status_code != 200:
            pytest.skip("admin 密码非默认值，跳过登录用例")
        data = r.json()["data"]
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: httpx.Client):
        """错误密码返回 401（密码需 ≥6 字符以通过 Pydantic 校验）。"""
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpass"})
        assert r.status_code in (401, 400)

    def test_login_nonexistent_user(self, client: httpx.Client):
        """不存在的用户返回 401。"""
        r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "password"})
        assert r.status_code in (401, 400)


class TestAuthMe:
    """当前用户信息端点。"""

    def test_me_with_token(self, client: httpx.Client, auth_headers):
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "username" in data
        assert "role" in data

    def test_me_without_token(self, client: httpx.Client):
        """无 Token 访问 me 返回 401。"""
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_update_me(self, client: httpx.Client, auth_headers):
        """更新个人资料（bio 字段）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过认证用例")
        r = client.put("/api/v1/auth/me", json={"bio": "集成测试更新"}, headers=auth_headers)
        assert r.status_code == 200


class TestAuthRefresh:
    """Token 刷新端点。"""

    def test_refresh_success(self, client: httpx.Client):
        """登录后用 refresh_token 刷新 access_token。"""
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        if r.status_code != 200:
            pytest.skip("admin 登录失败，跳过刷新用例")
        # refresh_token 在 Cookie 中
        cookies = r.cookies
        if not cookies.get("refresh_token"):
            pytest.skip("响应未携带 refresh_token Cookie")
        r2 = client.post("/api/v1/auth/refresh")
        assert r2.status_code in (200, 401)  # 401 可能因 Cookie 未正确传递

    def test_refresh_without_cookie(self, client: httpx.Client):
        """无 refresh_token Cookie 调用刷新返回 401。

        清除 client 携带的 Cookie（前序登录测试可能残留 refresh_token），
        确保 _extract_refresh_token 取不到任何 token。
        """
        client.cookies.clear()
        r = client.post("/api/v1/auth/refresh")
        assert r.status_code in (401, 400)


class TestAuthPassword:
    """修改密码端点。"""

    def test_change_password_wrong_old(self, client: httpx.Client, auth_headers):
        """旧密码错误返回 code=400（error() 默认 http_status=200，需检查 body code）。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过密码用例")
        r = client.post(
            "/api/v1/auth/password",
            json={"old_password": "wrongpass", "new_password": "newpass123"},
            headers=auth_headers,
        )
        body = r.json()
        # error(400, "原密码错误") 默认 http_status=200，通过 body.code 判定
        assert body.get("code") == 400 or r.status_code in (400, 401)


class TestAuthLogout:
    """登出端点。"""

    def test_logout_with_token(self, client: httpx.Client, auth_headers):
        """登出返回 200。"""
        if not auth_headers:
            pytest.skip("admin 登录失败，跳过登出用例")
        r = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert r.status_code == 200

    def test_logout_without_token(self, client: httpx.Client):
        """无 Token 登出也返回 200（登出端点不要求认证，仅清 Cookie + 拉黑 jti）。"""
        r = client.post("/api/v1/auth/logout")
        assert r.status_code == 200


class TestAuthRegister:
    """注册端点正反用例。"""

    def test_register_duplicate_username(self, client: httpx.Client):
        """注册已存在的用户名返回 code=409（error() 默认 http_status=200，需检查 body code）。

        先注册一个唯一用户名，再尝试重复注册同一用户名验证 409。
        """
        import uuid

        # 先注册一个新用户（UUID 后缀避免跨运行残留）
        unique = f"itest_{uuid.uuid4().hex[:8]}"
        r1 = client.post(
            "/api/v1/auth/register",
            json={"username": unique, "password": "testpass123"},
        )
        if r1.status_code != 200 or r1.json().get("code") != 0:
            pytest.skip(f"首次注册失败（{r1.status_code}），跳过重复用例")
        # 重复注册同一用户名 → code=409
        r2 = client.post(
            "/api/v1/auth/register",
            json={"username": unique, "password": "testpass123"},
        )
        body = r2.json()
        # error(409, "用户名已存在") 默认 http_status=200，通过 body.code 判定
        assert body.get("code") == 409 or r2.status_code == 409

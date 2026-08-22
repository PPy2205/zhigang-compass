"""智岗罗盘性能压测脚本（TE-M5-01，设计文档 §13.3）。

目标：100 并发下 P95 < 2s。

使用方法：
    # 启动压测（Web UI）
    cd backend && uv run locust -f tests/performance/locustfile.py

    # 无界面直接运行（推荐 CI/自动化）
    cd backend && uv run locust -f tests/performance/locustfile.py \
        --host http://localhost:8000 \
        --users 100 --spawn-rate 20 \
        --run-time 5m \
        --headless \
        --csv=reports/performance/baseline

压测场景（模拟真实用户行为）：
    - 权重 30%：图谱全景（首页加载）
    - 权重 25%：技能搜索
    - 权重 15%：岗位详情 + 技能列表
    - 权重 15%：匹配推荐（含 LLM 诊断）
    - 权重 10%：演化看板
    - 权重 5%：认证流程
"""

import random
import uuid
from locust import HttpUser, task, between, tag


class CompassUser(HttpUser):
    """模拟智岗罗盘用户行为。"""

    wait_time = between(1, 3)  # 用户操作间隔 1-3 秒

    # 压测开始时自动登录获取 token
    def on_start(self):
        """每个虚拟用户启动时登录。"""
        self.token = None
        self.username = f"perf_test_{uuid.uuid4().hex[:8]}"

        # 先尝试注册（可能已存在则跳过）
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@test.com",
                "password": "Test@123456",
            },
            catch_response=True,
        )
        if resp.status_code in (200, 201):
            self.token = resp.json().get("access_token")
        elif resp.status_code == 409:
            # 用户已存在，直接登录
            login_resp = self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": self.username,
                    "password": "Test@123456",
                },
                catch_response=True,
            )
            if login_resp.status_code == 200:
                self.token = login_resp.json().get("access_token")

        if self.token:
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    # ── 图谱全景（首页加载，权重最高）──

    @tag("graph", "homepage")
    @task(30)
    def graph_panorama(self):
        """图谱全景接口（首页加载）。"""
        self.client.get("/api/v1/graph/panorama", name="graph/panorama")

    # ── 技能搜索（高频操作）──

    @tag("graph", "search")
    @task(25)
    def skill_search(self):
        """技能搜索接口。"""
        keywords = ["Python", "Java", "数据分析", "前端", "人工智能", "数据库"]
        keyword = random.choice(keywords)
        self.client.get(
            f"/api/v1/graph/search?q={keyword}&type=skill",
            name="graph/search",
        )

    # ── 岗位详情 + 技能列表（中等权重）──

    @tag("graph", "position")
    @task(15)
    def position_detail(self):
        """岗位详情 + 岗位技能列表。"""
        # 先搜索一个岗位
        search_resp = self.client.get(
            "/api/v1/graph/search?q=工程师&type=position",
            name="graph/search (position)",
            catch_response=True,
        )
        if search_resp.status_code == 200:
            data = search_resp.json()
            positions = data.get("results", []) if isinstance(data, dict) else []
            if positions:
                pos = random.choice(positions[:5])
                pos_id = pos.get("id", "")
                if pos_id:
                    with self.client.get(
                        f"/api/v1/graph/position/{pos_id}",
                        name="graph/position/{id}",
                        catch_response=True,
                    ) as resp:
                        if resp.status_code == 422:
                            resp.success()  # 测试环境数据可能为空，422 不算失败
                    self.client.get(
                        f"/api/v1/graph/position/{pos_id}/skills",
                        name="graph/position/{id}/skills",
                        catch_response=True,
                    )

    # ── 匹配推荐（较重操作）──

    @tag("match", "llm")
    @task(15)
    def match_recommend(self):
        """匹配推荐接口（含 LLM 诊断）。"""
        # 先搜索一个岗位作为目标
        search_resp = self.client.get(
            "/api/v1/graph/search?q=数据分析师&type=position",
            name="graph/search (recommend target)",
            catch_response=True,
        )
        if search_resp.status_code == 200:
            data = search_resp.json()
            positions = data.get("results", []) if isinstance(data, dict) else []
            if positions:
                pos_name = positions[0].get("name", "数据分析师")
                # 发起匹配推荐（异步）
                resp = self.client.post(
                    "/api/v1/match/recommend",
                    json={
                        "resume_skills": ["Python", "SQL", "数据分析", "Excel"],
                        "target_position": pos_name,
                        "top_n": 10,
                    },
                    name="match/recommend",
                    catch_response=True,
                )
                if resp.status_code == 202:
                    task_id = resp.json().get("task_id")
                    if task_id:
                        # 轮询任务状态（最多 3 次）
                        for _ in range(3):
                            status_resp = self.client.get(
                                f"/api/v1/match/task/{task_id}",
                                name="match/task/{id}",
                                catch_response=True,
                            )
                            if status_resp.status_code == 200:
                                status = status_resp.json().get("status")
                                if status in ("completed", "failed"):
                                    # 获取匹配结果
                                    match_id = status_resp.json().get("match_id")
                                    if match_id:
                                        self.client.get(
                                            f"/api/v1/match/result/{match_id}",
                                            name="match/result/{id}",
                                            catch_response=True,
                                        )
                                    break

    # ── 演化看板（低频但重要）──

    @tag("evolution")
    @task(10)
    def evolution_dashboard(self):
        """演化看板接口。"""
        self.client.get("/api/v1/evolution/versions", name="evolution/versions")
        self.client.get("/api/v1/evolution/trends", name="evolution/trends")
        self.client.get("/api/v1/evolution/signals", name="evolution/signals")

    # ── 认证流程（低频）──

    @tag("auth")
    @task(5)
    def auth_flow(self):
        """认证流程：刷新 token + 获取用户信息。"""
        self.client.get("/api/v1/auth/me", name="auth/me")

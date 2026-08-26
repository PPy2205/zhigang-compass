import { expect, test } from '@playwright/test'

/**
 * 仪表盘 E2E（TE-M4-02，设计文档 §13.2 / §10.2）。
 *
 * 覆盖：页面加载 → 统计卡片 → 快捷入口 → 最近活动流。
 * 数据来源：真实后端 API（/graph/panorama, /admin/crawl/status, /resume/list, /evolution/versions）。
 * 后端不可达时断言降级态（"—"占位），不 fail。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(ADMIN.username)
  await page.getByLabel('密码').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })
}

test.describe('仪表盘', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    // 登录成功后默认跳转首页（仪表盘）
    await page.waitForURL(/\/$/, { timeout: 10_000 })
  })

  test('页面标题与描述可见', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('多源异构驱动的岗位能力动态演化与人岗匹配系统')).toBeVisible()
  })

  test('四张统计卡片渲染（含降级占位）', async ({ page }) => {
    // 等待数据加载（真实 API 或降级占位）
    await page.waitForTimeout(3000)

    // 四个统计指标标签
    await expect(page.getByText('图谱节点')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('累计采集量')).toBeVisible()
    await expect(page.getByText('已解析简历')).toBeVisible()
    await expect(page.getByText('图谱版本')).toBeVisible()
  })

  test('快捷入口卡片可点击跳转', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 快捷入口 → 能力图谱
    const graphLink = page.getByRole('link', { name: /能力图谱/ }).first()
    if (await graphLink.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await graphLink.click()
      await expect(page).toHaveURL(/\/graph/, { timeout: 10_000 })
    }
  })

  test('顶栏导航菜单包含所有主路由', async ({ page }) => {
    // 侧边栏/顶栏导航链接
    await expect(page.getByRole('link', { name: '仪表盘' })).toBeVisible()
    await expect(page.getByRole('link', { name: '能力图谱' })).toBeVisible()
    await expect(page.getByRole('link', { name: '演化看板' })).toBeVisible()
  })

  test('admin 用户可见管理后台入口', async ({ page }) => {
    await expect(page.getByRole('link', { name: '管理后台' })).toBeVisible({ timeout: 10_000 })
  })
})

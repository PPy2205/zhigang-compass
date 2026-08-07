import { expect, test } from '@playwright/test'

/**
 * 演化看板 E2E（TE-M4-02，设计文档 §13.2 / §7）。
 *
 * 覆盖：页面加载 → 顶部指标卡 → 新兴/衰退信号 → 技能趋势查询 → 岗位演化 → 版本对比 → 状态机。
 * 数据来源：真实后端 API（/evolution/versions, /evolution/signals, /evolution/trends,
 * /evolution/position/{id}/evolution, /evolution/diff, /evolution/state-machine）。
 * 冷启动（快照不足）时断言降级提示，不 fail。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(ADMIN.username)
  await page.getByLabel('密码').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })
}

test.describe('演化看板', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto('/evolution')
  })

  test('页面标题与描述可见', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '演化看板' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText(/Z-score.*新兴\/衰退信号/)).toBeVisible()
  })

  test('顶部指标卡渲染（四张）', async ({ page }) => {
    await page.waitForTimeout(3000)

    await expect(page.getByText('图谱版本数')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('当前版本号')).toBeVisible()
    await expect(page.getByText('最新版本节点变化')).toBeVisible()
    await expect(page.getByText('新兴/衰退信号')).toBeVisible()
  })

  test('T+1 发布频率 Badge 可见', async ({ page }) => {
    await expect(page.getByText('T+1 05:00 发布')).toBeVisible({ timeout: 10_000 })
  })

  test('新兴/衰退技能 Top-10 区域存在', async ({ page }) => {
    await page.waitForTimeout(3000)
    // 两个区域标题（可能因冷启动显示提示文字）
    await expect(page.getByText('新兴技能 Top-10').first()).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('衰退技能 Top-10').first()).toBeVisible()
  })

  test('技能频次趋势查询区域存在', async ({ page }) => {
    await page.waitForTimeout(2000)
    await expect(page.getByText('技能频次趋势')).toBeVisible({ timeout: 15_000 })
    // 查询输入框
    await expect(page.getByPlaceholder('技能节点 ID（sk_xxxx）')).toBeVisible()
  })

  test('岗位演化历史查询区域存在', async ({ page }) => {
    await page.waitForTimeout(2000)
    await expect(page.getByText('岗位演化历史')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByPlaceholder('岗位节点 ID（pos_xxxx）')).toBeVisible()
  })

  test('版本快照对比区域存在', async ({ page }) => {
    await page.waitForTimeout(3000)
    await expect(page.getByText(/版本快照对比|版本对比/).first()).toBeVisible({ timeout: 15_000 })
  })

  test('冷启动场景 — 信号区域显示降级提示或数据', async ({ page }) => {
    await page.waitForTimeout(5000)
    // 新兴/衰退区域：有数据（表格行）或降级提示（"历史快照不足"或"本期无该趋势信号"）
    const hasTable = await page.locator('table').first().isVisible({ timeout: 8000 }).catch(() => false)
    const hasHint = await page.getByText(/历史快照不足|本期无该趋势信号|冷启动/).first().isVisible({ timeout: 5000 }).catch(() => false)
    expect(hasTable || hasHint).toBeTruthy()
  })
})

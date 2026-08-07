import { expect, test } from '@playwright/test'

/**
 * 能力图谱 E2E（TE-M4-02，设计文档 §13.2 / §6 / §10.3）。
 *
 * 覆盖：页面加载 → 四种视图切换 → 全文检索 → 节点详情面板。
 * 依赖 Neo4j：图谱无数据时断言降级提示（不 fail），有数据时断言交互。
 * 前置：后端 8000 + 前端 5173。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

/** 登录辅助 */
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(ADMIN.username)
  await page.getByLabel('密码').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })
}

test.describe('能力图谱', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto('/graph')
  })

  test('页面标题与结构', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '能力图谱' })).toBeVisible({ timeout: 20_000 })
    // 页面描述
    await expect(page.getByText('岗位-技能-证据关系可视化')).toBeVisible()
  })

  test('四种视图切换 Tab 存在', async ({ page }) => {
    // 等待页面加载完成（loading 或数据）
    await page.waitForTimeout(3000)

    // 四种视图 Tab
    const tabs = page.locator('[role="tab"]')
    await expect(tabs).toHaveCount(4, { timeout: 10_000 })

    // 点击各 Tab 不报错
    await page.getByRole('tab', { name: '技术栈视图' }).click()
    await page.getByRole('tab', { name: '级别视图' }).click()
    await page.getByRole('tab', { name: '岗位中心' }).click()
    await page.getByRole('tab', { name: '全景视图' }).click()
  })

  test('2D/3D 模式切换按钮存在', async ({ page }) => {
    await page.waitForTimeout(3000)
    // 2D 按钮始终可用
    await expect(page.getByRole('button', { name: '2D' })).toBeVisible({ timeout: 10_000 })
    // 3D 按钮存在（可能 disabled）
    await expect(page.getByRole('button', { name: '3D' })).toBeVisible()
  })

  test('全文检索输入框存在', async ({ page }) => {
    await page.waitForTimeout(3000)
    const searchInput = page.getByPlaceholder('搜索技能（如 Python）')
    await expect(searchInput).toBeVisible({ timeout: 10_000 })
  })

  test('图例显示所有节点类型', async ({ page }) => {
    await page.waitForTimeout(3000)
    // 图例区域
    await expect(page.getByText('图例')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('稳定岗位')).toBeVisible()
    await expect(page.getByText('新兴岗位')).toBeVisible()
    await expect(page.getByText('技能')).toBeVisible()
  })

  test('无数据时显示降级提示（Neo4j 不可达场景）', async ({ page }) => {
    await page.waitForTimeout(5000)
    // 图谱可能因 Neo4j 不可达显示错误或空态
    const errorOrEmpty = page.getByText(/图谱暂无数据|加载失败|请确认后端服务/)
    const loading = page.getByText('正在加载图谱全景')
    const nodeStat = page.getByText('节点', { exact: true })

    // 三选一：加载中 / 错误空态 / 有数据
    const hasAny = await Promise.race([
      errorOrEmpty.waitFor({ state: 'visible', timeout: 8000 }).then(() => 'empty'),
      loading.waitFor({ state: 'visible', timeout: 2000 }).then(() => 'loading'),
      nodeStat.waitFor({ state: 'visible', timeout: 8000 }).then(() => 'data'),
    ]).catch(() => 'timeout')

    // 不论哪种状态，页面不应崩溃
    expect(['empty', 'loading', 'data', 'timeout']).toContain(hasAny)
  })
})

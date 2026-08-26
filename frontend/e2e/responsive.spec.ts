import { expect, test } from '@playwright/test'

/**
 * 响应式布局 E2E（FE-M5-02，设计文档 §10.5 三断点）。
 *
 * 三视口验证：
 * - 桌面 (1280x800)：侧边栏可见 + 顶部导航完整
 * - 平板 (768x1024)：侧边栏隐藏 + 汉堡菜单 + 内容全宽
 * - 移动 (393x851)：底部 Tab 导航 + 汉堡菜单 + 单栏布局
 *
 * 由 playwright.config.ts 的 tablet/mobile 项目运行，chromium 项目跳过。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

test.describe('响应式布局 — 三断点验证', () => {
  test('移动端：底部导航可见 + 侧边栏隐藏', async ({ page, isMobile }) => {
    test.skip(!isMobile, '仅移动设备执行')

    await page.goto('/')
    // 移动端底部导航栏可见
    await expect(page.locator('nav[aria-label="底部导航"]')).toBeVisible()
    // 桌面侧边栏不可见
    await expect(page.locator('aside').filter({ hasText: /导航菜单|智岗罗盘/ }).first()).not.toBeInViewport()
    // 汉堡菜单按钮可见
    await expect(page.getByLabel('打开导航菜单')).toBeVisible()
  })

  test('移动端：底部导航 Tab 点击可切换路由', async ({ page, isMobile }) => {
    test.skip(!isMobile, '仅移动设备执行')

    await page.goto('/')
    const bottomNav = page.locator('nav[aria-label="底部导航"]')
    await expect(bottomNav).toBeVisible()

    // 点击"能力图谱" Tab
    await bottomNav.getByRole('link', { name: '能力图谱' }).click()
    await expect(page).toHaveURL(/\/graph/)

    // 点击"演化看板" Tab
    await bottomNav.getByRole('link', { name: '演化看板' }).click()
    await expect(page).toHaveURL(/\/evolution/)
  })

  test('移动端：汉堡菜单可打开侧边栏抽屉', async ({ page, isMobile }) => {
    test.skip(!isMobile, '仅移动设备执行')

    await page.goto('/')
    // 初始状态侧边栏不可见
    const sidebar = page.locator('aside').filter({ hasText: '导航菜单' }).first()
    await expect(sidebar).not.toBeInViewport()

    // 点击汉堡菜单
    await page.getByLabel('打开导航菜单').click()
    await expect(sidebar).toBeVisible()

    // 点击遮罩关闭
    await page.locator('.fixed.inset-0.bg-black\\/40').click()
    await expect(sidebar).not.toBeInViewport()
  })

  test('平板端：侧边栏隐藏 + 汉堡菜单 + 内容全宽', async ({ page, viewport }) => {
    test.skip(viewport.width < 600 || viewport.width > 900, '仅平板视口执行')

    await page.goto('/')
    // 桌面侧边栏不可见
    const desktopSidebar = page.locator('aside.hidden.lg\\:flex')
    await expect(desktopSidebar).not.toBeVisible()
    // 汉堡菜单可见
    await expect(page.getByLabel('打开导航菜单')).toBeVisible()
    // 底部导航不可见（平板非移动端）
    await expect(page.locator('nav[aria-label="底部导航"]')).not.toBeVisible()
  })

  test('平板端：汉堡菜单可打开侧边栏', async ({ page, viewport }) => {
    test.skip(viewport.width < 600 || viewport.width > 900, '仅平板视口执行')

    await page.goto('/')
    await page.getByLabel('打开导航菜单').click()

    const drawerSidebar = page.locator('aside').filter({ hasText: '导航菜单' }).first()
    await expect(drawerSidebar).toBeVisible()
    await expect(drawerSidebar.getByText('仪表盘')).toBeVisible()
  })

  test('桌面端：侧边栏可见 + 底部导航隐藏', async ({ page, viewport }) => {
    test.skip(viewport.width < 1000, '仅桌面视口执行')

    await page.goto('/')
    // 桌面侧边栏可见
    const desktopSidebar = page.locator('aside.hidden.lg\\:flex')
    await expect(desktopSidebar).toBeVisible()
    // 底部导航不可见
    await expect(page.locator('nav[aria-label="底部导航"]')).not.toBeVisible()
    // 汉堡菜单不可见（桌面端不需要）
    await expect(page.getByLabel('打开导航菜单')).not.toBeVisible()
  })

  test('桌面端：侧边栏导航可跳转', async ({ page, viewport }) => {
    test.skip(viewport.width < 1000, '仅桌面视口执行')

    await page.goto('/')
    const sidebar = page.locator('aside.hidden.lg\\:flex')
    await sidebar.getByRole('link', { name: '能力图谱' }).click()
    await expect(page).toHaveURL(/\/graph/)
  })
})

test.describe('响应式 — 关键页面无横向滚动', () => {
  async function checkNoHorizontalScroll(page: import('@playwright/test').Page) {
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
    // 允许 1px 的误差（subpixel 渲染）
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1)
  }

  test('登录页无横向滚动', async ({ page }) => {
    await page.goto('/login')
    await checkNoHorizontalScroll(page)
  })

  test('仪表盘无横向滚动', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill(ADMIN.password)
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page).toHaveURL(/\//, { timeout: 20_000 })
    await checkNoHorizontalScroll(page)
  })

  test('图谱页无横向滚动', async ({ page }) => {
    await page.goto('/graph')
    await checkNoHorizontalScroll(page)
  })

  test('简历匹配页无横向滚动', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill(ADMIN.password)
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page).toHaveURL(/\//, { timeout: 20_000 })

    await page.goto('/resume-match')
    await checkNoHorizontalScroll(page)
  })
})

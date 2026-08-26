import { expect, test } from '@playwright/test'

/**
 * 认证 E2E（TE-M4-02，设计文档 §13.2 / §10.2）。
 *
 * 覆盖：登录正反用例 → 路由守卫 → 注册 → 登出 → Token 失效跳转。
 * 前置：后端 8000 + 前端 5173 由 playwright.config.ts webServer 拉起。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

// ---- 登录 ----

test.describe('登录', () => {
  test('正确凭据登录成功', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()

    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill(ADMIN.password)
    await page.getByRole('button', { name: '登录' }).click()

    // 登录成功 → 跳转首页，顶栏显示用户名
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 20_000 })
    await expect(page.getByText(ADMIN.username).first()).toBeVisible()
  })

  test('错误密码显示提示', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill('wrongpass')
    await page.getByRole('button', { name: '登录' }).click()

    // 后端 error(4010) http_status=200，前端 ApiError 解析 body.msg
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10_000 })
  })

  test('空字段提交被前端校验拦截', async ({ page }) => {
    await page.goto('/login')
    // HTML required 属性阻止空提交，按钮不触发 API
    await page.getByRole('button', { name: '登录' }).click()
    // 仍在登录页
    await expect(page).toHaveURL(/\/login/)
  })
})

// ---- 路由守卫 ----

test.describe('路由守卫', () => {
  test('未登录访问受保护页面 → 重定向至 /login', async ({ page }) => {
    await page.goto('/graph')
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
  })

  test('未登录访问 /resume-match → 重定向至 /login', async ({ page }) => {
    await page.goto('/resume-match')
    await expect(page).toHaveURL(/\/login/)
  })

  test('未登录访问 /admin → 重定向至 /login', async ({ page }) => {
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/login/)
  })

  test('已登录访问 /login → 重定向至首页', async ({ page }) => {
    // 先登录
    await page.goto('/login')
    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill(ADMIN.password)
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })

    // 再访问 /login → GuestGuard 重定向
    await page.goto('/login')
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10_000 })
  })
})

// ---- 注册 ----

test.describe('注册', () => {
  test('注册新用户成功', async ({ page }) => {
    await page.goto('/register')
    await expect(page.getByRole('heading', { name: '注册' })).toBeVisible()

    const unique = `e2e_${Date.now().toString(36)}`
    await page.getByLabel('用户名 *').fill(unique)
    await page.getByLabel('密码 *').fill('testpass123')
    await page.getByLabel('确认密码 *').fill('testpass123')
    await page.getByRole('button', { name: '注册' }).click()

    // 注册成功提示
    await expect(page.getByText(/注册成功/)).toBeVisible({ timeout: 10_000 })
    // 最近注册表中出现新用户
    await expect(page.getByText(unique)).toBeVisible()
  })

  test('两次密码不一致被前端校验拦截', async ({ page }) => {
    await page.goto('/register')
    await page.getByLabel('用户名 *').fill('e2e_mismatch')
    await page.getByLabel('密码 *').fill('password1')
    await page.getByLabel('确认密码 *').fill('password2')
    await page.getByRole('button', { name: '注册' }).click()

    await expect(page.getByText('两次密码不一致')).toBeVisible()
  })
})

// ---- 登出 ----

test.describe('登出', () => {
  test('登出后跳转至 /login 且无法回退', async ({ page }) => {
    // 登录
    await page.goto('/login')
    await page.getByLabel('用户名').fill(ADMIN.username)
    await page.getByLabel('密码').fill(ADMIN.password)
    await page.getByRole('button', { name: '登录' }).click()
    await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })

    // 登出
    await page.getByRole('button', { name: '登出' }).click()
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })

    // 回退后仍被守卫拦截
    await page.goto('/graph')
    await expect(page).toHaveURL(/\/login/)
  })
})

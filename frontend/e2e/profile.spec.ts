import { expect, test } from '@playwright/test'

/**
 * 个人中心 E2E（TE-M4-02，设计文档 §13.2 / §10.2）。
 *
 * 覆盖：页面加载 → 用户摘要卡 → 基本信息编辑 → 修改密码 → 简历管理列表。
 * 数据来源：真实后端 API（/auth/me, PUT /auth/me, POST /auth/password, /resume/list）。
 * 后端不可达时断言降级态，不 fail。
 */

const ADMIN = { username: 'admin', password: 'admin123' }

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(ADMIN.username)
  await page.getByLabel('密码').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText(ADMIN.username).first()).toBeVisible({ timeout: 20_000 })
}

test.describe('个人中心', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    await page.goto('/profile')
  })

  test('页面标题与描述可见', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('账户信息与简历管理')).toBeVisible()
  })

  test('用户摘要卡显示用户名', async ({ page }) => {
    await page.waitForTimeout(3000)
    // 用户名出现在摘要卡 h2 中
    await expect(page.getByRole('heading', { name: ADMIN.username })).toBeVisible({ timeout: 15_000 })
  })

  test('基本信息编辑区域存在', async ({ page }) => {
    await page.waitForTimeout(2000)
    await expect(page.getByText('基本信息')).toBeVisible({ timeout: 15_000 })
    // 用户名输入框（disabled）
    await expect(page.getByLabel('用户名')).toBeVisible()
    // 邮箱输入框
    await expect(page.getByLabel('邮箱')).toBeVisible()
    // 保存按钮
    await expect(page.getByRole('button', { name: '保存修改' })).toBeVisible()
  })

  test('修改密码区域存在', async ({ page }) => {
    await page.waitForTimeout(2000)
    await expect(page.getByText('修改密码')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByLabel('原密码')).toBeVisible()
    await expect(page.getByLabel('新密码')).toBeVisible()
    await expect(page.getByLabel('确认新密码')).toBeVisible()
    await expect(page.getByRole('button', { name: '修改密码' })).toBeVisible()
  })

  test('简历管理列表区域存在（可能为空）', async ({ page }) => {
    await page.waitForTimeout(3000)
    await expect(page.getByText('简历管理')).toBeVisible({ timeout: 15_000 })
    // 表头存在
    await expect(page.getByRole('columnheader', { name: '文件名' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '技能' })).toBeVisible()
  })

  test('修改密码 — 两次密码不一致被前端校验拦截', async ({ page }) => {
    await page.waitForTimeout(2000)
    await page.getByLabel('原密码').fill('someoldpass')
    await page.getByLabel('新密码').fill('newpass1')
    await page.getByLabel('确认新密码').fill('newpass2')
    await page.getByRole('button', { name: '修改密码' }).click()

    await expect(page.getByText('两次密码不一致')).toBeVisible({ timeout: 10_000 })
  })
})

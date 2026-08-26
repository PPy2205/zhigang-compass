import { Outlet, useLocation } from 'react-router'
import { TopNav } from './top-nav'
import { Sidebar } from './sidebar'
import { BottomNav } from './bottom-nav'

/**
 * 应用外壳 — 顶部导航 + 侧边栏 + 主内容区 + 移动端底部导航
 *
 * 布局策略（设计文档 §10.5 三断点响应式）：
 * - 桌面端 ≥1025px（lg）：双栏全功能（侧边栏 + 内容 + 顶部导航）
 * - 平板 641-1024px（sm→md）：侧边栏隐藏，内容全宽，顶部导航含汉堡菜单
 * - 移动端 ≤640px（max-sm）：纯单栏 + 底部 Tab 导航
 *
 * FE-M5-01：路由切换时主内容区淡入动画，key 触发 re-mount
 * FE-M5-02：移动端底部 Tab 导航 + 安全区域适配
 */
export function AppShell() {
  const location = useLocation()
  return (
    <div className="flex h-screen flex-col bg-canvas">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          {/* 移动端：底部导航栏高度 + 安全区域，避免内容被遮挡 */}
          <div
            key={location.pathname}
            className="page-enter mx-auto max-w-7xl px-4 py-6 pb-20 sm:pb-6 lg:px-8 lg:py-8"
          >
            <Outlet />
          </div>
        </main>
      </div>
      <BottomNav />
    </div>
  )
}

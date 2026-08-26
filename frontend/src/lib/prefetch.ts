/**
 * 路由预取 — 设计文档 §10.1 前端可视化性能
 *
 * 用户 hover 导航链接时提前加载下一页 chunk，
 * 点击时组件已就绪，实现瞬时路由切换。
 *
 * 原理：调用与 lazy() 相同的 import() 路径，浏览器/Vite 缓存
 * 已加载模块，后续 lazy() 渲染时直接命中缓存。
 */

// 路由路径 → 对应页面模块的 import() 路径
const PREFETCH_MAP: Record<string, () => Promise<unknown>> = {
  '/': () => import('@/routes/dashboard-page'),
  '/graph': () => import('@/routes/graph-page'),
  '/resume-match': () => import('@/routes/resume-match-page'),
  '/evolution': () => import('@/routes/evolution-page'),
  '/profile': () => import('@/routes/profile-page'),
  '/admin': () => import('@/routes/admin-dashboard-page'),
  '/admin/users': () => import('@/routes/admin-users-page'),
  '/admin/crawl': () => import('@/routes/admin-crawl-page'),
  '/admin/review': () => import('@/routes/admin-review-page'),
  '/admin/llm': () => import('@/routes/admin-llm-page'),
}

// 已预取的路径集合，避免重复触发
const prefetched = new Set<string>()

/**
 * 预取指定路由的 chunk。
 * 安全调用：路径不存在或 import 失败时静默降级。
 */
export function prefetchRoute(path: string): void {
  if (prefetched.has(path)) return
  const importer = PREFETCH_MAP[path]
  if (!importer) return
  prefetched.add(path)
  // 触发 import，不 await —— 加载在后台进行，不阻塞 UI
  importer().catch(() => {
    // 预取失败时清除标记，允许下次重试
    prefetched.delete(path)
  })
}

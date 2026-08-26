import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/auth'
import { mainNav, type NavItem } from './nav-config'

/**
 * 移动端底部 Tab 导航 — 设计文档 §10.5
 *
 * 显示规则：
 * - 仅在 ≤640px (max-sm) 时显示
 * - 主导航项水平排列，激活态高亮
 * - 与侧边栏导航项一致（mainNav），按角色过滤
 * - 高度 56px，底部安全区域适配（env(safe-area-inset-bottom)）
 */
export function BottomNav() {
  const { user } = useAuthStore()
  const role = user?.role

  function filterByRole(items: NavItem[]): NavItem[] {
    if (!role) return items.filter((i) => !i.requireRole)
    return items.filter((i) => !i.requireRole || i.requireRole.includes(role))
  }

  // 移动端最多显示 5 个 Tab，取前 5 个有权限的
  const visibleItems = filterByRole(mainNav).slice(0, 5)

  if (visibleItems.length === 0) return null

  return (
    <nav
      className="sm:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-canvas/90 backdrop-blur-md"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0)' }}
      aria-label="底部导航"
    >
      <div className="flex h-14 items-center justify-around px-2">
        {visibleItems.map((item) => (
          <BottomNavItem key={item.to} item={item} />
        ))}
      </div>
    </nav>
  )
}

function BottomNavItem({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex flex-1 flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] transition-colors',
          isActive
            ? 'text-ink'
            : 'text-ink-muted hover:text-ink-secondary',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon className={cn('size-5', isActive && 'stroke-[2.25px]')} />
          <span className={cn(isActive && 'font-medium')}>{item.label}</span>
        </>
      )}
    </NavLink>
  )
}

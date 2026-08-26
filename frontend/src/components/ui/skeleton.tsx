/**
 * 骨架屏组件 — 设计文档 §10.6 交互打磨
 *
 * 在数据加载阶段显示灰色占位块，避免白屏 + CLS 跳动。
 * - SkeletonCard：卡片骨架
 * - SkeletonText：文本行骨架
 * - SkeletonGraph：图谱/图表骨架
 */
import { cn } from '@/lib/utils'

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-subtle',
        className,
      )}
    />
  )
}

/** 文本行骨架 — 可指定行数和行宽 */
export function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  )
}

/** 卡片骨架 — 带标题 + 内容占位 */
export function SkeletonCard({
  className,
  contentLines = 4,
}: {
  className?: string
  contentLines?: number
}) {
  return (
    <div className={cn('rounded-lg border border-border p-4', className)}>
      <Skeleton className="h-5 w-32 mb-3" />
      <SkeletonText lines={contentLines} />
    </div>
  )
}

/** 图表骨架 — 圆形/方形占位，适配 ECharts/图谱加载 */
export function SkeletonGraph({
  className,
  variant = 'rect',
}: {
  className?: string
  variant?: 'rect' | 'circle' | 'radar'
}) {
  if (variant === 'circle') {
    return (
      <div className={cn('flex items-center justify-center', className)}>
        <Skeleton className="size-32 rounded-full" />
      </div>
    )
  }
  if (variant === 'radar') {
    return (
      <div className={cn('flex items-center justify-center py-10', className)}>
        <Skeleton className="size-48 rotate-45" />
      </div>
    )
  }
  return <Skeleton className={cn('h-[280px] w-full', className)} />
}

/** 列表项骨架 — 适配推荐列表/差距列表 */
export function SkeletonList({
  count = 3,
  className,
}: {
  count?: number
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-md border border-border p-3 space-y-2"
        >
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 w-12" />
          </div>
          <SkeletonText lines={2} />
        </div>
      ))}
    </div>
  )
}

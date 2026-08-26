/**
 * 性能优化 hooks — 设计文档 §10.1 前端可视化性能
 *
 * - useDebouncedValue：防抖值（搜索框输入 → 延迟触发 API）
 * - useDebouncedCallback：防抖回调（避免快速点击重复请求）
 * - useIntersectionObserver：可见性检测（懒加载图表/3D 视图）
 */

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 防抖值 — 延迟更新状态值，减少不必要的 API 请求。
 *
 * 用法：
 *   const [query, setQuery] = useState('')
 *   const debouncedQuery = useDebouncedValue(query, 300)
 *   useEffect(() => { if (debouncedQuery) doSearch(debouncedQuery) }, [debouncedQuery])
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

/**
 * 防抖回调 — 延迟执行，快速重复调用时只执行最后一次。
 * 返回的函数引用稳定（useCallback），可直接用于事件处理器。
 */
export function useDebouncedCallback<T extends (...args: never[]) => void>(
  fn: T,
  delay: number,
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fnRef = useRef(fn)

  // 在 effect 中更新 ref，避免 render 期间访问 ref
  useEffect(() => {
    fnRef.current = fn
  }, [fn])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => fnRef.current(...args), delay)
    },
    [delay],
  ) as T
}

/**
 * 可见性检测 — 元素进入视口时才触发回调，用于懒加载重资源组件。
 *
 * 用法：
 *   const ref = useRef<HTMLDivElement>(null)
 *   const visible = useIntersectionObserver(ref, { rootMargin: '200px' })
 *   // visible 为 true 后才渲染 ECharts 实例
 */
export function useIntersectionObserver(
  ref: React.RefObject<HTMLElement | null>,
  options?: IntersectionObserverInit,
): boolean {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '100px', threshold: 0.1, ...options },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref, options])

  return visible
}

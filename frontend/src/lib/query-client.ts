import { QueryClient } from '@tanstack/react-query'

/**
 * TanStack Query 客户端 — 单例
 *
 * FE-M5-01 性能优化：
 * - staleTime 30s：30s 内相同查询不重新请求（设计文档 §10.1）
 * - gcTime 5min：垃圾回收前缓存保留 5 分钟，支持返回时即时展示
 * - retry 1：仅重试一次，避免雪崩
 * - refetchOnWindowFocus false：切回标签页不自动刷新（减少不必要的请求）
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30s 内不重新请求
      gcTime: 5 * 60_000,      // 5min 后回收缓存
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
})

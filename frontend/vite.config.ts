import { configDefaults, defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    // 模块预取：将 link rel=modulepreload 注入 HTML head
    modulePreload: {
      polyfill: true,
    },
    // 构建优化（FE-M5-01 §10.1）：manualChunks 分包 + chunk 大小提升
    build: {
      target: 'es2020',
      cssMinify: 'lightningcss',
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          // 入口文件名带 hash，支持 CDN 长缓存
          entryFileNames: 'assets/[name]-[hash].js',
          chunkFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash][extname]',
          // 手动分包：将第三方库拆分为独立 chunk，
          // 避免单个 vendor 包过大且利用浏览器并行下载
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router'],
            'vendor-echarts': ['echarts'],
            'vendor-query': ['@tanstack/react-query'],
            'vendor-state': ['zustand'],
            'vendor-icons': ['lucide-react'],
            'vendor-radix': [
              '@radix-ui/react-dialog',
              '@radix-ui/react-dropdown-menu',
              '@radix-ui/react-label',
              '@radix-ui/react-select',
              '@radix-ui/react-slot',
              '@radix-ui/react-tabs',
              '@radix-ui/react-tooltip',
            ],
            'vendor-force-graph': ['react-force-graph-3d'],
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      // e2e/ 下的 Playwright spec 由 `pnpm e2e` 单独运行，vitest 不得收集
      exclude: [...configDefaults.exclude, 'e2e/**'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'text-summary', 'json-summary'],
        reportsDirectory: './coverage',
        // 核心子集门禁（设计文档 §17.1"核心 ≥ 80%"）：业务逻辑密集的 lib/store/
        // 守卫/UI 基础组件/layout；页面级交互由 E2E（Playwright）覆盖，echarts/
        // force-graph 可视化页不做单元测试覆盖（jsdom 无 canvas，收益低）。
        thresholds: {
          global: { lines: 80, functions: 80, branches: 70, statements: 80 },
        },
        all: true,
        include: [
          'src/lib/**',
          'src/store/**',
          'src/routes/guards.tsx',
          'src/components/ui/**',
          'src/components/resume/**',
          'src/components/layout/**',
        ],
        exclude: ['src/types/**', 'src/styles/**', 'src/test/**', '**/*.d.ts'],
      },
    },
  }
})

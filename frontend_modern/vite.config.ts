import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  // Butler 使用 pywebview 加载本地文件，base 设为相对路径
  base: './',

  // 路径别名
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  build: {
    outDir: 'dist',
    // 多页面应用配置 (3 个独立入口)
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        flash: resolve(__dirname, 'flash_input.html'),
        workflow: resolve(__dirname, 'workflow.html'),
      },
    },
    // 生产环境压缩
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: ['log', 'debug'],
        drop_debugger: true,
      },
    },
    // Source map (生产环境关闭)
    sourcemap: false,
    // 资源内联阈值 (4KB 以下内联为 base64)
    assetsInlineLimit: 4096,
  },

  server: {
    port: 3000,
    open: false,
    // 代理后端 API (Flask 跑在 5001)
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },

  css: {
    // CSS Modules 配置
    modules: {
      localsConvention: 'camelCaseOnly',
    },
  },

  // 开发环境变量前缀
  envPrefix: 'BUTLER_',
});

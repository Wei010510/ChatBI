import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/ChatBI/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 用 127.0.0.1 而不是 localhost：Windows 下 localhost 可能先解析到 IPv6 ::1
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // 问数单次 40~90s，代理侧也要给足时间，避免长请求被中断
        timeout: 300000,
        proxyTimeout: 300000,
      },
    },
  },
});

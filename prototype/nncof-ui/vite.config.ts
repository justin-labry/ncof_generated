import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// 포트 단일 출처(prototype/nf_ports.conf)에서 NCOF 포트를 읽어 dev 프록시 타깃을 구성한다.
function ncofPort(): string {
  try {
    const txt = readFileSync(resolve(process.cwd(), "../nf_ports.conf"), "utf-8");
    const m = txt.match(/^\s*NCOF_PORT\s*=\s*(\d+)/m);
    if (m) return m[1];
  } catch {
    /* 파일을 못 읽으면 기본값으로 폴백 */
  }
  return "9000";
}

const PORT = ncofPort();
const httpTarget = `http://127.0.0.1:${PORT}`;
const wsTarget = `ws://127.0.0.1:${PORT}`;

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      // 경로가 '/api'로 시작하는 요청을 대상으로 합니다.
      "/api": {
        target: httpTarget, // NCOF 서버 (nf_ports.conf 의 NCOF_PORT)
        changeOrigin: true,
        secure: false,
      },
      "/subscriptions": {
        target: httpTarget,
        changeOrigin: true,
        secure: false,
      },
      "/api/ws": {
        target: wsTarget,
        ws: true, // WebSocket 프록시 활성화 (핵심!)
        changeOrigin: true,
      },
    },
  },
});

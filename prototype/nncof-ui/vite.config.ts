import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// 포트 단일 출처(prototype/nf_ports.conf)에서 NCOF 포트를 읽어 dev 프록시 타깃을 구성한다.
function ncofPort(): string {
  try {
    const txt = readFileSync(
      resolve(process.cwd(), "../nf_ports.conf"),
      "utf-8",
    );
    const m = txt.match(/^\s*NCOF_PORT\s*=\s*(\d+)/m);
    if (m) return m[1];
  } catch {
    /* 파일을 못 읽으면 기본값으로 폴백 */
  }
  return "9000";
}

const PORT = ncofPort();
const httpTarget = `https://127.0.0.1:${PORT}`;
const wsTarget = `wss://127.0.0.1:${PORT}`;

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      "/api/ws": {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
        secure: false,
      },
      "/api": {
        target: httpTarget,
        changeOrigin: true,
        secure: false,
      },
      "/subscriptions": {
        target: httpTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

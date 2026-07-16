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
        target: wsTarget, // 실제 배포될 서버 주소
        ws: true, // WebSocket 프록시 활성화 (핵심!)
        changeOrigin: true,
        secure: false,
        // rewrite: (path) => path.replace(/^\/ws/, ""), // 경로 재작성이 필요한 경우
        // rewrite: (path) => path.replace(/^\/api/, ""),
      },

      // 경로가 '/api'로 시작하는 요청을 대상으로 합니다.
      "/api": {
        target: httpTarget, // 실제 배포될 서버 주소
        changeOrigin: true, // 대상 서버의 호스트 헤더를 target 주소로 변경
        // rewrite: (path) => path.replace(/^\/api/, ""), // 요청 경로에서 '/api' 제거
        secure: false, // HTTPS의 자가 서명 인증서를 사용할 경우 false
      },
      "/subscriptions": {
        target: httpTarget, // 실제 배포될 서버 주소
        changeOrigin: true, // 대상 서버의 호스트 헤더를 target 주소로 변경
        // rewrite: (path) => path.replace(/^\/api/, ""), // 요청 경로에서 '/api' 제거
        secure: false, // HTTPS의 자가 서명 인증서를 사용할 경우 false
      },
    },
  },
});

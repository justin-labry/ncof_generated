import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      // 경로가 '/api'로 시작하는 요청을 대상으로 합니다.
      "/api": {
        target: "http://localhost:8000", // 실제 배포될 서버 주소
        changeOrigin: true, // 대상 서버의 호스트 헤더를 target 주소로 변경
        // rewrite: (path) => path.replace(/^\/api/, ""), // 요청 경로에서 '/api' 제거
        secure: false, // HTTPS의 자가 서명 인증서를 사용할 경우 false
      },
      "/subscriptions": {
        target: "http://localhost:8000", // 실제 배포될 서버 주소
        changeOrigin: true, // 대상 서버의 호스트 헤더를 target 주소로 변경
        // rewrite: (path) => path.replace(/^\/api/, ""), // 요청 경로에서 '/api' 제거
        secure: false, // HTTPS의 자가 서명 인증서를 사용할 경우 false
      },
      "/api/ws": {
        target: "ws://localhost:8000", // 실제 배포될 서버 주소
        ws: true, // WebSocket 프록시 활성화 (핵심!)
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/ws/, ""), // 경로 재작성이 필요한 경우
        // rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// 설정 단일 출처(prototype/ncof_setting.conf)에서 NCOF 포트/TLS 를 읽어 dev 프록시를 구성한다.
// 우선순위: 환경변수 > ncof_setting.conf > 기본값.
function readConf(): Record<string, string> {
  const conf: Record<string, string> = {};
  try {
    const txt = readFileSync(resolve(process.cwd(), "../ncof_setting.conf"), "utf-8");
    for (const line of txt.split("\n")) {
      if (/^\s*#/.test(line)) continue;
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S*)/);
      if (m) conf[m[1]] = m[2];
    }
  } catch {
    /* 파일을 못 읽으면 기본값으로 폴백 */
  }
  return conf;
}

const conf = readConf();
const PORT = process.env.NCOF_PORT ?? conf.NCOF_PORT ?? "9000";
// 기본 h2c(http/ws). NCOF_TLS=1 이면 https/wss.
const TLS = /^(1|true|yes|on)$/i.test(process.env.NCOF_TLS ?? conf.NCOF_TLS ?? "");
const httpTarget = `${TLS ? "https" : "http"}://127.0.0.1:${PORT}`;
const wsTarget = `${TLS ? "wss" : "ws"}://127.0.0.1:${PORT}`;

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

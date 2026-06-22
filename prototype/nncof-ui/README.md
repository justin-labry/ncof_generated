# NcofViz - NCOF Visualizer

Vue 3, D3.js 및 Tailwind CSS v4를 기반으로 구축된 고성능 NCOF 시각화 도구

## 🚀 Features

- 구독/알림 메시지 실시간 시각화
- 메시지별 상세 구조 출력

## 🛠️ Tech Stack

- **Framework**: [Vue 3](https://vuejs.org/) (Composition API + `<script setup>`)
- **State Management**: [Pinia](https://pinia.vuejs.org/)
- **Visualization**: [D3.js](https://d3js.org/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Icons**: [Lucide](https://lucide.dev/)
- **Build Tool**: [Vite](https://vitejs.dev/)

## 🏃 Getting Started

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

### Production Build

```bash
npm run build
```

빌드 명령을 수행하면 빌드 결과물이 다음과 같이 NCOF 서버의 특정 경로에 복사된다.

```bash
cp -r dist/. ../nncof-server/src/nncof/static/
```

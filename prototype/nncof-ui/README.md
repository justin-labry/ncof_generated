# SignalViz - Network Signaling Visualizer

A high-performance, interactive network signaling visualization tool built with Vue 3, D3.js, and Tailwind CSS v4.

## 🚀 Features

- **Protocol Simulation**: Build message queues and simulate network flows (SUBSCRIBE, NOTIFY, etc.)
- **Persistent Links**: 'SUBSCRIBED' state maintains a visual connection between nodes.
- **Interactive Topology**: Drag and drop nodes to reorganize your network.
- **Deep Monitoring**: Inspect node details, system statuses, and active communication channels.
- **Aesthetic UI**: Modern glassmorphism design with a focus on usability and visual clarity.

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

## 📝 Usage

1. **Select a Node**: Click on any node (NCOF, User, or Resource) to view its details in the right panel.
2. **Add Messages**: Choose a message type and target, then click "Enqueue" to add to the simulation queue.
3. **Run Simulation**: Use the left panel to execute the entire queue or run messages individually.
4. **Organize**: Drag nodes anywhere on the canvas. The layout will persist during your session.

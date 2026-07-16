<script setup lang="ts">
import { ref, onMounted, watch, provide } from 'vue';
import NetworkCanvas from './components/NetworkCanvas.vue';
import SimulationPanel from './components/SimulationPanel.vue';
import NodeDetails from './components/NodeDetails.vue';
// import StatusTray from './components/StatusTray.vue';
import StatusInfo from './components/StatusInfo.vue';
import SubscriptionList from './components/SubscriptionList.vue';
import NotificationList from './components/NotificationList.vue';
import ControlList from './components/ControlList.vue';
import StatusTray from './components/StatusTray.vue';
import AppHeader from './components/AppHeader.vue';

import { useNetworkStore } from './store/network';
import { useWebSocket } from './composables/useWebSocket';
import type { Message } from './types';

const store = useNetworkStore();

// 새로고침 트리거 — provide/inject 로 모든 자식 컴포넌트의 fetchAll 호출
const refreshKey = ref(0);
provide('refreshKey', refreshKey);

import { Activity, Zap, Wifi, Radio, BarChart3 } from 'lucide-vue-next';

const canvasRef = ref<InstanceType<typeof NetworkCanvas> | null>(null);
const wsReady = ref(false);

const handleRunMessage = async (msg: Message) => {
  if (canvasRef.value) {
    await canvasRef.value.animateMessage(msg);
  }
};


// Initial Data Fetch
const fetchInitialRelations = async () => {
  try {
    const response = await fetch('/api/subscriptions/relations');
    if (response.ok) {
      const relations = await response.json();
      console.log(relations.length)
      const addRelRecursive = (rel: any) => {
        const from = rel.from;
        const to = rel.to || rel.target;
        const subId = rel.sub_id || rel.subscriptionId || rel.externalSubId;

        if (from && to) {
          store.addSubscription(from, to, subId);

          // 메시지 로그에도 추가 (중복 방지를 위해 subId 체크)
          if (subId) {
            store.addMessage(
              from,
              to,
              (rel.type || 'SUBSCRIBED') as any,
              { subscriptionId: subId },
              undefined,
              'COMPLETED',
              `init-${subId.slice(0, 8)}-${Math.random().toString(36).substr(2, 4)}`
            );
          }
        }

        // 중첩된 외부 구독 처리
        if (rel.externalSubscriptions && Array.isArray(rel.externalSubscriptions)) {
          rel.externalSubscriptions.forEach((ext: any) => {
            // 외부 구독의 경우 보통 NCOF가 출발지임
            const extFrom = ext.from || from || 'ncof';
            const extTo = ext.to || ext.target;
            const extSubId = ext.externalSubId || (ext.subscription && (ext.subscription.sub_id || ext.subscription.subscriptionId));

            addRelRecursive({
              from: extFrom,
              to: extTo,
              sub_id: extSubId,
              type: 'SUBSCRIBED',
              externalSubscriptions: ext.subscription ? ext.subscription.externalSubscriptions : null
            });
          });
        }
      };

      relations.forEach((rel: any) => addRelRecursive(rel));

    }
  } catch (err) {
    console.error("Failed to fetch initial relations:", err);
  }
};

const protocol = window.location.protocol === "https:" ? "wss" : "ws";


// WebSocket — useWebSocket composable 으로 위임
const ws = useWebSocket({
  url: `${protocol}://${window.location.host}/api/ws`,
  onOpen: () => {
    ws.send('Hello NCOF Server!');
    store.pushLog('[Sent] Hello NCOF Server!');
    console.log("%c WebSocket connected", 'color: red;');
  },
  onMessage: (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      if (data.from && data.to && data.type) {
        const newMessage: Message = {
          id: data.id || `ws-${Date.now()}`,
          subId: data.sub_id,
          from: data.from,
          to: data.to,
          type: data.type,
          status: 'RUNNING',
          timestamp: data.timestamp || Date.now(),
          data: data.data,
        };

        handleRunMessage(newMessage);

        // if (newMessage.to === 'pcf' || newMessage.to === 'ricf') {
          refreshKey.value++;
        // }

        store.addMessage(
          data.from,
          data.to,
          data.type,
          data.data,
          data.sub_id,
          'COMPLETED',
          data.id || `ws-${Date.now()}`,
          data.timestamp,
        );
      }

      store.pushLog(`[Rcv] ${event.data}`);
    } catch (e) {
      store.pushLog(`[Raw] ${event.data}`);
    }
  },
  onLog: (entry) => {
    store.pushLog(entry);
  },
});

watch(ws.status, (v) => { store.wsStatus = v; }, { immediate: true });
watch(ws.pulse, (v) => { store.wsPulse = v; });

onMounted(() => {
  ws.connect();
  wsReady.value = true;
  fetchInitialRelations();
});


// const store = useNetworkStore();

// WebSocket 수신 펄스 효과
const pulsing = ref(false);
watch(
  () => store.wsPulse,
  () => {
    pulsing.value = true;
    setTimeout(() => { pulsing.value = false; }, 600);
  },
);

</script>

<template>
  <div
    class="flex w-full h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30">

    <!-- WebSocket 연결 상태 오버레이 -->
    <div
      v-if="wsReady && store.wsStatus !== 'CONNECTED'"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/50 backdrop-blur-xs"
    >
      <div class="glass-panel rounded-2xl p-8 flex flex-col items-center gap-5 min-w-80 border border-white/10">
        <!-- Spinner -->
        <svg class="w-10 h-10 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>

        <!-- 상태 메시지 -->
        <p class="text-base font-semibold text-slate-200">
          <template v-if="store.wsStatus === 'DISCONNECTED'">
            서버와의 연결이 끊어졌습니다
          </template>
          <template v-else-if="store.wsStatus === 'CONNECTING'">
            서버에 연결 중입니다
          </template>
          <template v-else-if="store.wsStatus === 'ERROR'">
            연결 오류가 발생했습니다
          </template>
        </p>
        <p class="text-sm text-slate-500">재연결을 기다리는 중...</p>
      </div>
    </div>

    <main class="flex-1- relative flex flex-col gap-2 h-screen">
      <AppHeader class="ml-2"/>
      <div class="flex-1 flex min-w-0 gap-2">
        <div class="flex flex-col gap-2 shrink-0">
          <SimulationPanel :on-run-message="handleRunMessage" class="w-72 ml-2 min-h-120 h-full- max-h-200 overflow-auto"/>
          <StatusInfo class="ml-2 w-72 h-max"  />
        </div>
        <div class="flex flex-col gap-2 min-w-0 flex-1">
          <div class="flex gap-2">
            <NetworkCanvas ref="canvasRef" class="min-w-200 max-w-200 min-h-120 glass-panel border rounded-xl border-white/5" :class="{ 'animate-tray-pulse': pulsing }"/>
            <ControlList class="w-full min-w-96 max-w-200 shrink-0- h-full- max-h-120 rounded-2xl glass-panel"/>
          </div>
          <div class="flex-1 flex gap-2 ">
            <SubscriptionList class="w-full max-w-200 h-full rounded-2xl glass-panel" />
            <NotificationList class="w-full max-w-200 h-full rounded-2xl glass-panel" />
          </div>
        </div>
      </div>
      <StatusTray class="ml-2 mb-2 rounded-lg glass-pane-l"/>
    </main>

    <!-- 우측 사이드바: 1800px 이상에서 표시 (여유 공간 활용) -->
    <div class="hidden min-[1640px]:flex flex-col gap-3 p-2 overflow-y-auto w-full flex-1 h-full overflow-hidden max-w-80">
      <div class="glass-panel rounded-lg p-4 flex flex-col gap-4 border border-white/5 bg-amber-500 h-full relative">
        <!-- 헤더 -->
        <div class="flex items-center gap-2 pb-3 border-b border-white/10">
          <div class="w-1 h-5 bg-linear-to-b from-blue-500 to-cyan-400 rounded-full"></div>
          <span class="text-[10px] font-black uppercase tracking-widest text-slate-400">Dashboard Overview</span>
        </div>

        <!-- 상태 요약 카드 그리드 -->
        <div class="grid grid-cols-1 gap-2">
          <div class="bg-white/5 rounded-xl p-3 flex flex-col gap-1.5 hover:bg-white/10 transition-colors">
            <div class="flex items-center gap-1.5">
              <Radio class="w-3 h-3 text-blue-400" />
              <span class="text-[9px] text-slate-500 uppercase tracking-wider font-bold truncate">Nodes</span>
            </div>
            <span class="text-lg font-bold text-slate-200">{{ store.nodes.length }}</span>
          </div>
          <div class="bg-white/5 rounded-xl p-3 flex flex-col gap-1.5 hover:bg-white/10 transition-colors">
            <div class="flex items-center gap-1.5">
              <Zap class="w-3 h-3 text-amber-400" />
              <span class="text-[9px] text-slate-500 uppercase tracking-wider font-bold truncate">Subscriptions</span>
            </div>
            <span class="text-lg font-bold text-amber-300">{{ store.activeSubscriptions.length }}</span>
          </div>
          <div class="bg-white/5 rounded-xl p-3 flex flex-col gap-1.5 hover:bg-white/10 transition-colors">
            <div class="flex items-center gap-1.5">
              <Activity class="w-3 h-3 text-emerald-400" />
              <span class="text-[9px] text-slate-500 uppercase tracking-wider font-bold truncate">Messages</span>
            </div>
            <span class="text-lg font-bold text-emerald-300">{{ store.messageQueue.length }}</span>
          </div>
          <div class="bg-white/5 rounded-xl p-3 flex flex-col gap-1.5 hover:bg-white/10 transition-colors">
            <div class="flex items-center gap-1.5">
              <BarChart3 class="w-3 h-3 text-violet-400" />
              <span class="text-[9px] text-slate-500 uppercase tracking-wider font-bold">Logs</span>
            </div>
            <span class="text-lg font-bold text-violet-300">{{ store.wsLog.length }}</span>
          </div>
        </div>

        <div class="flex items-center justify-center h-64 mt-12">
          <div class="text-8xl rotate-270 font-black text-slate-700/90">
            NCOF
          </div>
        </div>

        <!-- 하단: 보조 정보 및 디자인 -->
        <div class="mt-auto pt-3 border-t border-white/5 flex flex-col gap-2">
          <div class="flex items-center justify-center gap-2 text-[10px] text-slate-600">
            <Wifi class="w-3 h-3 text-slate-600" />
            <span>NCOF v0.4.0 — 5G Core Event Exposure</span>
          </div>
          <!-- 장식: 도트 패턴 -->
          <div class="flex justify-center gap-1.5 opacity-30">
            <div class="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-cyan-500"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
            <div class="w-1.5 h-1.5 rounded-full bg-violet-500"></div>
          </div>
        </div>
      </div>
    </div>


    <NodeDetails />

  </div>
</template>

<style scoped>
@keyframes spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin-slow {
  animation: spin-slow 8s linear infinite;
}

@keyframes tray-pulse {
  0%, 100% {
    border-color: rgba(255, 255, 255, 0.05);
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0);
  }
  50% {
    border-color: rgba(52, 211, 153, 0.4);
    box-shadow: 0 0 18px 2px rgba(52, 211, 153, 0.2);
  }
}

.animate-tray-pulse {
  animation: tray-pulse 0.6s ease-in-out;
}
</style>

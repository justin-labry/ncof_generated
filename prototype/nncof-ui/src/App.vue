<script setup lang="ts">
import { ref, onMounted, onUnmounted, provide } from 'vue';
import NetworkCanvas from './components/NetworkCanvas.vue';
import SimulationPanel from './components/SimulationPanel.vue';
import NodeDetails from './components/NodeDetails.vue';
import StatusTray from './components/StatusTray.vue';
import SubscriptionList from './components/SubscriptionList.vue';
import NotificationList from './components/NotificationList.vue';
import ControlList from './components/ControlList.vue';
import AppHeader from './components/AppHeader.vue';
import { useNetworkStore } from './store/network';
import type { Message } from './types';

const store = useNetworkStore();

// 새로고침 트리거 — provide/inject 로 모든 자식 컴포넌트의 fetchAll 호출
const refreshKey = ref(0);
provide('refreshKey', refreshKey);

// import { Play, RotateCcw, Trash2, Send, CheckCircle, Clock, Save, Wifi, WifiOff, Activity, Terminal, XCircle, Zap } from 'lucide-vue-next';

const canvasRef = ref<InstanceType<typeof NetworkCanvas> | null>(null);

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
      console.log("[InitialData] Relations fetched:", relations);

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


// WebSocket (managed via store)
let ws: WebSocket | null = null;

onMounted(() => {
  store.wsStatus = 'CONNECTING';
  const socketAddress = `ws://${window.location.host}/api/ws`
  const socket = new WebSocket(socketAddress);
  ws = socket;

  socket.onopen = () => {
    store.wsStatus = 'CONNECTED';
    store.wsLog.push('[Connected]');
    socket.send('Hello NCOF Server!');
    store.wsLog.push('[Sent] Hello NCOF Server!');

    console.log("%c WebSocket connected", 'color: red;')
  };

  socket.onmessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      // 만약 메시지 타입이 시뮬레이션 메시지라면
      if (data.from && data.to && data.type) {
        const newMessage: Message = {
          id: data.id || `ws-${Date.now()}`,
          subId: data.sub_id,
          from: data.from,
          to: data.to,
          type: data.type,
          status: 'RUNNING',
          timestamp: data.timestamp || Date.now(),
          data: data.data
        };



        // 즉시 캔버스에 애니메이션 표시
        handleRunMessage(newMessage);

        console.log(newMessage)

        if (newMessage.to === 'ricf' || newMessage.to === 'pcf') {
          // ricf/pcf 대상 메시지 수신 시 모든 리스트 컴포넌트 데이터 갱신
          refreshKey.value++;
        }

        // 시뮬레이션 패널의 큐에도 기록
        store.addMessage(
          data.from,
          data.to,
          data.type,
          data.data,
          data.sub_id,
          'COMPLETED',
          data.id || `ws-${Date.now()}`,
          data.timestamp
        );
      }

      store.wsPulse++;
      store.wsLog.push(`[Rcv] ${event.data}`);
    } catch (e) {
      store.wsLog.push(`[Raw] ${event.data}`);
    }
  };

  socket.onerror = () => {
    store.wsStatus = 'ERROR';
    console.error('WebSocket connection error');
  };

  socket.onclose = () => {
    store.wsStatus = 'DISCONNECTED';
    store.wsLog.push('[Disconnected]');
  };

  fetchInitialRelations();
});

onUnmounted(() => {
  if (ws) {
    ws.close();
    ws = null;
  }
});

</script>

<template>
  <div
    class="flex w-full h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30">

    <main class="flex-1 relative flex flex-col gap-2">
      <AppHeader />

      <div class="flex gap-2 min-h-130 max-h-130 mx-2">
        <SimulationPanel :on-run-message="handleRunMessage" class="min-w-80"/>
        <NetworkCanvas ref="canvasRef" class="min-w-xl glass-panel border rounded-xl border-white/5 " />
        <ControlList class="min-w-96 max-w-96"/>
      </div>

      <div class="grid gap-2 px-2 flex-1" style="grid-template-columns: 2fr 2fr;">
        <SubscriptionList />
        <NotificationList />
      </div>

      <div class="p-2">
        <StatusTray />
      </div>
    </main>

    <NodeDetails />

  </div>
</template>

<style></style>

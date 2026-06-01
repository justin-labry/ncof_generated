<script setup lang="ts">
import { ref, computed } from 'vue';

import { Play, RotateCcw, Trash2, CheckCircle, Clock, Activity, Terminal, XCircle, Zap } from 'lucide-vue-next';

import { useNetworkStore } from '../store/network';
import { nodeColorClass } from '../utils/nodeColors';
import type { Message } from '../types';

const store = useNetworkStore();
const props = defineProps<{
  onRunMessage: (msg: Message) => Promise<void>;
}>();

const playSimulation = async () => {
  if (store.isSimulationRunning || store.messageQueue.length === 0) return;
  store.isSimulationRunning = true;

  for (let i = 0; i < store.messageQueue.length; i++) {
    const msg = store.messageQueue[i];
    if (!msg || msg.status === 'COMPLETED') continue;

    store.currentMessageIndex = i;
    msg.status = 'RUNNING';
    await props.onRunMessage(msg);
    msg.status = 'COMPLETED';

    // Smooth delay between messages
    await new Promise(resolve => setTimeout(resolve, 300));
  }

  store.isSimulationRunning = false;
};

const activeTab = ref<'simulation' | 'live'>('live');

const filteredMessages = computed(() => {
  if (activeTab.value === 'simulation') {
    return store.messageQueue.filter(m => !m.id.toString().startsWith('ws-'));
  } else {
    return store.messageQueue
      .filter(m => m.id.toString().startsWith('ws-'))
      .filter(m => !['ANALIZED', 'ANALIZING'].includes(m.type))
      ;

  }
});

const runSingleMessage = async (id: string) => {
  if (store.isSimulationRunning) return;
  const index = store.messageQueue.findIndex(m => m.id === id);
  const msg = store.messageQueue[index];
  if (!msg || msg.status === 'COMPLETED') return;

  store.currentMessageIndex = index;
  msg.status = 'RUNNING';
  await props.onRunMessage(msg);
  msg.status = 'COMPLETED';
};


const reset = () => {
  store.resetSimulation();
};

const unsubscribe = async (msg: Message) => {
  const subId = msg.subId

  console.log('unsubscribe:', subId)
  if (!subId) {
    console.warn("No subscriptionId found for message:", subId);
    return;
  }

  try {
    const response = await fetch(`/subscriptions/${subId}`, {
      method: 'DELETE'
    });
    console.log("[Unsubscribe] subId", subId, "Response:", response);
    if (response.ok) {
      store.removeSubscription(msg.from, msg.to);
      store.removeMessage(msg.id);
    } else {
      console.error("Failed to delete subscription:", await response.text());
    }
  } catch (err) {
    console.error("Error during unsubscribe:", err);
  }
};

const clear = () => {
  store.clearQueue();
};

const getNodeName = (id: string) => store.nodes.find(n => n.id === id)?.name || id;

const getNodeColor = (id: string) => nodeColorClass(getNodeName(id));

const getMessageTypeStyle = (type: Message['type']) => {
  switch (type) {
    case 'SUBSCRIBE':
    case 'UNSUBSCRIBE':
    case 'SUBSCRIBED':
    case 'UNSUBSCRIBED':
      return 'bg-red-500/10 text-red-400 border-red-500/20';
    case 'NOTIFICATION':
      return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
    case 'ANALIZING':
    case 'ANALIZED':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    default:
      return 'bg-slate-800 text-slate-400 border-white/5';
  }
};

const formatMessageData = (msg: Message) => {
  if (msg.type === 'NOTIFICATION' && msg.data) {
    return `${msg.data.notificationType || ''} | ${msg.data.event || ''}`;
  }
  if (msg.data?.subscriptionId) {
    return `ID: ${msg.data.subscriptionId.substring(0, 8)}...`;
  }
  return '';
};
</script>

<template>
  <div class="glass-panel flex flex-col h-full rounded-xl overflow-hidden shadow-2xl z-20 p-2">
    <!-- Header -->
    <!-- <div class="p-6 border-b border-white/5 bg-slate-00/80">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2" v-if="activeTab === 'simulation'">
          <span v-if="store.isSimulationRunning" class="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Execution</span>
        </div>
      </div>
    </div> -->

    <!-- Tabs -->
    <div class="py-2 bg-slate-900/20 border-b border-white/5 flex gap-4">
      <button @click="activeTab = 'simulation'" :class="[
        'flex items-center gap-2 py-2 text-[11px] font-black uppercase tracking-widest transition-all relative',
        activeTab === 'simulation' ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'
      ]">
        <Activity class="w-3.5 h-3.5" />
        Simulation
        <div v-if="activeTab === 'simulation'"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]">
        </div>
      </button>

      <button @click="activeTab = 'live'" :class="[
        'flex items-center gap-2 py-2 text-[11px] font-black uppercase tracking-widest transition-all relative',
        activeTab === 'live' ? 'text-emerald-400' : 'text-slate-500 hover:text-slate-300'
      ]">
        <Terminal class="w-3.5 h-3.5" />
        Live Log
        <div v-if="activeTab === 'live'"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500 shadow-[0_0_8px_rgba(52,211,153,0.5)]">
        </div>
      </button>
    </div>

    <!-- Tab Contents -->
    <div class="flex-1 overflow-y-auto custom-scrollbar">
      <div class="p-2 py-4 border-b border-white/5">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
            Event Log
            <span class="text-[9px] bg-white/5 px-1.5 py-0.5 rounded text-slate-500 font-bold">LAST {{
              filteredMessages.length }}</span>
          </h3>
        </div>
        <div class="flex gap-2 mb-2" v-if="activeTab === 'simulation'">
          <button @click="playSimulation" :disabled="store.isSimulationRunning || store.messageQueue.length === 0"
            class="p-1.5 rounded-xl border border-white/10 text-slate-400 hover:bg-blue-400/5 transition-all hover:cursor-pointer">
            <Play class="w-4 h-4" />
          </button>
          <button @click="reset" title="Reset Simulation"
            class="p-1.5 rounded-xl border border-white/10 text-slate-400 hover:bg-white/5 transition-all hover:cursor-pointer">
            <RotateCcw class="w-4 h-4" />
          </button>
          <button @click="clear" title="Clear Queue"
            class="p-1.5 rounded-xl border text-rose-400/70 hover:bg-rose-900/10 transition-all border-rose-900/30 hover:cursor-pointer">
            <Trash2 class="w-4 h-4" />
          </button>
          <div class="h-8 bg-white/5 mx-1"></div>
        </div>
      </div>
      <div v-if="filteredMessages.length === 0"
        class="flex flex-col items-center justify-center py-12- opacity-30 select-none h-full">
        <p class="text-xs font-medium uppercase">
          {{ activeTab === 'simulation' ? 'Simulation queue empty' : 'No live messages received' }}
        </p>
      </div>
      <div v-for="msg in filteredMessages" :key="msg.id" :class="[
        'flex flex-col- gap-1.5 p-1.5 border-b border-white/5 transition-all group relative',
        msg.status === 'RUNNING' ? 'bg-blue-500/5' : 'hover:bg-white/5'
      ]">

        <div class="flex items-center gap-1 overflow-hidden">
          <span class="text-[10px] text-slate-500 font-mono w-10 shrink-0">#{{ msg.id.toString().slice(-4) }}</span>
          <span
            :class="['text-[9px] w-20 text-center px-1.5 py-0.5 rounded font-black uppercase tracking-tighter border shrink-0', getMessageTypeStyle(msg.type)]">
            {{ msg.type }}
          </span>
          <span class="text-[11px] text-cyan-400/70 truncate flex-1 font-medium">
            {{ formatMessageData(msg) }}
          </span>
        </div>

        <div class="flex items-center gap-2">

          <span :class="['w-12 text-xs font-bold truncate text-center rounded-lg', getNodeColor(msg.from)]">{{
            getNodeName(msg.from) }}</span>
          <span class="w-4 text-blue-500 font-bold text-center">→</span>
          <span :class="['w-12 text-xs rounded-lg text-center font-bold truncate', getNodeColor(msg.to)]">{{
            getNodeName(msg.to)
          }}</span>

          <div class="ml-auto flex items-center gap-2">
            <!-- <CheckCircle v-if="msg.status === 'COMPLETED'" class="w-3.5 h-3.5 text-emerald-500" /> -->
            <div v-if="msg.status === 'RUNNING'" class="flex gap-0.5">
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce"></span>
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-100"></span>
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-200"></span>
            </div>
            <div
              v-if="msg.id.toString().startsWith('ws-')"
              class="px-1 py-0.5 bg-emerald-500/10 rounded text-[8px] text-emerald-500 font-bold">LIVE</div>
          </div>
        </div>



        <!-- Hover Actions Overlay -->
        <div
          class="absolute inset-0 bg-slate-900/90 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center gap-2 px-4">
          <button v-if="activeTab === 'simulation' && msg.status !== 'COMPLETED'" @click="runSingleMessage(msg.id)"
            class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-bold uppercase tracking-wider transition-all">
            <Zap class="w-3 h-3" /> Run
          </button>
          <button v-if="msg.type === 'SUBSCRIBED' && msg.to === 'ncof'" @click="unsubscribe(msg)"
            class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-bold uppercase tracking-wider transition-all">
            <XCircle class="w-3 h-3" /> Unsubscribe
          </button>
          <button v-if="!store.isSimulationRunning" @click.stop="store.removeMessage(msg.id)"
            class="p-1.5 rounded-lg bg-white/10 hover:bg-rose-600/20 text-slate-400 hover:text-rose-400 transition-all border border-white/10">
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  @apply bg-transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-white/10 rounded-full;
}
</style>

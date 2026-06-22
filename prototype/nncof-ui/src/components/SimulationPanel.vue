<script setup lang="ts">
import { ref, computed } from 'vue';

import { Zap } from 'lucide-vue-next';

import { useNetworkStore } from '../store/network';
import { nodeColorClass } from '../utils/nodeColors';
import type { Message } from '../types';

const store = useNetworkStore();
const props = defineProps<{
  onRunMessage: (msg: Message) => Promise<void>;
}>();



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


const getNodeName = (id: string) => store.nodes.find(n => n.id === id)?.name || id;

const getNodeColor = (id: string) => nodeColorClass(getNodeName(id));

const getMessageTypeStyle = (type: Message['type']) => {
  switch (type) {
    case 'SUBSCRIBE':
    case 'SUBSCRIBED':
      return 'bg-green-500/30 text-green-400 border-green-500/20';
    case 'UNSUBSCRIBE':
    case 'UNSUBSCRIBED':
      return 'bg-red-500/30 text-red-400 border-red-500/20';
    case 'NOTIFICATION':
      return 'bg-amber-500/30 text-amber-500 border-amber-500/20';
    case 'ANALIZING':
    case 'ANALIZED':
      return 'bg-emerald-500/30 text-emerald-400 border-emerald-500/20';
    default:
      return 'bg-slate-800 text-slate-400 border-white/5';
  }
};

</script>

<template>
  <div class="glass-panel flex flex-col rounded-xl p-2">
    <div class="flex-1 overflow-y-auto custom-scrollbar">
      <div class="p-2 border-b border-white/5">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
            <Zap class="w-4 h-4 text-green-400/90"/>
            Event Log
            <span class="text-[9px] bg-white/5 px-1.5 py-0.5 rounded text-slate-500 font-bold">
              LAST {{ filteredMessages.length }}
            </span>
          </h3>
        </div>
      </div>
      <div v-for="msg in filteredMessages" :key="msg.id" :class="['flex flex-col- gap-1.5 p-1.5 border-b border-white/5 transition-all group relative', msg.status === 'RUNNING' ? 'bg-blue-500/5' : 'hover:bg-white/5' ]">
        <div class="flex items-center gap-1 overflow-hidden">
          <div class="w-2 h-2 bg-yellow-400- rounded-full" :class="getMessageTypeStyle(msg.type)"></div>
          <span :class="['text-[9px] w-20 text-center px-1 py-0.5 rounded font-black uppercase tracking-tighter border shrink-0', getMessageTypeStyle(msg.type)]" > {{ msg.type }} </span>
        </div>

        <div class="flex items-center gap-2">
          <span :class="['w-12 text-xs font-bold truncate text-center rounded-lg', getNodeColor(msg.from)]">{{ getNodeName(msg.from) }}</span>
          <span class="w-4 text-blue-500 font-bold text-center">→</span>
          <span :class="['w-12 text-xs rounded-lg text-center font-bold truncate', getNodeColor(msg.to)]"> {{ getNodeName(msg.to) }}
          </span>

          <div class="ml-auto flex items-center gap-2">
            <div v-if="msg.status === 'RUNNING'" class="flex gap-0.5">
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce"></span>
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-100"></span>
              <span class="w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-200"></span>
            </div>
            <div v-if="msg.id.toString().startsWith('ws-')" class="px-1 py-0.5 bg-emerald-500/10 rounded text-[8px] text-emerald-500 font-bold">LIVE</div>
          </div>
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

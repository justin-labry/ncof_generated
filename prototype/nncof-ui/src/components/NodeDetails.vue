<script setup lang="ts">
import { ref, computed } from 'vue';
import { useNetworkStore } from '../store/network';
import { Cpu, User, Database, Plus, X, Activity, Server, Hash } from 'lucide-vue-next';
import type { MessageType } from '../types';

const store = useNetworkStore();
const targetNodeId = ref('');
const messageType = ref<MessageType>('SUBSCRIBE');

const canAddMessage = computed(() => 
  store.selectedNodeId && 
  targetNodeId.value && 
  targetNodeId.value !== store.selectedNodeId && 
  !store.isSimulationRunning
);

const addMessageToQueue = () => {
  if (!canAddMessage.value) return;
  store.addMessage(store.selectedNodeId!, targetNodeId.value, messageType.value);
};

const getNodeIcon = (type: string | undefined) => {
  switch (type) {
    case 'NCOF': return Cpu;
    case 'USER': return User;
    case 'RESOURCE': return Database;
    default: return Cpu;
  }
};

const getBadgeColor = (type: string | undefined) => {
  switch (type) {
    case 'NCOF': return 'bg-blue-600/20 text-blue-400 border-blue-500/20';
    case 'USER': return 'bg-emerald-600/20 text-emerald-400 border-emerald-500/20';
    case 'RESOURCE': return 'bg-amber-600/20 text-amber-400 border-amber-500/20';
    default: return 'bg-slate-600/20 text-slate-400 border-slate-500/20';
  }
};
</script>

<template>
  <div v-if="store.selectedNode" class="glass-panel w-96 rounded-l-3xl p-6 shadow-2xl flex flex-col gap-6 animate-in slide-in-from-right-12 duration-500 z-20">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-4">
        <div :class="['p-4 rounded-2xl border flex items-center justify-center', getBadgeColor(store.selectedNode.type)]">
          <component :is="getNodeIcon(store.selectedNode.type)" class="w-8 h-8" />
        </div>
        <div>
          <h2 class="text-xl font-bold">{{ store.selectedNode.name }}</h2>
          <div class="flex items-center gap-2 mt-1">
             <span :class="['text-[10px] font-black uppercase tracking-[0.2em] px-2 py-0.5 rounded border', getBadgeColor(store.selectedNode.type)]">
                {{ store.selectedNode.type }}
             </span>
             <span class="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold uppercase tracking-wider">
                <span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span> {{ store.selectedNode.status }}
             </span>
          </div>
        </div>
      </div>
      <button @click="store.selectedNodeId = null" class="p-2 hover:bg-white/5 rounded-xl transition-all">
        <X class="w-5 h-5 text-slate-500" />
      </button>
    </div>

    <!-- Metadata Grid -->
    <div class="grid grid-cols-2 gap-3">
        <div class="bg-slate-900/50 p-3 rounded-2xl border border-white/5">
            <p class="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-1.5"><Server class="w-3 h-3" /> Host Rack</p>
            <p class="font-mono text-xs">{{ store.selectedNode.server }}</p>
        </div>
        <div class="bg-slate-900/50 p-3 rounded-2xl border border-white/5">
            <p class="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-1.5"><Hash class="w-3 h-3" /> System ID</p>
            <p class="font-mono text-xs">{{ store.selectedNode.id.toUpperCase() }}</p>
        </div>
    </div>

    <!-- Interface Controller -->
    <div class="space-y-4 pt-4 border-t border-white/5">
      <h3 class="text-xs font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
        <Activity class="w-4 h-4" /> Signal Interface
      </h3>
      
      <!-- Type Select -->
      <div class="space-y-1.5">
          <label class="text-[10px] font-bold text-slate-400 uppercase ml-1">Message Type</label>
          <select 
            v-model="messageType"
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-blue-500 outline-none transition-all appearance-none cursor-pointer"
          >
            <option value="SUBSCRIBE">SUBSCRIBE</option>
            <option value="UNSUBSCRIBE">UNSUBSCRIBE</option>
            <option value="NOTIFY">NOTIFY</option>
            <option value="SUBSCRIBED">SUBSCRIBED (Arrow)</option>
            <option value="UNSUBSCRIBED">UNSUBSCRIBED (Rem)</option>
          </select>
      </div>

      <!-- Target Select -->
      <div class="space-y-1.5">
          <label class="text-[10px] font-bold text-slate-400 uppercase ml-1">Target Cluster</label>
          <select 
            v-model="targetNodeId"
            class="w-full bg-slate-900 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-blue-500 outline-none transition-all appearance-none cursor-pointer"
          >
            <option value="" disabled selected>Select destination node...</option>
            <option v-for="node in store.nodes.filter(n => n.id !== store.selectedNodeId)" :key="node.id" :value="node.id">
              {{ node.name }}
            </option>
          </select>
      </div>

      <button 
        @click="addMessageToQueue"
        :disabled="!canAddMessage"
        class="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:grayscale py-3.5 rounded-2xl flex items-center justify-center gap-2 font-bold transition-all shadow-xl shadow-blue-900/10"
      >
        <Plus class="w-5 h-5" /> Enqueue Protocol Message
      </button>
    </div>

    <!-- Subscription View (Optional) -->
    <div class="flex-1 mt-4">
        <div class="flex items-center justify-between mb-3">
             <h3 class="text-[9px] font-black text-slate-500 uppercase tracking-widest">Active Channels</h3>
             <span class="text-[10px] font-bold text-blue-400 px-2 py-0.5 rounded-full bg-blue-400/10 border border-blue-400/20">
                {{ store.activeSubscriptions.filter(s => s.from === store.selectedNodeId).length }}
             </span>
        </div>
        <div class="space-y-2 opacity-80 overflow-y-auto max-h-40 pr-1 custom-scrollbar">
            <div 
                v-for="sub in store.activeSubscriptions.filter(s => s.from === store.selectedNodeId)" 
                :key="sub.id"
                class="flex items-center justify-between p-2.5 rounded-xl bg-blue-950/20 border border-blue-500/10 text-xs"
            >
                <span class="font-mono text-blue-300">→ {{ store.nodes.find(n => n.id === sub.to)?.name }}</span>
                <span class="text-[9px] opacity-40 italic">{{ new Date(sub.timestamp).toLocaleTimeString() }}</span>
            </div>
            <p v-if="store.activeSubscriptions.filter(s => s.from === store.selectedNodeId).length === 0" class="text-center py-4 text-[10px] text-slate-600 italic">No direct subscriptions active</p>
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

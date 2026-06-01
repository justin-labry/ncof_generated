<!-- NCOF 대시보드 상단 헤더 컴포넌트 (브랜딩, 상태, 저장) -->
<script setup lang="ts">
import { ref, inject } from 'vue';
import type { Ref } from 'vue';
import { VectorSquare, Globe, Save, CheckCircle, RefreshCw } from 'lucide-vue-next';

import { useNetworkStore } from '../store/network';

const store = useNetworkStore();

const refreshKey = inject<Ref<number>>('refreshKey', ref(0));

const isSaving = ref(false);
const handleSave = async () => {
  isSaving.value = true;
  store.saveNodes();
  // Visual feedback
  await new Promise(resolve => setTimeout(resolve, 800));
  isSaving.value = false;
};

const isRefreshing = ref(false);
const handleRefreshAll = async () => {
  isRefreshing.value = true;
  refreshKey.value++;
  await new Promise(resolve => setTimeout(resolve, 800));
  isRefreshing.value = false;
};
</script>

<template>
  <header class="flex justify-between items-center pointer-events-none glass-panel mt-2 mx-2 rounded-xl">
    <div class="flex items-center gap-6 pointer-events-auto group p-2">
      <div class="flex items-center gap-2">
        <VectorSquare class="text-emerald-500"/>
        <div class="font-black tracking-tight"> NCOF </div>
        <div class="text-blue-400 font-black uppercase tracking-[0.2em] flex items-center gap-2">
          <!-- <Activity class="text-emerald-500" />  -->
          Network Control &amp; Optimization Function
        </div>
        <div
          class="bg-white/10 px-2 rounded-full text-slate-400 font-bold uppercase tracking-widest border border-white/5">
          v0.3</div>
      </div>
    </div>

    <div class="flex gap-4 pointer-events-auto">
      <!-- <div class="px-5 py-2.5 flex items-center gap-3 shadow-xl">
        <div class="relative">
          <div class="w-3 h-3 bg-emerald-500 rounded-full"></div>
          <div class="absolute inset-0 bg-emerald-400 rounded-full animate-ping opacity-75"></div>
        </div>
        <div class="flex flex-col">
          <span class="text-xs font-bold text-emerald-400">NCOF Core Connected</span>
        </div>
      </div> -->

      <div class="px-5 py-1.5 flex items-center gap-3 shadow-xl">
        <Globe class="w-5 h-5 text-blue-400" />
        <div class="flex flex-col">
          <span class="text-xs font-bold text-blue-400">PoC: 6G-I2P ETRI-DoDo1</span>
        </div>
      </div>
      <div class="px-5 py-1.5 flex items-center gap-3 shadow-xl">
        <button @click="handleRefreshAll" title="Refresh All Data" :class="[
          'p-2.5 rounded-xl border transition-all flex items-center gap-2',
          isRefreshing ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'border-white/10 text-slate-400 hover:bg-white/5'
        ]">
          <RefreshCw class="w-5 h-5" :class="{ 'animate-spin': isRefreshing }" />
        </button>
        <button @click="handleSave" title="Save Node Layout" :class="[
          'p-2.5 rounded-xl border transition-all flex items-center gap-2',
          isSaving ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'border-white/10 text-slate-400 hover:bg-white/5'
        ]">
          <Save v-if="!isSaving" class="w-5 h-5" />
          <CheckCircle v-else class="w-5 h-5 animate-bounce" />
        </button>
      </div>
    </div>
  </header>
</template>

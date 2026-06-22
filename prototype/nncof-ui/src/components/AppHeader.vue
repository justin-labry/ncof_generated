<!-- NCOF 대시보드 상단 헤더 컴포넌트 (브랜딩, 상태, 저장) -->
<script setup lang="ts">
import { ref, inject } from 'vue';
import type { Ref } from 'vue';
import { Globe,RefreshCw } from 'lucide-vue-next';

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
  <header class="flex justify-between items-center pointer-events-none glass-panel mt-2 rounded-xl">
    <div class="flex items-center gap-6 pointer-events-auto group p-2">
      <div class="flex items-center gap-2">
        <Globe class="text-gray-200/910 w-4"/>
        <div>
          <span class="font-black tracking-wider text-blue-300">N</span>
          <span class="font-black tracking-wider">COF</span>
        </div>
        <!-- <div class="text-blue-400 font-black uppercase tracking-wider flex items-center gap-2">
          Network Control &amp; Optimization Function
        </div> -->
      </div>
    </div>

    <div class="flex gap-4 pointer-events-auto">
      <div class="px-5 py-1.5 flex items-center gap-2 shadow-xl">
        <!-- <Globe class="w-5 h-5 text-blue-400" /> -->
        <div class="w-2 h-2 bg-blue-400/80 rounded-full"></div>
        <div class="flex flex-col">
          <span class="text-xs font-bold tracking-wider font-sans text-blue-40-0">PoC: 6G-I2P ETRI-DoDo1</span>
        </div>
      </div>
      <div class="px-2 py-1.5 flex items-center gap-3 shadow-xl">
        <button @click="handleRefreshAll" title="Refresh All Data" :class="[
          'p-2.5 rounded-xl border transition-all flex items-center gap-2',
          isRefreshing ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'border-white/10 text-slate-400 hover:bg-white/5'
        ]">
          <RefreshCw class="w-5 h-5" :class="{ 'animate-spin': isRefreshing }" />
        </button>
        <!-- <button @click="handleSave" title="Save Node Layout" :class="[
          'p-2.5 rounded-xl border transition-all flex items-center gap-2',
          isSaving ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'border-white/10 text-slate-400 hover:bg-white/5'
        ]">
          <Save v-if="!isSaving" class="w-5 h-5" />
          <CheckCircle v-else class="w-5 h-5 animate-bounce" />
        </button> -->
      </div>
    </div>
  </header>
</template>

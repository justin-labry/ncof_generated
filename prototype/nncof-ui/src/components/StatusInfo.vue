<!-- 하단 상태 표시줄 (메시지 개수, 구독 상태, API/WS 연결 상태) -->
<script setup lang="ts">

import { ref, watch, onMounted } from 'vue';
import {  Cog } from 'lucide-vue-next';
// import { Terminal } from 'lucide-vue-next';

import { useNetworkStore } from '../store/network';

const store = useNetworkStore();

// WebSocket 수신 펄스 효과
const pulsing = ref(false);
watch(
  () => store.wsPulse,
  () => {
    pulsing.value = true;
    setTimeout(() => { pulsing.value = false; }, 600);
  },
);

// WS 로그 표시 토글
// const showLog = ref(false);
// const LOG_PREVIEW_COUNT = 10;
// const reversedLog = computed(() =>
//   store.wsLog.slice(-LOG_PREVIEW_COUNT).reverse(),
// );

const apiStatus = ref<any>({});
const apiLoading = ref(false);
const apiError = ref<string | null>(null);

const checkApiStatus = async () => {
  apiLoading.value = true;
  apiError.value = null;
  apiStatus.value = {};
  try {
    const response = await fetch('/api/status');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    apiStatus.value = data
  } catch (err) {
    console.log(err)
    apiError.value = err instanceof Error ? err.message : String(err);
  } finally {
    apiLoading.value = false;
  }
};

onMounted(() => {
  checkApiStatus();
});
</script>

<template>
  <div class="flex justify-center pointer-events-none">
    <div class="glass-panel p-4 flex flex-col gap-2 shadow-2xl pointer-events-auto border-white/5 bg-slate-900/60 transition-all hover:bg-slate-900/80 rounded-xl w-full">

      <h3 class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
        <Cog class="w-4 h-4 text-yellow-400/90"/> System Info
      </h3>
      <div class="flex gap-2 my-2">
        <div class="w-1 h-full bg-blue-500"></div>
        <div class="flex flex-col gap-1">
          <div class="text-xs flex gap-2">
            <span class="font-bold uppercase tracking-widest">NCOF</span>
            <span class="font-black text-yellow-500">{{ apiStatus?.version }}</span>
          </div>
          <span class="text-[9px] font-bold uppercase tracking-widest">Network Control &amp; Optimization Function</span>
          <span class="text-[8px] font-bold uppercase tracking-widest text-blue-400">{{apiStatus?.description}}</span>
          <span class="text-[9px] font-bold uppercase tracking-widest">2026</span>
        </div>
      </div>

      <!-- 구독 상태 -->
      <div class="flex items-center gap-2 hover:opacity-100 transition-opacity">
        <div class="w-3 h-3 rounded-full bg-amber-200"></div>
        <span class="text-xs font-bold uppercase tracking-widest">Subscriptions:</span>
        <span class="text-xs font-bold text-amber-200">{{ store.activeSubscriptions.filter((s) => s.to ==='ncof').length }}</span>
      </div>

      <!-- WebSocket 상태 -->
      <div class="flex items-center gap-2 hover:opacity-100 transition-opacity">
        <div class="relative">
          <div class="w-3 h-3 rounded-full" :class="{
            'bg-slate-500': store.wsStatus === 'DISCONNECTED',
            'bg-yellow-400': store.wsStatus === 'CONNECTING',
            'bg-emerald-500': store.wsStatus === 'CONNECTED',
            'bg-red-500': store.wsStatus === 'ERROR',
          }"></div>
          <div v-if="store.wsStatus === 'CONNECTING'" class="absolute inset-0 bg-yellow-400 rounded-full animate-ping opacity-75"></div>
        </div>
        <div class="flex gap-2 ">
          <span class="text-xs font-black text-slate-300 uppercase tracking-widest">WebSocket:</span>
          <span class="text-xs font-bold" :class="{
            'text-red-500': store.wsStatus === 'DISCONNECTED',
            'text-yellow-400': store.wsStatus === 'CONNECTING',
            'text-emerald-400': store.wsStatus === 'CONNECTED',
            'text-red-400': store.wsStatus === 'ERROR',
          }">{{ store.wsStatus }}</span>
        </div>
      </div>

      <!-- 서버정보 -->
      <div class="text-xs flex items-center gap-2">
        <div class="w-3 h-3 rounded-full bg-cyan-300"></div>
        <span class="font-black text-slate-300 uppercase tracking-widest">Server:</span>
        <span class="font-mono font-bold text-cyan-300">{{ apiStatus?.ip }}:{{ apiStatus?.port }}</span>
      </div>

      <!-- WS 로그 -->
      <!-- <div class="relative">
        <button @click="showLog = !showLog"
          class="flex items-center gap-2 opacity-60 hover:opacity-100 transition-opacity cursor-pointer">
          <Terminal class="w-3.5 h-3.5 text-slate-400" />
          <span class="text-[10px] font-black uppercase tracking-widest">Log</span>
          <span class="text-[10px] font-bold text-slate-600">{{ store.wsLog.length }}</span>
        </button>
      </div> -->

      <!-- WS 로그 드롭다운 (fixed로 다른 패널보다 위에 표시) -->
      <!-- <Teleport to="body">
        <div v-if="showLog"
          class="fixed z-999 bottom-2 left-2- w-[calc(100vw-30px)] m-4 max-h-52 overflow-y-auto bg-slate-900 border border-white/10 rounded-xl p-2 shadow-2xl custom-scrollbar pointer-events-auto"
          @click.self="showLog = false">
          <div v-for="(entry, i) in reversedLog" :key="i"
            class="text-[10px] font-mono text-slate-400 truncate hover:text-slate-200 transition-colors py-0.5">
            {{ entry }}
          </div>
          <div v-if="store.wsLog.length === 0"
            class="text-[10px] text-slate-600 text-center py-2">
            No logs yet
          </div>
        </div>
      </Teleport> -->
    </div>
  </div>
</template>

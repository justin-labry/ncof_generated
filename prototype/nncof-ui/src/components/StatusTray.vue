<!-- 하단 상태 표시줄 (메시지 개수, 구독 상태, API/WS 연결 상태) -->
<script setup lang="ts">

import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

import { Clock, Terminal } from 'lucide-vue-next';

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

// 실시간 시계
const now = ref(new Date());
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date();
  }, 1000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});

// WS 로그 표시 토글
const showLog = ref(false);
const LOG_PREVIEW_COUNT = 10;
const reversedLog = computed(() =>
  store.wsLog.slice(-LOG_PREVIEW_COUNT).reverse(),
);

// API Status State
const apiStatus = ref<string | null>(null);
const apiLoading = ref(false);
const apiError = ref<string | null>(null);

const checkApiStatus = async () => {
  apiLoading.value = true;
  apiError.value = null;
  apiStatus.value = null;
  try {
    const response = await fetch('/api/status');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    apiStatus.value = JSON.stringify(data, null, 2);
  } catch (err) {
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
    <div
      class="w-full p-1 flex items-center justify-end gap-8 pointer-events-auto border-white/5 bg-slate-900/60 transition-all hover:bg-slate-900/80"
      :class="{ 'animate-tray-pulse': pulsing }">

      <!-- 실시간 시계 -->
      <div class="flex items-center gap-2 mr-auto opacity-60">
        <Clock class="w-3.5 h-3.5 text-slate-400" />
        <span class="text-xs font-mono font-bold text-slate-400 tracking-wider">
          {{ now.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }) }}
          {{ now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) }}
        </span>
      </div>

      <div class="h-4 bg-white/10"></div>

      <!-- API 상태 -->
      <button @click="checkApiStatus" :disabled="apiLoading"
        class="flex items-center gap-3 opacity-60 hover:opacity-100 transition-opacity disabled:opacity-30 cursor-pointer">
        <div class="relative">
          <div class="w-3 h-3 rounded-full" :class="{
            'bg-slate-500': apiStatus === null && !apiError,
            'bg-emerald-500': apiStatus !== null,
            'bg-red-500': apiError !== null,
            'animate-pulse': apiLoading
          }"></div>
          <div v-if="apiLoading" class="absolute inset-0 bg-blue-400 rounded-full animate-ping opacity-75"></div>
        </div>
        <div class="flex gap-2 text-left">
          <span class="text-xs font-black text-slate-500 uppercase tracking-widest">API Status:</span>
          <span class="text-xs font-bold" :class="{
            'text-slate-500': apiStatus === null && !apiError,
            'text-emerald-400': apiStatus !== null,
            'text-red-400': apiError !== null
          }">
            {{ apiLoading ? 'CHECKING...' : apiError ? 'ERROR' : apiStatus ? 'CONNECTED' : 'IDLE' }}
          </span>
        </div>
      </button>

      <div class="h-4 bg-white/10"></div>

      <!-- WebSocket 상태 -->
      <div class="flex items-center gap-3 opacity-60 hover:opacity-100 transition-opacity">
        <div class="relative">
          <div class="w-3 h-3 rounded-full" :class="{
            'bg-slate-500': store.wsStatus === 'DISCONNECTED',
            'bg-yellow-400': store.wsStatus === 'CONNECTING',
            'bg-emerald-500': store.wsStatus === 'CONNECTED',
            'bg-red-500': store.wsStatus === 'ERROR',
          }"></div>
          <div v-if="store.wsStatus === 'CONNECTING'"
            class="absolute inset-0 bg-yellow-400 rounded-full animate-ping opacity-75"></div>
        </div>
        <div class="flex gap-2 ">
          <span class="text-xs font-black text-slate-500 uppercase tracking-widest">WebSocket Status:</span>
          <span class="text-xs font-bold" :class="{
            'text-red-500': store.wsStatus === 'DISCONNECTED',
            'text-yellow-400': store.wsStatus === 'CONNECTING',
            'text-emerald-400': store.wsStatus === 'CONNECTED',
            'text-red-400': store.wsStatus === 'ERROR',
          }">{{ store.wsStatus }}</span>
        </div>
      </div>

      <div class="h-4 w-0.5 bg-white/10"></div>

      <!-- WS 로그 -->
      <div class="relative">
        <button @click="showLog = !showLog"
          class="flex items-center gap-2 opacity-60 hover:opacity-100 transition-opacity cursor-pointer">
          <Terminal class="w-3.5 h-3.5 text-slate-400" />
          <span class="text-[10px] font-black uppercase tracking-widest">Log</span>
          <span class="text-[10px] font-bold text-slate-600">{{ store.wsLog.length }}</span>
        </button>
      </div>

      <!-- WS 로그 드롭다운 (fixed로 다른 패널보다 위에 표시) -->
      <Teleport to="body">
        <div v-if="showLog"
          class="fixed z-999 bottom-22 left-1/2 -translate-x-1/2 w-6xl m-4 max-h-52 overflow-y-auto bg-slate-900 border border-white/10 rounded-xl p-2 shadow-2xl custom-scrollbar pointer-events-auto"
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
      </Teleport>
    </div>
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

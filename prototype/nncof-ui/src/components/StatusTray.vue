<!-- 하단 상태 표시줄 (메시지 개수, 구독 상태, API/WS 연결 상태) -->
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useNetworkStore } from '../store/network';
import { Shield, RefreshCw } from 'lucide-vue-next';

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
  <div class="flex justify-center pointer-events-none mb-2">
    <div
      class="glass-panel w-full px-8 py-4 flex items-center gap-8 shadow-2xl pointer-events-auto border-white/5 bg-slate-900/60 transition-all hover:bg-slate-900/80"
      :class="{ 'animate-tray-pulse': pulsing }">
      
      <!-- 메시지 통계 -->
      <div class="flex items-center gap-3 opacity-60 hover:opacity-100 transition-opacity">
        <Shield class="w-4 h-4 text-emerald-500" />
        <span class="text-[10px] font-bold uppercase tracking-widest">Total Messages:</span>
        <span class="text-sm font-bold">{{ store.messageQueue.length }}</span>
      </div>
      
      <div class="h-4 bg-white/10"></div>
      
      <!-- 구독 상태 -->
      <div class="flex items-center gap-3 opacity-60 hover:opacity-100 transition-opacity">
        <RefreshCw class="w-4 h-4 text-blue-500 animate-spin-slow" />
        <span class="text-[10px] font-bold uppercase tracking-widest">Active Subscriptions:</span>
        <span class="text-sm font-bold">{{ store.activeSubscriptions.length }}</span>
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
          <span class="text-xs font-black text-slate-500 uppercase tracking-widest">API:</span>
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
          <span class="text-xs font-black text-slate-500 uppercase tracking-widest">WS:</span>
          <span class="text-xs font-bold" :class="{
            'text-red-500': store.wsStatus === 'DISCONNECTED',
            'text-yellow-400': store.wsStatus === 'CONNECTING',
            'text-emerald-400': store.wsStatus === 'CONNECTED',
            'text-red-400': store.wsStatus === 'ERROR',
          }">{{ store.wsStatus }}</span>
        </div>
      </div>
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

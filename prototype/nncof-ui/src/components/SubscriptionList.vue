<!-- 활성 구독 목록 표시 컴포넌트 -->
<script setup lang="ts">
import { ref, onMounted, inject, watch } from "vue";
import type { Ref } from "vue";
import { RefreshCw, XCircle, ChevronDown, ChevronRight } from "lucide-vue-next";
import VueJsonPretty from "vue-json-pretty";
import "vue-json-pretty/lib/styles.css";

import { useNetworkStore } from "../store/network";
import { nodeColorClass } from "../utils/nodeColors";

const store = useNetworkStore();

// Subscription List State
const rawData = ref<Record<string, any>[]>([]);
const loading = ref(false);
const refreshed = ref(false);
const expanded = ref<Record<string, boolean>>({});
const error = ref<string | null>(null);

// 인라인 확인 상태 (unsubscribe 버튼 → Yes/No)
const confirmingSubId = ref<string | null>(null);

// 상세보기 모달
const detailModalEntry = ref<any | null>(null);
const openDetailModal = (entry: any) => {
  detailModalEntry.value = entry;
};
const closeDetailModal = () => {
  detailModalEntry.value = null;
};

const toggle = (key: string) => {
  expanded.value[key] = !expanded.value[key];
};

const BASE_URI = "/api/subscriptions/all";

// AppHeader 새로고침 트리거 구독
const refreshKey = inject<Ref<number>>("refreshKey", ref(0));
watch(refreshKey, () => {
  fetchAll().catch((err) => {
    console.error("[SubscriptionList] fetchAll error:", err);
  });
});

const fetchAll = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(BASE_URI);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    rawData.value = await response.json();
    // 새로고침 완료 표시 애니메이션
    refreshed.value = true;
    setTimeout(() => { refreshed.value = false; }, 1200);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loading.value = false;
  }
};

const requestUnsubscribe = (subId: string) => {
  confirmingSubId.value = subId;
};

const cancelUnsubscribe = () => {
  confirmingSubId.value = null;
};

const confirmUnsubscribe = async (subId: string, sub: any) => {
  if (!subId) return;
  confirmingSubId.value = null;
  loading.value = true;
  try {
    const response = await fetch(`/subscriptions/${subId}`, {
      method: "DELETE",
    });
    if (response.ok) {
      rawData.value = rawData.value.filter(
        (s: any) => s.subscriptionId !== subId,
      );

      const fromSub = sub.from || sub.subscription?.from;
      const toSub = sub.to || sub.subscription?.to;
      if (fromSub && toSub) {
        store.removeSubscription(fromSub, toSub);
      }

      if (sub.externalSubscriptions?.length > 0) {
        sub.externalSubscriptions.forEach((ext: any) => {
          const extTo = ext.target || ext.subscription?.to;
          if (extTo) {
            store.removeSubscription("ncof", extTo, ext.externalSubId);
          }
        });
      }

      console.log(`[Unsubscribe] Success: ${subId}`);
    } else {
      const errText = await response.text();
      console.error(`[Unsubscribe] Failed: ${subId}`, errText);
    }
  } catch (err) {
    console.error("[Unsubscribe] Error:", err);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchAll);
</script>

<template>
  <div class="flex flex-col gap-4 z-10 pointer-events-none " v-bind="$attrs">
    <div class="p-2 pointer-events-auto border-white/5 flex flex-col gap-3 h-full" >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-1 h-4 bg-blue-500 "></div>
          <h2 class="text-xs font-black uppercase tracking-widest text-slate-400" > Subscriptions </h2>
        </div>
        <button @click="fetchAll" :disabled="loading" class="p-1.5 hover:bg-white/5 rounded-lg transition-all duration-300 text-slate-500 hover:text-blue-400 disabled:opacity-30" >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshed, 'animate-pulse': refreshed }" />
        </button>
      </div>

      <div
        v-if="Object.keys(rawData).length === 0 && !loading"
        class="flex-1 flex flex-col justify-center p-8 text-center text-sm text-slate-600 font-bold uppercase border border-dashed border-white/5 rounded-2xl"
      >
        No Active Subscriptions
      </div>

      <div class="flex flex-col gap-2 custom-scrollbar">
        <div v-for="sub in rawData" :key="sub.subscriptionId" class="bg-white/2 hover:bg-white/4 border border-white/5 rounded-2xl transition-all duration-300" >
          <!-- Clickable header: expand/collapse toggle -->
          <div class="p-2 cursor-pointer select-none" >
            <div class="w-full text-xs mt-2">
              <!-- Main Subscription row -->
              <div class="flex gap-1 items-center px-1.5 py-1.5 border-b border-white/3 hover:bg-gray-600/80 transition-colors rounded-2xl" @click="toggle(sub.subscriptionId)">
                <div class="flex items-center gap-1">
                  <ChevronDown v-if="expanded[sub.subscriptionId]" class="w-3 h-3 text-slate-500 shrink-0" />
                  <ChevronRight v-else class="w-3 h-3 text-slate-500 shrink-0" />
                  <div class="w-2 h-2 bg-blue-500/80 rounded-full"></div>
                  <span class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2">SUBSCRIPTION</span>
                </div>
                <div class="flex gap-1 truncate w-40 font-mono text-gray-400"> {{ sub.subscriptionId }} </div>
                <div class="flex gap-2 w-32">
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass(sub.fromNode)">{{ sub.fromNode }}</span>
                  <span class="text-blue-500 font-bold">→</span>
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass('ncof')">NCOF</span>
                </div>
                <div class="flex gap-2">
                  <span class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-1">{{ sub.eventReq?.notificationMethod }}</span>
                  <span class="bg-purple-400/10 border border-purple-400/20 rounded font-black text-purple-400 px-1">{{ sub.eventReq?.repPeriod }}s</span>
                </div>

                <div>
                  <button @click.stop="openDetailModal(sub.data)" class="text-[10px] px-2 py-1 rounded bg-slate-700/30 hover:bg-slate-600/50 text-slate-400 hover:text-slate-200 transition-colors hover:cursor-pointer w-max">상세보기</button>
                </div>
              </div>
              <!-- Expanded detail content (hover content moved here) -->
              <div v-if="expanded[sub.subscriptionId]" class="border-t border-white/5 px-4 pb-4">
                <div class="flex items-center gap-2 mt-3 mb-2">
                  <template v-if="confirmingSubId === sub.subscriptionId">
                    <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Unsubscribe?</span>
                    <button @click="confirmUnsubscribe(sub.subscriptionId, sub)" :disabled="loading"
                      class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-30">
                      Yes
                    </button>
                    <button @click="cancelUnsubscribe" :disabled="loading"
                      class="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-30">
                      No
                    </button>
                  </template>
                  <button v-else @click.prevent="requestUnsubscribe(sub.subscriptionId)" :disabled="loading"
                    class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-30">
                    <XCircle class="w-3.5 h-3.5" />
                    Unsubscribe
                  </button>
                </div>

                <div v-if="sub.externalSubscriptions?.length > 0" class="space-y-1 mt-2">
                  <div class="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">External Subscriptions</div>
                  <div v-for="ext in sub.externalSubscriptions" :key="ext.externalSubId" class="text-[11px] text-slate-400">
                    <span class="font-bold text-slate-300">{{ ext.target }}:</span>
                    notifUri:
                    <span class="font-mono text-green-400 break-all">{{ ext.subscription?.notifUri }}</span>
                  </div>
                </div>
              </div>
              <!-- External Subscription rows -->
              <div v-if="sub.externalSubscriptions?.length > 0" class="border-t border-white/5 mt-1 pt-1">
                <div v-for="ext in sub.externalSubscriptions" :key="ext.externalSubId">
                  <div class="flex gap-1 items-center px-1.5 py-1.5 border-b border-white/3 hover:bg-gray-600/80 transition-colors rounded-2xl">

                    <div class="ml-4 w-2 h-2 bg-blue-500/80 rounded-full"></div>
                    <div class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2 w-max">
                        SUBSCRIPTION
                    </div>
                    <div class="flex gap-1 truncate w-40 font-mono text-gray-400">
                      {{ ext.externalSubId || sub.subscriptionId }}
                    </div>
                    <div class="flex gap-2 w-32">
                      <span class="font-black uppercase bg-amber-500/20 px-2 text-amber-400 w-max rounded-2xl">NCOF</span>
                      <span class="text-blue-500 font-bold">→</span>
                      <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass(ext.target)">{{ ext.target?.slice(0, 4) }}</span>
                    </div>

                    <div class="flex gap-2">
                      <span class="bg-blue-500/20 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-1">{{ ext.subscription?.eventReq?.notificationMethod }}</span>
                      <span class="bg-purple-400/10 border border-purple-400/20 rounded font-black px-1">{{ ext.subscription?.eventReq?.repPeriod }}s</span>
                    </div>

                    <!-- <div class="flex flex-wrap- gap-1 truncate col-span-2">
                      <span v-for="ee in ext.subscription?.eventSubscriptions" :key="ee.event" class="font-bold text-blue-500/80">#{{ ee.event }}</span>
                    </div> -->

                    <!-- {{ ext.subscription?.data.nfId }} -->

                    <button @click.stop="openDetailModal(ext.subscription?.data)" class="text-[10px] px-2 py-1 rounded bg-slate-700/30 hover:bg-slate-600/50 text-slate-400 hover:text-slate-200 transition-colors hover:cursor-pointer w-max">상세보기</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error" class="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 font-medium" >
        Error: {{ error }}
      </div>
    </div>
  </div>
  <!-- 상세보기 모달 -->
  <Teleport to="body">
    <div v-if="detailModalEntry"
      class="fixed inset-0 z-9999 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      @click.self="closeDetailModal">
      <div class="relative w-[90vw] max-w-3xl max-h-[85vh] bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        <div class="flex items-center justify-between px-5 py-3 border-b border-white/10 shrink-0">
          <h3 class="text-sm font-bold text-slate-300 truncate">Detail — {{ detailModalEntry.subscriptionId || detailModalEntry.externalSubId }}</h3>
          <button @click="closeDetailModal"
            class="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/10 text-slate-500 hover:text-slate-200 transition-colors text-lg leading-none">&times;</button>
        </div>
        <div class="flex-1 overflow-auto p-4 custom-scrollbar">
          <vue-json-pretty
            :data="detailModalEntry"
            :deep="3"
            theme="dark"
            show-length
            show-icon
            :show-line="true"
            :show-double-quotes="true"
            :collapsed-node-length="100"
            class="json-pretty-modal"
          />
        </div>
      </div>
    </div>
  </Teleport>

</template>

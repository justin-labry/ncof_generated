<!-- 활성 구독 목록 표시 컴포넌트 -->
<script setup lang="ts">
import { ref, onMounted, inject, watch } from "vue";
import type { Ref } from "vue";
import { RefreshCw, XCircle, FileText, ChevronDown, ChevronRight } from "lucide-vue-next";

import { useNetworkStore } from "../store/network";
import { nodeColorClass } from "../utils/nodeColors";

const store = useNetworkStore();

// Subscription List State
const rawData = ref<Record<string, any>[]>([]);
const loading = ref(false);
const refreshed = ref(false);
const expanded = ref<Record<string, boolean>>({});
const error = ref<string | null>(null);

const toggle = (key: string) => {
  expanded.value[key] = !expanded.value[key];
};

const BASE_URI = "/api/subscriptions/all";

// AppHeader 새로고침 트리거 구독
const refreshKey = inject<Ref<number>>("refreshKey", ref(0));
watch(refreshKey, () => { fetchAll(); });

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

const unsubscribeSubscription = async (subId: string, sub: any) => {
  if (!subId) return;
  if (!confirm("Unsubscribe this subscription?")) return;

  loading.value = true;
  try {
    const response = await fetch(`/subscriptions/${subId}`, {
      method: "DELETE",
    });
    if (response.ok) {
      // 로컬 목록에서 제거
      rawData.value = rawData.value.filter(
        (s: any) => s.subscriptionId !== subId,
      );

      // store의 activeSubscriptions 에서도 제거
      const fromSub = sub.from || sub.subscription?.from;
      const toSub = sub.to || sub.subscription?.to;
      if (fromSub && toSub) {
        store.removeSubscription(fromSub, toSub);
      }

      // externalSubscriptions 도 정리
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
  <div class="flex flex-col gap-4 z-10 pointer-events-none h-full">
    <div
      class="glass-panel p-4 rounded-xl shadow-2xl pointer-events-auto border-white/5 flex flex-col gap-3 h-full"
    >
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <div class="w-2 h-4 bg-blue-500 rounded-full"></div>
          <h2
            class="text-xs font-black uppercase tracking-widest text-slate-400"
          >
            Subscriptions
          </h2>
        </div>
        <button
          @click="fetchAll"
          :disabled="loading"
          class="p-1.5 hover:bg-white/5 rounded-lg transition-all duration-300 text-slate-500 hover:text-blue-400 disabled:opacity-30"
          :class="{ '!text-emerald-400 !bg-emerald-500/20 ring-1 ring-emerald-500/40': refreshed }"
        >
          <RefreshCw
            class="w-3.5 h-3.5"
            :class="{ 'animate-spin': loading, 'animate-pulse': refreshed }"
          />
        </button>
      </div>

      <div
        class="flex flex-col gap-2 max-h-100 overflow-y-auto pr-1 custom-scrollbar h-full"
      >
        <div
          v-if="Object.keys(rawData).length === 0 && !loading"
          class="flex items-center justify-center py-8 text-center text-[10px] text-slate-600 font-bold uppercase tracking-widest border border-dashed border-white/5 rounded-2xl h-full"
        >
          No Active Subscriptions
        </div>

        <div
          v-for="sub in rawData"
          :key="sub.subscriptionId"
          class="bg-white/2 hover:bg-white/4 border border-white/5 rounded-2xl transition-all duration-300"
        >
          <!-- Clickable header: expand/collapse toggle -->
          <div class="p-4 cursor-pointer select-none" @click="toggle(sub.subscriptionId)">
            <div class="w-full text-xs mt-2">
              <!-- Table Header -->
              <!-- <div class="grid grid-cols-5 gap-1 items-center px-1.5 py-1.5 border-b border-white/3">
                <div class="text-center">TYPE</div>
                <div class="text-center">subscription id</div>
                <div class="text-center">DIRECTION</div>
                <div class="text-center">PERIOD</div>
                <div class="text-center">Events</div>
              </div> -->

              <!-- Main Subscription row -->
              <div class="grid grid-cols-6 gap-1 items-center px-1.5 py-1.5 border-b border-white/3">
                <div class="flex items-center gap-1">
                  <ChevronDown v-if="expanded[sub.subscriptionId]" class="w-3 h-3 text-slate-500 shrink-0" />
                  <ChevronRight v-else class="w-3 h-3 text-slate-500 shrink-0" />
                  <span class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2">SUBSCRIPTION</span>
                </div>
                <div class="flex gap-1 truncate">
                  <FileText class="w-3.5 h-3.5 text-slate-500 shrink-0" />{{ sub.subscriptionId }}
                </div>
                <div class="flex gap-2">
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass(sub.fromNode)">{{ sub.fromNode }}</span>
                  <span class="text-blue-500 font-bold">→</span>
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass('ncof')">NCOF</span>
                </div>
                <div class="flex gap-2">
                  <span class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2">{{ sub.eventReq?.notificationMethod }}</span>
                  <span class="rounded font-black text-purple-400 px-2">{{ sub.eventReq?.repPeriod }}s</span>
                </div>
                <div class="flex flex-wrap- gap-1 overflow-hidden col-span-2">
                  <span v-for="e in sub.eventSubscriptions" :key="e.event" class="font-bold text-blue-500/80">#{{ e.event }}</span>
                </div>
              </div>


          <!-- Expanded detail content (hover content moved here) -->
          <div v-if="expanded[sub.subscriptionId]" class="border-t border-white/5 px-4 pb-4">
            <div class="flex items-center gap-2 mt-3 mb-2">
              <button @click="unsubscribeSubscription(sub.subscriptionId, sub)" :disabled="loading"
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
                  <div class="grid grid-cols-6 gap-1 items-center px-1.5 py-1.5 border-b border-white/3">

                    <div class="ml-4 bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2 w-max">EXTERNAL</div>
                    <div class="flex gap-1 truncate">
                      <FileText class="w-3.5 h-3.5 text-slate-500 shrink-0" />{{ ext.externalSubId || sub.subscriptionId }}
                    </div>
                    <div class="flex gap-2">
                      <span class="font-black uppercase bg-amber-500/20 px-2 text-amber-400 w-max rounded-2xl">NCOF</span>
                      <span class="text-blue-500 font-bold">→</span>
                      <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass(ext.target)">{{ ext.target?.slice(0, 4) }}</span>
                    </div>
                    <div class="flex gap-2">
                      <span class="bg-blue-500/10 border border-blue-500/20 rounded font-black text-blue-400 uppercase px-2">{{ ext.subscription?.eventReq?.notificationMethod }}</span>
                      <span class="font-black text-purple-400 px-2">{{ ext.subscription?.eventReq?.repPeriod }}s</span>
                    </div>
                    <div class="flex flex-wrap- gap-1 truncate col-span-2">
                      <span v-for="ee in ext.subscription?.eventSubscriptions" :key="ee.event" class="font-bold text-blue-500/80">#{{ ee.event }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div
        v-if="error"
        class="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 font-medium"
      >
        Error: {{ error }}
      </div>
    </div>
  </div>
</template>

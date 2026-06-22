<!-- 제어 Notification 데이터를 구독별로 조회/표시하는 컴포넌트 -->
<script setup lang="ts">
import 'vue-json-pretty/lib/styles.css';

import { ref, computed, onMounted, inject, watch } from 'vue';
import type { Ref } from 'vue';

import { Bell, RefreshCw, ChevronDown, ChevronRight } from 'lucide-vue-next';

import VueJsonPretty from 'vue-json-pretty';

import { nodeColorClass, extractMiddle } from '../utils/nodeColors';

const rawData = ref<Record<string, any>[]>([]);
const loading = ref(false);
const refreshed = ref(false);
const error = ref<string | null>(null);
const expanded = ref<Record<string, boolean>>({});

const subIds = computed(() => Object.keys(rawData.value));

interface CtrlEntry {
  id: string;
  corrId: string;
  content: any;
}

const BASE_URI = '/api/controls/all'

// AppHeader 새로고침 트리거 구독
const refreshKey = inject<Ref<number>>('refreshKey', ref(0));
watch(refreshKey, () => {
  fetchAll().catch((err) => {
    console.error("[ControlList] fetchAll error:", err);
  });
});

const entriesBySub = computed(() => {
  const result: Record<string, CtrlEntry[]> = {};
  for (const [subId, corrMap] of Object.entries(rawData.value)) {
    const entries: CtrlEntry[] = [];
    for (const [corrId, data] of Object.entries(corrMap as Record<string, any>)) {
      entries.push({ id: corrId, corrId, content: data });
    }
    result[subId] = entries;
  }
  return result;
});

const fetchAll = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(BASE_URI);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
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

const detailModalEntry = ref<CtrlEntry | null>(null);

const openDetailModal = (entry: CtrlEntry) => {
  detailModalEntry.value = entry;
};

const closeDetailModal = () => {
  detailModalEntry.value = null;
};

const toggle = (key: string) => {
  expanded.value[key] = !expanded.value[key];
};

onMounted(fetchAll);
</script>

<template>
  <div class="flex flex-col gap-4 z-10 pointer-events-none" v-bind="$attrs">
    <div class="p-2 pointer-events-auto border-white/5 flex flex-col gap-3 h-full">
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <div class="w-1 h-4 bg-rose-500 rounded-full"></div>
          <h2 class="text-xs font-black uppercase tracking-widest text-slate-400">Controls - NCOF to NF</h2>
        </div>
        <button
          @click="fetchAll" :disabled="loading"
          class="p-1.5 hover:bg-white/5 rounded-lg transition-all duration-300 text-slate-500 hover:text-rose-400 disabled:opacity-30"
          >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshed}" />
        </button>
      </div>

      <div v-if="subIds.length === 0 && !loading"
        class="flex-1 flex flex-col justify-center p-8 text-center text-sm text-slate-600 font-bold uppercase border border-dashed border-white/5 rounded-2xl">
        No Active Controls
      </div>

      <div class="flex flex-col gap-2 flex-1- min-h-0 overflow-y-auto pr-1- custom-scrollbar">

        <div v-for="subId in subIds" :key="subId"
          class="rounded-xl p-1 transition-all duration-300">

          <div class="flex items-center gap-2 mb-3">
            <Bell class="w-4 h-4 text-rose-400 shrink-0" />
            <span class="text-sm font-black text-slate-300 tracking-tighter truncate">S_ID:</span>
            <span class="text-sm font-black text-slate-300 tracking-tighter truncate">{{ subId }}</span>
            <span class="text-[10px] font-bold text-slate-600 ml-auto">{{ entriesBySub[subId]?.length ?? 0 }}</span>
          </div>

          <div class="flex flex-col gap-1">
            <div v-for="entry in entriesBySub[subId]" :key="entry.id"
              class="bg-black/30- border-b- border-gray-600/30 text-xs text-white/30 overflow-hidden">

              <div class="flex items-center gap-2 p-2 cursor-pointer rounded-full hover:bg-gray-600/80 transition-colors select-none"
                @click="toggle(`${subId}:${entry.id}`)">
                <ChevronRight v-if="expanded[`${subId}:${entry.id}`]" class="w-3 h-3 text-slate-500 shrink-0" />
                <ChevronDown v-else class="w-3 h-3 text-slate-500 shrink-0" />
                <div class="w-2 h-2 bg-red-500/70 rounded-full"></div>
                <div class="text-xs text-center bg-red-500/10 border border-red-500/20 rounded font-black text-red-400 uppercase px-2 w-max">Control</div>

                <span class="text-[11px] font-mono font-bold text-slate-400 truncate w-40">{{ entry.id }}</span>

                <span class="px-1 py-0.5 text-center rounded font-black text-[11px] uppercase" :class="nodeColorClass('ncof')">NCOF</span>
                <span class="w-4 text-blue-500 font-bold text-center">→</span>
                <span class="px-1 py-0.5 text-center rounded font-black text-[11px] uppercase" :class="nodeColorClass(extractMiddle(entry.id))">{{ extractMiddle(entry.id) }}</span>
                                    <button @click.stop="openDetailModal(entry)" class="text-[10px] px-2 py-1 rounded bg-slate-700/30 hover:bg-slate-600/50 text-slate-400 hover:text-slate-200 transition-colors hover:cursor-pointer w-max">상세보기</button>
              </div>

              <!-- Expanded Contents -->
              <div v-if="!expanded[`${subId}:${entry.id}`]" class="border-white/3 bg-slate-700/20 rounded-lg m-2">
                <div v-for="value, idx of entry.content?.eventNotifications" :key="idx" class="p-2 flex flex-col gap-2">
                  <div class="flex gap-2 items-center">
                    <span class="px-2 py-1 w-max text-xs rounded bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/20 hover:border-blue-500/40 text-blue-300 hover:text-blue-300 font-black uppercase ">
                      {{ value.event }}
                    </span>
                    <!-- <button @click.stop="openDetailModal(entry)" class="text-[10px] px-2 py-1 rounded bg-slate-700/30 hover:bg-slate-600/50 text-slate-400 hover:text-slate-200 transition-colors">상세보기</button> -->
                  </div>

                  <!--_CELL_POWER_CTRL -->

                  <div v-for="cell_opt_infos, idx of value._cellPowerCtrlOptInfos" :key="idx" class="text-sm min-h-32">
                    <div v-for="cell_infos, idx of cell_opt_infos" :key="idx">
                      <div v-for="param_sets, idx of cell_infos" :key="idx">
                          <div v-for="x, idx of param_sets?._cellPowerParamSets" :key="idx" class="mt-2">

                            <div class="flex flex-row items-start">
                              <table class="flex-1 text-[11px] border-collapse">
                                <thead>
                                  <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                    <th class="px-2 py-1 border-b border-white/10 w-1/2">Parameter</th>
                                    <th class="px-2 py-1 border-b border-white/10">Value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">cellPowerState</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ x._cellPowerParamSet?._cellPowerState }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">cellTxPower</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._cellTxPower }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">ssPbchBlockPower</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._ssPbchBlockPower }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">siBlockPower</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._siBlockPower }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">pdschBlockPower</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._pdschBlockPower }}</td>
                                  </tr>
                                </tbody>
                              </table>
                              <!-- 오른쪽 테이블: 나머지 4개 파라미터 -->
                              <table class="flex-1 text-[11px] border-collapse">
                                <thead>
                                  <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                    <th class="px-2 py-1 border-b border-white/10 w-1/2">Parameter</th>
                                    <th class="px-2 py-1 border-b border-white/10">Value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">pdcchBlockPower</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._pdcchBlockPower }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">csiRsPowerOffset</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._csiRsPowerOffset }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">qRxLevMin</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._qRxLevMin }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">cellIndividualOffset</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ x._cellPowerParamSet?._cellIndividualOffset }}</td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          </div>

                      </div>
                    </div>
                  </div>

                  <!-- QOS_POLICY_ASSIST -->
                  <div v-for="(q, qIdx) of value.qosPolAssistInfos" :key="qIdx" v-if="value.qosPolAssistInfos">
                    <div v-for="(q2, q2Idx) of q.qosPolAssistInfo" :key="q2Idx">
                      <div v-if="q2.qosPolAssistSets?.length" class="mt-2">
                        <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">QoS Policy Assist Sets (Info {{ qIdx }} / Set {{ q2Idx }})</div>
                        <table class="w-full text-[11px] border-collapse">
                          <thead>
                            <tr class="text-left text-slate-500 font-bold tracking-wider">
                              <th class="px-1 py-1 border-b border-white/10">#</th>
                              <th class="px-1 py-1 border-b border-white/10">gnbValue</th>
                              <th class="px-1 py-1 border-b border-white/10">n3LwfId</th>
                              <th class="px-1 py-1 border-b border-white/10">gbrDl</th>
                              <th class="px-1 py-1 border-b border-white/10">mbrDl</th>
                              <th class="px-1 py-1 border-b border-white/10 truncate">ratType</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(q3, q3Idx) of q2.qosPolAssistSets" :key="q3Idx"
                              class="even:bg-white/3 hover:bg-white/6 transition-colors">
                              <td class="px-1 py-1 text-slate-600 border-b border-white/5 truncate">{{ q3Idx }}</td>
                              <td class="px-1 py-1 font-mono text-sky-300 border-b border-white/5 max-w-12 truncate-">{{ q3.spatialValidity.gRanNodeIds[0]?.gNbId?.gNBValue }}</td>
                              <td class="px-1 py-1 font-mono text-sky-300 border-b border-white/5 max-w-12 truncate-">{{ q3.spatialValidity.gRanNodeIds[0]?.n3IwfId }}</td>
                              <td class="px-1 py-1 font-mono text-emerald-300 border-b border-white/5">{{ q3.qosParamSet?.gbrDl ?? '-' }}</td>
                              <td class="px-1 py-1 font-mono text-amber-300 border-b border-white/5">{{ q3.qosParamSet?.mbrDl ?? '-' }}</td>
                              <td class="px-1 py-1 font-mono text-amber-300 border-b border-white/5">{{ q3.ratTypes?.join(',') ?? '-' }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error"
        class="p-2 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 font-medium">
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
          <h3 class="text-sm font-bold text-slate-300 truncate">Detail — {{ detailModalEntry.id }}</h3>
          <button @click="closeDetailModal"
            class="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/10 text-slate-500 hover:text-slate-200 transition-colors text-lg leading-none">&times;</button>
        </div>
        <div class="flex-1 overflow-auto p-4 custom-scrollbar">
          <vue-json-pretty
            :data="detailModalEntry"
            :deep="8"
            theme="dark"
            show-length
            show-icon
            :show-line="true"
            :show-double-quotes="true"
            :collapsed-node-length="30"
            class="json-pretty-modal"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style>
</style>

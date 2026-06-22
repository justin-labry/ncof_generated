<!-- Notification 데이터를 구독별로 조회/표시하는 컴포넌트 -->
<script setup lang="ts">
import { ref, computed, onMounted, inject, watch } from 'vue';
import type { Ref } from 'vue';
import { Bell, RefreshCw, ChevronDown, ChevronRight } from 'lucide-vue-next';
import VueJsonPretty from 'vue-json-pretty';
import 'vue-json-pretty/lib/styles.css';

import { nodeColorClass, extractMiddle } from '../utils/nodeColors';

const rawData = ref<Record<string, any>[]>([]);
const loading = ref(false);
const refreshed = ref(false);
const error = ref<string | null>(null);
const expanded = ref<Record<string, boolean>>({});

const subIds = computed(() => Object.keys(rawData.value));

const BASE_URI = '/api/notifications/all'

// AppHeader 새로고침 트리거 구독
const refreshKey = inject<Ref<number>>('refreshKey', ref(0));
watch(refreshKey, () => {
  fetchAll().catch((err) => {
    console.error("[NotificationList] fetchAll error:", err);
  });
});

const notificationsBySub = computed(() => {
  const result: Record<string, any[]> = {};
  for (const [subId, sources] of Object.entries(rawData.value)) {
    const entries: any[] = [];
    for (const [sourceNf, dataTypes] of Object.entries(sources as Record<string, any>)) {
      entries.push({notifUri: sourceNf, data: dataTypes})
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

onMounted(fetchAll);
</script>

<template>
  <div class="flex flex-col gap-4 z-10 pointer-events-none" v-bind="$attrs">
    <div class="p-2 pointer-events-auto border-white/5 flex flex-col gap-3 h-full">
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <div class="w-1 h-4 bg-amber-500 rounded-full"></div>
          <h2 class="text-xs font-black uppercase tracking-widest text-slate-400">Notifications</h2>
        </div>
        <button
          @click="fetchAll" :disabled="loading"
          class="p-1.5 hover:bg-white/5 rounded-lg transition-all duration-300 text-slate-500 hover:text-amber-400 disabled:opacity-30"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshed}" />
        </button>
      </div>

      <div v-if="subIds.length === 0 && !loading"
        class="flex-1 flex flex-col justify-center p-8 text-center text-sm text-slate-600 font-bold uppercase border border-dashed border-white/5 rounded-2xl">
        No Active Notifications
      </div>

      <div class="flex flex-col gap-2 custom-scrollbar">

        <div v-for="subId in subIds" :key="subId"
          class="bg-white/2 border border-white/5 rounded-2xl p-4 transition-all duration-300">

          <div class="flex items-center gap-2 mb-3">
            <Bell class="w-4 h-4 text-amber-400 shrink-0" />
            <span class="text-sm font-black text-slate-300 tracking-tighter truncate">S_ID:</span>
            <span class="text-sm font-black text-slate-300 tracking-tighter truncate"> {{ subId }} </span>
            <span class="text-[10px] font-bold text-slate-600 ml-auto">{{ notificationsBySub[subId]?.length ?? 0 }}</span>
          </div>

          <div class="flex flex-col gap-0.5">
            <div v-for="entry in notificationsBySub[subId]" :key="entry.id" class="border-gray-600/30 overflow-hidden text-xs" >
              <div class="rounded-full flex items-center gap-2 p-1 cursor-pointer hover:bg-blue-300/20 transition-colors select-none" @click="toggle(`${subId}:${entry.notifUri}`)">
                <ChevronDown v-if="expanded[`${subId}:${entry.notifUri}`]" class="w-3 h-3 text-slate-500 shrink-0" />
                <ChevronRight v-else class="w-3 h-3 text-slate-500 shrink-0" />
                <div class="w-2 h-2 bg-yellow-500/70 rounded-full"></div>
                <div class="text-center bg-yellow-500/10 border border-yellow-500/20 rounded font-black text-yellow-400 uppercase px-2 w-max">Notification</div>
                <!-- <FileText class="w-3.5 h-3.5 text-slate-500 shrink-0" /> -->
                <span class="text-[11px] font-mono font-bold text-slate-400 truncate w-48" :title="entry.notifUri">{{ entry.notifUri  }}</span>
                <div class="flex justify-between items-center gap-1 w-28">
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass(extractMiddle(entry.notifUri))">{{ extractMiddle(entry.notifUri) }}</span>
                  <span class="text-blue-500 font-bold text-center">→</span>
                  <span class="font-black uppercase w-max rounded-2xl px-2" :class="nodeColorClass('ncof')">NCOF</span>
                </div>
                <!-- <span class="text-xs" v-if="entry.data.eventNotifs">{{ entry.data.eventNotifs?.length }}</span>
                <span class="text-xs" v-if="entry.data.notificationItems">{{ entry.data.notificationItems?.length }}</span> -->
                <button @click.stop="openDetailModal(entry.data)" class="text-[10px] px-2 py-1 rounded bg-slate-700/30 hover:bg-slate-600/50 text-slate-400 hover:text-slate-200 transition-colors hover:cursor-pointer">상세보기</button>
              </div>

              <div v-if="expanded[`${subId}:${entry.notifUri}`]" class="">
                <div class="">
                    <!-- UPF Notification -->
                    <div v-if="entry.data.notificationItems">
                      <div v-for="(item,idx) of entry.data.notificationItems" :key="idx" class="" >
                        <div class="px-1.5 text-[10px]">
                          <div class="px-1.5 py-0.5 ">
                            <!-- <span class="uppercase">event type:</span> {{ item.eventType }} -->
                          </div>

                          <div v-if="item.eventType === 'USER_DATA_USAGE_MEASURES'" class="px-1 pb-2">
                            <div class="flex items-center gap-1">
                              <div class="w-1 h-4 bg-amber-500 rounded-full"></div>
                              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                                USER_DATA_USAGE_MEASURES
                              </div>
                            </div>

                            <table class="w-full text-[11px] border-collapse">
                              <thead>
                                <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                  <th class="px-2 py-1 border-b border-white/10">#</th>
                                  <th class="px-2 py-1 border-b border-white/10">Flow Desc</th>
                                  <th class="px-2 py-1 border-b border-white/10">Avg TP</th>
                                  <th class="px-2 py-1 border-b border-white/10">Peak TP</th>
                                  <th class="px-2 py-1 border-b border-white/10">Avg Pkt TP</th>
                                  <th class="px-2 py-1 border-b border-white/10">Volume</th>
                                  <th class="px-2 py-1 border-b border-white/10">Packets</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr v-for="(value, idx) of item.userDataUsageMeasurements" :key="idx"
                                  class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                  <td class="px-2 py-1 text-slate-600 border-b border-white/5 align-top">{{ idx }}</td>
                                  <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5 align-top max-w-20 truncate" :title="value.flowInfo?.flowDescription ?? '-'">{{ value.flowInfo?.flowDescription ?? '-' }}</td>
                                  <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5 align-top whitespace-nowrap">
                                    <template v-if="value.throughputStatisticsMeasurement">
                                      <div v-if="value.throughputStatisticsMeasurement.ulAverageThroughput">UL: {{ value.throughputStatisticsMeasurement.ulAverageThroughput }}</div>
                                      <div v-if="value.throughputStatisticsMeasurement.dlAverageThroughput">DL: {{ value.throughputStatisticsMeasurement.dlAverageThroughput }}</div>
                                    </template>
                                    <span v-else class="text-slate-600">-</span>
                                  </td>
                                  <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5 align-top whitespace-nowrap">
                                    <template v-if="value.throughputStatisticsMeasurement">
                                      <div v-if="value.throughputStatisticsMeasurement.ulPeakThroughput">UL: {{ value.throughputStatisticsMeasurement.ulPeakThroughput }}</div>
                                      <div v-if="value.throughputStatisticsMeasurement.dlPeakThroughput">DL: {{ value.throughputStatisticsMeasurement.dlPeakThroughput }}</div>
                                    </template>
                                    <span v-else class="text-slate-600">-</span>
                                  </td>
                                  <td class="px-2 py-1 font-mono text-violet-300 border-b border-white/5 align-top whitespace-nowrap">
                                    <template v-if="value.throughputStatisticsMeasurement">
                                      <div v-if="value.throughputStatisticsMeasurement.ulAveragePacketThroughput">UL: {{ value.throughputStatisticsMeasurement.ulAveragePacketThroughput }}</div>
                                      <div v-if="value.throughputStatisticsMeasurement.dlAveragePacketThroughput">DL: {{ value.throughputStatisticsMeasurement.dlAveragePacketThroughput }}</div>
                                    </template>
                                    <span v-else class="text-slate-600">-</span>
                                  </td>
                                  <td class="px-2 py-1 font-mono text-teal-300 border-b border-white/5 align-top whitespace-nowrap">
                                    <template v-if="value.volumeMeasurement">
                                      <div v-if="value.volumeMeasurement.ulVolume">UL: {{ value.volumeMeasurement.ulVolume }}</div>
                                      <div v-if="value.volumeMeasurement.dlVolume">DL: {{ value.volumeMeasurement.dlVolume }}</div>
                                    </template>
                                    <span v-else class="text-slate-600">-</span>
                                  </td>
                                  <td class="px-2 py-1 font-mono text-slate-300 border-b border-white/5 align-top whitespace-nowrap">
                                    <template v-if="value.volumeMeasurement">
                                      <div v-if="value.volumeMeasurement.ulNbOfPackets">UL: {{ value.volumeMeasurement.ulNbOfPackets }}</div>
                                      <div v-if="value.volumeMeasurement.dlNbOfPackets">DL: {{ value.volumeMeasurement.dlNbOfPackets }}</div>
                                    </template>
                                    <span v-else class="text-slate-600">-</span>
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>

                          <div v-if="item.eventType === 'QOS_MONITORING'" class="px-1 pb-2">

                            <div class="flex items-center gap-1">
                              <div class="w-1 h-4 bg-amber-500 rounded-full"></div>
                              <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                                QOS_MONITORING — QoS Monitoring Measurement
                              </div>
                            </div>
                            <div class="flex flex-row gap-4 items-start">
                              <!-- 왼쪽: Packet Delay Metrics -->
                              <table class="flex-1 text-[11px] border-collapse">
                                <thead>
                                  <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                    <th class="px-2 py-1 border-b border-white/10 w-1/2">Parameter</th>
                                    <th class="px-2 py-1 border-b border-white/10">Value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">dlPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.dlPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">ulPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.ulPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">rtrPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.rtrPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <!-- <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_dlMinPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._dlMinPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_ulMinPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._ulMinPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_rtrMinPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._rtrMinPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_dlMaxPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._dlMaxPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_ulMaxPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._ulMaxPacketDelay ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_rtrMaxPacketDelay</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._rtrMaxPacketDelay ?? '-' }}</td>
                                  </tr> -->
                                </tbody>
                              </table>
                              <!-- 오른쪽: Throughput & Quality -->
                              <table class="flex-1 text-[11px] border-collapse">
                                <thead>
                                  <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                    <th class="px-2 py-1 border-b border-white/10 w-1/2">Parameter</th>
                                    <th class="px-2 py-1 border-b border-white/10">Value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">dlAveThroughput</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.dlAveThroughput ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">ulAveThroughput</td>
                                    <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.ulAveThroughput ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">dlAvailableBitrate</td>
                                    <td class="px-2 py-1 font-mono text-teal-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.dlAvailableBitrate ?? '-' }}</td>
                                  </tr>
                                  <!-- <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">ulAvailableBitrate</td>
                                    <td class="px-2 py-1 font-mono text-teal-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?.ulAvailableBitrate ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_packetLossRate</td>
                                    <td class="px-2 py-1 font-mono text-red-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._packetLossRate ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">_jitter</td>
                                    <td class="px-2 py-1 font-mono text-violet-300 border-b border-white/5">{{ item.qosMonitoringMeasurement?._jitter ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">measureFailure</td>
                                    <td class="px-2 py-1 font-mono text-slate-400 border-b border-white/5">{{ item.qosMonitoringMeasurement?.measureFailure ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">dlCongestion</td>
                                    <td class="px-2 py-1 font-mono text-slate-400 border-b border-white/5">{{ item.qosMonitoringMeasurement?.dlCongestion ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">ulCongestion</td>
                                    <td class="px-2 py-1 font-mono text-slate-400 border-b border-white/5">{{ item.qosMonitoringMeasurement?.ulCongestion ?? '-' }}</td>
                                  </tr>
                                  <tr class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                    <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5">defaultQosFlowInd</td>
                                    <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5 whitespace-nowrap">{{ item.qosMonitoringMeasurement?.defaultQosFlowInd === true ? 'true' : item.qosMonitoringMeasurement?.defaultQosFlowInd === false ? 'false' : '-' }}</td>
                                  </tr> -->
                                </tbody>
                              </table>
                            </div>
                          </div>



                          <!-- <div v-else class="text-red-500">
                            Unknown type
                          </div> -->
                        </div>
                      </div>
                    </div>

                    <!-- NEF Notification: AF, RICF -->
                    <div v-if="entry.data.eventNotifs">
                      <div v-for="(item,idx) of entry.data.eventNotifs" :key="idx" class="px-1.5 py-0.5 text-xs font-black text-blue-400">
                        <div v-if="item.event === '_RF_SIGNAL'" class="">
                          <div class="flex items-center gap-1">
                            <div class="w-1 h-4 bg-secondary rounded-full"></div>
                            <div>{{ item.event }}</div>
                          </div>
                          <div v-for="(x, idx) of item._rfSignalInfos" :key="idx" class="flex flex-col gap-1">
                            <pre>{{ x._rfSignalData}}</pre>
                          </div>
                        </div>
                        <div v-if="item.event === '_POWER_ENERGY_CONSUMPTION'">
                        <div class="flex items-center gap-1">
                          <div class="w-1 h-4 bg-secondary rounded-full"></div>
                          <div>{{ item.event }}</div>
                        </div>
                          <div v-for="(x, idx) of item._powerEnergyConsumptionInfos" :key="idx" class="flex flex-col gap-1">
                            <pre>{{ x._powerEnergyConsData}}</pre>
                          </div>
                        </div>

                        <div v-if="item.event === 'PERF_DATA'" class="px-2 pb-2">
                          <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">PERF_DATA — Performance Data Infos</div>
                          <table class="w-full text-[11px] border-collapse">
                            <thead>
                              <tr class="text-left text-slate-500 font-bold uppercase tracking-wider">
                                <th class="px-2 py-1 border-b border-white/10 w-4">#</th>
                                <th class="px-2 py-1 border-b border-white/10 w-32">App ID</th>
                                <th class="px-2 py-1 border-b border-white/10 w-24">UE IP</th>
                                <th class="px-2 py-1 border-b border-white/10 max-w-12">Flow Desc</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="(item2, idx) of item.perfDataInfos" :key="idx"
                                class="even:bg-white/3 hover:bg-white/6 transition-colors">
                                <td class="px-2 py-1 text-slate-600 border-b border-white/5 w-4">{{ idx }}</td>
                                <td class="px-2 py-1 font-mono text-sky-300 border-b border-white/5 truncate max-w-32" :title="item2.appId" >{{ item2.appId }}</td>
                                <td class="px-2 py-1 font-mono text-emerald-300 border-b border-white/5 max-w-24">{{ item2.ueIpAddr?.ipv4Addr ?? '-' }}</td>
                                <td class="px-2 py-1 font-mono text-amber-300 border-b border-white/5 truncate max-w-12" :title="item2.ipTrafficFilter?.flowDescriptions ?? '-' ">{{ item2.ipTrafficFilter?.flowDescriptions ?? '-' }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>

                        <div v-if="item.event === 'DISPERSION'">
                          <!-- {{ item.event }} -->
                          <div class="flex items-center gap-1">
                            <div class="w-2 h-2 bg-secondary rounded-full"></div>
                            <div>{{ item.event }}</div>
                          </div>
                          <div v-for="(x, idx) of item.dispersionInfos" :key="idx" class="flex flex-col gap-1">
                            <pre>{{ x.dataUsage}}</pre>
                          </div>
                        </div>
                      </div>
                    </div>


                  <!-- <div v-if="entry.data.eventNotifs" class="px-1.5 text-xs">

                    <div v-for="(item, idx) of entry.data.eventNotifs" :key="idx" class="flex flex-col gap-1">
                      <div class="text-red-500">{{ item.event }}</div>
                      <div v-for="(item2, idx) of item.perfDataInfos" :key="idx" class="p-2 border-b border-amber-400/50">

                        <div>AppID: {{ item2.appId }} </div>
                        <div>IP: {{ item2.ueIpAddr?.ipv4Addr }}</div>
                        <div>Flow: {{ item2.ipTrafficFilter?.flowDescriptions }}</div>
                      </div>


                    </div>
                  </div> -->
                  <!-- <pre
                  class="text-[10px] text-slate-400 font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto bg-black/40 p-3 m-0">{{ JSON.stringify(entry.data.eventNotifs, null, 2) }}</pre> -->
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error" class="p-2 bg-red-500/10 border border-red-500/20 rounded-xl text-[10px] text-red-400 font-medium">
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
          <h3 class="text-sm font-bold text-slate-300 truncate">Detail — {{ detailModalEntry.notifUri }}</h3>
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

<style>

</style>

import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { NetworkNode, Message, Subscription, NodeEdge } from "../types";

export const useNetworkStore = defineStore("network", () => {
  const STORAGE_KEY = "network-topology-layout";
  const MAX_QUEUE_SIZE = 5;

  // prettier-ignore
  const defaultNodes: NetworkNode[] = [
    { id: "ncof", name: "NCOF", type: "NCOF", x: 0, y: 0, status: "ACTIVE", },
    { id: "ricf", name: "RICF", type: "RICF", x: -250, y: -150, status: "ACTIVE", },
    { id: "pcf", name: "PCF", type: "PCF", x: -250, y: 150, status: "ACTIVE", },
    { id: "upf", name: "UPF", type: "UPF", x: 300, y: -200, status: "ACTIVE", },
    { id: "smf", name: "SMF", type: "SMF", x: 300, y: -50, status: "ACTIVE", },
    { id: "amf", name: "AMF", type: "AMF", x: 300, y: -50, status: "ACTIVE", },
    { id: "af", name: "AF", type: "AF", x: 300, y: 100, status: "ACTIVE", },
    { id: "ue1", name: "UE1", type: "UE", x: 300, y: 100, status: "ACTIVE", },
    { id: "ue2", name: "UE2", type: "UE", x: 300, y: 100, status: "ACTIVE", },
    { id: "gNodeB1", name: "gNodeB", type: "GNODEB", x: 300, y: 100, status: "INACTIVE", },
    { id: "gNodeB2", name: "gNodeB", type: "GNODEB", x: 300, y: 100, status: "INACTIVE", },
    { id: "wifi", name: "WIFI", type: "WIFI", x: 300, y: 100, status: "INACTIVE"},
  ];

  const loadNodes = (): NetworkNode[] => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return defaultNodes;
    try {
      const positions = JSON.parse(saved) as Record<
        string,
        { x: number; y: number }
      >;
      return defaultNodes.map((node) => ({
        ...node,
        x: positions[node.id]?.x ?? node.x,
        y: positions[node.id]?.y ?? node.y,
      }));
    } catch (e) {
      console.error("Failed to load layout:", e);
      return defaultNodes;
    }
  };

  const nodes = ref<NetworkNode[]>(loadNodes());

  const saveNodes = () => {
    const positions = nodes.value.reduce(
      (acc, node) => {
        acc[node.id] = { x: node.x, y: node.y };
        return acc;
      },
      {} as Record<string, { x: number; y: number }>,
    );
    localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
    console.log("Layout saved to localStorage");
  };

  const resetLayout = () => {
    nodes.value = defaultNodes.map((n) => ({ ...n }));
    localStorage.removeItem(STORAGE_KEY);
  };

  const messageQueue = ref<Message[]>([
    {
      id: "1",
      from: "ricf",
      to: "ncof",
      type: "SUBSCRIBED",
      timestamp: Date.now(),
      status: "QUEUED",
    },
    {
      id: "2",
      from: "pcf",
      to: "ncof",
      type: "SUBSCRIBED",
      timestamp: Date.now() + 1,
      status: "QUEUED",
    },
    {
      id: "3",
      from: "ncof",
      to: "ricf",
      type: "SUBSCRIBED",
      timestamp: Date.now() + 2,
      status: "QUEUED",
    },
    {
      id: "4",
      from: "ncof",
      to: "pcf",
      type: "SUBSCRIBED",
      timestamp: Date.now() + 3,
      status: "QUEUED",
    },
    {
      id: "5",
      from: "pcf",
      to: "ncof",
      type: "NOTIFY",
      timestamp: Date.now() + 4,
      status: "QUEUED",
    },
    {
      id: "6",
      from: "ricf",
      to: "ncof",
      type: "NOTIFY",
      timestamp: Date.now() + 5,
      status: "QUEUED",
    },
    {
      id: "7",
      from: "ncof",
      to: "ncof",
      type: "ANALIZING",
      timestamp: Date.now() + 6,
      status: "QUEUED",
    },
    {
      id: "8",
      from: "ncof",
      to: "ncof",
      type: "ANALIZING",
      timestamp: Date.now() + 7,
      status: "QUEUED",
    },
    {
      id: "9",
      from: "ncof",
      to: "ncof",
      type: "ANALIZED",
      timestamp: Date.now() + 8,
      status: "QUEUED",
    },
    {
      id: "10",
      from: "ncof",
      to: "pcf",
      type: "UNSUBSCRIBED",
      timestamp: Date.now() + 9,
      status: "QUEUED",
    },
    {
      id: "11",
      from: "ncof",
      to: "ricf",
      type: "UNSUBSCRIBED",
      timestamp: Date.now() + 10,
      status: "QUEUED",
    },
    {
      id: "12",
      from: "pcf",
      to: "ncof",
      type: "UNSUBSCRIBED",
      timestamp: Date.now() + 11,
      status: "QUEUED",
    },
    {
      id: "13",
      from: "ricf",
      to: "ncof",
      type: "UNSUBSCRIBED",
      timestamp: Date.now() + 12,
      status: "QUEUED",
    },
  ]);

  const isAnalyzing = ref(false);

  const activeSubscriptions = ref<Subscription[]>([]);
  const selectedNodeId = ref<string | null>(null);
  const isSimulationRunning = ref(false);

  // 노드 간 연결관계를 나타내는 토폴로지 엣지 (구독과 무관)
  const nodeEdges = ref<NodeEdge[]>([
    // { id: "e-ncof-ricf", from: "ncof", to: "ricf", label: "N13" },
    { id: "e-ncof-pcf", from: "ncof", to: "pcf", label: "N7" },
    { id: "e-ncof-af", from: "ncof", to: "af", label: "N5" },
    { id: "e-ncof-smf", from: "ncof", to: "smf", label: "N14" },
    { id: "e-ncof-upf", from: "ncof", to: "upf", label: "N6" },
    // { id: "e-ricf-gnb1", from: "ricf", to: "gNodeB1", label: "N2" },
    // { id: "e-ricf-gnb2", from: "ricf", to: "gNodeB2", label: "N2" },
    { id: "e-amf-gnb1", from: "amf", to: "gNodeB1", label: "N2" },
    { id: "e-amf-gnb2", from: "amf", to: "gNodeB2", label: "N2" },
    { id: "e-smf-upf", from: "smf", to: "upf", label: "N4" },
    { id: "e-smf-amf", from: "smf", to: "amf", label: "N11" },
    // { id: "e-pcf-af", from: "pcf", to: "af", label: "N5" },
    { id: "e-gnb1-ue1", from: "gNodeB1", to: "ue1" },
    { id: "e-gnb2-ue2", from: "gNodeB2", to: "ue2" },
    { id: "e-wifi-ue2", from: "wifi", to: "ue2" },
    // { id: "e-upf-gnb1", from: "upf", to: "gNodeB1", label: "N3" },
    // { id: "e-upf-gnb2", from: "upf", to: "gNodeB2", label: "N3" },
  ]);
  const currentMessageIndex = ref(-1);

  // WebSocket State
  const wsStatus = ref<"DISCONNECTED" | "CONNECTING" | "CONNECTED" | "ERROR">(
    "DISCONNECTED",
  );
  const wsLog = ref<string[]>([]);
  const wsPulse = ref(0);

  const selectedNode = computed(
    () =>
      nodes.value.find((n: NetworkNode) => n.id === selectedNodeId.value) ||
      null,
  );

  const addMessage = (
    from: string,
    to: string,
    type: Message["type"],
    data?: any,
    subId?: string,
    status: Message["status"] = "QUEUED",
    id?: string,
    timestamp?: number,
  ) => {
    if (isSimulationRunning.value) return;
    const msg: Message = {
      id: id || Math.random().toString(36).substr(2, 9),
      from,
      to,
      type,
      data,
      subId,
      timestamp: timestamp || Date.now(),
      status,
    };
    console.log("add message");
    messageQueue.value.push(msg);
    if (messageQueue.value.length > MAX_QUEUE_SIZE) {
      messageQueue.value.shift();
    }
  };

  const removeMessage = (id: string) => {
    if (isSimulationRunning.value) return;
    messageQueue.value = messageQueue.value.filter((m: Message) => m.id !== id);
  };

  const clearQueue = () => {
    if (isSimulationRunning.value) return;
    messageQueue.value = [];
    activeSubscriptions.value = [];
    currentMessageIndex.value = -1;
    isAnalyzing.value = false;
  };

  const resetSimulation = () => {
    isSimulationRunning.value = false;
    currentMessageIndex.value = -1;
    messageQueue.value.forEach((m: Message) => (m.status = "QUEUED"));
    activeSubscriptions.value = [];
    isAnalyzing.value = false;
  };

  const addSubscription = (from: string, to: string, subId?: string) => {
    const id =
      subId ||
      `${from}-${to}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const existing = activeSubscriptions.value.find((s) => s.id === id);

    if (existing) {
      existing.count = (existing.count || 1) + 1;
    } else {
      activeSubscriptions.value.push({
        id,
        from,
        to,
        subId,
        timestamp: Date.now(),
        count: 1,
      });
    }
  };

  const removeSubscription = (from: string, to: string, subId?: string) => {
    const index = activeSubscriptions.value.findIndex((s) => {
      if (subId) return s.id === subId;
      return s.from === from && s.to === to;
    });

    if (index !== -1) {
      const sub = activeSubscriptions.value[index];
      if (sub && (sub.count || 1) > 1) {
        sub.count! -= 1;
      } else {
        activeSubscriptions.value.splice(index, 1);
      }
    }
  };

  return {
    nodes,
    messageQueue,
    activeSubscriptions,
    nodeEdges,
    selectedNodeId,
    selectedNode,
    isSimulationRunning,
    currentMessageIndex,
    isAnalyzing,
    addMessage,
    removeMessage,
    clearQueue,
    resetSimulation,
    saveNodes,
    resetLayout,
    wsStatus,
    wsLog,
    wsPulse,
    addSubscription,
    removeSubscription,
  };
});

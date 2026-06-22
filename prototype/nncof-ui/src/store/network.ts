import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type {
  NetworkNode,
  Message,
  MessageType,
  Subscription,
  NodeEdge,
} from "../types";

export const useNetworkStore = defineStore("network", () => {
  const STORAGE_KEY = "network-topology-layout";
  const MAX_QUEUE_SIZE = 18;

  // prettier-ignore
  const defaultNodes: NetworkNode[] = [
  { id: "ncof", name: "NCOF", type: "NCOF", x: 24.0408935546875, y: -98.17474365234375, status: "ACTIVE", size: "normal" },

  { id: "pcf",  name: "PCF",  type: "PCF",  x: -144, y: -99, status: "ACTIVE", size: "small" },
  { id: "upf",  name: "UPF",  type: "UPF",  x: 128, y: 112, status: "ACTIVE", size: "small" },
  { id: "smf",  name: "SMF",  type: "SMF",  x: 4, y: 19, status: "ACTIVE", size: "small" },
  { id: "amf",  name: "AMF",  type: "AMF",  x: -146, y: 7, status: "ACTIVE", size: "small" },

  { id: "nef",  name: "NEF",  type: "NEF",  x: 145, y: -102, status: "ACTIVE", size: "small" },
  { id: "ricf", name: "RICF", type: "RICF", x: 281, y: -41, status: "ACTIVE", size: "small" },
  { id: "af",   name: "AF",   type: "AF",   x: 280, y: -155, status: "ACTIVE", size: "small" },

  { id: "ue1",  name: "UE1",  type: "UE",   x: -316.46563720703125, y: 76.2373275756836, status: "ACTIVE", size: "small" },
  { id: "ue2",  name: "UE2",  type: "UE",   x: -317, y: 179, status: "ACTIVE", size: "small" },

  { id: "wifi", name: "WIFI", type: "WIFI", x: -127, y: 213, status: "INACTIVE", size: "small" },

  { id: "n3iwf", name: "N3IWF", type: "N3IWF", x: 11, y: 193, status: "ACTIVE", size: "small" },

  { id: "gNodeB1", name: "gNodeB", type: "GNODEB", x: -178, y: 98, status: "INACTIVE", size: "small" },
  { id: "gNodeB2", name: "gNodeB", type: "GNODEB", x: -176, y: 160, status: "INACTIVE", size: "small" },

  { id: "network", name: "DATA NETWORK", type: "NETWORK", x: 303, y: 79, status: "ACTIVE", size: "large", image: "net.png" },
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

  const messageQueue = ref<Message[]>([]);

  const isAnalyzing = ref(false);

  const activeSubscriptions = ref<Subscription[]>([]);
  const selectedNodeId = ref<string | null>(null);
  const isSimulationRunning = ref(false);

  // 노드 간 연결관계를 나타내는 토폴로지 엣지 (구독과 무관)
  const nodeEdges = ref<NodeEdge[]>([
    { id: "e-ncof-smf", from: "ncof", to: "smf", label: "N14" },
    { id: "e-ncof-upf", from: "ncof", to: "upf", label: "N6" },

    { id: "e-amf-gnb1", from: "amf", to: "gNodeB1", label: "N2" },
    { id: "e-amf-gnb2", from: "amf", to: "gNodeB2", label: "N2" },
    { id: "e-upf-gnb1", from: "upf", to: "gNodeB1", label: "N3" },
    { id: "e-upf-gnb2", from: "upf", to: "gNodeB2", label: "N3" },
    { id: "e-upf-gnb2", from: "upf", to: "network", label: "N6" },

    { id: "e-smf-upf", from: "smf", to: "upf", label: "N4" },
    { id: "e-smf-amf", from: "smf", to: "amf", label: "N11" },

    { id: "e-ncof-pcf", from: "ncof", to: "pcf", label: "N7" },
    // { id: "e-ncof-af", from: "ncof", to: "af", label: "N5" },

    { id: "e-gnb1-ue1", from: "amf", to: "ue1", label: "N1" },
    { id: "e-gnb2-ue2", from: "amf", to: "ue2", label: "N1" },

    { id: "e-n3iwf-wifi", from: "wifi", to: "n3iwf", label: "Y2" },
    { id: "e-n3iwf-amf", from: "amf", to: "n3iwf", label: "N2" },
    { id: "e-n3iwf-upf", from: "upf", to: "n3iwf", label: "N3" },
    { id: "e-wifi-ue2", from: "wifi", to: "ue2" },
  ]);
  const currentMessageIndex = ref(-1);

  // WebSocket State
  const wsStatus = ref<"DISCONNECTED" | "CONNECTING" | "CONNECTED" | "ERROR">(
    "DISCONNECTED",
  );
  const wsLog = ref<string[]>([]);
  const MAX_LOG_LINES = 500;
  const pushLog = (entry: string) => {
    wsLog.value.push(entry);
    if (wsLog.value.length > MAX_LOG_LINES) {
      wsLog.value.splice(0, wsLog.value.length - MAX_LOG_LINES);
    }
  };
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
    messageQueue.value.push(msg);
    if (messageQueue.value.length > MAX_QUEUE_SIZE) {
      messageQueue.value.shift();
    }
    // console.log("type:", type);
    // if (type === "ANALYZING") {
    //   isAnalyzing.value = true;
    // } else if (type === "ANALYZED") {
    //   isAnalyzing.value = false;
    // }
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

  const addSubscription = (
    from: string,
    to: string,
    subId?: string,
    type?: MessageType,
  ) => {
    const id =
      subId ||
      `${from}-${to}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const existing = activeSubscriptions.value.find((s) => s.id === id);

    if (existing) {
      existing.count = (existing.count || 1) + 1;
      if (type) existing.type = type;
    } else {
      activeSubscriptions.value.push({
        id,
        from,
        to,
        subId,
        timestamp: Date.now(),
        count: 1,
        type,
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
    pushLog,
    wsPulse,
    addSubscription,
    removeSubscription,
  };
});

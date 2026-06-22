// WebSocket 연결 및 자동 재연결을 관리하는 Composable
import { ref, onUnmounted } from "vue";

export type WsStatus = "DISCONNECTED" | "CONNECTING" | "CONNECTED" | "ERROR";

interface UseWebSocketOptions {
  url: string;
  onMessage?: (event: MessageEvent) => void;
  onOpen?: () => void;
  onLog?: (entry: string) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    onMessage,
    onLog,
    reconnectInterval = 3000,
    maxReconnectAttempts = 50,
  } = options;

  const status = ref<WsStatus>("DISCONNECTED");
  const pulse = ref(0);

  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempt = 0;

  function pushLog(entry: string) {
    onLog?.(entry);
  }

  function connect(): void {
    if (
      ws &&
      (ws.readyState === WebSocket.OPEN ||
        ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    status.value = "CONNECTING";
    pushLog("[Connecting]");

    const socket = new WebSocket(url);
    ws = socket;

    socket.onopen = () => {
      reconnectAttempt = 0;
      status.value = "CONNECTED";
      pushLog("[Connected]");
    };

    socket.onmessage = (event: MessageEvent) => {
      pulse.value++;
      onMessage?.(event);
    };

    socket.onerror = () => {
      status.value = "ERROR";
      pushLog("[Error]");
    };

    socket.onclose = () => {
      status.value = "DISCONNECTED";
      pushLog("[Disconnected]");
      scheduleReconnect();
    };
  }

  function send(data: string): void {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(data);
    }
  }

  function disconnect(): void {
    cancelReconnect();
    if (ws) {
      ws.onclose = null;
      ws.close();
      ws = null;
    }
    status.value = "DISCONNECTED";
  }

  function scheduleReconnect(): void {
    if (reconnectTimer !== null) return;
    if (reconnectAttempt >= maxReconnectAttempts) {
      pushLog(
        `[Reconnect] Max attempts (${maxReconnectAttempts}) reached, stop retrying.`,
      );
      return;
    }
    reconnectAttempt++;
    pushLog(
      `[Reconnect] Attempt ${reconnectAttempt}/${maxReconnectAttempts} in ${reconnectInterval}ms...`,
    );
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, reconnectInterval);
  }

  function cancelReconnect(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  onUnmounted(() => {
    disconnect();
  });

  return {
    status,
    pulse,
    connect,
    send,
    disconnect,
  };
}

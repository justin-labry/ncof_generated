export type NodeType =
  | "NCOF"
  | "RICF"
  | "AF"
  | "PCF"
  | "SMF"
  | "AMF"
  | "UPF"
  | "UE"
  | "WIFI"
  | "GNODEB";

export interface NetworkNode {
  id: string;
  name: string;
  type: NodeType;
  server?: string;
  x: number;
  y: number;
  status: "ACTIVE" | "INACTIVE";
}

export type MessageType =
  | "SUBSCRIBE"
  | "UNSUBSCRIBE"
  | "NOTIFICATION"
  | "SUBSCRIBED"
  | "UNSUBSCRIBED"
  | "ANALIZING"
  | "ANALIZED";

export interface Message {
  id: string;
  from: string;
  to: string;
  type: MessageType;
  subId?: string;
  data?: any;
  timestamp: number;
  status: "QUEUED" | "RUNNING" | "COMPLETED";
}

export interface Subscription {
  id: string;
  from: string;
  to: string;
  subId?: string;
  timestamp: number;
  count?: number;
}

// 토폴로지 노드 간 연결관계를 나타내는 엣지 (구독과 무관)
export interface NodeEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
}

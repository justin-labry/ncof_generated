export type NodeType =
  | "NCOF"
  | "RICF"
  | "AF"
  | "PCF"
  | "SMF"
  | "AMF"
  | "UPF"
  | "UE"
  | "NEF"
  | "N3IWF"
  | "WIFI"
  | "NETWORK"
  | "GNODEB";

export type NodeSize = "large" | "normal" | "small";

export interface NetworkNode {
  id: string;
  name: string;
  type: NodeType;
  server?: string;
  x: number;
  y: number;
  status: "ACTIVE" | "INACTIVE";
  size?: NodeSize;
  /** src/assets/ 에 있는 이미지 파일명 (예: "nef.png") */
  image?: string;
}

export type MessageType =
  | "SUBSCRIBE"
  | "UNSUBSCRIBE"
  | "NOTIFICATION"
  | "SUBSCRIBED"
  | "UNSUBSCRIBED"
  | "ANALYZING"
  | "ANALYZED";

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
  type?: MessageType;
}

// 토폴로지 노드 간 연결관계를 나타내는 엣지 (구독과 무관)
export interface NodeEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
}

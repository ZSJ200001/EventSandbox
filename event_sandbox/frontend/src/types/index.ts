// Core entity types for EventSandbox

export interface Agent {
  id: string;
  name: string;
  type: AgentType;
  description: string;
  personality: string;
  goals: string[];
  beliefs: Belief[];
  relationships: Relationship[];
  status: AgentStatus;
  position?: { x: number; y: number };
}

export type AgentType =
  | 'individual'      // 个人
  | 'organization'    // 组织
  | 'company'          // 企业
  | 'government'       // 政府
  | 'competitor'       // 竞品
  | 'supplier'         // 供应商
  | 'consumer'         // 消费者
  | 'regulator';       // 监管机构

export type AgentStatus = 'active' | 'inactive' | 'intervened';

export interface Belief {
  key: string;
  value: string | number;
  confidence: number; // 0-1
}

export interface Relationship {
  targetAgentId: string;
  type: RelationType;
  strength: number; // -1 to 1
}

export type RelationType =
  | 'competitor'      // 竞争
  | 'cooperative'     // 合作
  | 'supply'          // 供应
  | 'demand'          // 需求
  | 'regulate'        // 监管
  | 'influence'       // 影响
  | 'neutral';

export interface Event {
  id: string;
  type: EventType;
  description: string;
  timestamp: number;
  round: number;
  involvedAgents: string[];
  impact: EventImpact;
  source?: string;
}

export type EventType =
  | 'action'           // Agent行动
  | 'reaction'         // 反应
  | 'external'         // 外部事件
  | 'intervention'     // 干预事件
  | 'system';          // 系统事件

export interface EventImpact {
  affectedAgents: string[];
  sentimentChange: Record<string, number>; // agent_id -> change amount
  metricChanges: Record<string, number>;   // metric_name -> change amount
}

export interface Simulation {
  id: string;
  name: string;
  description: string;
  agents: Agent[];
  events: Event[];
  topology: Topology;
  rounds: number;
  currentRound: number;
  status: SimulationStatus;
  metrics: SimulationMetrics;
  startTime?: number;
  endTime?: number;
}

export type SimulationStatus = 'pending' | 'running' | 'paused' | 'completed';

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface TopologyNode {
  id: string;
  agentId: string;
  label: string;
  type: AgentType;
}

export interface TopologyEdge {
  source: string;
  target: string;
  relation: RelationType;
  weight: number;
}

export interface SimulationMetrics {
  overallSentiment: number;
  marketActivity: number;
  cooperationLevel: number;
  conflictLevel: number;
  customMetrics: Record<string, number>;
}

export interface Intervention {
  id: string;
  type: InterventionType;
  target?: string;       // agent id or 'global'
  parameter?: string;    // parameter name
  value: unknown;
  timestamp: number;
  round: number;
}

export type InterventionType =
  | 'global_param'       // 全局参数调整
  | 'agent_state'        // Agent状态修改
  | 'external_event';    // 强制触发外部事件

export interface SimulationConfig {
  maxRounds: number;
  llmModel: string;
  temperature: number;
  knowledgeEnabled: boolean;
  visualizationInterval: number;
}

// API request/response types
export interface CreateSimulationRequest {
  name: string;
  description: string;
  eventText: string;
  config?: Partial<SimulationConfig>;
}

export interface CreateSimulationResponse {
  simulation: Simulation;
  generatedAgents: Agent[];
  topology: Topology;
}

export interface StepSimulationRequest {
  simulationId: string;
  intervention?: Intervention;
}

export interface StepSimulationResponse {
  simulation: Simulation;
  newEvents: Event[];
  updatedAgents: Agent[];
}

export interface InterventionRequest {
  simulationId: string;
  intervention: Intervention;
}

export interface CompareReport {
  simulationId: string;
  withoutIntervention: SimulationMetrics;
  withIntervention: SimulationMetrics;
  comparison: {
    metric: string;
    difference: number;
    percentageChange: number;
  }[];
}

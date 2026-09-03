export interface Metrics {
  revenue_at_risk: number;
  revenue_recovered: number;
  recovery_rate_percent: number;
  as_of: string;
}

export interface QueueItem {
  case_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  failure_type: string;
  failure_reason?: string | null;
  status: string;
  customer_id?: string | null;
  payment_method?: string | null;
  attempt_count: number;
  max_attempts: number;
  latest_action?: string | null;
  latest_outcome?: string | null;
  next_action?: string | null;
  next_action_delay_hours?: number | null;
  simulated_time_hours: number;
  recovered_amount?: number | null;
  can_advance: boolean;
  workflow_started: boolean;
}

export interface TimelineEvent {
  id: number;
  event_type: string;
  timestamp: string;
  actor: string;
  status: string;
  summary: string;
  details: string;
  metadata: Record<string, unknown>;
}

export interface AdvanceResult {
  case_id: string;
  status: string;
  can_advance: boolean;
  simulated_time_hours: number;
  attempt_count: number;
}

export interface DemoPopulateResult {
  status: string;
  message: string;
  case_ids: string[];
}

export type DisplayStatus =
  | "open"
  | "recovering"
  | "awaiting_customer"
  | "recovered"
  | "escalated"
  | "stopped";

export interface StrategyResult {
  recovered_revenue: number;
  recovery_rate_percent: number;
}

export interface BaselineComparison {
  case_count: number;
  total_revenue_at_risk: number;
  naive: StrategyResult;
  adaptive: StrategyResult;
  improvement_percentage_points: number;
  additional_revenue_recovered: number;
  evaluation_seed: number;
  external_llm_calls: boolean;
  simulation_mode: string;
}

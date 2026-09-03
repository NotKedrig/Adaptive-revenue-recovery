import type {
  AdvanceResult,
  BaselineComparison,
  DemoPopulateResult,
  Metrics,
  QueueItem,
  TimelineEvent,
} from "../types/recovery";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let message = `Recovery service returned ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the generic message rather than exposing raw bodies.
    }
    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export function getMetrics(): Promise<Metrics> {
  return request<Metrics>("/api/metrics");
}

export function getQueue(): Promise<QueueItem[]> {
  return request<QueueItem[]>("/api/queue");
}

export function getRecovered(): Promise<QueueItem[]> {
  return request<QueueItem[]>("/api/recovered");
}

export function getCase(caseId: string): Promise<QueueItem> {
  return request<QueueItem>(`/api/cases/${encodeURIComponent(caseId)}`);
}

export function getCaseTimeline(caseId: string): Promise<TimelineEvent[]> {
  return request<TimelineEvent[]>(`/api/cases/${encodeURIComponent(caseId)}/timeline`);
}

export function advanceRecovery(caseId: string): Promise<AdvanceResult> {
  return request<AdvanceResult>(`/api/cases/${encodeURIComponent(caseId)}/advance`, {
    method: "POST",
  });
}

export function loadDemoData(): Promise<DemoPopulateResult> {
  return request<DemoPopulateResult>("/api/demo/populate", { method: "POST" });
}

export function getBaselineComparison(): Promise<BaselineComparison> {
  return request<BaselineComparison>("/api/baseline-comparison");
}

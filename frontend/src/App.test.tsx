import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import * as api from "./services/api";
import type { BaselineComparison, Metrics } from "./types/recovery";

vi.mock("./services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./services/api")>();
  return {
    ...actual,
    getMetrics: vi.fn(),
    getQueue: vi.fn(),
    getRecovered: vi.fn(),
    getCase: vi.fn(),
    getCaseTimeline: vi.fn(),
    advanceRecovery: vi.fn(),
    loadDemoData: vi.fn(),
    getBaselineComparison: vi.fn(),
  };
});

const mocked = vi.mocked(api);

describe("App View Switching and Results Page", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    mocked.getMetrics.mockResolvedValue({
      revenue_at_risk: 1000,
      revenue_recovered: 0,
      recovery_rate_percent: 0,
      as_of: "2026-09-01T00:00:00Z",
    } as Metrics);
    mocked.getQueue.mockResolvedValue([]);
    mocked.getRecovered.mockResolvedValue([]);
    
    const mockBaseline: BaselineComparison = {
      case_count: 40,
      total_revenue_at_risk: 409754.8,
      naive: { recovered_revenue: 88727.76, recovery_rate_percent: 21.65 },
      adaptive: { recovered_revenue: 227205.47, recovery_rate_percent: 55.45 },
      improvement_percentage_points: 33.8,
      additional_revenue_recovered: 138477.71,
      evaluation_seed: 777,
      external_llm_calls: false,
      simulation_mode: "deterministic",
    };
    mocked.getBaselineComparison.mockResolvedValue(mockBaseline);
  });

  it("defaults to Recovery Operations and allows switching to Results", async () => {
    render(<App />);
    
    // Default view check
    expect(await screen.findByText("Recovery queue")).toBeTruthy();
    
    // Switch to Results
    await userEvent.click(screen.getByRole("button", { name: /Results/i }));
    
    // Verify Results page is active
    expect(await screen.findByText("RECOVERY RESULTS")).toBeTruthy();
    expect(screen.getByText("Deterministic evaluation · 40 cases")).toBeTruthy();
    
    // Verify API-provided values (using exact match)
    expect(screen.getByText("+33.8 percentage points")).toBeTruthy();
    // Use exact formatting match since the formatINR(x, true) renders ₹1,38,477.71
    expect(screen.getByText("₹1,38,477.71 additional revenue recovered")).toBeTruthy();
    
    // Recovery Queue should no longer be rendered
    expect(screen.queryByText("Recovery queue")).toBeNull();
  });

  it("fetches /api/baseline-comparison gracefully on API failure", async () => {
    mocked.getBaselineComparison.mockRejectedValue(new Error("network error"));
    render(<App />);
    
    await userEvent.click(screen.getByRole("button", { name: /Results/i }));
    
    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load benchmark results");
    // Ensure app didn't crash and we can navigate back
    await userEvent.click(screen.getByRole("button", { name: /Recovery Operations/i }));
    expect(await screen.findByText("Recovery queue")).toBeTruthy();
  });
});

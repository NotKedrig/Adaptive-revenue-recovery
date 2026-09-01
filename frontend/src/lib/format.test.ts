import { describe, expect, it } from "vitest";
import { formatHours, formatINR, formatPercent, looksLikeRawObject } from "./format";

describe("currency and time presentation", () => {
  it("formats INR with the rupee sign and never uses $ or €", () => {
    const value = formatINR(12450);
    expect(value).toContain("₹");
    expect(value).toContain("12,450");
    expect(value).not.toContain("$");
    expect(value).not.toContain("€");
  });

  it("formats recovery rate from the backend percentage", () => {
    expect(formatPercent(42.7)).toBe("42.7%");
  });

  it("renders virtual time as hours", () => {
    expect(formatHours(48)).toBe("48h");
    expect(formatHours(0)).toBe("Immediate");
  });

  it("detects raw dictionary strings", () => {
    expect(looksLikeRawObject("{'outcome': 'recovery_failed'}")).toBe(true);
    expect(looksLikeRawObject("Payment retry failed.")).toBe(false);
  });
});

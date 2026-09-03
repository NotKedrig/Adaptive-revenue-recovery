export function formatINR(amount: number, showDecimals = false): string {
  if (showDecimals) {
    return `₹${amount.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  const rounded = Math.round(amount);
  return `₹${rounded.toLocaleString("en-IN")}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatHours(hours: number): string {
  if (hours <= 0) return "Immediate";
  return `${hours}h`;
}

export function formatCustomer(customerId: string | null | undefined): string {
  if (!customerId) return "—";
  return customerId.replace(/^customer_/i, "").replace(/_/g, " ");
}

export function formatPaymentType(method: string | null | undefined): string {
  if (!method) return "—";
  if (method.toLowerCase() === "card") return "Card";
  if (method.toLowerCase() === "upi") return "UPI";
  return method.replace(/_/g, " ");
}

export function formatVirtualOffset(hours: number): string {
  if (hours <= 0) return "T+0";
  return `T+${hours}h`;
}

export function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

export function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

export function looksLikeRawObject(text: string): boolean {
  const trimmed = text.trim();
  return (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  );
}

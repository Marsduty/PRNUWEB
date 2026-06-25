export function formatYesterdayTrend(percentChange?: number | null, previous?: number | null, current?: number | null) {
  if (typeof current === "number" && Number.isFinite(current) && current <= 0) return null;
  if (!previous || previous === 0) return null;
  const value = typeof percentChange === "number" && Number.isFinite(percentChange) ? percentChange : 0;
  if (value === 0) return null;
  const rounded = Number(value.toFixed(2));
  const sign = rounded > 0 ? "+" : "";
  return `较昨日 ${sign}${rounded}%`;
}

export function formatYesterdayTrend(percentChange?: number | null) {
  const value = typeof percentChange === "number" && Number.isFinite(percentChange) ? percentChange : 0;
  const rounded = Number(value.toFixed(2));
  const sign = rounded > 0 ? "+" : "";
  return `较昨日 ${sign}${rounded}%`;
}

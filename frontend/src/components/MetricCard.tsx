import type { LucideIcon } from "lucide-react";

type MetricCardProps = {
  title: string;
  value: string;
  unit: string;
  trend: string;
  icon: LucideIcon;
};

export function MetricCard({ title, value, unit, trend, icon: Icon }: MetricCardProps) {
  const trendClassName = trend.includes("-") ? "text-warningGold" : "text-signalGreen";

  return (
    <section className="tech-panel flex min-h-[118px] items-center gap-4 p-4">
      <div className="grid h-14 w-14 shrink-0 place-items-center rounded-md border border-cyanLine/60 bg-cyan-500/10">
        <Icon className="h-8 w-8 text-cyan-200" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-sky-200">{title}</p>
        <div className="mt-2 flex items-end gap-2">
          <strong className="text-2xl leading-none text-white">{value}</strong>
          <span className="text-sm text-sky-200">{unit}</span>
        </div>
        <p className={`mt-2 text-xs ${trendClassName}`}>{trend}</p>
      </div>
    </section>
  );
}

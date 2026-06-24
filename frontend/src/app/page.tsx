"use client";

import { useEffect, useState } from "react";
import { Activity, BarChart3, Database, FileImage, Fingerprint as FingerprintIcon, Lock, ShieldCheck, Target, Zap } from "lucide-react";

import { DistributionChart } from "@/components/DistributionChart";
import { MetricCard } from "@/components/MetricCard";
import { ProcessFlow, type WorkflowStepId } from "@/components/ProcessFlow";
import { WorkflowWorkspace } from "@/components/WorkflowWorkspace";
import { fetchMetrics, type MetricsSummary } from "@/lib/api";
import { formatYesterdayTrend } from "@/lib/metrics";

const capabilities = [
  { label: "精准取证", detail: "高质量 PRNU 指纹提取", icon: Target },
  { label: "智能高效", detail: "任务队列实时处理", icon: Zap },
  { label: "安全可靠", detail: "数据入库与结果可追溯", icon: Lock },
  { label: "多维分析", detail: "品牌分布与比对结论联动", icon: BarChart3 }
];

export default function Home() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeStep, setActiveStep] = useState<WorkflowStepId | null>(null);

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const data = await fetchMetrics();
        setMetrics(data);
      } catch (error) {
        console.error("Failed to fetch metrics:", error);
      } finally {
        setLoading(false);
      }
    };

    loadMetrics();
    const interval = setInterval(loadMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  const getMetricValue = (key: keyof MetricsSummary, fallback: string) => {
    if (!metrics) return fallback;
    return String(metrics[key]);
  };

  return (
    <main className="dashboard-shell">
      <header className="dashboard-hero">
        <div className="hero-emblem" aria-hidden="true">
          <ShieldCheck className="h-14 w-14 text-cyan-100" />
          <FingerprintIcon className="h-8 w-8 text-white" />
        </div>
        <div className="hero-title">
          <h1>基于成像设备指纹的智能取证与比对分析平台</h1>
          <div className="hero-tags">
            <span>精准取证</span>
            <span>智能比对</span>
            <span>高效可信</span>
            <span>安全可靠</span>
          </div>
        </div>
        <div className="hero-secure" aria-hidden="true">
          <Lock className="h-8 w-8 text-cyan-100" />
          <span>SECURE</span>
        </div>
      </header>

      <section className="metric-ribbon" aria-label="关键指标（今日）">
        <MetricCard
          title="当前数据库录入设备指纹数量"
          value={getMetricValue("image_count", "0")}
          unit="枚"
          trend={loading ? "加载中..." : formatYesterdayTrend(metrics?.metric_trends?.image_count.percent_change, metrics?.metric_trends?.image_count.previous)}
          icon={Database}
        />
        <MetricCard
          title="今日录入设备指纹数量"
          value={getMetricValue("today_uploads", "0")}
          unit="枚"
          trend={loading ? "加载中..." : formatYesterdayTrend(metrics?.metric_trends?.today_uploads.percent_change, metrics?.metric_trends?.today_uploads.previous)}
          icon={FileImage}
        />
        <MetricCard
          title="今日比对任务数量"
          value={getMetricValue("today_comparisons", "0")}
          unit="次"
          trend={loading ? "加载中..." : formatYesterdayTrend(metrics?.metric_trends?.today_comparisons.percent_change, metrics?.metric_trends?.today_comparisons.previous)}
          icon={Activity}
        />
        <MetricCard
          title="今日比对命中数量"
          value={getMetricValue("today_hits", "0")}
          unit="次"
          trend={loading ? "加载中..." : formatYesterdayTrend(metrics?.metric_trends?.today_hits.percent_change, metrics?.metric_trends?.today_hits.previous)}
          icon={ShieldCheck}
        />
      </section>

      <section className="dashboard-main-grid">
        <section className="tech-panel p-4">
          <div className="panel-title-row">
            <h2>数据分布（当前录入指纹设备品牌）</h2>
            <span>实时同步</span>
          </div>
          <DistributionChart data={metrics?.device_distribution ?? []} />
        </section>
        <ProcessFlow onSelect={setActiveStep} />
      </section>

      <section className="capability-strip" aria-label="平台能力">
        {capabilities.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="capability-item">
              <Icon className="h-7 w-7 text-cyan-100" aria-hidden="true" />
              <div>
                <p>{item.label}</p>
                <span>{item.detail}</span>
              </div>
            </div>
          );
        })}
      </section>

      <WorkflowWorkspace activeStep={activeStep} metrics={metrics} onClose={() => setActiveStep(null)} />
    </main>
  );
}

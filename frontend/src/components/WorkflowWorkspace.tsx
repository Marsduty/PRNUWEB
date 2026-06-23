"use client";

import { X } from "lucide-react";

import { DatabaseComparisonPanel } from "@/components/DatabaseComparisonPanel";
import { ExternalComparisonPanel } from "@/components/ExternalComparisonPanel";
import { FingerprintBuildPanel } from "@/components/FingerprintBuildPanel";
import { ResultPanel } from "@/components/ResultPanel";
import { TaskTable } from "@/components/TaskTable";
import { workflowSteps, type WorkflowStepId } from "@/components/ProcessFlow";
import type { MetricsSummary } from "@/lib/api";

type WorkflowWorkspaceProps = {
  activeStep: WorkflowStepId | null;
  metrics: MetricsSummary | null;
  onClose: () => void;
};

export function WorkflowWorkspace({ activeStep, metrics, onClose }: WorkflowWorkspaceProps) {
  if (!activeStep) return null;

  const step = workflowSteps.find((item) => item.id === activeStep);
  const title = step?.label ?? "功能模块";

  return (
    <div className="workflow-overlay" role="dialog" aria-modal="true" aria-label={`${title}子页面`}>
      <div className="workflow-page">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm text-sky-200">PRNU 指纹取证与比对流程</p>
            <h2 className="text-2xl font-semibold text-white">{title}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭子页面" onClick={onClose}>
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {activeStep === "image-import" ? (
          <FingerprintBuildPanel />
        ) : null}

        {activeStep === "prnu-extract" ? (
          <div className="grid gap-4">
            <section className="tech-panel p-4">
              <h3 className="text-lg font-semibold">PRNU 提取状态</h3>
              <p className="mt-2 text-sm text-sky-200">设备指纹构建任务会在后台自动完成 PRNU 提取，完成后可在“图像导入”步骤的设备指纹管理中查看。</p>
            </section>
            <TaskTable filterTypes={["build_fingerprint", "rebuild_fingerprint"]} title="PRNU 提取相关任务" />
          </div>
        ) : null}

        {activeStep === "fingerprint-compare" ? (
          <div className="grid gap-4">
            <div className="grid gap-4 xl:grid-cols-2">
              <DatabaseComparisonPanel />
              <ExternalComparisonPanel />
            </div>
            <TaskTable filterTypes={["database_comparison", "external_comparison"]} title="指纹比对任务队列" />
          </div>
        ) : null}

        {activeStep === "result-judgement" ? (
          <ResultPanel results={metrics?.recent_results ?? []} />
        ) : null}
      </div>
    </div>
  );
}

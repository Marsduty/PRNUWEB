import { FileImage, Fingerprint, Network, ShieldCheck } from "lucide-react";

export type WorkflowStepId = "image-import" | "prnu-extract" | "fingerprint-compare" | "result-judgement";

export const workflowSteps = [
  { id: "image-import" as const, label: "图像导入", icon: FileImage },
  { id: "prnu-extract" as const, label: "PRNU 提取", icon: Fingerprint },
  { id: "fingerprint-compare" as const, label: "指纹比对", icon: Network },
  { id: "result-judgement" as const, label: "结果判定", icon: ShieldCheck }
];

type ProcessFlowProps = {
  onSelect: (step: WorkflowStepId) => void;
};

export function ProcessFlow({ onSelect }: ProcessFlowProps) {
  return (
    <section className="tech-panel process-panel p-4">
      <div className="process-header">
        <h2>PRNU 指纹取证与比对流程</h2>
        <span>点击步骤进入对应功能子页面</span>
      </div>
      <div className="process-track">
        {workflowSteps.map((step, index) => {
          const Icon = step.icon;
          return (
            <button
              key={step.id}
              className="process-step"
              type="button"
              onClick={() => onSelect(step.id)}
            >
              <div className="process-icon">
                <Icon className="h-7 w-7 text-cyan-200" aria-hidden="true" />
              </div>
              <p>{step.label}</p>
              <span className="process-step-index">{index + 1}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

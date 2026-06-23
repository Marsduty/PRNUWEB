"use client";

import { Images, Upload, X } from "lucide-react";
import { useState } from "react";

import { API_BASE_URL, fetchJobs } from "@/lib/api";
import { COMPARISON_TASK_TYPES, waitForDisplayTaskNo } from "@/lib/taskNumbers";

export function ExternalComparisonPanel() {
  const [imageA, setImageA] = useState<File | null>(null);
  const [imageB, setImageB] = useState<File | null>(null);
  const [message, setMessage] = useState("等待上传图像 A 和图像 B");
  const [busy, setBusy] = useState(false);
  const [taskNameDialogOpen, setTaskNameDialogOpen] = useState(false);
  const [taskName, setTaskName] = useState("");

  async function submit() {
    if (!imageA || !imageB) {
      setMessage("请同时选择图像 A 和图像 B");
      return;
    }
    setTaskNameDialogOpen(true);
  }

  async function submitWithTaskName() {
    if (!imageA || !imageB) {
      setMessage("请同时选择图像 A 和图像 B");
      setTaskNameDialogOpen(false);
      return;
    }
    if (!taskName.trim()) {
      setMessage("请填写任务名称");
      return;
    }
    setBusy(true);
    setTaskNameDialogOpen(false);
    setMessage("正在创建外来图像比对任务");
    try {
      const data = new FormData();
      data.append("image_a", imageA);
      data.append("image_b", imageB);
      data.append("task_name", taskName.trim());
      const response = await fetch(`${API_BASE_URL}/comparisons/external`, {
        method: "POST",
        body: data
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      const payload = await response.json();
      let taskNo: number | null = null;
      try {
        taskNo = await waitForDisplayTaskNo(fetchJobs, payload.job_id, COMPARISON_TASK_TYPES);
      } catch (error) {
        console.error("Failed to resolve comparison task number:", error);
      }
      setMessage(taskNo ? `任务已创建：#${taskNo}` : "任务已创建：任务号同步中");
      setTaskName("");
    } catch (error) {
      setMessage(`任务创建失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tech-panel p-4">
      <div className="mb-4 flex items-center gap-3">
        <Images className="h-6 w-6 text-cyan-200" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">外来图像比对</h2>
          <p className="text-sm text-sky-200">分别提取图像 A/B 单图指纹，执行 PCE 同源判定。</p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <input className="file-input" type="file" accept="image/*" aria-label="上传图像 A" onChange={(event) => setImageA(event.target.files?.[0] ?? null)} />
        <input className="file-input" type="file" accept="image/*" aria-label="上传图像 B" onChange={(event) => setImageB(event.target.files?.[0] ?? null)} />
      </div>
      <button className="tech-button mt-3 inline-flex w-full items-center justify-center gap-2" disabled={busy} onClick={submit}>
        <Upload className="h-4 w-4" aria-hidden="true" />
        {busy ? "任务创建中" : "上传并启动外来图像比对"}
      </button>
      <p className="mt-3 text-sm text-sky-200">{message}</p>
      {taskNameDialogOpen ? (
        <div className="subdialog-overlay" role="dialog" aria-modal="true" aria-label="填写外来图像比对任务名称">
          <div className="subdialog-page result-detail-dialog">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl font-semibold text-white">填写任务名称</h2>
              <button className="icon-button" type="button" aria-label="关闭任务名称窗口" onClick={() => setTaskNameDialogOpen(false)}>
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <label className="grid gap-2 text-sm text-sky-200">
              任务名称
              <input
                className="text-input"
                value={taskName}
                onChange={(event) => setTaskName(event.target.value)}
                placeholder="输入外来图像比对任务名称"
              />
            </label>
            <button className="tech-button mt-4 w-full" type="button" disabled={busy} onClick={submitWithTaskName}>
              确认启动
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

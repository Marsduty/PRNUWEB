"use client";

import { Database, Upload, X } from "lucide-react";
import { useState } from "react";

import { API_BASE_URL, fetchJobs } from "@/lib/api";
import { COMPARISON_TASK_TYPES, waitForDisplayTaskNo } from "@/lib/taskNumbers";

export function DatabaseComparisonPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("等待上传待检图像");
  const [busy, setBusy] = useState(false);
  const [taskNameDialogOpen, setTaskNameDialogOpen] = useState(false);
  const [taskName, setTaskName] = useState("");

  async function submit() {
    if (!file) {
      setMessage("请先选择待检图像");
      return;
    }
    setTaskNameDialogOpen(true);
  }

  async function submitWithTaskName() {
    if (!file) {
      setMessage("请先选择待检图像");
      setTaskNameDialogOpen(false);
      return;
    }
    if (!taskName.trim()) {
      setMessage("请填写任务名称");
      return;
    }
    setBusy(true);
    setTaskNameDialogOpen(false);
    setMessage("正在创建指纹数据库比对任务");
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("task_name", taskName.trim());
      const response = await fetch(`${API_BASE_URL}/comparisons/database`, {
        method: "POST",
        body: data
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
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
        <Database className="h-6 w-6 text-cyan-200" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-semibold">指纹数据库比对</h2>
          <p className="text-sm text-sky-200">待检图像指纹与数据库设备指纹做 PCE 比对，阈值 60。</p>
        </div>
      </div>
      <div className="grid gap-3">
        <input
          className="file-input"
          type="file"
          accept="image/*"
          aria-label="上传待检图像"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button className="tech-button inline-flex items-center justify-center gap-2" disabled={busy} onClick={submit}>
          <Upload className="h-4 w-4" aria-hidden="true" />
          {busy ? "任务创建中" : "上传并启动数据库比对"}
        </button>
        <p className="text-sm text-sky-200">{message}</p>
      </div>
      {taskNameDialogOpen ? (
        <div className="subdialog-overlay" role="dialog" aria-modal="true" aria-label="填写数据库比对任务名称">
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
                placeholder="输入数据库比对任务名称"
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

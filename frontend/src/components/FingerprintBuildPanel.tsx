"use client";

import { Fingerprint, Pencil, RefreshCcw, Save, Search, Settings, Trash2, Upload, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildFingerprint,
  createDevice,
  deleteFingerprint,
  fetchJob,
  fetchFingerprints,
  fetchJobs,
  rebuildFingerprintReferences,
  updateFingerprint,
  type FingerprintRow
} from "@/lib/api";
import { TaskTable } from "@/components/TaskTable";
import { PRNU_TASK_TYPES, waitForDisplayTaskNo } from "@/lib/taskNumbers";

type RebuildStatus = {
  jobId?: number;
  message: string;
  state: "submitting" | "submitted" | "running" | "succeeded" | "failed";
};

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function FingerprintBuildPanel() {
  const [fingerprints, setFingerprints] = useState<FingerprintRow[]>([]);
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [macAddress, setMacAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [message, setMessage] = useState("等待录入参考图像");
  const [busy, setBusy] = useState(false);
  const [managementOpen, setManagementOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editBrand, setEditBrand] = useState("");
  const [editModel, setEditModel] = useState("");
  const [editMacAddress, setEditMacAddress] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editFiles, setEditFiles] = useState<File[]>([]);
  const [rebuildStatus, setRebuildStatus] = useState<RebuildStatus | null>(null);
  const [searchName, setSearchName] = useState("");
  const [searchBrand, setSearchBrand] = useState("");
  const [searchModel, setSearchModel] = useState("");
  const [searchMacAddress, setSearchMacAddress] = useState("");
  const [searchNotes, setSearchNotes] = useState("");

  async function loadData() {
    try {
      const fingerprintRows = await fetchFingerprints();
      setFingerprints(fingerprintRows);
    } catch (error) {
      console.error("Failed to fetch fingerprint build data:", error);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const filteredFingerprints = useMemo(() => {
    const includes = (value: string | null | undefined, query: string) =>
      !query.trim() || (value || "").toLowerCase().includes(query.trim().toLowerCase());

    return fingerprints.filter((row) => {
      const device = row.device;
      return (
        includes(device?.name, searchName) &&
        includes(device?.brand, searchBrand) &&
        includes(device?.model, searchModel) &&
        includes(device?.mac_address, searchMacAddress) &&
        includes(device?.notes, searchNotes)
      );
    });
  }, [fingerprints, searchBrand, searchMacAddress, searchModel, searchName, searchNotes]);

  async function waitForJobCompletion(jobId: number) {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const job = await fetchJob(jobId);
      if (job.status === "succeeded") return job;
      if (job.status === "failed") {
        throw new Error(job.error || "设备指纹重构失败");
      }
      setRebuildStatus({
        jobId,
        state: "running",
        message: job.progress || "设备指纹重构进行中"
      });
      await delay(2000);
    }
    throw new Error("设备指纹重构超时");
  }

  async function submit() {
    if (!brand.trim() || !model.trim()) {
      setMessage("请填写品牌和型号");
      return;
    }
    if (files.length === 0) {
      setMessage("请至少选择一张参考图像");
      return;
    }

    setBusy(true);
    setMessage("正在创建设备指纹构建任务");
    try {
      const device = await createDevice({
        brand: brand.trim(),
        model: model.trim(),
        mac_address: macAddress.trim() || undefined,
        notes: notes.trim() || undefined
      });
      const payload = await buildFingerprint(device.id, files);
      let taskNo: number | null = null;
      try {
        taskNo = await waitForDisplayTaskNo(fetchJobs, payload.job_id, PRNU_TASK_TYPES);
      } catch (error) {
        console.error("Failed to resolve PRNU task number:", error);
      }
      setMessage(taskNo ? `设备指纹构建任务已创建：#${taskNo}` : "设备指纹构建任务已创建：任务号同步中");
      setBrand("");
      setModel("");
      setMacAddress("");
      setNotes("");
      setFiles([]);
      await loadData();
    } catch (error) {
      setMessage(`任务创建失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(false);
    }
  }

  function startEdit(row: FingerprintRow) {
    setEditingId(row.id);
    setEditBrand(row.device?.brand || "");
    setEditModel(row.device?.model || "");
    setEditMacAddress(row.device?.mac_address || "");
    setEditNotes(row.device?.notes || "");
    setEditFiles([]);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditFiles([]);
  }

  async function saveEdit(row: FingerprintRow) {
    if (!editBrand.trim() || !editModel.trim()) {
      setMessage("修改失败：品牌和型号不能为空");
      return;
    }
    setMessage("正在修改设备指纹信息");
    try {
      if (editFiles.length > 0) {
        setRebuildStatus({ state: "submitting", message: "正在提交设备信息与参考图像" });
      }
      await updateFingerprint(row.id, {
        brand: editBrand.trim(),
        model: editModel.trim(),
        mac_address: editMacAddress.trim(),
        notes: editNotes.trim()
      });
      if (editFiles.length > 0) {
        const payload = await rebuildFingerprintReferences(row.id, editFiles);
        setRebuildStatus({
          jobId: payload.job_id,
          state: "submitted",
          message: "等待重构任务提交"
        });
        setMessage("设备指纹重构任务已创建");
      } else {
        setMessage("设备指纹信息已更新");
      }
      setEditingId(null);
      setEditFiles([]);
      await loadData();
      if (editFiles.length > 0) {
        await delay(800);
        setRebuildStatus(null);
      }
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "未知错误";
      setMessage(`修改失败：${messageText}`);
      if (editFiles.length > 0) {
        setRebuildStatus({ state: "failed", message: `设备指纹重构失败：${messageText}` });
        await delay(1800);
        setRebuildStatus(null);
      }
    }
  }

  async function removeFingerprint(row: FingerprintRow) {
    const confirmed = window.confirm(`确认删除设备指纹 #${row.id}？`);
    if (!confirmed) return;
    setMessage("正在删除设备指纹");
    try {
      await deleteFingerprint(row.id);
      setMessage("设备指纹已删除");
      await loadData();
    } catch (error) {
      setMessage(`删除失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  return (
    <section className="grid gap-4">
      <div className="tech-panel p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Fingerprint className="h-6 w-6 text-cyan-200" aria-hidden="true" />
            <div>
              <h2 className="text-lg font-semibold">设备指纹录入</h2>
              <p className="text-sm text-sky-200">建立指纹数据库</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="tech-button inline-flex items-center justify-center gap-2 px-3" type="button" onClick={() => setManagementOpen(true)}>
              <Settings className="h-4 w-4" aria-hidden="true" />
              设备指纹管理
            </button>
            <button className="icon-button" type="button" aria-label="刷新设备指纹" onClick={loadData}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[0.8fr_1.2fr]">
          <div className="grid gap-3">
            <div className="grid gap-3 md:grid-cols-3">
              <input
                className="text-input"
                type="text"
                placeholder="品牌"
                aria-label="品牌"
                value={brand}
                onChange={(event) => setBrand(event.target.value)}
              />
              <input
                className="text-input"
                type="text"
                placeholder="型号"
                aria-label="型号"
                value={model}
                onChange={(event) => setModel(event.target.value)}
              />
              <input
                className="text-input"
                type="text"
                placeholder="设备 MAC 地址"
                aria-label="设备 MAC 地址"
                value={macAddress}
                onChange={(event) => setMacAddress(event.target.value)}
              />
            </div>
            <input
              className="text-input"
              type="text"
              placeholder="备注"
              aria-label="备注"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>

          <div className="grid gap-3">
            <input
              className="file-input"
              type="file"
              accept="image/*"
              multiple
              aria-label="上传参考图像"
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
            <button className="tech-button inline-flex items-center justify-center gap-2" disabled={busy} onClick={submit}>
              <Upload className="h-4 w-4" aria-hidden="true" />
              {busy ? "任务创建中" : "上传并构建设备指纹"}
            </button>
            <p className="text-sm text-sky-200">{message}</p>
          </div>
        </div>
      </div>

      {managementOpen ? (
        <div className="subdialog-overlay" role="dialog" aria-modal="true" aria-label="设备指纹管理子页面">
          <div className="subdialog-page fingerprint-management-page">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm text-sky-200">图像导入</p>
                <h2 className="text-xl font-semibold text-white">设备指纹管理</h2>
              </div>
              <div className="flex gap-2">
                <button className="icon-button" type="button" aria-label="刷新设备指纹" onClick={loadData}>
                  <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                </button>
                <button className="icon-button" type="button" aria-label="关闭设备指纹管理" onClick={() => setManagementOpen(false)}>
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="search-grid mb-3">
              <label className="search-field">
                <span>设备名称</span>
                <div>
                  <Search className="h-4 w-4" aria-hidden="true" />
                  <input value={searchName} onChange={(event) => setSearchName(event.target.value)} placeholder="搜索设备名称" />
                </div>
              </label>
              <label className="search-field">
                <span>品牌</span>
                <div>
                  <Search className="h-4 w-4" aria-hidden="true" />
                  <input value={searchBrand} onChange={(event) => setSearchBrand(event.target.value)} placeholder="搜索品牌" />
                </div>
              </label>
              <label className="search-field">
                <span>型号</span>
                <div>
                  <Search className="h-4 w-4" aria-hidden="true" />
                  <input value={searchModel} onChange={(event) => setSearchModel(event.target.value)} placeholder="搜索型号" />
                </div>
              </label>
              <label className="search-field">
                <span>MAC 地址</span>
                <div>
                  <Search className="h-4 w-4" aria-hidden="true" />
                  <input value={searchMacAddress} onChange={(event) => setSearchMacAddress(event.target.value)} placeholder="搜索 MAC 地址" />
                </div>
              </label>
              <label className="search-field">
                <span>备注</span>
                <div>
                  <Search className="h-4 w-4" aria-hidden="true" />
                  <input value={searchNotes} onChange={(event) => setSearchNotes(event.target.value)} placeholder="搜索备注" />
                </div>
              </label>
            </div>

            {filteredFingerprints.length === 0 ? (
              <p className="rounded-md border border-cyanLine/25 bg-cyan-950/30 p-3 text-sm text-sky-200">暂无匹配的设备指纹</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1220px] text-left text-sm">
                  <thead className="text-sky-200">
                    <tr className="border-b border-cyanLine/30">
                      <th className="py-2">指纹号</th>
                      <th className="py-2">设备名称</th>
                      <th className="py-2">品牌</th>
                      <th className="py-2">型号</th>
                      <th className="py-2">MAC 地址</th>
                      <th className="py-2">备注</th>
                      <th className="py-2">参考图</th>
                      <th className="py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFingerprints.map((row) => {
                      const editing = editingId === row.id;
                      return (
                        <tr key={row.id} className="border-b border-cyanLine/10 align-top">
                          <td className="py-3 text-cyan-100">#{row.id}</td>
                          <td className="py-3">{row.device?.name || "-"}</td>
                          <td className="py-3">
                            {editing ? (
                              <input className="text-input" aria-label="修改品牌" value={editBrand} onChange={(event) => setEditBrand(event.target.value)} />
                            ) : (
                              row.device?.brand || "-"
                            )}
                          </td>
                          <td className="py-3">
                            {editing ? (
                              <input className="text-input" aria-label="修改型号" value={editModel} onChange={(event) => setEditModel(event.target.value)} />
                            ) : (
                              row.device?.model || "-"
                            )}
                          </td>
                          <td className="py-3">
                            {editing ? (
                              <input className="text-input" aria-label="修改 MAC 地址" value={editMacAddress} onChange={(event) => setEditMacAddress(event.target.value)} />
                            ) : (
                              row.device?.mac_address || "-"
                            )}
                          </td>
                          <td className="py-3">
                            {editing ? (
                              <input className="text-input min-w-[220px]" aria-label="修改备注" value={editNotes} onChange={(event) => setEditNotes(event.target.value)} />
                            ) : (
                              <span className="block max-w-[240px] whitespace-normal break-words text-sky-200">{row.device?.notes || "-"}</span>
                            )}
                          </td>
                          <td className="py-3 text-sky-200">
                            {editing ? (
                              <input
                                className="file-input min-w-[220px]"
                                type="file"
                                accept="image/*"
                                multiple
                                aria-label="修改参考图像"
                                onChange={(event) => setEditFiles(Array.from(event.target.files ?? []))}
                              />
                            ) : (
                              `${row.image_count} 张`
                            )}
                          </td>
                          <td className="py-3">
                            <div className="flex gap-2">
                              {editing ? (
                                <>
                                  <button className="icon-button" type="button" aria-label="保存指纹信息" onClick={() => saveEdit(row)}>
                                    <Save className="h-4 w-4" aria-hidden="true" />
                                  </button>
                                  <button className="icon-button" type="button" aria-label="取消修改指纹信息" onClick={cancelEdit}>
                                    <X className="h-4 w-4" aria-hidden="true" />
                                  </button>
                                </>
                              ) : (
                                <button className="icon-button" type="button" aria-label="修改指纹信息" onClick={() => startEdit(row)}>
                                  <Pencil className="h-4 w-4" aria-hidden="true" />
                                </button>
                              )}
                              <button className="icon-button" type="button" aria-label="删除指纹" onClick={() => removeFingerprint(row)}>
                                <Trash2 className="h-4 w-4" aria-hidden="true" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-4">
              <TaskTable filterTypes={["rebuild_fingerprint"]} title="设备指纹重构任务队列" />
            </div>
          </div>
        </div>
      ) : null}

      {rebuildStatus ? (
        <div className="subdialog-overlay blocking-dialog" role="dialog" aria-modal="true" aria-label="设备指纹重构状态" onClick={() => rebuildStatus.state !== "submitting" && setRebuildStatus(null)}>
          <div className="subdialog-page result-detail-dialog text-center" onClick={(e) => e.stopPropagation()}>
            <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-md border border-cyanLine/60 bg-cyan-500/10">
              <RefreshCcw className="h-6 w-6 text-cyan-100" aria-hidden="true" />
            </div>
            <h2 className="text-xl font-semibold text-white">设备指纹重构</h2>
            <p className="mt-3 text-sm text-sky-200">{rebuildStatus.message}</p>
            {rebuildStatus.jobId ? <p className="mt-2 text-xs text-sky-300">后台任务：#{rebuildStatus.jobId}</p> : null}
            {rebuildStatus.state === "submitting" ? (
              <p className="mt-4 text-xs text-warningGold">正在提交，请稍候...</p>
            ) : (
              <button className="mt-4 rounded bg-cyan-700 px-4 py-2 text-sm text-white hover:bg-cyan-600" onClick={() => setRebuildStatus(null)}>
                关闭
              </button>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { Eye, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchComparison, fetchJobs, type ComparisonDetail, type JobRow, type MetricsSummary } from "@/lib/api";
import { buildComparisonResultRows, COMPARISON_TASK_TYPES, getJobTaskName } from "@/lib/taskNumbers";

type ResultPanelProps = {
  results: MetricsSummary["recent_results"];
};

function visibleDetailResults(detail: ComparisonDetail) {
  const hits = detail.results.filter((row) => row.is_hit);
  if (hits.length > 0) return hits;
  return [...detail.results]
    .sort((left, right) => {
      const leftPce = typeof left.pce === "number" ? left.pce : Number.NEGATIVE_INFINITY;
      const rightPce = typeof right.pce === "number" ? right.pce : Number.NEGATIVE_INFINITY;
      return rightPce - leftPce;
    })
    .slice(0, 1);
}

export function ResultPanel({ results }: ResultPanelProps) {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [detail, setDetail] = useState<ComparisonDetail | null>(null);
  const [detailMessage, setDetailMessage] = useState("");
  const [detailContext, setDetailContext] = useState<{ taskNo: number; taskName: string; typeLabel: string } | null>(null);

  useEffect(() => {
    const loadJobs = async () => {
      try {
        setJobs(await fetchJobs());
      } catch (error) {
        console.error("Failed to fetch comparison jobs:", error);
      } finally {
        setJobsLoading(false);
      }
    };

    loadJobs();
    const interval = setInterval(loadJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const resultRows = useMemo(
    () => buildComparisonResultRows(jobs, results, COMPARISON_TASK_TYPES),
    [jobs, results]
  );

  async function openDetail(jobId: number, context: { taskNo: number; taskName: string; typeLabel: string }) {
    setDetailMessage("正在加载匹配详情");
    setDetail(null);
    setDetailContext(context);
    try {
      const payload = await fetchComparison(jobId);
      setDetail(payload);
      setDetailMessage("");
    } catch (error) {
      setDetailMessage(error instanceof Error ? error.message : "匹配详情加载失败");
    }
  }

  return (
    <section className="tech-panel p-4">
      <div className="mb-3 flex items-center gap-3">
        <ShieldCheck className="h-6 w-6 text-signalGreen" aria-hidden="true" />
        <h2 className="text-lg font-semibold">最新比对结论</h2>
      </div>
      {jobsLoading ? (
        <div className="rounded-md border border-cyanLine/30 bg-cyan-950/30 p-3 text-sm text-sky-200">正在同步任务号...</div>
      ) : resultRows.length === 0 ? (
        <div className="rounded-md border border-cyanLine/30 bg-cyan-950/30 p-3 text-sm text-sky-200">暂无比对结论</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead className="text-sky-200">
              <tr className="border-b border-cyanLine/30">
                <th className="py-2">任务号</th>
                <th className="py-2">任务名</th>
                <th className="py-2">任务类型</th>
                <th className="py-2">比对结论</th>
              </tr>
            </thead>
            <tbody>
              {resultRows.map((item) => (
                <tr
                  key={item.result.id}
                  className="cursor-pointer border-b border-cyanLine/10 transition hover:bg-cyan-950/30"
                  onClick={() => openDetail(item.result.job_id, {
                    taskNo: item.taskNo,
                    taskName: item.taskName,
                    typeLabel: item.typeLabel
                  })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openDetail(item.result.job_id, {
                        taskNo: item.taskNo,
                        taskName: item.taskName,
                        typeLabel: item.typeLabel
                      });
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <td className="py-3 text-cyan-100">#{item.taskNo}</td>
                  <td className="py-3">{item.taskName}</td>
                  <td className="py-3 text-sky-100">{item.typeLabel}</td>
                  <td className={`py-3 ${item.result.is_hit ? "text-signalGreen" : "text-warningGold"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <span>{item.result.decision}</span>
                      <Eye className="h-4 w-4 flex-none text-cyan-200" aria-hidden="true" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {detailMessage ? <p className="mt-3 text-sm text-sky-200">{detailMessage}</p> : null}
      {detail ? (
        <div className="subdialog-overlay" role="dialog" aria-modal="true" aria-label="匹配详情子窗口">
          <div className="subdialog-page result-detail-dialog">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-sky-200">任务号：#{detailContext?.taskNo ?? detail.job_id}</p>
                <p className="text-sm text-sky-200">
                  任务名：{detailContext?.taskName ?? getJobTaskName(jobs.find((row) => row.id === detail.job_id))}
                </p>
                <h3 className="text-xl font-semibold text-white">匹配详情</h3>
              </div>
              <button className="icon-button" type="button" aria-label="关闭匹配详情" onClick={() => setDetail(null)}>
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <p className="rounded-md border border-cyanLine/25 bg-cyan-950/30 p-3 text-white">{detail.decision || "暂无结论"}</p>
            <div className="mt-3 grid gap-3">
              {visibleDetailResults(detail).map((row, index) => (
                <div key={`${row.rank ?? index}-${row.pce ?? "none"}`} className="rounded-md border border-cyanLine/25 bg-cyan-950/30 p-3">
                  <p className={row.is_hit ? "text-signalGreen" : "text-warningGold"}>{row.decision}</p>
                  <p className="mt-1 text-sky-200">
                    PCE：{typeof row.pce === "number" ? row.pce.toFixed(2) : "-"}，NCC：
                    {typeof row.ncc === "number" ? row.ncc.toFixed(4) : "-"}
                  </p>
                  {row.device ? (
                    <div className="mt-2 grid gap-1 text-sky-100">
                      <p>设备名称：{row.device.name}</p>
                      <p>品牌：{row.device.brand || "-"}，型号：{row.device.model || "-"}</p>
                      <p>MAC 地址：{row.device.mac_address || "-"}</p>
                    </div>
                  ) : null}
                  {row.fingerprint ? (
                    <p className="mt-2 text-sky-200">
                      指纹编号：#{row.fingerprint.id}，参考图像：{row.fingerprint.image_count} 张
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

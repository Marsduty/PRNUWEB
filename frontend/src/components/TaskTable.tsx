"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchJobs, type JobRow } from "@/lib/api";
import { formatJobDateTime, getJobDeviceName, getJobTaskName, withDisplayTaskNumbers } from "@/lib/taskNumbers";

type TaskTableProps = {
  filterTypes?: string[];
  title?: string;
};

export function TaskTable({ filterTypes, title = "任务队列" }: TaskTableProps) {
  const [rows, setRows] = useState<JobRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTaskNo, setSearchTaskNo] = useState("");
  const [searchTaskName, setSearchTaskName] = useState("");
  const [searchDeviceName, setSearchDeviceName] = useState("");
  const [searchType, setSearchType] = useState("");
  const [searchStatus, setSearchStatus] = useState("");
  const [searchProgress, setSearchProgress] = useState("");

  useEffect(() => {
    const loadJobs = async () => {
      try {
        const data = await fetchJobs();
        const filtered = filterTypes?.length ? data.filter((row) => filterTypes.includes(row.type)) : data;
        setRows(filtered);
      } catch (error) {
        console.error("Failed to fetch jobs:", error);
      } finally {
        setLoading(false);
      }
    };

    loadJobs();
    const interval = setInterval(loadJobs, 3000);
    return () => clearInterval(interval);
  }, [filterTypes]);

  const displayRows = useMemo(() => {
    const includes = (value: string | number | null | undefined, query: string) =>
      !query.trim() || String(value ?? "").toLowerCase().includes(query.trim().toLowerCase());

    return withDisplayTaskNumbers(rows)
      .filter(({ row, taskNo, typeLabel, statusText }) =>
        includes(taskNo, searchTaskNo) &&
        includes(getJobTaskName(row), searchTaskName) &&
        includes(getJobDeviceName(row), searchDeviceName) &&
        includes(typeLabel, searchType) &&
        includes(statusText, searchStatus) &&
        includes(row.progress, searchProgress)
      );
  }, [rows, searchDeviceName, searchProgress, searchStatus, searchTaskName, searchTaskNo, searchType]);

  return (
    <section className="tech-panel p-4">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <div className="search-grid mb-3">
        <label className="search-field">
          <span>任务号</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchTaskNo} onChange={(event) => setSearchTaskNo(event.target.value)} placeholder="搜索任务号" />
          </div>
        </label>
        <label className="search-field">
          <span>任务名称</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchTaskName} onChange={(event) => setSearchTaskName(event.target.value)} placeholder="搜索任务名称" />
          </div>
        </label>
        <label className="search-field">
          <span>设备名称</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchDeviceName} onChange={(event) => setSearchDeviceName(event.target.value)} placeholder="搜索设备名称" />
          </div>
        </label>
        <label className="search-field">
          <span>类型</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchType} onChange={(event) => setSearchType(event.target.value)} placeholder="搜索类型" />
          </div>
        </label>
        <label className="search-field">
          <span>状态</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchStatus} onChange={(event) => setSearchStatus(event.target.value)} placeholder="搜索状态" />
          </div>
        </label>
        <label className="search-field">
          <span>进度</span>
          <div>
            <Search className="h-4 w-4" aria-hidden="true" />
            <input value={searchProgress} onChange={(event) => setSearchProgress(event.target.value)} placeholder="搜索进度" />
          </div>
        </label>
      </div>
      <div className="overflow-x-auto">
        {loading ? (
          <p className="text-sky-200">加载中...</p>
        ) : displayRows.length === 0 ? (
          <p className="text-sky-200">暂无任务</p>
        ) : (
          <table className="w-full min-w-[980px] text-left text-sm">
            <thead className="text-sky-200">
              <tr className="border-b border-cyanLine/30">
                <th className="py-2">任务号</th>
                <th className="py-2">任务名称</th>
                <th className="py-2">设备名称</th>
                <th className="py-2">类型</th>
                <th className="py-2">状态</th>
                <th className="py-2">进度</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map(({ row, taskNo, typeLabel, statusText }) => (
                <tr key={row.id} className="border-b border-cyanLine/10">
                  <td className="py-3 text-cyan-100">#{taskNo} · {formatJobDateTime(row.created_at)}</td>
                  <td className="py-3">{getJobTaskName(row)}</td>
                  <td className="py-3">{getJobDeviceName(row)}</td>
                  <td className="py-3">{typeLabel}</td>
                  <td className="py-3 text-signalGreen">{statusText}</td>
                  <td className="py-3 text-sky-200">{row.progress || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

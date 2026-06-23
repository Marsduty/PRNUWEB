import type { JobRow, MetricsSummary } from "@/lib/api";

export const COMPARISON_TASK_TYPES = ["database_comparison", "external_comparison"] as const;
export const PRNU_TASK_TYPES = ["build_fingerprint", "rebuild_fingerprint"] as const;

export type DisplayJobRow = {
  row: JobRow;
  taskNo: number;
  typeLabel: string;
  statusText: string;
};

export type ComparisonResultDisplayRow = {
  row: JobRow;
  taskNo: number;
  taskName: string;
  typeLabel: string;
  result: MetricsSummary["recent_results"][number];
};

export function jobTypeLabel(type: string) {
  if (type === "database_comparison") return "指纹数据库比对";
  if (type === "external_comparison") return "外来图像比对";
  if (type === "build_fingerprint") return "设备指纹构建";
  if (type === "rebuild_fingerprint") return "设备指纹重构";
  return type;
}

export function statusLabel(status?: string | null) {
  if (status === "queued") return "排队中";
  if (status === "running") return "处理中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  return status || "-";
}

export function formatJobDateTime(value?: string) {
  if (!value) return "日期未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "日期未知";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

export function getJobTaskName(row?: Pick<JobRow, "task_name" | "payload"> | null) {
  const taskName = row?.task_name?.trim() || row?.payload?.task_name?.trim();
  return taskName || "-";
}

export function getJobDeviceName(row?: Pick<JobRow, "device_name"> | null) {
  return row?.device_name?.trim() || "-";
}

function jobTime(row: Pick<JobRow, "created_at">) {
  if (!row.created_at) return 0;
  const timestamp = new Date(row.created_at).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function compareJobsForDisplay(left: JobRow, right: JobRow) {
  const timeDiff = jobTime(right) - jobTime(left);
  if (timeDiff !== 0) return timeDiff;
  return right.id - left.id;
}

export function withDisplayTaskNumbers(jobs: JobRow[], filterTypes?: readonly string[]): DisplayJobRow[] {
  const filtered = filterTypes?.length ? jobs.filter((row) => filterTypes.includes(row.type)) : jobs;
  const ordered = [...filtered].sort(compareJobsForDisplay);
  const total = ordered.length;
  return ordered.map((row, rowIndex) => ({
    row,
    taskNo: total - rowIndex,
    typeLabel: jobTypeLabel(row.type),
    statusText: statusLabel(row.status)
  }));
}

export function findDisplayTaskNo(jobs: JobRow[], jobId: number, filterTypes?: readonly string[]) {
  return withDisplayTaskNumbers(jobs, filterTypes).find((item) => item.row.id === jobId)?.taskNo ?? null;
}

export function buildComparisonResultRows(
  jobs: JobRow[],
  results: MetricsSummary["recent_results"],
  filterTypes: readonly string[] = COMPARISON_TASK_TYPES
): ComparisonResultDisplayRow[] {
  const resultByJobId = new Map(results.map((result) => [result.job_id, result]));
  return withDisplayTaskNumbers(jobs, filterTypes)
    .map((item) => ({
      row: item.row,
      taskNo: item.taskNo,
      taskName: getJobTaskName(item.row),
      typeLabel: item.typeLabel,
      result: resultByJobId.get(item.row.id)
    }))
    .filter((item): item is ComparisonResultDisplayRow => Boolean(item.result));
}

export async function waitForDisplayTaskNo(
  loadJobs: () => Promise<JobRow[]>,
  jobId: number,
  filterTypes?: readonly string[],
  retries = 4,
  delayMs = 300
) {
  for (let attempt = 0; attempt < retries; attempt += 1) {
    const taskNo = findDisplayTaskNo(await loadJobs(), jobId, filterTypes);
    if (taskNo !== null) return taskNo;
    if (attempt < retries - 1) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return null;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type MetricsSummary = {
  image_count: number;
  today_uploads: number;
  today_comparisons: number;
  today_hits: number;
  metric_trends?: {
    image_count: { previous: number; percent_change: number };
    today_uploads: { previous: number; percent_change: number };
    today_comparisons: { previous: number; percent_change: number };
    today_hits: { previous: number; percent_change: number };
  };
  device_distribution: Array<{ name: string; value: number }>;
  recent_results: Array<{
    id: number;
    job_id: number;
    comparison_type: string;
    decision: string;
    pce?: number | null;
    is_hit: boolean;
    created_at?: string;
    device?: DeviceSummary | null;
  }>;
};

export type JobRow = {
  id: number;
  type: string;
  status: string;
  progress?: string | null;
  error?: string | null;
  task_name?: string | null;
  device_name?: string | null;
  payload?: {
    task_name?: string | null;
    device_id?: number | null;
  };
  created_at?: string;
};

export type DeviceRow = {
  id: number;
  name: string;
  brand?: string | null;
  model?: string | null;
  mac_address?: string | null;
  notes?: string | null;
  created_at?: string;
};

export type DeviceSummary = Pick<DeviceRow, "id" | "name" | "brand" | "model" | "mac_address">;

export type DeviceCreatePayload = {
  brand: string;
  model: string;
  mac_address?: string;
  notes?: string;
};

export type FingerprintRow = {
  id: number;
  device_id?: number | null;
  object_key: string;
  image_count: number;
  height: number;
  width: number;
  created_at?: string;
  device?: DeviceRow | null;
};

export type FingerprintUpdatePayload = {
  brand?: string;
  model?: string;
  mac_address?: string;
  notes?: string;
};

export type ComparisonDetail = {
  job_id: number;
  status: string;
  decision?: string | null;
  results: Array<{
    rank?: number | null;
    pce?: number | null;
    ncc?: number | null;
    is_hit: boolean;
    decision: string;
    peak_row?: number | null;
    peak_col?: number | null;
    device?: DeviceSummary | null;
    fingerprint?: Pick<FingerprintRow, "id" | "image_count" | "height" | "width" | "created_at"> | null;
  }>;
};

export async function fetchMetrics(): Promise<MetricsSummary> {
  const response = await fetch(`${API_BASE_URL}/metrics/summary`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取主看板指标");
  }
  return response.json();
}

export async function fetchDevices(): Promise<DeviceRow[]> {
  const response = await fetch(`${API_BASE_URL}/devices`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取设备列表");
  }
  return response.json();
}

export async function createDevice(payload: DeviceCreatePayload): Promise<DeviceRow> {
  const response = await fetch(`${API_BASE_URL}/devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error("设备创建失败");
  }
  return response.json();
}

export async function buildFingerprint(deviceId: number, files: File[]): Promise<{ job_id: number; status: string }> {
  const data = new FormData();
  data.append("device_id", String(deviceId));
  files.forEach((file) => data.append("files", file));

  const response = await fetch(`${API_BASE_URL}/fingerprints/build`, {
    method: "POST",
    body: data
  });
  if (!response.ok) {
    throw new Error("设备指纹构建任务创建失败");
  }
  return response.json();
}

export async function fetchFingerprints(): Promise<FingerprintRow[]> {
  const response = await fetch(`${API_BASE_URL}/fingerprints`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取设备指纹列表");
  }
  return response.json();
}

export async function updateFingerprint(fingerprintId: number, payload: FingerprintUpdatePayload): Promise<FingerprintRow> {
  const response = await fetch(`${API_BASE_URL}/fingerprints/${fingerprintId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error("指纹信息修改失败");
  }
  return response.json();
}

export async function rebuildFingerprintReferences(
  fingerprintId: number,
  files: File[]
): Promise<{ job_id: number; status: string }> {
  const data = new FormData();
  files.forEach((file) => data.append("files", file));

  const response = await fetch(`${API_BASE_URL}/fingerprints/${fingerprintId}/references`, {
    method: "POST",
    body: data
  });
  if (!response.ok) {
    throw new Error("参考图像重建任务创建失败");
  }
  return response.json();
}

export async function deleteFingerprint(fingerprintId: number): Promise<{ deleted: boolean; id: number }> {
  const response = await fetch(`${API_BASE_URL}/fingerprints/${fingerprintId}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error("指纹删除失败");
  }
  return response.json();
}

export async function fetchJobs(): Promise<JobRow[]> {
  const response = await fetch(`${API_BASE_URL}/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取任务列表");
  }
  return response.json();
}

export async function fetchJob(jobId: number): Promise<JobRow> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取任务状态");
  }
  return response.json();
}

export async function fetchComparison(jobId: number): Promise<ComparisonDetail> {
  const response = await fetch(`${API_BASE_URL}/comparisons/${jobId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("无法获取比对详情");
  }
  return response.json();
}

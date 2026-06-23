import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { test } from "node:test";
import ts from "typescript";

const root = fileURLToPath(new URL("..", import.meta.url));

async function importTaskNumbers() {
  const source = readFileSync(join(root, "src/lib/taskNumbers.ts"), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022
    }
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`);
}

test("比对任务显示编号按子模块独立连续且新任务编号更大", async () => {
  const { COMPARISON_TASK_TYPES, withDisplayTaskNumbers, findDisplayTaskNo } = await importTaskNumbers();
  const jobs = [
    { id: 30, type: "database_comparison", created_at: "2026-06-02T10:00:02" },
    { id: 29, type: "external_comparison", created_at: "2026-06-02T10:00:01" },
    { id: 28, type: "build_fingerprint", created_at: "2026-06-02T10:00:00" },
    { id: 27, type: "database_comparison", created_at: "2026-06-02T09:59:59" }
  ];

  const comparisonRows = withDisplayTaskNumbers(jobs, COMPARISON_TASK_TYPES);

  assert.deepEqual(comparisonRows.map((item) => [item.row.id, item.taskNo]), [
    [30, 3],
    [29, 2],
    [27, 1]
  ]);
  assert.equal(findDisplayTaskNo(jobs, 30, COMPARISON_TASK_TYPES), 3);
});

test("结果判定可复用比对任务显示编号生成列表行", async () => {
  const { COMPARISON_TASK_TYPES, buildComparisonResultRows } = await importTaskNumbers();
  const jobs = [
    { id: 8, type: "external_comparison", task_name: "外来图像比对A", created_at: "2026-06-02T11:00:01" },
    { id: 7, type: "database_comparison", task_name: "库内检索B", created_at: "2026-06-02T11:00:00" }
  ];
  const results = [
    { id: 2, job_id: 7, comparison_type: "database_comparison", decision: "库中未检索到匹配设备" },
    { id: 3, job_id: 8, comparison_type: "external_comparison", decision: "倾向认定图像A和图像B同源" }
  ];

  const rows = buildComparisonResultRows(jobs, results, COMPARISON_TASK_TYPES);

  assert.deepEqual(rows.map((item) => [item.taskNo, item.taskName, item.typeLabel, item.result.decision]), [
    [2, "外来图像比对A", "外来图像比对", "倾向认定图像A和图像B同源"],
    [1, "库内检索B", "指纹数据库比对", "库中未检索到匹配设备"]
  ]);
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { test } from "node:test";
import ts from "typescript";

const root = fileURLToPath(new URL("..", import.meta.url));

async function importMetricsHelpers() {
  const source = readFileSync(join(root, "src/lib/metrics.ts"), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022
    }
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`);
}

test("今日指标趋势文案显示为较昨日百分比", async () => {
  const { formatYesterdayTrend } = await importMetricsHelpers();

  assert.equal(formatYesterdayTrend(8), "较昨日 +8%");
  assert.equal(formatYesterdayTrend(-1), "较昨日 -1%");
  assert.equal(formatYesterdayTrend(2.35), "较昨日 +2.35%");
  assert.equal(formatYesterdayTrend(0), "较昨日 0%");
});

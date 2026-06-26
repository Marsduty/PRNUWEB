import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { test } from "node:test";

const root = fileURLToPath(new URL("..", import.meta.url));

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

test("前端通过流程步骤打开功能工作区", () => {
  assert.equal(existsSync(join(root, "src/components/FingerprintBuildPanel.tsx")), true);
  assert.equal(existsSync(join(root, "src/components/WorkflowWorkspace.tsx")), true);

  const page = read("src/app/page.tsx");
  assert.match(page, /WorkflowWorkspace/);
  assert.doesNotMatch(page, /<FingerprintBuildPanel/);
  assert.doesNotMatch(page, /<DatabaseComparisonPanel/);
});

test("前端 API 封装包含设备创建、指纹构建和指纹管理", () => {
  const api = read("src/lib/api.ts");

  assert.match(api, /export async function createDevice/);
  assert.match(api, /export async function buildFingerprint/);
  assert.match(api, /mac_address/);
  assert.match(api, /export async function fetchFingerprints/);
  assert.match(api, /export async function updateFingerprint/);
  assert.match(api, /export async function deleteFingerprint/);
  assert.match(api, /export async function fetchComparison/);
});

test("任务队列支持按任务类型过滤并实时刷新", () => {
  const taskTable = read("src/components/TaskTable.tsx");
  const taskNumbers = read("src/lib/taskNumbers.ts");

  assert.match(taskTable, /filterTypes/);
  assert.match(taskTable, /setInterval\([^,]+, 3000\)/);
  assert.match(taskTable, /formatJobDateTime/);
  assert.match(taskTable, /withDisplayTaskNumbers/);
  assert.match(taskNumbers, /total - rowIndex/);
  assert.match(taskNumbers, /COMPARISON_TASK_TYPES/);
  assert.doesNotMatch(taskTable, /rowIndex \+ 1/);
  assert.doesNotMatch(taskTable, /#\{row\.id\}/);
  assert.match(taskNumbers, /hour: "2-digit"/);
  assert.match(taskNumbers, /second: "2-digit"/);
  assert.match(taskTable, /任务名称/);
  assert.match(taskTable, /设备名称/);
  assert.match(taskTable, /searchTaskName/);
  assert.match(taskTable, /searchDeviceName/);
  assert.match(taskTable, /searchStatus/);
});

test("图像导入不再内嵌任务队列", () => {
  const workspace = read("src/components/WorkflowWorkspace.tsx");

  assert.doesNotMatch(workspace, /图像导入任务队列/);
});

test("设备指纹录入使用独立管理弹窗和搜索", () => {
  const panel = read("src/components/FingerprintBuildPanel.tsx");
  const api = read("src/lib/api.ts");
  const taskNumbers = read("src/lib/taskNumbers.ts");

  assert.doesNotMatch(panel, /新建设备/);
  assert.doesNotMatch(panel, /设备名称由系统生成/);
  assert.match(panel, /managementOpen/);
  assert.match(panel, /searchName/);
  assert.match(panel, /searchBrand/);
  assert.match(panel, /searchModel/);
  assert.match(panel, /searchMacAddress/);
  assert.match(panel, /searchNotes/);
  assert.match(panel, /搜索备注/);
  assert.match(panel, /修改备注/);
  assert.match(panel, /row\.device\?\.notes/);
  assert.match(panel, /rebuildStatus/);
  assert.match(panel, /waitForJobCompletion/);
  assert.match(panel, /waitForDisplayTaskNo/);
  assert.match(panel, /PRNU_TASK_TYPES/);
  assert.match(panel, /fetchJobs/);
  assert.match(panel, /设备指纹重构/);
  assert.doesNotMatch(panel, /设备指纹构建任务已创建：#\$\{payload\.job_id\}/);
  assert.match(taskNumbers, /PRNU_TASK_TYPES/);
  assert.match(api, /export async function rebuildFingerprintReferences/);
  assert.match(api, /export async function fetchJob/);
});

test("指纹管理重构任务在工作区中独立分类", () => {
  const workspace = read("src/components/WorkflowWorkspace.tsx");
  const taskNumbers = read("src/lib/taskNumbers.ts");

  assert.match(workspace, /rebuild_fingerprint/);
  assert.match(taskNumbers, /设备指纹重构/);
});

test("指纹比对上传前要求填写任务名称", () => {
  const databasePanel = read("src/components/DatabaseComparisonPanel.tsx");
  const externalPanel = read("src/components/ExternalComparisonPanel.tsx");
  const api = read("src/lib/api.ts");

  assert.match(databasePanel, /taskNameDialogOpen/);
  assert.match(databasePanel, /任务名称/);
  assert.match(databasePanel, /task_name/);
  assert.match(databasePanel, /waitForDisplayTaskNo/);
  assert.match(externalPanel, /taskNameDialogOpen/);
  assert.match(externalPanel, /任务名称/);
  assert.match(externalPanel, /task_name/);
  assert.match(externalPanel, /waitForDisplayTaskNo/);
  assert.match(api, /task_name/);
});

test("结果判定以列表展示并复用指纹比对任务编号", () => {
  const resultPanel = read("src/components/ResultPanel.tsx");

  assert.match(resultPanel, /fetchComparison/);
  assert.match(resultPanel, /fetchJobs/);
  assert.match(resultPanel, /buildComparisonResultRows/);
  assert.match(resultPanel, /COMPARISON_TASK_TYPES/);
  assert.match(resultPanel, /任务号/);
  assert.match(resultPanel, /任务名/);
  assert.match(resultPanel, /任务类型/);
  assert.match(resultPanel, /比对结论/);
  assert.match(resultPanel, /匹配详情/);
  assert.match(resultPanel, /role="dialog"/);
  assert.match(resultPanel, /visibleDetailResults/);
  assert.doesNotMatch(resultPanel, /results\.slice\(0, 4\)/);
});

test("品牌分布饼图显示数量和百分比", () => {
  const chart = read("src/components/DistributionChart.tsx");

  assert.match(chart, /设备品牌分布/);
  assert.match(chart, /percent/);
  assert.match(chart, /value/);
});

test("主看板指标下方显示较昨日百分比", () => {
  const page = read("src/app/page.tsx");
  const api = read("src/lib/api.ts");

  assert.match(page, /formatYesterdayTrend/);
  assert.match(page, /metric_trends/);
  assert.doesNotMatch(page, /今日数据/);
  assert.doesNotMatch(page, /实时统计/);
  assert.match(api, /metric_trends/);
});

test("主界面标题使用新版名称并移除标题下方标签", () => {
  const page = read("src/app/page.tsx");
  const globals = read("src/app/globals.css");

  assert.match(page, /成像设备指纹智能取证与比对分析平台/);
  assert.doesNotMatch(page, /基于成像设备指纹的智能取证与比对分析平台/);
  assert.doesNotMatch(page, /hero-tags/);
  assert.doesNotMatch(page, /hero-icon-badge/);
  assert.doesNotMatch(globals, /\.hero-icon-badge/);
  assert.doesNotMatch(page, /<span>精准取证<\/span>/);
  assert.doesNotMatch(page, /<span>智能比对<\/span>/);
  assert.doesNotMatch(page, /<span>高效可信<\/span>/);
  assert.doesNotMatch(page, /<span>安全可靠<\/span>/);
});

test("页面底部左侧显示工信部备案链接", () => {
  const layout = read("src/app/layout.tsx");
  const globals = read("src/app/globals.css");

  assert.match(layout, /https:\/\/beian\.miit\.gov\.cn\//);
  assert.match(layout, /target="_blank"/);
  assert.match(layout, /rel="noreferrer"/);
  assert.match(layout, /皖ICP备2026018644号/);
  assert.match(layout, /icp-footer-link/);
  assert.match(globals, /\.icp-footer-link/);
  assert.match(globals, /bottom:/);
  assert.match(globals, /left:/);
});

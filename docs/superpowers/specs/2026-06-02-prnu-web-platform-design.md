# PRNU 智能取证与比对分析平台设计文档

日期：2026-06-02

## 文档语言约定

从本版本开始，本项目当前及后续设计文档、实现计划、接口说明和测试说明默认使用中文编写。代码标识、目录名、API 路径、数据库字段名和第三方库名称保留英文。

## 目标

开发一个完整工程版 PRNU 图像取证网页平台。平台用于上传图像、提取 PRNU 指纹、建设设备指纹数据库、执行 PCE 指纹比对，并在深蓝科技风看板中展示任务状态、统计指标和比对结论。

现有 Python PRNU 代码继续作为算法核心。网页工程负责补齐 API、数据库、对象存储、异步任务、结果持久化和前端交互。

## 总体架构

采用分层单仓库工程结构，并使用 Docker Compose 管理服务：

- `frontend/`：Next.js、React、TypeScript、Tailwind CSS、ECharts
- `backend/`：FastAPI、SQLAlchemy、Pydantic、PostgreSQL 访问、MinIO 访问
- `worker/`：Celery worker，负责调用 PRNU Python 算法
- `prnu_core/`：复制现有 PRNU 模块形成可导入算法包，迁移期间保留根目录现有文件
- `postgres`：结构化元数据、任务状态和比对结果
- `redis`：Celery broker/result backend 和轻量缓存
- `minio`：上传图像、生成的 `.npy` 指纹文件和结果附件

该架构完整覆盖工程链路，但不拆成过多微服务。

## 业务比对模式

第一版平台包含两类核心比对任务。

### 指纹数据库比对

用途：用户上传一张待检图片，系统判断它是否与当前指纹数据库中的某个设备/图像指纹同源。

流程：

1. 用户上传待检图片。
2. 后端保存原图并创建异步任务。
3. Worker 对待检图片进行预处理并提取单图 PRNU 指纹。
4. Worker 读取数据库内已有设备指纹。
5. 对待检图片指纹与数据库内每个设备指纹进行 PCE 比对。
6. 输出所有 `PCE > 60` 的候选结果，按 PCE 从高到低排序。
7. 如果存在候选结果，结论文案为：`倾向认定设备指纹 A / 图像 A 与待检图像同源`。
8. 如果数据库内没有任何结果满足 `PCE > 60`，结论文案为：`当前指纹数据库内无该图像指纹`。

判定规则：

- 主要判定指标：`PCE`
- 阈值：`60`
- 命中条件：`PCE > 60`
- `NCC` 可作为辅助分数记录和展示，但不作为第一版主判定条件。

### 外来图像比对

用途：用户分别上传图像 A 和图像 B，系统判断两张外来图片是否倾向同源。

流程：

1. 用户上传图像 A 和图像 B。
2. 后端分别保存两张原图并创建异步任务。
3. Worker 对两张图像执行相同预处理。
4. Worker 分别提取图像 A 和图像 B 的单图 PRNU 指纹。
5. Worker 对两个单图指纹进行 PCE 比对。
6. 如果 `PCE > 60`，结论文案为：`倾向认定图像 A 和图像 B 同源`。
7. 如果 `PCE <= 60`，结论文案为：`倾向认定图像 A 和图像 B 不同源`。

判定规则：

- 主要判定指标：`PCE`
- 阈值：`60`
- 同源条件：`PCE > 60`
- 不同源条件：`PCE <= 60`

## 用户界面

### 主看板

首屏采用用户提供的深蓝科技风取证平台样式。界面不是营销页，而是可操作工作台。

主看板展示：

- 当前指纹数据库图像数量
- 今日录入图像数量
- 今日比对任务数量
- 今日比对成功/命中数量
- 设备型号或品牌分布图
- PRNU 指纹取证与比对流程图
- 最近任务列表
- 最新比对结论

### 指纹数据库管理

用于建设和维护数据库内的设备指纹：

- 新建设备/型号标签
- 上传某设备的参考图像
- 触建设备 PRNU 指纹提取任务
- 查看设备指纹状态、图像数量、生成时间和文件尺寸

### 指纹数据库比对页面

用于上传待检图像并与数据库指纹比对：

- 上传待检图片
- 显示任务状态：排队中、处理中、成功、失败
- 显示 Top-K PCE 候选
- 对 `PCE > 60` 的候选标记为命中
- 无候选超过阈值时显示：`当前指纹数据库内无该图像指纹`

### 外来图像比对页面

用于直接比较两张外来图像：

- 上传图像 A
- 上传图像 B
- 显示两张图像的处理状态
- 显示 PCE、峰值位置和判定结果
- `PCE > 60` 显示倾向同源，否则显示倾向不同源

### 任务列表

任务列表展示：

- 任务类型：设备指纹构建、指纹数据库比对、外来图像比对
- 状态：queued、running、succeeded、failed
- 进度说明
- 创建时间、开始时间、完成时间
- 失败原因

## 后端 API

FastAPI 第一版接口：

- `GET /health`：服务健康检查
- `GET /metrics/summary`：主看板统计数据
- `GET /devices`：设备列表
- `POST /devices`：创建设备/型号标签
- `POST /fingerprints/build`：上传参考图像并触建设备指纹构建任务
- `POST /comparisons/database`：上传待检图片，触发指纹数据库比对
- `POST /comparisons/external`：上传图像 A 和图像 B，触发外来图像比对
- `GET /jobs`：任务列表
- `GET /jobs/{job_id}`：任务状态详情
- `GET /comparisons/{job_id}`：获取指定比对任务结果

API 不直接执行 PRNU 计算。API 负责校验请求、保存元数据、上传文件到 MinIO，并投递 Celery 任务。

## 数据模型

PostgreSQL 表：

- `devices`
  - `id`、`name`、`brand`、`model`、`notes`、`created_at`
- `images`
  - `id`、`device_id`、`kind`、`filename`、`object_key`、`content_type`、`width`、`height`、`created_at`
  - `kind` 取值：`reference`、`database_query`、`external_a`、`external_b`
- `fingerprints`
  - `id`、`device_id`、`source_image_id`、`object_key`、`image_count`、`height`、`width`、`enhancement_config`、`created_at`
  - 设备指纹由多张参考图生成；外来图像单图指纹可记录 `source_image_id`
- `jobs`
  - `id`、`type`、`status`、`progress`、`error`、`payload`、`created_at`、`started_at`、`finished_at`
  - `type` 取值：`build_fingerprint`、`database_comparison`、`external_comparison`
- `comparison_results`
  - `id`、`job_id`、`comparison_type`、`query_image_id`、`image_a_id`、`image_b_id`、`candidate_device_id`、`candidate_fingerprint_id`、`rank`、`ncc`、`pce`、`peak_row`、`peak_col`、`is_hit`、`decision`、`created_at`
  - `comparison_type` 取值：`database`、`external`

图像文件和指纹矩阵不存入 PostgreSQL。PostgreSQL 只保存 MinIO object key。

## 对象存储

MinIO bucket：

- `prnu-images`：上传的参考图像、待检图像和外来比对图像
- `prnu-artifacts`：设备指纹、单图指纹、残差图和任务附件

对象路径：

- `reference/{device_id}/{image_id}/{filename}`
- `database-query/{image_id}/{filename}`
- `external/{job_id}/a/{image_id}/{filename}`
- `external/{job_id}/b/{image_id}/{filename}`
- `fingerprints/devices/{device_id}/{fingerprint_id}.npy`
- `fingerprints/images/{image_id}/{fingerprint_id}.npy`
- `jobs/{job_id}/...`

## Worker 任务

Celery 任务：

### `build_fingerprint_job(job_id)`

- 从 MinIO 读取设备参考图像
- 统一预处理图像
- 调用 `get_fingerprint(...)`
- 保存设备 `.npy` 指纹到 MinIO
- 写入 `fingerprints` 元数据
- 更新任务状态

### `database_comparison_job(job_id)`

- 从 MinIO 读取待检图像
- 统一预处理图像
- 调用 `get_fingerprint([query_image], enhancement_config)` 生成单图指纹
- 读取数据库内所有可用设备指纹
- 对每个设备指纹计算 PCE
- 保存所有候选分数
- 对 `PCE > 60` 的候选设置 `is_hit = true`
- 如果存在命中候选，生成 `倾向认定设备指纹 A / 图像 A 与待检图像同源`
- 如果不存在命中候选，生成 `当前指纹数据库内无该图像指纹`
- 更新任务状态

### `external_comparison_job(job_id)`

- 从 MinIO 读取图像 A 和图像 B
- 统一预处理两张图像
- 分别调用 `get_fingerprint([image_a], enhancement_config)` 和 `get_fingerprint([image_b], enhancement_config)`
- 对两个单图指纹计算 PCE
- 如果 `PCE > 60`，生成 `倾向认定图像 A 和图像 B 同源`
- 如果 `PCE <= 60`，生成 `倾向认定图像 A 和图像 B 不同源`
- 保存 PCE、峰值和结论
- 更新任务状态

## PRNU 算法集成

现有文件作为 PRNU 核心：

- `noise_extract.py`
- `prnu_utils.py`
- `enhancers.py`
- `fingerprint.py`
- `matching_core.py`

后端不直接在路由中调用算法，而是通过服务包装层调用。

服务包装层函数：

- `build_device_fingerprint(image_paths, enhancement_config) -> np.ndarray`
- `build_single_image_fingerprint(image_path, enhancement_config) -> np.ndarray`
- `compare_with_database(query_fingerprint, database_fingerprints, threshold=60) -> list[dict]`
- `compare_external_images(fingerprint_a, fingerprint_b, threshold=60) -> dict`

`matching_core.py` 提供数组级 PCE/NCC 计算。业务层负责阈值判断和中文结论文案生成。

## 图像预处理

第一版统一图像预处理规则：

- 尽可能应用 EXIF 方向修正
- 解码后转为 RGB
- 居中裁剪为正方形
- 默认缩放到 `1024x1024`
- 如果图像无法解码，任务失败
- 如果图像尺寸过小，任务失败并给出错误说明

所有设备指纹、待检图像单图指纹、外来图像单图指纹都使用相同输出尺寸，确保 PCE 比对有效。

## 前端设计

前端是密集型取证工作台：

- 深蓝背景
- 青蓝色 PRNU/取证视觉元素
- 紧凑指标卡
- ECharts 图表
- 上传面板
- 任务表格
- 结果表格
- 清晰的中文判定结果

首页直接展示平台主界面，不做营销落地页。

## 错误处理

- API 校验文件类型、必填字段和上传数量
- Worker 捕获算法错误并写入 `jobs.error`
- 数据库无指纹时，数据库比对任务输出明确提示
- 图像尺寸不一致、解码失败、MinIO 读取失败、PCE 输入形状不一致都作为任务失败记录
- 前端展示失败任务的错误文本，不隐藏诊断信息

## 测试策略

后端：

- PRNU 服务包装层单元测试
- 上传接口测试
- 任务创建接口测试
- 比对结果接口测试

PRNU 核心：

- 保留 `dc`、`get_fingerprint`、`matching_core` 回归测试
- 增加图像预处理测试
- 增加 PCE 阈值判定测试

Worker：

- 设备指纹构建任务测试
- 指纹数据库比对任务测试
- 外来图像比对任务测试

前端：

- 首屏渲染验证
- 上传控件验证
- 任务状态展示验证
- 两类比对结果中文文案验证

端到端：

- Docker Compose 服务启动检查
- `GET /health` 成功
- 前端页面可打开
- 创建设备、上传参考图像、创建指纹任务
- 上传待检图像并触发数据库比对
- 上传图像 A/B 并触发外来图像比对

## 第一版实现范围

1. 创建完整工程目录和依赖文件
2. 复制并封装 PRNU 核心代码
3. 添加 Docker Compose：PostgreSQL、Redis、MinIO、backend、worker、frontend
4. 实现数据库模型和初始化逻辑
5. 实现 MinIO 存储服务
6. 实现 FastAPI 接口
7. 实现 Celery worker 任务
8. 实现深蓝科技风前端工作台
9. 接入两类比对任务：指纹数据库比对、外来图像比对
10. 运行测试和浏览器验证

## 第一版暂不包含

- 用户登录
- 角色权限
- Kubernetes 生产部署
- 完整审计追踪
- 阈值标定后台
- 大规模向量索引

## 当前约束

当前工作区不是 git 仓库，因此设计文档暂时无法提交。后续如需要版本管理，应先初始化 git 仓库或将项目移动到已有仓库中。

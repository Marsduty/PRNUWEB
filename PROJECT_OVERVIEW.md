# PRNU 智能取证与比对分析平台 — 项目说明文档

> 最后更新：2026-06-11

---

## 一、项目概述

本项目是一个**基于成像设备 PRNU（Photo Response Non-Uniformity）指纹的智能取证与比对分析 Web 平台**。平台通过提取图像传感器的固有噪声模式作为设备"指纹"，实现对数字图像来源设备的溯源鉴定。

核心能力：
- 从多张参考图像中提取设备级别的 PRNU 指纹并入库
- 将待检图像与指纹库中的设备指纹进行 PCE（Peak-to-Correlation Energy）比对，判定归属设备
- 对两张外来图像进行同源性比对，判定是否来自同一设备

技术栈采用 **Python + TypeScript** 全栈架构，通过 Docker Compose 编排多服务。

---

## 二、技术架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 15)                     │
│              React 19 + TypeScript + Tailwind                 │
│              ECharts 图表 + Lucide 图标                        │
│                       Port :3000                              │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP REST
┌──────────────────────────▼───────────────────────────────────┐
│                   Backend (FastAPI)                           │
│         Python 3.12 + SQLAlchemy + Pydantic                   │
│           路由校验 + 任务投递 + 元数据管理                      │
│                       Port :8000                              │
└──────┬──────────────────────────────┬────────────────────────┘
       │                              │
       │ 投递 Celery 任务              │ 读写元数据
       ▼                              ▼
┌──────────────────┐    ┌──────────────────┐
│  Celery Worker   │    │   PostgreSQL 16  │
│  PRNU 核心算法    │    │   设备/图像/指纹   │
│  指纹提取+PCE比对 │    │   任务/比对结果    │
│                  │    │    Port :5432     │
└────┬─────────────┘    └──────────────────┘
     │
     │ 读写图像 + .npy 指纹
     ▼
┌──────────────────┐    ┌──────────────────┐
│   MinIO 对象存储  │    │      Redis 7     │
│  原始图+指纹文件  │    │  Celery 消息队列  │
│  Port :9000/9001 │    │    Port :6379    │
└──────────────────┘    └──────────────────┘
```

### 服务一览

| 服务 | 技术 | 端口 | 用途 |
|------|------|------|------|
| **frontend** | Next.js 15 + React 19 + TypeScript | 3000 | 深蓝科技风 Web 工作台 |
| **backend** | FastAPI (Python 3.12) | 8000 | REST API，请求校验，任务投递 |
| **worker** | Celery (Python 3.12) | — | 异步执行 PRNU 算法 |
| **postgres** | PostgreSQL 16 | 5432 | 元数据持久化 |
| **redis** | Redis 7 | 6379 | Celery broker / result backend |
| **minio** | MinIO | 9000/9001 | 图像与指纹文件对象存储 |

---

## 三、目录结构

```
PRNUweb/
├── frontend/                     # Next.js 前端 (TypeScript)
│   ├── Dockerfile
│   ├── package.json              # 依赖：React 19, ECharts, Lucide, Tailwind
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx        # 根布局
│       │   └── page.tsx          # 主看板页面（Client Component）
│       ├── components/
│       │   ├── MetricCard.tsx           # 指标卡片
│       │   ├── DistributionChart.tsx    # 品牌分布饼图（ECharts）
│       │   ├── ProcessFlow.tsx          # 工作流步骤导航
│       │   ├── WorkflowWorkspace.tsx    # 工作流子页面容器（路由分发）
│       │   ├── FingerprintBuildPanel.tsx # 设备指纹录入 & 管理
│       │   ├── DatabaseComparisonPanel.tsx # 指纹数据库比对
│       │   ├── ExternalComparisonPanel.tsx # 外来图像比对
│       │   ├── TaskTable.tsx            # 任务队列表格
│       │   └── ResultPanel.tsx          # 比对结论展示
│       └── lib/
│           ├── api.ts             # API 调用封装 & 类型定义
│           ├── metrics.ts         # 指标格式化工具
│           └── taskNumbers.ts     # 任务号映射 & 状态标签
│
├── backend/                      # FastAPI 后端 (Python)
│   ├── Dockerfile
│   ├── requirements.txt          # fastapi, sqlalchemy, celery, minio, numpy, scipy, PyWavelets...
│   ├── app/
│   │   ├── main.py               # FastAPI 应用入口 + CORS + lifespan
│   │   ├── api/
│   │   │   ├── router.py         # 路由汇总
│   │   │   └── routes/
│   │   │       ├── health.py     # GET /health
│   │   │       ├── metrics.py    # GET /metrics/summary
│   │   │       ├── devices.py    # CRUD /devices
│   │   │       ├── fingerprints.py # CRUD /fingerprints + 构建/重建
│   │   │       ├── jobs.py       # GET /jobs, GET /jobs/{id}
│   │   │       ├── comparisons.py # POST /comparisons/database|external, GET /comparisons/{id}
│   │   │       └── serializers.py # 模型序列化 & 判定文案生成
│   │   ├── core/
│   │   │   └── config.py         # Pydantic Settings（环境变量驱动）
│   │   ├── db/
│   │   │   ├── base.py           # SQLAlchemy DeclarativeBase
│   │   │   └── session.py        # Engine + SessionLocal + get_db 依赖
│   │   ├── models/
│   │   │   ├── device.py         # Device 模型
│   │   │   ├── image.py          # ImageRecord 模型
│   │   │   ├── fingerprint.py    # Fingerprint 模型
│   │   │   ├── job.py            # Job 模型
│   │   │   └── comparison_result.py # ComparisonResult 模型
│   │   ├── services/
│   │   │   ├── storage.py        # MinIO 客户端 + 上传/下载
│   │   │   ├── prnu_service.py   # PRNU 算法服务封装层
│   │   │   └── image_preprocess.py # 图像预处理（EXIF/RGB/裁剪/缩放）
│   │   └── worker/
│   │       ├── celery_app.py     # Celery 应用配置
│   │       └── tasks.py          # 三个异步任务
│   └── tests/
│       ├── test_health.py        # 健康检查接口测试
│       ├── test_models.py        # 数据库模型测试
│       └── test_storage.py       # 存储路径安全测试
│
├── prnu_core/                    # PRNU 算法核心包
│   ├── __init__.py               # 导出 get_fingerprint, ncc_score, pce_score, rank_references
│   ├── noise_extract.py          # 小波域噪声残差提取
│   ├── prnu_utils.py             # 小波构造、维纳滤波、光强加权、灰度化
│   ├── enhancers.py              # 5 种指纹增强算法 (RSC/SEA/DC/HF/GF)
│   ├── fingerprint.py            # 设备指纹融合提取
│   └── matching_core.py          # NCC/PCE 核心计算
│
├── fingerprint.py                # [根目录残留] 设备指纹提取（同 prnu_core/fingerprint.py）
├── matching.py                   # [根目录残留] 批量 NCC/PCE 评估脚本
├── matching_core.py              # [根目录残留] NCC/PCE 核心（同 prnu_core/matching_core.py）
├── noise_extract.py              # [根目录残留] 噪声提取（同 prnu_core/noise_extract.py）
├── prnu_utils.py                 # [根目录残留] PRNU 工具函数（同 prnu_core/prnu_utils.py）
├── enhancers.py                  # [根目录残留] 增强算法（同 prnu_core/enhancers.py）
│
├── scripts/                      # 数据集批量导入脚本
│   ├── import_vision_dataset.py  # VISION 数据集导入
│   ├── import_floreview_dataset.py  # FloreView 数据集导入
│   └── import_fodb_dataset.py    # FODB 数据集导入
│
├── tests/
│   └── test_prnu_core.py         # PRNU 核心算法回归测试
│
├── docs/
│   └── superpowers/
│       ├── specs/2026-06-02-prnu-web-platform-design.md    # 详细设计文档
│       └── plans/2026-06-02-prnu-web-platform-implementation.md # 实现计划
│
├── docker-compose.yml            # 本地开发六服务编排
├── docker-compose.prod.yml       # 服务器生产部署覆盖配置
├── nginx.conf.example            # Nginx 服务器私有配置模板
├── docker-daemon.json            # Docker 镜像加速配置（国内）
├── DOCKER_DEPLOYMENT.md          # Docker 部署详细指南
├── .env.local.example            # 本地开发环境变量示例
├── .env.prod.example             # 服务器生产环境变量示例
└── .gitignore
```

> 注意：PRNU 正式算法代码统一维护在 `prnu_core/` 包中。根目录下迁移前的 `fingerprint.py`、`matching.py`、`matching_core.py`、`noise_extract.py`、`prnu_utils.py`、`enhancers.py` 已移动到本地 `_local_archive/`，并排除在 Git 与 Docker 构建上下文之外。

---

## 四、PRNU 算法原理

### 4.1 什么是 PRNU

PRNU（Photo Response Non-Uniformity）是图像传感器在制造过程中由于硅片不均匀导致的像素级光电响应差异。每台设备的光电响应模式是**唯一且稳定**的，类似于传感器的"指纹"。通过分析图像中残留的传感器模式噪声，可以追溯图像来源设备。

### 4.2 核心算法链路

```
原始图像（多张）
    │
    ▼
┌─────────────────────────────┐
│ 1. 小波域噪声残差提取         │  noise_extract.py
│    Daubechies-8 四级小波分解  │
│    维纳 MAP 估计去噪          │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 2. 加权累加融合              │  fingerprint.py
│    光强加权 (IntenScale)      │
│    饱和区域剔除 (Saturation)  │
│    多图叠加求均值             │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 3. 增强后处理                │  enhancers.py
│    RSC - 去除 CFA 共享伪影   │
│    SEA - 频谱均衡去峰值      │
│    DC  - PCA 去相关          │
│    HF  - DCT 高通滤波        │
│    GF  - 导向滤波分离高低频   │
└─────────────┬───────────────┘
              ▼
         设备 PRNU 指纹
              │
              ▼
┌─────────────────────────────┐
│ 4. 比对判定                  │  matching_core.py
│    NCC - 归一化互相关        │
│    PCE - 峰值相关能量比      │
│    阈值：PCE > 60 → 同源     │
└─────────────────────────────┘
```

### 4.3 PCE 比对算法

PCE（Peak-to-Correlation Energy）是 PRNU 比对的黄金标准指标：

$$PCE = \frac{(peak\ value)^2}{\frac{1}{N - |\Omega|}\sum_{(i,j)\notin \Omega} corr(i,j)^2}$$

其中 `peak value` 是互相关平面的最大值，分母是排除峰值邻域后的旁瓣均方能量。PCE > 60 被判定为同源设备。

---

## 五、数据模型

### 5.1 PostgreSQL 表结构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   devices    │     │   images     │     │  fingerprints    │
├──────────────┤     ├──────────────┤     ├──────────────────┤
│ id (PK)      │◄────│ device_id(FK)│◄────│ device_id (FK)   │
│ name (UQ)    │     │ kind         │     │ source_image_id  │
│ brand        │     │ filename     │     │ object_key       │
│ model        │     │ object_key   │     │ image_count      │
│ mac_address  │     │ content_type │     │ height, width    │
│ notes        │     │ width,height │     │ enhancement_conf │
│ created_at   │     │ created_at   │     │ created_at       │
└──────────────┘     └──────┬───────┘     └────────┬─────────┘
                            │                      │
                            │    ┌──────────────┐  │
                            │    │    jobs      │  │
                            │    ├──────────────┤  │
                            │    │ id (PK)      │  │
                            │    │ type         │  │
                            │    │ status       │  │
                            │    │ progress     │  │
                            │    │ error        │  │
                            │    │ payload(JSON)│  │
                            │    │ created_at   │  │
                            │    └──────┬───────┘  │
                            │           │           │
                            │    ┌──────▼───────────▼──┐
                            │    │ comparison_results  │
                            └────┤ query_image_id (FK) │
                                 │ image_a_id (FK)     │
                                 │ image_b_id (FK)     │
                                 │ candidate_device_id │
                                 │ candidate_fp_id     │
                                 │ rank, ncc, pce     │
                                 │ is_hit, decision   │
                                 └────────────────────┘
```

### 5.2 枚举取值

| 字段 | 取值 |
|------|------|
| `images.kind` | `reference`, `query`, `external_a`, `external_b` |
| `jobs.type` | `build_fingerprint`, `rebuild_fingerprint`, `database_comparison`, `external_comparison` |
| `jobs.status` | `queued`, `running`, `succeeded`, `failed` |
| `comparison_results.comparison_type` | `database_comparison`, `external_comparison` |

---

## 六、业务对比模式

### 6.1 指纹数据库比对（Database Comparison）

```
用户上传待检图片 → Worker 提取单图 PRNU
                          ↓
          遍历指纹库中所有设备指纹
                          ↓
          逐对计算 PCE（频域快速互相关）
                          ↓
         PCE > 60 → "倾向认定设备指纹：XXX 与待检图像同源"
         PCE ≤ 60 → "库中未检索到匹配设备"
```

### 6.2 外来图像比对（External Comparison）

```
用户上传图像 A + 图像 B → Worker 分别提取单图 PRNU
                                   ↓
                    计算图像 A 与图像 B 的 PCE
                                   ↓
                PCE > 60 → "倾向认定图像 A 和图像 B 同源"
                PCE ≤ 60 → "倾向认定图像 A 和图像 B 不同源"
```

---

## 七、后端 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 服务健康检查 |
| `GET` | `/metrics/summary` | 主看板指标：指纹数、今日上传、今日任务、命中数、品牌分布、最近结论 |
| `GET` | `/devices` | 设备列表 |
| `POST` | `/devices` | 创建设备（品牌、型号、MAC、备注） |
| `PATCH` | `/devices/{id}` | 更新设备信息 |
| `GET` | `/fingerprints` | 设备指纹列表 |
| `POST` | `/fingerprints/build` | 上传参考图像，创建指纹构建任务 |
| `GET` | `/fingerprints/{id}` | 指纹详情 |
| `PATCH` | `/fingerprints/{id}` | 修改指纹关联设备信息 |
| `DELETE` | `/fingerprints/{id}` | 删除指纹记录 |
| `POST` | `/fingerprints/{id}/references` | 重建指纹（替换参考图像） |
| `GET` | `/jobs` | 最近 50 条任务列表 |
| `GET` | `/jobs/{id}` | 任务状态详情 |
| `POST` | `/comparisons/database` | 上传待检图，触发数据库比对 |
| `POST` | `/comparisons/external` | 上传图像 A/B，触发外来比对 |
| `GET` | `/comparisons/{job_id}` | 获取比对结果详情 |

---

## 八、前端界面

### 主看板
- 深蓝科技风取证平台视觉风格
- 4 个指标卡（指纹总数、今日录入、今日比对、今日命中）带较昨日变化趋势
- 设备品牌分布饼图（ECharts）
- 四步 PRNU 取证比对流程图（点击进入子页面）

### 四大工作流子页面
1. **图像导入** — 设备指纹录入表单 + 指纹管理表格（支持搜索/编辑/删除/重建）
2. **PRNU 提取** — 显示指纹构建/重建任务队列
3. **指纹比对** — 数据库比对面板 + 外来图像比对面板 + 比对任务队列
4. **结果判定** — 最新比对结论列表，点击查看详细匹配信息

---

## 九、Celery 异步任务

| 任务名 | 触发方式 | 主要逻辑 |
|--------|----------|----------|
| `build_fingerprint_job` | POST `/fingerprints/build` | 读取参考图 → 预处理 → `get_fingerprint()` → 保存 .npy 到 MinIO → 写入 fingerprints 表 |
| `database_comparison_job` | POST `/comparisons/database` | 读取待检图 → 提取单图指纹 → 遍历库内所有设备指纹计算 PCE → 生成候选列表 → 写入 comparison_results |
| `external_comparison_job` | POST `/comparisons/external` | 读取图像 A/B → 分别提取单图指纹 → 计算 PCE → 写入判定结果 |

---

## 十、对象存储设计

| Bucket | 用途 | 路径模式 |
|--------|------|----------|
| `prnu-images` | 上传的原始图像 | `references/{device_id}/{job_id}/{filename}` |
| | | `comparisons/{job_id}/{slot}/{filename}` |
| `prnu-artifacts` | 生成的指纹文件 | `fingerprints/devices/{device_id}/job-{job_id}.npy` |

---

## 十一、部署方式

### 一键启动

```bash
cd G:/PRNUweb
docker-compose up --build
```

启动后访问：
- 前端工作台：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`
- MinIO 控制台：`http://localhost:9001`

### 环境变量

通过 `.env` 文件配置，支持环境解耦：

| 文件 | 用途 |
|------|------|
| `.env.example` | 通用模板 |
| `.env.local.example` | 本地开发模板 |
| `.env.prod.example` | 生产部署模板 |

| 变量 | 说明 |
|------|------|
| `POSTGRES_PASSWORD` | 数据库密码 |
| `MINIO_ROOT_PASSWORD` | MinIO 密码 |
| `NEXT_PUBLIC_API_BASE_URL` | 前端 API 地址（本地 `http://localhost:8000`，生产 `/api`） |
| `CORS_ALLOW_ORIGINS` | CORS 跨域来源 |
| `MINIO_SECURE` | MinIO HTTPS 开关 |

---

## 十二、批量导入脚本

`scripts/` 目录下提供三个数据集批量导入脚本，均支持 `--dry-run` 预演模式：

- `import_vision_dataset.py` — VISION 数据集（45 台设备）
- `import_floreview_dataset.py` — FloreView 数据集
- `import_fodb_dataset.py` — FODB 数据集

用法示例：
```bash
python scripts/import_vision_dataset.py --dataset /path/to/VISION --api http://localhost:8000 --apply --wait
```

---

## 十三、测试

```bash
# PRNU 核心算法测试
cd G:/PRNUweb
python -m pytest tests/ -v

# 后端测试
python -m pytest backend/tests/ -v
```

---

## 十四、关键设计决策

1. **单仓库分层架构**：前端、后端、Worker 共处一个仓库，通过 Docker Compose 统一编排，不拆分为独立微服务
2. **API 不直接计算**：FastAPI 只做校验和任务投递，PRNU 计算全部在 Celery Worker 中异步执行
3. **PostgreSQL 只存元数据**：图像和 .npy 指纹文件全部存储在 MinIO 中
4. **统一图像预处理**：所有输入图像经过 EXIF 修正 → RGB → 居中裁剪正方形 → 1024×1024 缩放
5. **PCE 阈值固定为 60**：第一版暂不支持动态阈值标定
6. **默认增强配置**：`[RSC=1, SEA=0, DC=0, HF=0, GF=0]`，仅启用 RSC 增强

---

## 十五、待完成事项

- [ ] 用户认证与权限管理
- [ ] 阈值标定后台（ROC 曲线可视化）
- [ ] 大规模向量索引（加速数据库比对）
- [ ] Kubernetes 生产部署配置
- [ ] 完整审计追踪日志
- [ ] 清理根目录残留的旧算法文件（已全部迁移到 `prnu_core/`）

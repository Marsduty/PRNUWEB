# PRNU 智能取证网页平台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建完整工程版 PRNU 智能取证与比对分析平台，支持设备指纹构建、指纹数据库比对、外来图像比对和深蓝科技风前端工作台。

**Architecture:** 采用分层单仓库结构：Next.js 前端、FastAPI 后端、Celery worker、PostgreSQL、Redis、MinIO、Docker Compose。现有 PRNU Python 算法复制到 `prnu_core/`，后端通过服务包装层调用，不在 API 路由中直接执行耗时算法。

**Tech Stack:** Next.js、React、TypeScript、Tailwind CSS、ECharts、FastAPI、SQLAlchemy、Pydantic、Celery、Redis、PostgreSQL、MinIO、NumPy、SciPy、PyWavelets、Pillow、pytest、Docker Compose。

---

## 范围检查

本规格覆盖多个子系统，但它们共同服务同一个首版闭环：上传图像、生成指纹、执行 PCE 比对、展示结果。实现按阶段推进，每个阶段都必须能独立验证。当前工作区不是 git 仓库，因此提交步骤只有在后续初始化 git 后执行。

## 文件结构

第一版创建或修改以下文件：

- `prnu_core/__init__.py`：导出 PRNU 核心入口。
- `prnu_core/enhancers.py`：复制根目录 `enhancers.py`。
- `prnu_core/noise_extract.py`：复制根目录 `noise_extract.py` 并改为包内导入。
- `prnu_core/prnu_utils.py`：复制根目录 `prnu_utils.py`。
- `prnu_core/fingerprint.py`：复制根目录 `fingerprint.py` 并改为包内导入。
- `prnu_core/matching_core.py`：复制根目录 `matching_core.py`。
- `backend/app/main.py`：FastAPI 应用入口。
- `backend/app/core/config.py`：环境变量配置。
- `backend/app/db/session.py`：数据库连接和 session。
- `backend/app/db/base.py`：SQLAlchemy Base。
- `backend/app/models/*.py`：数据库模型。
- `backend/app/schemas/*.py`：API 响应和请求模型。
- `backend/app/services/storage.py`：MinIO 文件读写。
- `backend/app/services/image_preprocess.py`：图像解码、EXIF 修正、RGB 转换、中心裁剪、缩放。
- `backend/app/services/prnu_service.py`：PRNU 算法包装层和 PCE 判定文案。
- `backend/app/api/routes/*.py`：健康检查、指标、设备、任务、比对 API。
- `backend/app/worker/celery_app.py`：Celery 实例。
- `backend/app/worker/tasks.py`：设备指纹构建、指纹数据库比对、外来图像比对任务。
- `backend/requirements.txt`：后端和 worker Python 依赖。
- `backend/Dockerfile`：后端/worker 镜像。
- `frontend/package.json`：前端依赖和脚本。
- `frontend/src/app/page.tsx`：主工作台页面。
- `frontend/src/app/layout.tsx`：Next.js 布局。
- `frontend/src/app/globals.css`：全局样式。
- `frontend/src/lib/api.ts`：前端 API 调用封装。
- `frontend/src/components/*.tsx`：指标卡、图表、上传面板、任务表、结果面板。
- `docker-compose.yml`：完整服务编排。
- `tests/`：保留现有 PRNU 核心测试。
- `backend/tests/`：后端服务、API、worker 测试。

## Task 1: PRNU 核心包迁移

**Files:**
- Create: `prnu_core/__init__.py`
- Create: `prnu_core/enhancers.py`
- Create: `prnu_core/noise_extract.py`
- Create: `prnu_core/prnu_utils.py`
- Create: `prnu_core/fingerprint.py`
- Create: `prnu_core/matching_core.py`
- Modify: `tests/test_prnu_core.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_prnu_core.py` 新增包导入测试：

```python
def test_prnu_core_package_exports_main_functions():
    from prnu_core import get_fingerprint, ncc_score, pce_score

    assert callable(get_fingerprint)
    assert callable(ncc_score)
    assert callable(pce_score)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_prnu_core.py::test_prnu_core_package_exports_main_functions -q`

Expected: `ModuleNotFoundError: No module named 'prnu_core'`

- [ ] **Step 3: 创建 `prnu_core` 包**

复制现有根目录 PRNU 文件到 `prnu_core/`。在包内文件中使用相对导入：

```python
# prnu_core/noise_extract.py
from .prnu_utils import get_daubechies_8_wavelet, wiener_noise_extract

# prnu_core/fingerprint.py
from .noise_extract import extract_noise
from .prnu_utils import inten_scale, saturation, rgb2gray1
from .enhancers import rsc, sea, dc, hf, gf
```

创建 `prnu_core/__init__.py`：

```python
from .fingerprint import get_fingerprint
from .matching_core import ncc_score, pce_score, rank_references

__all__ = ["get_fingerprint", "ncc_score", "pce_score", "rank_references"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_prnu_core.py -q`

Expected: 所有 PRNU 核心测试通过。

- [ ] **Step 5: 提交**

当前工作区不是 git 仓库。如已初始化 git，执行：

```bash
git add prnu_core tests/test_prnu_core.py
git commit -m "feat: package prnu core"
```

## Task 2: 后端项目骨架和配置

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/api/router.py`
- Create: `backend/requirements.txt`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_health.py`：

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_health.py -q`

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: 创建后端基础文件**

`backend/requirements.txt`：

```text
fastapi==0.115.14
uvicorn[standard]==0.34.3
pydantic-settings==2.10.1
sqlalchemy==2.0.41
psycopg[binary]==3.2.9
python-multipart==0.0.20
minio==7.2.15
celery==5.5.3
redis==6.2.0
pillow==11.2.1
numpy==2.3.0
scipy==1.15.3
PyWavelets==1.8.0
pytest==8.4.1
httpx==0.28.1
```

`backend/app/core/config.py`：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://prnu:prnu@localhost:5432/prnu"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "prnuadmin"
    minio_secret_key: str = "prnupassword"
    minio_secure: bool = False
    prnu_image_bucket: str = "prnu-images"
    prnu_artifact_bucket: str = "prnu-artifacts"
    pce_threshold: float = 60.0
    prnu_image_size: int = 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

`backend/app/api/routes/health.py`：

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}
```

`backend/app/api/router.py`：

```python
from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
```

`backend/app/main.py`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router

app = FastAPI(title="PRNU 智能取证与比对分析平台")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_health.py -q`

Expected: `1 passed`

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add backend
git commit -m "feat: scaffold fastapi backend"
```

## Task 3: 数据库模型和初始化

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/models/device.py`
- Create: `backend/app/models/image.py`
- Create: `backend/app/models/fingerprint.py`
- Create: `backend/app/models/job.py`
- Create: `backend/app/models/comparison_result.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_models.py`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.device import Device
from app.models.job import Job


def test_can_create_device_and_job_in_sqlite_memory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        device = Device(name="设备A", brand="Canon", model="A1")
        job = Job(type="build_fingerprint", status="queued", progress="等待处理")
        session.add_all([device, job])
        session.commit()

        assert session.query(Device).count() == 1
        assert session.query(Job).count() == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -q`

Expected: `ModuleNotFoundError` 或模型不存在错误。

- [ ] **Step 3: 实现模型**

核心字段按设计文档创建。所有模型继承 `Base`，主键使用 `Integer` 自增，时间字段使用 `datetime.utcnow` 默认值。`Job.status` 默认 `queued`，`ComparisonResult.is_hit` 默认 `False`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_models.py -q`

Expected: `1 passed`

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add backend/app/db backend/app/models backend/tests/test_models.py
git commit -m "feat: add database models"
```

## Task 4: 图像预处理和 PRNU 服务包装层

**Files:**
- Create: `backend/app/services/image_preprocess.py`
- Create: `backend/app/services/prnu_service.py`
- Create: `backend/tests/test_prnu_service.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_prnu_service.py`：

```python
from io import BytesIO

import numpy as np
from PIL import Image

from app.services.image_preprocess import load_rgb_square
from app.services.prnu_service import decide_database_matches, decide_external_match


def _png_bytes(size=(80, 64), color=(120, 130, 140)):
    image = Image.new("RGB", size, color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_load_rgb_square_returns_configured_shape():
    result = load_rgb_square(_png_bytes(), output_size=32)

    assert result.shape == (32, 32, 3)
    assert result.dtype == np.uint8


def test_database_decision_uses_pce_threshold():
    rows = decide_database_matches(
        [{"name": "设备A", "pce": 61.0}, {"name": "设备B", "pce": 12.0}],
        threshold=60,
    )

    assert rows["decision"] == "倾向认定设备指纹 设备A / 图像 设备A 与待检图像同源"
    assert rows["hits"][0]["is_hit"] is True


def test_external_decision_uses_pce_threshold():
    assert decide_external_match(61.0, threshold=60)["decision"] == "倾向认定图像 A 和图像 B 同源"
    assert decide_external_match(60.0, threshold=60)["decision"] == "倾向认定图像 A 和图像 B 不同源"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_prnu_service.py -q`

Expected: 服务模块不存在错误。

- [ ] **Step 3: 实现图像预处理**

`load_rgb_square(image_bytes, output_size)` 使用 Pillow 解码、`ImageOps.exif_transpose` 修正方向、转 RGB、中心裁剪正方形、缩放到指定尺寸，返回 `np.uint8` 的 `H x W x 3` 数组。

- [ ] **Step 4: 实现 PRNU 判定函数**

`decide_database_matches(candidates, threshold)` 过滤 `pce > threshold`，按 PCE 降序输出命中列表；没有命中时返回 `当前指纹数据库内无该图像指纹`。

`decide_external_match(pce, threshold)` 在 `pce > threshold` 时输出同源文案，否则输出不同源文案。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_prnu_service.py -q`

Expected: `3 passed`

- [ ] **Step 6: 提交**

如已初始化 git：

```bash
git add backend/app/services backend/tests/test_prnu_service.py
git commit -m "feat: add prnu service wrapper"
```

## Task 5: MinIO 存储服务

**Files:**
- Create: `backend/app/services/storage.py`
- Create: `backend/tests/test_storage.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_storage.py`：

```python
from app.services.storage import build_object_key


def test_build_object_key_removes_windows_path_segments():
    key = build_object_key("reference", 1, "..\\bad\\image.png")

    assert key == "reference/1/image.png"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_storage.py -q`

Expected: `ModuleNotFoundError` 或函数不存在错误。

- [ ] **Step 3: 实现存储服务**

实现 `build_object_key(prefix, owner_id, filename)`、`ensure_buckets()`、`put_bytes(object_key, data, content_type)`、`get_bytes(object_key)`。`build_object_key` 必须使用 `PurePath(filename).name` 和反斜杠替换，避免路径穿越。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_storage.py -q`

Expected: `1 passed`

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add backend/app/services/storage.py backend/tests/test_storage.py
git commit -m "feat: add minio storage service"
```

## Task 6: Celery worker 任务

**Files:**
- Create: `backend/app/worker/celery_app.py`
- Create: `backend/app/worker/tasks.py`
- Create: `backend/tests/test_worker_decisions.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_worker_decisions.py`：

```python
from app.services.prnu_service import decide_database_matches, decide_external_match


def test_database_no_hit_message():
    result = decide_database_matches([{"name": "设备A", "pce": 60.0}], threshold=60)

    assert result["decision"] == "当前指纹数据库内无该图像指纹"
    assert result["hits"] == []


def test_external_hit_message():
    result = decide_external_match(60.1, threshold=60)

    assert result["is_hit"] is True
```

- [ ] **Step 2: 运行测试确认失败或复用 Task 4 通过**

Run: `cd backend && python -m pytest tests/test_worker_decisions.py -q`

Expected: 如果 Task 4 已完成，则测试通过；否则因服务函数不存在失败。

- [ ] **Step 3: 实现 Celery app**

`celery_app.py` 从 `settings.redis_url` 读取 broker 和 backend。默认队列名使用 `prnu`。

- [ ] **Step 4: 实现任务函数**

`tasks.py` 实现：

- `build_fingerprint_job(job_id)`
- `database_comparison_job(job_id)`
- `external_comparison_job(job_id)`

任务内部按设计文档更新 `jobs.status`、`jobs.progress`、`jobs.error` 和 `comparison_results`。算法调用统一走 `prnu_service.py`。

- [ ] **Step 5: 运行 worker 判定测试**

Run: `cd backend && python -m pytest tests/test_worker_decisions.py -q`

Expected: `2 passed`

- [ ] **Step 6: 提交**

如已初始化 git：

```bash
git add backend/app/worker backend/tests/test_worker_decisions.py
git commit -m "feat: add celery worker tasks"
```

## Task 7: FastAPI 业务接口

**Files:**
- Create: `backend/app/api/routes/devices.py`
- Create: `backend/app/api/routes/jobs.py`
- Create: `backend/app/api/routes/metrics.py`
- Create: `backend/app/api/routes/fingerprints.py`
- Create: `backend/app/api/routes/comparisons.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_api_contract.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_api_contract.py`：

```python
from fastapi.testclient import TestClient

from app.main import app


def test_api_routes_exist():
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/devices").status_code in {200, 500}
    assert client.get("/jobs").status_code in {200, 500}
    assert client.get("/metrics/summary").status_code in {200, 500}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_api_contract.py -q`

Expected: `/devices`、`/jobs` 或 `/metrics/summary` 返回 `404`。

- [ ] **Step 3: 实现接口路由**

实现路由并接入 `api_router`：

- `GET /devices`
- `POST /devices`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /metrics/summary`
- `POST /fingerprints/build`
- `POST /comparisons/database`
- `POST /comparisons/external`
- `GET /comparisons/{job_id}`

文件上传接口使用 `UploadFile` 和 `File(...)`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_api_contract.py -q`

Expected: `1 passed`

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add backend/app/api backend/tests/test_api_contract.py
git commit -m "feat: add api routes"
```

## Task 8: Docker Compose 和容器文件

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: 写配置检查测试**

创建 `backend/tests/test_compose_config.py`：

```python
from pathlib import Path


def test_compose_declares_required_services():
    text = Path("../docker-compose.yml").read_text(encoding="utf-8")

    for service in ["frontend", "backend", "worker", "postgres", "redis", "minio"]:
        assert f"{service}:" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_compose_config.py -q`

Expected: `FileNotFoundError`。

- [ ] **Step 3: 创建 Docker 配置**

`docker-compose.yml` 包含六个服务：`frontend`、`backend`、`worker`、`postgres`、`redis`、`minio`。端口映射：

- frontend: `3000:3000`
- backend: `8000:8000`
- postgres: `5432:5432`
- redis: `6379:6379`
- minio API: `9000:9000`
- minio console: `9001:9001`

- [ ] **Step 4: 运行配置测试**

Run: `cd backend && python -m pytest tests/test_compose_config.py -q`

Expected: `1 passed`

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile backend/tests/test_compose_config.py
git commit -m "feat: add docker compose stack"
```

## Task 9: 前端工程和深蓝工作台

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/DatabaseComparisonPanel.tsx`
- Create: `frontend/src/components/ExternalComparisonPanel.tsx`
- Create: `frontend/src/components/TaskTable.tsx`
- Create: `frontend/src/components/ResultPanel.tsx`

- [ ] **Step 1: 创建前端文件**

实现 Next.js App Router 首页。首屏包含：

- 顶部标题：`基于PRNU指纹的智能取证与比对分析平台`
- 四个指标卡
- 设备分布图
- PRNU 流程图
- 指纹数据库比对上传区
- 外来图像比对上传区
- 任务表格
- 结果面板

- [ ] **Step 2: 安装和构建**

Run: `cd frontend && npm install`

Expected: 依赖安装完成。

Run: `cd frontend && npm run build`

Expected: Next.js production build 成功。

- [ ] **Step 3: 浏览器验证**

Run: `cd frontend && npm run dev -- --hostname 127.0.0.1 --port 3000`

Expected: 前端服务启动在 `http://localhost:3000`。

使用浏览器打开 `http://localhost:3000`，检查：

- 首屏不是空白
- 标题可见
- 两类比对入口可见
- 按钮文字不溢出
- 页面没有明显重叠

- [ ] **Step 4: 提交**

如已初始化 git：

```bash
git add frontend
git commit -m "feat: add prnu dashboard frontend"
```

## Task 10: 联调和最终验证

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes/*.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: 后端测试**

Run: `python -m pytest -q`

Expected: 根目录 PRNU 测试全部通过。

Run: `cd backend && python -m pytest -q`

Expected: 后端测试全部通过。

- [ ] **Step 2: 容器启动检查**

Run: `docker compose up --build`

Expected:

- `postgres` 启动成功
- `redis` 启动成功
- `minio` 启动成功
- `backend` 暴露 `http://localhost:8000/health`
- `frontend` 暴露 `http://localhost:3000`
- `worker` 连接 Redis 成功

- [ ] **Step 3: API 健康检查**

Run: `Invoke-WebRequest -Uri http://localhost:8000/health`

Expected: 响应 JSON 包含 `{"status":"ok"}`。

- [ ] **Step 4: 浏览器截图验证**

打开 `http://localhost:3000`，截图确认：

- 深蓝科技风主界面可见
- 指纹数据库比对入口可见
- 外来图像比对入口可见
- 任务表和结果区可见

- [ ] **Step 5: 提交**

如已初始化 git：

```bash
git add .
git commit -m "feat: complete prnu web platform mvp"
```

## 自检结果

- 规格覆盖：计划覆盖 PRNU 核心迁移、后端 API、数据库、MinIO、Celery、两类 PCE 比对、前端工作台、Docker Compose 和验证。
- 占位扫描：计划不包含 `TBD`、`TODO`、`FIXME`。
- 类型一致性：任务类型使用 `build_fingerprint`、`database_comparison`、`external_comparison`；比对接口使用 `/comparisons/database` 和 `/comparisons/external`；阈值统一为 `PCE > 60`。
- 当前约束：工作区不是 git 仓库，因此提交步骤只有在初始化 git 后执行。

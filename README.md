# 觅迹 · PRNUWEB

基于成像设备 PRNU（Photo Response Non-Uniformity）指纹的智能取证与比对分析 Web 平台。

通过提取图像传感器的固有噪声模式作为设备"指纹"，实现数字图像来源设备的溯源鉴定。同时集成深度伪造检测，构建"来源 + 内容"双重鉴定体系。

---

## 快速开始（本地开发）

```bash
# 1. 复制环境变量
cp .env.local.example .env.local

# 2. 启动全部服务（首次需拉取镜像，约 3-5 分钟）
docker compose up -d --build

# 3. 访问
# 前端：http://localhost:3000
# API 文档：http://localhost:8000/docs
# MinIO 控制台：http://localhost:9001
```

## 生产部署

```bash
# 1. 准备生产配置
cp .env.prod.example .env.prod
cp nginx.conf.example nginx.conf
# 编辑 .env.prod（改强密码）和 nginx.conf（换域名）

# 2. 申请 SSL 证书（可选）
mkdir -p ssl
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d your-domain.com --email you@example.com --agree-tos --non-interactive
ln -sf /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/fullchain.pem
ln -sf /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/privkey.pem

# 3. 启动
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 技术架构

```
Frontend (Next.js 15 + React 19)     :3000
        │ HTTP REST
Backend (FastAPI + Celery)           :8000
        │
  ┌─────┼─────┐
  ▼     ▼     ▼
PostgreSQL  Redis   MinIO
 :5432    :6379   :9000
```

| 服务 | 技术 | 用途 |
|------|------|------|
| frontend | Next.js 15 + ECharts + Tailwind | Web 取证工作台 |
| backend | FastAPI + SQLAlchemy | REST API、任务调度 |
| worker | Celery | 异步 PRNU 计算 |
| postgres | PostgreSQL 16 | 元数据持久化 |
| redis | Redis 7 | 消息队列 |
| minio | MinIO | 图像与指纹文件存储 |

## 核心能力

- **设备指纹提取**：小波域噪声残差 → 加权融合 → 增强后处理 → PRNU 指纹入库
- **指纹库比对**：待检图 vs 库内所有设备指纹，PCE > 60 判定同源
- **同源性比对**：两张外来图像比对，判定是否来自同一设备

## 环境变量说明

| 变量 | 说明 |
|------|------|
| `POSTGRES_PASSWORD` | 数据库密码 |
| `MINIO_ROOT_PASSWORD` | MinIO 密码 |
| `NEXT_PUBLIC_API_BASE_URL` | 前端 API 地址（本地 `http://localhost:8000`，生产 `/api`） |
| `CORS_ALLOW_ORIGINS` | CORS 允许来源 |
| `MINIO_SECURE` | MinIO HTTPS 开关 |

注意：`.env` / `.env.local` / `.env.prod` / `nginx.conf` 包含敏感信息，已通过 `.gitignore` 排除。提交前请检查。

## 目录结构

```
PRNUweb/
├── frontend/          # Next.js 前端
├── backend/           # FastAPI 后端 + Celery Worker
├── prnu_core/         # PRNU 算法核心包
├── scripts/           # 数据集批量导入
├── docs/              # 设计文档
├── tests/             # 测试
├── docker-compose.yml          # 基础服务编排
├── docker-compose.prod.yml     # 生产环境覆写（Nginx + SSL）
├── nginx.conf.example          # Nginx 配置模板
├── .env.example                # 环境变量模板
├── .env.local.example          # 本地开发模板
└── .env.prod.example           # 生产部署模板
```

# PRNU 智能取证平台 Docker 部署指南

## 前置条件

### Windows 系统

#### 方案 1：Docker Desktop（推荐）
1. 下载 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. 安装时选择 WSL 2 backend（推荐）或 Hyper-V
3. 重启计算机
4. 验证安装：
   ```bash
   docker --version
   docker-compose --version
   ```

#### 方案 2：WSL 2 + Docker
如果已有 WSL 2，在 WSL 2 中安装 Docker：
```bash
# 在 WSL 2 terminal 中
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### Linux / macOS 系统

```bash
# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER

# macOS
brew install docker docker-compose
# 或使用 Docker Desktop for Mac
```

---

## 部署步骤

### 1️⃣ 准备项目目录

```bash
cd g:/PRNUweb
# 验证必要文件存在
ls -la docker-compose.yml backend/Dockerfile frontend/Dockerfile
```

### 2️⃣ 构建并启动容器

#### 方案 A：一键启动（推荐）
```bash
docker-compose up --build
```

这会：
- 构建后端镜像
- 构建前端镜像
- 启动 PostgreSQL、Redis、MinIO
- 启动 Backend API 服务
- 启动 Celery Worker
- 启动前端服务

#### 方案 B：后台运行
```bash
docker-compose up -d --build
```

查看日志：
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker
```

---

## 验证部署

### 1. 检查容器状态

```bash
docker-compose ps
```

输出示例：
```
NAME                COMMAND                  SERVICE      STATUS
prnu-backend-1      uvicorn app.main:app     backend      Up 2 minutes
prnu-frontend-1     npm run dev              frontend     Up 2 minutes
prnu-postgres-1     postgres                 postgres     Up 3 minutes
prnu-redis-1        redis-server             redis        Up 3 minutes
prnu-minio-1        minio server             minio        Up 3 minutes
prnu-worker-1       celery -A app.worker     worker       Up 2 minutes
```

### 2. 验证后端 API

打开浏览器或使用 curl：

```bash
# 健康检查
curl http://localhost:8000/health
# 输出：{"status":"ok"}

# 获取设备列表
curl http://localhost:8000/devices
# 输出：[]

# 获取指标
curl http://localhost:8000/metrics/summary
# 输出：{"image_count":0,"today_uploads":0,...}
```

### 3. 访问前端

打开浏览器访问：
```
http://localhost:3000
```

应该看到：
- 深蓝科技风主界面
- 4 个指标卡（顶部）
- 数据分布图和流程图（中部）
- 指纹库比对和外来图像比对上传面板（下部）
- 任务表和结果面板（底部）

### 4. 访问数据库和存储管理

- **PostgreSQL**：`postgresql://prnu:prnu@localhost:5432/prnu`
- **Redis**：`redis://localhost:6379/0`
- **MinIO 控制台**：`http://localhost:9001`
  - 用户名：`prnuadmin`
  - 密码：`prnupassword`

---

## 常见问题排查

### 问题 1：端口被占用

如果提示端口已占用（3000, 8000, 5432 等）：

```bash
# 查看占用的进程
netstat -ano | findstr :3000

# 方案 A：修改端口（在 docker-compose.yml 中）
# 将 "3000:3000" 改为 "3001:3000"

# 方案 B：关闭占用进程后重新启动
docker-compose down
docker-compose up --build
```

### 问题 2：容器启动失败

查看具体错误日志：

```bash
docker-compose logs backend
docker-compose logs worker
docker-compose logs frontend
```

常见错误：
- **"connection refused"**：数据库未就绪，等待 30 秒后重试
- **"Module not found"**：Python 依赖未安装，检查 `requirements.txt`
- **"listen tcp: bind: permission denied"**：端口权限，使用 `sudo` 或改端口

### 问题 3：数据库连接失败

```bash
# 检查 PostgreSQL 容器日志
docker-compose logs postgres

# 进入 PostgreSQL 容器手动检查
docker exec -it prnu-postgres-1 psql -U prnu -d prnu
```

### 问题 4：前端无法连接后端 API

检查 `frontend/Dockerfile` 中的 API 端点：
```dockerfile
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

或在 `docker-compose.yml` 中修改：
```yaml
environment:
  NEXT_PUBLIC_API_BASE_URL: http://your-server-ip:8000
```

---

## 管理容器

### 停止所有服务
```bash
docker-compose down
```

### 重启服务
```bash
docker-compose restart backend
docker-compose restart frontend
```

### 查看实时日志
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend --tail=100
```

### 进入容器交互
```bash
# 进入后端容器
docker exec -it prnu-backend-1 bash

# 进入前端容器
docker exec -it prnu-frontend-1 sh

# 进入数据库容器
docker exec -it prnu-postgres-1 psql -U prnu -d prnu
```

### 清理容器和数据

```bash
# 停止并删除所有容器
docker-compose down

# 同时删除持久化数据（谨慎！）
docker-compose down -v

# 删除未使用的镜像
docker image prune -a
```

---

## 生产部署建议

### 1. 使用环境变量文件

创建 `.env` 文件：
```env
# 数据库
DATABASE_URL=postgresql+psycopg://prnu:prnu@postgres:5432/prnu
POSTGRES_PASSWORD=your-secure-password

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ROOT_PASSWORD=your-secure-password
MINIO_SECURE=true  # 生产环境使用 HTTPS

# 前端 API
NEXT_PUBLIC_API_BASE_URL=https://your-domain.com

# FastAPI
PYTHONUNBUFFERED=1
LOG_LEVEL=info
```

在 `docker-compose.yml` 中引用：
```yaml
environment:
  - DATABASE_URL=${DATABASE_URL}
  - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
```

### 2. 使用 Nginx 反向代理

创建 `nginx.conf`：
```nginx
upstream backend {
  server backend:8000;
}

upstream frontend {
  server frontend:3000;
}

server {
  listen 80;
  server_name your-domain.com;

  location /api {
    proxy_pass http://backend;
    proxy_set_header Host $host;
  }

  location / {
    proxy_pass http://frontend;
    proxy_set_header Host $host;
  }
}
```

在 `docker-compose.yml` 中添加 Nginx 服务：
```yaml
nginx:
  image: nginx:latest
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
  depends_on:
    - backend
    - frontend
```

### 3. 添加卷挂载备份

```yaml
volumes:
  postgres-data:
    driver: local
  minio-data:
    driver: local
  # 自定义本地路径
  postgres-backup:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /path/to/backup
```

### 4. 配置健康检查

```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s

frontend:
  healthcheck:
    test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### 5. 日志管理

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 性能优化

### 1. 资源限制

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

### 2. 数据库优化

```sql
-- 进入 PostgreSQL 容器
docker exec -it prnu-postgres-1 psql -U prnu -d prnu

-- 创建索引
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_images_device_id ON images(device_id);
CREATE INDEX idx_comparison_results_job_id ON comparison_results(job_id);
```

### 3. Redis 持久化

在 `docker-compose.yml` 中：
```yaml
redis:
  command: redis-server --appendonly yes
  volumes:
    - redis-data:/data
```

---

## 监控和日志

### 使用 Docker Stats 实时监控

```bash
docker stats --no-stream
```

### 集中日志收集（可选）

安装 ELK Stack 或 Loki：
```bash
# Loki + Promtail 示例
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions
```

### 设置告警

```bash
# 检查失败的容器
docker ps --filter "status=exited"

# 查看容器事件
docker events --filter 'type=container'
```

---

## 常用命令速查

| 命令 | 功能 |
|------|------|
| `docker-compose up -d` | 后台启动所有服务 |
| `docker-compose down` | 停止并删除所有服务 |
| `docker-compose ps` | 查看容器状态 |
| `docker-compose logs -f` | 查看实时日志 |
| `docker-compose exec backend bash` | 进入后端容器 |
| `docker-compose restart backend` | 重启后端服务 |
| `docker-compose pull` | 更新基础镜像 |
| `docker-compose build --no-cache` | 强制重新构建镜像 |

---

## 备份和恢复

### 备份数据库

```bash
docker exec prnu-postgres-1 pg_dump -U prnu -d prnu > backup.sql
```

### 恢复数据库

```bash
docker exec -i prnu-postgres-1 psql -U prnu -d prnu < backup.sql
```

### 备份 MinIO 数据

```bash
docker exec prnu-minio-1 tar czf /tmp/minio-backup.tar.gz /data
docker cp prnu-minio-1:/tmp/minio-backup.tar.gz ./
```

---

## 升级和更新

### 更新镜像

```bash
# 拉取最新镜像
docker-compose pull

# 重建并重启
docker-compose up -d --build
```

### 数据库迁移

```bash
# 进入容器执行迁移脚本
docker-compose exec backend alembic upgrade head
```

---

## 故障恢复

### 一键重置（开发环境）

```bash
# 警告：这会删除所有数据！
docker-compose down -v
docker-compose up --build
```

### 查看容器详细信息

```bash
docker inspect prnu-backend-1
docker inspect prnu-postgres-1
```

### 网络诊断

```bash
# 查看容器网络
docker network ls
docker network inspect prnu-default

# 测试容器间连接
docker exec prnu-backend-1 ping postgres
```

---

## 总结

✅ **部署完成后，应该能访问：**
- 前端工作台：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- MinIO 控制台：http://localhost:9001

✅ **核心服务都在运行：**
- PostgreSQL（数据库）
- Redis（消息队列）
- MinIO（对象存储）
- FastAPI（后端服务）
- Celery Worker（异步任务）
- Next.js（前端）

有任何问题，查看日志：`docker-compose logs -f service-name`

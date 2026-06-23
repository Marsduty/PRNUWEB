#!/bin/bash
# =============================================
# PRNU 智能取证平台 - 阿里云一键部署脚本
# 使用方法：
#   1. 先 SSH 登录阿里云服务器
#   2. 将本项目上传到服务器（scp -r ./PRNUweb root@IP:/opt/prnu）
#   3. 在服务器上运行：bash scripts/deploy-aliyun.sh
# =============================================

set -e

echo "========================================"
echo "  PRNU 智能取证平台 - 阿里云部署脚本"
echo "========================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker 安装完成"
else
    echo "✅ Docker 已安装"
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，正在安装..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose 安装完成"
else
    echo "✅ Docker Compose 已安装"
fi

# 切换到项目目录
cd /opt/prnu || { echo "❌ 找不到 /opt/prnu 目录，请先上传项目"; exit 1; }

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在创建..."
    echo "请先输入你的服务器公网 IP 或域名："
    read -r SERVER_ADDR

    # 生成随机密码
    DB_PASS=$(openssl rand -base64 16)
    MINIO_PASS=$(openssl rand -base64 16)

    cat > .env << EOF
# 数据库密码
POSTGRES_PASSWORD=${DB_PASS}

# MinIO 密码
MINIO_ROOT_PASSWORD=${MINIO_PASS}

# 前端 API 地址
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_ADDR}:8000

# 后端 CORS 配置
CORS_ALLOW_ORIGINS=http://${SERVER_ADDR}:3000,http://${SERVER_ADDR}

# MinIO 安全模式
MINIO_SECURE=false

# 局域网 IP
LAN_HOST=${SERVER_ADDR}
EOF

    echo "✅ .env 文件已创建"
    echo "📝 数据库密码: ${DB_PASS}"
    echo "📝 MinIO 密码: ${MINIO_PASS}"
    echo "⚠️  请妥善保管以上密码！"
    echo ""
fi

# 检查并修改 nginx.conf 中的域名
if [ -f nginx.conf ]; then
    echo "🔧 检查 nginx.conf 配置..."
    if grep -q "your-domain.com" nginx.conf; then
        echo "⚠️  nginx.conf 中还有占位符域名，请手动编辑 nginx.conf"
        echo "   将 your-domain.com 替换为你的实际域名"
    fi
fi

echo ""
echo "========================================"
echo "  开始构建和启动服务..."
echo "========================================"

# 构建并启动所有服务
docker-compose up --build -d

echo ""
echo "========================================"
echo "  🚀 部署完成！"
echo "========================================"
echo ""
echo "📊 服务状态："
docker-compose ps

echo ""
echo "🌐 访问地址："
echo "  前端页面：      http://你的服务器IP:3000"
echo "  后端 API：      http://你的服务器IP:8000"
echo "  API 文档：      http://你的服务器IP:8000/docs"
echo "  MinIO 控制台：  http://你的服务器IP:9001"
echo ""
echo "📝  MinIO 登录信息："
echo "  用户名：prnuadmin"
echo "  密码：  查看 .env 文件中的 MINIO_ROOT_PASSWORD"
echo ""
echo "📋 查看日志命令："
echo "  docker-compose logs -f backend    # 后端日志"
echo "  docker-compose logs -f frontend   # 前端日志"
echo "  docker-compose logs -f worker     # 工作进程日志"
echo ""

# 输出密码提示
if [ -f .env ]; then
    echo "⚠️  重要：请检查 .env 文件中的密码是否已修改！"
    echo "   建议使用强密码并定期更换。"
fi

echo ""
echo "💡 后续步骤："
echo "  1. 配置域名解析（将域名解析到服务器 IP）"
echo "  2. 申请 SSL 证书（使用 certbot）"
echo "  3. 使用 Nginx 反向代理（参考 nginx.conf）"
echo "  4. 日常维护见 DOCKER_DEPLOYMENT.md"

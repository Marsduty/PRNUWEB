#!/bin/bash
# =============================================
# PRNU 智能取证平台 - 阿里云一键部署脚本
# 使用方法：
#   1. 先 SSH 登录阿里云服务器
#   2. 将本项目上传到服务器或从 GitHub clone 到 /opt/prnu
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

# 检查 Docker Compose v2
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose v2 未安装，请先安装 Docker Compose 插件后重试"
    exit 1
else
    echo "✅ Docker Compose v2 已安装"
fi

# 切换到项目目录
cd /opt/prnu || { echo "❌ 找不到 /opt/prnu 目录，请先上传项目"; exit 1; }

# 检查生产环境变量文件
if [ ! -f .env.prod ]; then
    echo "⚠️  未找到 .env.prod 文件，正在创建..."
    echo "请先输入你的服务器公网 IP："
    read -r SERVER_IP
    echo "请输入你的域名（没有域名可直接回车，默认使用服务器 IP）："
    read -r SERVER_DOMAIN
    if [ -z "$SERVER_DOMAIN" ]; then
        SERVER_DOMAIN="$SERVER_IP"
    fi

    # 生成随机密码
    DB_PASS=$(openssl rand -base64 16)
    MINIO_PASS=$(openssl rand -base64 16)

    cat > .env.prod << EOF
# 数据库密码
POSTGRES_PASSWORD=${DB_PASS}

# MinIO 密码
MINIO_ROOT_PASSWORD=${MINIO_PASS}

# 生产环境由 Nginx 统一入口代理 API
NEXT_PUBLIC_API_BASE_URL=/api

# 后端 CORS 配置
CORS_ALLOW_ORIGINS=http://${SERVER_DOMAIN},https://${SERVER_DOMAIN},http://${SERVER_IP},https://${SERVER_IP}

# MinIO 安全模式
MINIO_SECURE=false
EOF

    echo "✅ .env.prod 文件已创建"
    echo "📝 数据库密码: ${DB_PASS}"
    echo "📝 MinIO 密码: ${MINIO_PASS}"
    echo "⚠️  请妥善保管以上密码！"
    echo ""
fi

# 检查并生成服务器私有 nginx.conf
if [ ! -f nginx.conf ]; then
    if [ ! -f nginx.conf.example ]; then
        echo "❌ 找不到 nginx.conf.example，请检查项目文件是否完整"
        exit 1
    fi

    echo "⚠️  未找到 nginx.conf，正在从 nginx.conf.example 创建..."
    if [ -z "$SERVER_IP" ]; then
        echo "请先输入你的服务器公网 IP："
        read -r SERVER_IP
    fi
    if [ -z "$SERVER_DOMAIN" ]; then
        echo "请输入你的域名（没有域名可直接回车，默认使用服务器 IP）："
        read -r SERVER_DOMAIN
        if [ -z "$SERVER_DOMAIN" ]; then
            SERVER_DOMAIN="$SERVER_IP"
        fi
    fi

    cp nginx.conf.example nginx.conf
    sed -i "s/your-domain.com/${SERVER_DOMAIN}/g" nginx.conf
    sed -i "s/your-server-ip/${SERVER_IP}/g" nginx.conf
    echo "✅ nginx.conf 已创建"
else
    echo "✅ nginx.conf 已存在，保持当前服务器私有配置"
fi

echo ""
echo "========================================"
echo "  开始构建和启动服务..."
echo "========================================"

# 构建并启动所有服务
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d

echo ""
echo "========================================"
echo "  🚀 部署完成！"
echo "========================================"
echo ""
echo "📊 服务状态："
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml ps

echo ""
echo "🌐 访问地址："
echo "  前端页面：      http://你的服务器IP 或域名"
echo "  后端 API：      http://你的服务器IP 或域名/api"
echo "  API 文档：      http://你的服务器IP 或域名/docs"
echo "  MinIO 控制台：  生产环境默认不暴露公网端口"
echo ""
echo "📝  MinIO 登录信息："
echo "  用户名：prnuadmin"
echo "  密码：  查看 .env.prod 文件中的 MINIO_ROOT_PASSWORD"
echo ""
echo "📋 查看日志命令："
echo "  docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml logs -f backend"
echo "  docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml logs -f frontend"
echo "  docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml logs -f worker"
echo ""

# 输出密码提示
if [ -f .env.prod ]; then
    echo "⚠️  重要：请检查 .env.prod 文件中的密码是否已修改！"
    echo "   建议使用强密码并定期更换。"
fi

echo ""
echo "💡 后续步骤："
echo "  1. 配置域名解析（将域名解析到服务器 IP）"
echo "  2. 申请 SSL 证书（使用 certbot）"
echo "  3. 使用 Nginx 反向代理（参考 nginx.conf）"
echo "  4. 日常维护见 DOCKER_DEPLOYMENT.md"

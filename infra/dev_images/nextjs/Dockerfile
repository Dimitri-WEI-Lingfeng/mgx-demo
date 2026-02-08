# Next.js 开发环境镜像
# 基于 Node.js 22
FROM node:22-slim

# 设置工作目录
WORKDIR /workspace

# 配置淘宝 npm 镜像源
RUN npm config set registry https://registry.npmmirror.com

# 安装常用开发工具和 SSH 服务
RUN apt-get update && apt-get install -y \
    git \
    curl \
    vim \
    wget \
    openssh-server \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 配置 SSH 服务
RUN mkdir /var/run/sshd && \
    # 允许 root 登录（可选，根据安全需求调整）
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    # 允许密码认证
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    # 禁用 PAM
    sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config && \
    # SSH 登录时不更新 motd
    sed -i 's/#PrintMotd yes/PrintMotd no/' /etc/ssh/sshd_config

# 创建开发用户
RUN useradd -m -s /bin/bash -G sudo developer && \
    # 设置默认密码（生产环境应该通过环境变量或密钥认证）
    echo 'developer:developer' | chpasswd && \
    echo 'root:root' | chpasswd && \
    # 允许 developer 用户无密码使用 sudo
    echo 'developer ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers


# 为 developer 用户配置 npm 镜像源
RUN su - developer -c "npm config set registry https://registry.npmmirror.com"

# 设置环境变量
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1

# 暴露端口
EXPOSE 3000 22

# 创建启动脚本
RUN echo '#!/bin/bash\n\
# 启动 SSH 服务\n\
service ssh start\n\
\n\
# 保持容器运行\n\
tail -f /dev/null\n\
' > /start.sh && chmod +x /start.sh

# 启动服务
CMD ["/start.sh"]

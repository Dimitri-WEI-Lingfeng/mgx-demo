# Next.js 开发环境镜像

## 镜像说明

这是一个用于 Next.js 应用开发的 Docker 镜像，包含：

- Node.js 22 (LTS)
- npm (配置淘宝镜像源)
- pnpm (配置淘宝镜像源)
- yarn (配置淘宝镜像源)
- SSH 服务器（支持远程开发）
- git, curl, vim, wget 等常用工具
- sudo 支持

## 构建镜像

```bash
cd infra/dev_images/nextjs
docker build -t mgx-dev-nextjs:latest .
```

## 使用方式

### 方式 1: 使用 docker-compose（推荐）

```bash
# 复制示例配置
cp docker-compose.example.yml docker-compose.yml

# 修改 docker-compose.yml 中的配置（如果需要）
# 然后启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 方式 2: 直接使用 docker run

```bash
docker run -d \
  --name my-nextjs-dev \
  -v /path/to/workspace:/workspace \
  -p 3000:3000 \
  -p 2222:22 \
  mgx-dev-nextjs:latest
```

### 2. 通过 SSH 连接到容器

```bash
# 使用 developer 用户登录（推荐）
ssh -p 2222 developer@localhost
# 默认密码: developer

# 或使用 root 用户登录
ssh -p 2222 root@localhost
# 默认密码: root
```

**安全提示**: 生产环境请修改默认密码或使用 SSH 密钥认证。

### 3. 或直接进入容器 Shell

```bash
docker exec -it my-nextjs-dev bash
```

### 4. 在容器内运行 Next.js 项目

```bash
# 安装依赖
npm install
# 或使用 pnpm
pnpm install

# 启动开发服务器
npm run dev
# 或
pnpm dev
```

## 端口说明

- **3000**: Next.js 开发服务器默认端口
- **22**: SSH 服务端口（建议映射到宿主机的非标准端口，如 2222）

## 用户账户

镜像包含两个预配置用户：

| 用户 | 密码 | 权限 | 说明 |
|------|------|------|------|
| developer | developer | sudo (无密码) | 推荐用于日常开发 |
| root | root | 完全权限 | 系统管理 |

**重要**: 生产环境请修改默认密码！

### 修改密码

进入容器后执行：

```bash
# 修改当前用户密码
passwd

# 修改其他用户密码（需要 sudo）
sudo passwd developer
sudo passwd root
```

### 使用 SSH 密钥认证（推荐）

```bash
# 在宿主机生成密钥（如果还没有）
ssh-keygen -t rsa -b 4096

# 将公钥复制到容器
ssh-copy-id -p 2222 developer@localhost

# 或手动复制
docker exec my-nextjs-dev mkdir -p /home/developer/.ssh
cat ~/.ssh/id_rsa.pub | docker exec -i my-nextjs-dev tee -a /home/developer/.ssh/authorized_keys
docker exec my-nextjs-dev chown -R developer:developer /home/developer/.ssh
docker exec my-nextjs-dev chmod 700 /home/developer/.ssh
docker exec my-nextjs-dev chmod 600 /home/developer/.ssh/authorized_keys
```

## 环境变量

- `NODE_ENV=development`: 开发模式
- `NEXT_TELEMETRY_DISABLED=1`: 禁用 Next.js 遥测

## NPM 镜像源

镜像已配置淘宝 npm 镜像源 (https://registry.npmmirror.com)，加速国内依赖下载。

如需恢复官方源：

```bash
npm config set registry https://registry.npmjs.org/
```

## VSCode Remote SSH 开发

可以使用 VSCode 的 Remote-SSH 扩展连接到容器进行开发：

1. 安装 VSCode 扩展: **Remote - SSH**
2. 配置 SSH 连接 (~/.ssh/config):

```
Host mgx-nextjs-dev
    HostName localhost
    Port 2222
    User developer
    # 可选：指定密钥文件
    # IdentityFile ~/.ssh/id_rsa
```

3. 在 VSCode 中按 `F1`，选择 "Remote-SSH: Connect to Host"，选择 `mgx-nextjs-dev`

## 安全建议

1. **修改默认密码**: 首次使用后立即修改所有用户密码
2. **使用密钥认证**: 禁用密码登录，仅使用 SSH 密钥
3. **限制 SSH 访问**: 只在必要时暴露 SSH 端口
4. **网络隔离**: 在生产环境中使用 Docker 网络隔离
5. **定期更新**: 定期重建镜像以获取安全补丁

### 禁用密码认证（使用密钥后）

```bash
docker exec my-nextjs-dev sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
docker exec my-nextjs-dev service ssh restart
```

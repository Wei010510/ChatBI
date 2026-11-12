# ChatBI 云端自动部署计划

## Context

用户希望新购云服务器后尽量不动手，由代理完成首次部署，并通过 GitHub Actions 持续自动发布。生产复用现有 Supabase、LLM 与 Embedding 配置，服务器只运行 FastAPI 与前端 Nginx 两个容器，不引入 K8s。

截图中的改动目前并未全部落盘：实际只有 `backend/docker-compose.yml` 和 `backend/Dockerfile`，根目录没有 `.gitignore`、`.dockerignore`、`.env.production` 或 GitHub Actions 工作流，且当前目录不是 Git 仓库。现有 Compose 的 web 没有前端构建产物，Docker 构建可能带入真实 `.env`，生产配置也缺少真实模型开关，不能直接上线。

## 截图改动取舍

- `.gitignore`：必须新增，阻止真实环境文件、依赖、缓存和构建产物进入 Git。
- 根目录 `.dockerignore`：必须新增；当前 Docker build context 是根目录，它能阻止 `.env` 等文件进入镜像。
- `backend/.dockerignore`：不新增；当前构建不会使用它，重复文件没有实际作用。
- `.env.production`：真实文件只放服务器；仓库新增不含密钥的 `backend/.env.production.example`。
- Compose：保留本地配置，不通过注释 db 改造；新增独立生产 Compose，仅含 api/web。
- `deploy.yml`：因用户选择 GitHub Actions 而保留，正确路径为 `.github/workflows/deploy.yml`。

## 用户只需提供的资源

1. 新购云服务器：建议 2 核 4G、Ubuntu 24.04、40GB 系统盘、公网 IP，地域尽量靠近现有 Supabase；安全组开放 22、80，443 可预留，不对公网开放 8000/5432。
2. 购买后提供公网 IP 和可用的 sudo SSH 登录方式。密码仅用于首次接入时，后续改用专用部署密钥。
3. GitHub 账号完成一次授权；已有私有仓库则提供地址，没有则由代理创建。当前机器有 Git/SSH，无 `gh`，GitHub SSH 尚未配置，这些均由代理处理。
4. 无需重新提供 Supabase、LLM、Embedding 密钥；复用本机现有 `backend/.env`，全程不打印、不提交。

## 实施步骤

### 1. 先完成本轮 Spec

新建 `.trae/specs/cloud_deploy/spec.md`、`tasks.md`、`checklist.md`，范围只包含云端 Docker Compose 与 GitHub Actions 部署。现有 PRD/SDD 已定义 F8 和生产 Supabase，不改业务功能文档。Spec 经用户确认后再修改部署代码。

### 2. 修正部署文件

- 根目录 `.gitignore`：忽略各级 `.env`、`.env.*`，保留 `*.env.example` / `.env.production.example` 等模板，并忽略依赖、缓存、日志与构建产物。
- 根目录 `.dockerignore`：排除 `.git`、真实环境文件、`node_modules`、`dist`、Python 缓存和本地测试产物；保留后端、算法、前端源码及语义资源。
- `backend/Dockerfile`：先复制 backend/algorithm 源码，再安装两个本地项目依赖，避免在源码缺失时执行 editable install。
- 新增 `frontend/Dockerfile`：使用 lockfile 执行 `npm ci` 和 `npm run build`，再用 Nginx 托管 `dist`。
- `backend/nginx.conf`：保留 SPA 路由与 `/api` 反向代理，将代理读取超时调整到 300 秒，匹配现有问数请求上限。
- 新增 `backend/docker-compose.production.yml`：仅 api/web；api 不暴露公网端口，web 暴露 80；显式设置 `USE_MOCK_LLM=false`，关键连接配置缺失时启动前报错；配置健康检查与 `unless-stopped`。
- 新增 `backend/.env.production.example`：只放变量名、占位符和必要说明；服务器真实配置沿用当前工作值，包括现有 `EMBED_DIM`，不回退到示例默认值。

### 3. 初始化服务器

- 通过 SSH 安装 Docker Engine、Compose 插件与 rsync，创建 `/opt/chatbi` 和专用部署账号/密钥。
- 将本机现有数据库与模型配置安全写入服务器 `backend/.env.production`，权限设为 600，并确保真实模型模式开启。
- 配置 SSH known-host 校验；GitHub 只保存 `SSH_HOST`、`SSH_USER`、`SSH_PRIVATE_KEY`、主机公钥等部署信息，不保存数据库或模型密钥。

### 4. 配置 GitHub 自动发布

- 初始化 Git，创建私有仓库，先配置 Actions Secrets 再首次推送，避免工作流立即失败。
- 新增 `.github/workflows/deploy.yml`：`main` 推送或手动触发；通过 SSH/rsync 同步源码，明确排除所有真实 env，且不使用 `--delete-excluded`。
- 远端执行生产 Compose 构建与启动，轮询 `/api/health`；健康检查失败则工作流失败并输出不含密钥的容器状态与日志。
- 使用并发锁避免两个部署同时写入同一目录；首版不引入镜像仓库、K8s 或复杂回滚体系。

## 验证

1. 本地运行前端生产构建、相关 Python 测试和工作流/YAML 静态检查；本机没有 Docker 时不伪造本地镜像验收。
2. 在服务器实际构建 api/web 镜像，确认镜像内不存在 `.env`、`.env.production` 或其他真实密钥文件。
3. 确认服务器只有 api/web 两个应用容器，8000/5432 未对公网开放，`/api/health` 通过。
4. 浏览器通过公网 IP 打开页面，完成一次真实问数，验证 Supabase、真实 LLM、表/图/解读和超过 60 秒请求不触发 Nginx 504。
5. 手动重跑一次 GitHub Actions，验证重复部署幂等且不会覆盖服务器真实 env。
6. 交付公网地址、仓库地址、Actions 运行结果和验收结果；域名/HTTPS 作为可选后续，不阻塞首版上线。

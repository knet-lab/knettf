# 仓库结构

本文说明 knettf 仓库里每个目录是什么、谁在用、哪些东西**不在**仓库里。
新人先读本文，再读 [ONBOARDING.md](ONBOARDING.md)。

## 1. 顶层目录（会进 git 的）

| 目录 | 作用 | 主要使用者 |
|---|---|---|
| `apps/backend/` | 线上后端（Django）：采集、检测、数据库、API | 线上服务 `netsentinel.service` |
| `apps/frontend/` | 网站前端（Vue） | 线上服务 |
| `scripts/` | 数据脚本，入口 `scripts/manage.py`（同步、快照、还原、导出） | 开发机，定时任务 |
| `lab/` | 实验环境：K8s 集群脚本、流量转发（shipper）、仿真流量、注入壳子 | 实验集群 |
| `model-kit/` | 模型接入规范、模板、样本数据（给模型方用） | 模型方 |
| `ops/` | 部署脚本、systemd 单元模板、CI 检查脚本 | 部署、CI |
| `docs/` | 文档：交接、数据规范、新人手册、本文；`archive/` 是旧文档 | 所有人 |
| `.github/` | CI 工作流 | GitHub |
| `README.md` | 项目总入口 | 所有人 |
| `pyproject.toml`、`uv.lock`、`.python-version` | 根目录的 Python 依赖（后端和脚本） | 开发、CI |

## 2. 仓库根目录下**不应该有**的东西（已移出）

以下内容已于 2026-11-20 移到 `~/knettf-local/`，不在仓库里：

| 原位置 | 现位置 | 说明 |
|---|---|---|
| `experiments/` | `~/knettf-local/artifacts/experiments/` | 模型训练和对比脚本、数据、模型文件 |
| `claude-analysis/` | `~/knettf-local/artifacts/claude-analysis/` | 数据集压缩包、训练好的模型 |
| `lab/collect`、`lab/dataset`、`lab/replay`、`lab/simulation` | `~/knettf-local/removed/lab/` | 旧实验脚本，`lab/README.md` 写着已删除 |
| `.env` | `~/knettf-local/secrets/root.env` | 含 `VIGIL_BRIDGE_TOKEN`，权限 600，没有代码读取它 |
| `.cloudflared/` | `~/knettf-local/secrets/.cloudflared/` | 隧道脚本和 pid 文件（另一个项目的隧道用） |
| `chat.md`、`Linux Host Info.md`、`terraform/` | `~/knettf-local/notes/` | 个人笔记、主机信息、旧的 Terraform 目录 |

> 注意：`apps/backend/terraform/` 是后端 autotf 使用的目录，不是这个 `terraform/`，两者不同。

## 3. 本地但仍在仓库目录里的东西（已被 `.gitignore` 排除）

| 路径 | 用途 | 说明 |
|---|---|---|
| `.venv/` | 根目录的 Python 环境（后端、脚本） | 不进 git |
| `lab/.venv/` | 仿真客户端的 Python 环境 | **被 10 个运行中的 locust 服务直接调用，不能删或移** |
| `apps/backend/backend/.env` | 后端的开发配置 | 不进 git，不要提交 |
| `apps/frontend/.env`、`lab/.env` | 前端和实验配置 | 不进 git |
| `.ruff_cache/`、`__pycache__/` | 缓存 | 可随时删除 |
| `.vscode/` | 编辑器设置（已加入 `apps/backend` 的分析路径） | 不进 git |

## 4. 数据和运行时位置（都不在仓库里）

| 内容 | 位置 | 说明 |
|---|---|---|
| 数据目录 | `~/knettf-data/` | `snapshots/`、`increments/`、`exports/`、`restored/`，权限 700 |
| 只读角色凭据 | `~/.config/knettf/reader.env` | 权限 600，定时任务读取 |
| 线上部署 | `/srv/netsentinel/prod/` | 从 `main` 自动部署，**不在这里改代码** |
| 线上日志 | `/srv/netsentinel/logs/auto-deploy.log` | 自动部署日志 |
| 定时任务 | `~/.config/systemd/user/knettf-snapshot.{service,timer}` | 每小时 `scripts/manage.py collect sync` |
| 仿真客户端 | `knettf-client-01..10.service`（系统级） | 使用 `lab/.venv` 和 `lab/traffic/boutique_locust.py` |

## 5. 分支和流程

- 开发只在 `dev/soar009` 上进行，不新建分支。
- 合并到 `main` 会触发线上自动部署。
- 数据和密钥不进仓库：数据放 `~/knettf-data`，密钥放 `~/.config/knettf/` 或 `~/knettf-local/secrets/`。

## 6. 还没有做的整理

以下两项是有意推迟的，原因如下：

- **合并 Python 环境**：`lab/` 有自己的 `pyproject.toml`、`uv.lock`、`requirements.txt` 和 `.venv`。这个 `.venv` 被运行中的仿真客户端使用，修改路径需要先停服务、重装依赖、再启动。等实验环境停止运行时再做。
- **`lab/.python-version` 与根目录重复**：内容相同，无害，合并环境时一起处理。

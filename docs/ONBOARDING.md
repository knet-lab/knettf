# 新人接手手册

> 读者：接手 knettf / NetSentinel 的新同事。
> 目标：读完本文后，你能说清楚数据从哪里来、到哪里去、每一步由什么脚本完成，并能独立排查常见问题。
> 本文描述的是 2026-11-20 的状态。如果与代码不一致，以代码为准，并更新本文。

配套文档：
- [LAYOUT.md](LAYOUT.md)：仓库目录结构，哪些东西不在仓库里。
- [HANDOVER.md](HANDOVER.md)：迁移到新环境时要改哪些值。
- [../model-kit/README.md](../model-kit/README.md)：模型接入规范，35 个特征的定义。
- [data-spec-v1.md](data-spec-v1.md)：流的切分规则。
- [../lab/README.md](../lab/README.md)：实验集群和仿真流量。

---

## 0. 一分钟概述

- 实验集群（5 台 VM，K8s）的流量经 eBPF（Cilium/Hubble）抓取，进入线上平台后端，切成双向流，算出 35 个特征。
- 线上后端现在处于**采集模式**：流量写入线上库的 `vigil_collectrecord`，不跑检测模型。
- **自动同步**：每小时一个定时任务，用只读账号从线上拉取新增记录，压缩归档，写入开发库 `pg-dev`。开发库为空时，第一次运行会自动全量拉取。你不需要手动做任何同步。
- **导出**：需要数据时，用 `scripts/manage.py collect export` 从开发库导出 CSV。
- **注入**：异常流量注入还没有实现，目前只有壳子。

---

## 1. 架构

```
┌──────── 实验环境 ────────┐
│ K8s 集群（5 台 VM）        │
│ 正常流量：Boutique + 仿真客户端（netns）│
│ 异常流量：未实现（壳子）    │
└────────────┬─────────────┘
             │ Cilium/Hubble → flow-shipper → Kafka
┌────────────▼──────────────────────────────────────────┐
│ 线上后端 netsentinel.service（8080，Cloudflare 对外）      │
│   Bridge → vigil/ingest（切流、35 特征、不打标签）           │
│   采集模式 → 写入 线上库 vigil_collectrecord               │
└────────────┬──────────────────────────────────────────┘
             │ 只读（账号 knettf_reader，TCP+密码，运行时验证）
┌────────────▼──────────────────────────────────────────┐
│ 定时任务 knettf-snapshot.timer（每小时）                   │
│   manage.py collect sync：增量拉取 → 压缩归档 → 写入开发库     │
└────────────┬──────────────────────────────────────────┘
             │ 写入（账号 knettf_dev，只能写开发库）
┌────────────▼──────────────────────────────────────────┐
│ 开发数据库 pg-dev（容器，127.0.0.1:5433，库 vigil_dev）    │
│ 数据目录 ~/knettf-data（快照、归档、导出结果，权限 700）       │
└───────────────────────────────────────────────────────┘
```

线上数据库容器是 `pg`（端口 5432，库 `vigil`）。开发数据库是独立的容器 `pg-dev`（端口 5433，库 `vigil_dev`）。两者是**两个实例**，开发脚本没有任何写线上库的凭据。

| 组件 | 位置 | 说明 |
|---|---|---|
| 开发仓库 | `~/github/knettf`，分支 `dev/soar009` | 代码、脚本、文档 |
| 线上部署目录 | `/srv/netsentinel/prod` | 从 `main` 自动部署，不要在这里改代码 |
| 线上后端 | `netsentinel.service`（8080） | 采集模式 |
| 线上数据库 | 容器 `pg`，5432，库 `vigil` | 线上读写；脚本只读 |
| 开发数据库 | 容器 `pg-dev`，127.0.0.1:5433，库 `vigil_dev` | 脚本唯一写入目标 |
| 定时任务 | `knettf-snapshot.timer` / `.service`（用户级 systemd） | 每小时增量同步 |
| 凭据 | `~/.config/knettf/`（权限 600，不在仓库里） | `reader.env`、`dev.env`、`pgdev-admin.env` |
| 数据目录 | `~/knettf-data/` | `snapshots/`、`increments/`、`exports/`、`restored/` |

查看状态：

```bash
systemctl --user list-timers knettf-snapshot.timer --no-pager
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^pg'
```

---

## 2. 数据流

```
线上 vigil_collectrecord
  → sync（定时，只读）：id > 开发库最大 id − 5000 的记录
      → 压缩归档 increments/collect-<起>-<止>.csv.gz
      → 开发库 pg-dev：删除 id > 起点 后导入（同一事务）
  → export（手动）：开发库 → exports/NN/<时段>.csv + .txt
  → restore（手动）：increments/*.csv.gz → restored/*.csv（--merge 去重）
```

### 2.1 增量同步（自动，每小时）
`scripts/collect/sync.py`
1. 验证线上账号只读（不能有 INSERT/UPDATE/DELETE/TRUNCATE 权限，不能是超级用户，库名必须正确）。
2. 验证开发库库名是 `vigil_dev`。
3. 读取开发库最大 `id` 记为 `DST_MAX`，起点取 `DST_MAX − 5000`（重叠，覆盖事务延迟提交的记录）。
4. 线上只读：`COPY (... WHERE id > 起点) TO STDOUT`。
5. 压缩归档，然后在开发库同一事务中删除 `id > 起点` 并导入。
6. 核对开发库最大 `id` ≥ 本批终点。
7. 归档目录超过 `KNETTF_MAX_GB`（默认 20GB）时删除最旧的。

**首次运行**：开发库为空，`DST_MAX = 0`，所以第一次会自动全量拉取。2026-11-20 首次运行拉取了 46669 条。

### 2.2 整库覆盖（手动，慎用）
`scripts/collect/reseed.py`：线上全量读取（只读）→ 保存到 `snapshots/` → 清空开发库采集表并重新导入 → 核对行数。
会覆盖开发库的采集表，但不影响线上。正常情况下不需要用，同步已经是自动的。

### 2.3 导出（手动）
`scripts/collect/export.py`
- Django 连接的是开发库（`VIGIL_DB_*` 环境变量），必须是 `127.0.0.1:5433/vigil_dev`，否则拒绝运行。
- 输出：`~/knettf-data/exports/NN/{时间1}-{时间2}.csv` 和 `.txt`。
- 标签只用 `--label` 显式指定，**不沿用**采集时写入的标签（历史数据里有误标）。
- 导出只需要开发库凭据，不需要线上凭据。

### 2.4 还原（手动）
`scripts/collect/restore.py`：把增量归档还原为 CSV，`--merge` 时按第一列 `id` 去重。只处理增量归档，不处理整库覆盖快照。

### 2.5 注入（未实现）
`lab/traffic/inject_attack.sh`：攻击类型是占位（`syn_flood`、`port_scan`、`http_flood`）。默认演练模式，不发流量。真正执行需要 `ENABLE=1 DRY_RUN=0` 和 `TARGET`。执行后追加一行到 `lab/traffic/inject_log.csv`。以后导出时，标签应按这份日志的时间窗口决定。

---

## 3. 数据库

| 实例 | 库 | 用户 | 权限 | 用途 |
|---|---|---|---|---|
| 容器 `pg`（5432） | `vigil` | `vigil` | 读写 | 线上后端 |
| 容器 `pg`（5432） | `vigil` | `knettf_reader` | 只读（仅采集表 SELECT） | 同步、查询 |
| 容器 `pg-dev`（5433） | `vigil_dev` | `knettf_dev` | 读写（库的所有者） | 脚本写入、导出 |
| 容器 `pg-dev`（5433） | `vigil_dev` | `postgres` | 超级用户 | 仅用于建库建用户，凭据在 `pgdev-admin.env` |

- `vigil_collectrecord`：流的五元组、`flow_input`（JSON，35 个特征）、`label`（采集时为空）、`created_at`。
- `vigil_detectionrecord`：按天分区，DDL 由手写 SQL 管理，见 `apps/backend/vigil/migrations/0001_initial.py`。
- 迁移：`vigil` 库的迁移不会被部署自动执行，需要手动执行。开发库 `pg-dev` 的迁移已经执行过。

---

## 4. 配置

### 4.1 线上后端（`apps/backend/backend/settings.py`，线上 `.env`）
| 变量 | 默认值 | 说明 |
|---|---|---|
| `VIGIL_MODELS` | `lof_baseline` | 检测模式下启用的模型 |
| `VIGIL_COLLECT_ONLY` | `False` | `True` 时只采集，不跑模型（线上当前为采集模式） |
| `VIGIL_KAFKA_GROUP_ID` | `vigil-bridge` | 开发环境必须设为 `vigil-bridge-dev` |

### 4.2 脚本（环境变量，由 `~/.config/knettf/` 提供）
| 变量 | 说明 |
|---|---|
| `KNETTF_SRC_HOST` / `_PORT` / `_DB` / `_USER` / `_PASSWORD` | 线上只读来源，默认 `127.0.0.1:5432 vigil knettf_reader`。密码在 `reader.env` |
| `KNETTF_DST_HOST` / `_PORT` / `_DB` / `_USER` / `_PASSWORD` | 开发库写入目标，默认 `127.0.0.1:5433 vigil_dev knettf_dev`。密码在 `dev.env` |
| `KNETTF_DATA_DIR` | 数据目录，默认 `~/knettf-data`，不能在仓库内或 `/srv/netsentinel` 下 |
| `KNETTF_MAX_GB` | 归档目录容量上限，默认 20 |
| `KNETTF_OVERLAP` | 增量同步的重叠条数，默认 5000 |

凭据文件（权限 600，都不在仓库里）：
- `~/.config/knettf/reader.env`：线上只读账号（`KNETTF_SRC_USER`、`KNETTF_SRC_PASSWORD`）。
- `~/.config/knettf/dev.env`：开发库账号（`KNETTF_DST_*`），也包含导出时 Django 用的 `VIGIL_DB_*`。
- `~/.config/knettf/pgdev-admin.env`：`pg-dev` 容器的超级用户密码，只用于容器本身。

定时任务的服务单元读取 `dev.env` 和 `reader.env`。

---

## 5. 日常操作

> 运行脚本一律用仓库的 `.venv`：`.venv/bin/python scripts/manage.py ...`。

### 5.1 检查状态（每次接手先做）
```bash
set -a && . ~/.config/knettf/dev.env && . ~/.config/knettf/reader.env && set +a
cd ~/github/knettf && .venv/bin/python scripts/manage.py check
```
期望输出：`线上连接 ... 可写=否 ... ✓ 只读`，`开发连接 库=vigil_dev → ✓`，退出码 0。

定时任务状态：
```bash
systemctl --user list-timers knettf-snapshot.timer --no-pager
systemctl --user show knettf-snapshot.service -p Result --no-pager
journalctl --user -u knettf-snapshot.service -n 30 --no-pager
```

### 5.2 手动触发一次同步（一般不需要）
```bash
systemctl --user start knettf-snapshot.service
```
这会使用定时任务的真实配置运行一次。

### 5.3 导出 CSV
```bash
set -a && . ~/.config/knettf/dev.env && set +a
cd ~/github/knettf && .venv/bin/python scripts/manage.py collect export \
  --since "2026-11-20 00:00" --until "2026-11-20 06:00" [--label 0|1] [--kind ns|ew|all]
```
输出在 `~/knettf-data/exports/NN/`。

### 5.4 还原归档
```bash
.venv/bin/python scripts/manage.py collect restore --merge
```
输出在 `~/knettf-data/restored/`。

### 5.5 切换采集/检测模式（需要线上权限）
开启采集（停止检测）：
1. 确认迁移：`manage.py showmigrations vigil --database=vigil` 显示 `[X] 0003_collectrecord`。
2. 线上 `.env` 设置 `VIGIL_COLLECT_ONLY=true`（先备份）。
3. `sudo systemctl restart netsentinel.service`，然后确认 `vigil_collectrecord` 在增长。

恢复检测：设为 `false` 或删除该行，重启。

> 以上需要线上权限。不要自行在线上执行迁移或修改 `.env`，先与负责人确认。

### 5.6 发布代码
1. 在 `dev/soar009` 上修改，运行 `ops/scripts/check.sh backend`。
2. 推送到 `origin/dev/soar009`，在 GitHub 上开 PR 到 `main`。
3. CI 通过后合并。合并会触发线上自动部署，日志在 `/srv/netsentinel/logs/auto-deploy.log`。
4. 合并后检查：`systemctl is-active netsentinel.service` 为 `active`，`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/` 返回 200。

---

## 6. 代码地图

```
apps/backend/
  backend/settings.py            配置（VIGIL_* 变量）
  backend/db_router.py           路由：kcore → default，vigil → vigil
  vigil/ingest/                  切流、特征、Kafka Bridge
  vigil/services.py              采集/检测写库入口（collect_batch、detect_batch）
  vigil/models.py                DetectionRecord、CollectRecord
  vigil/detection/               检测模型（模型方提供）
  vigil/response/cilium.py       Cilium 处置（apply_action 为 stub）
  vigil/migrations/              vigil 库迁移（0003 为采集表）
  vigil/tests/                   测试

scripts/                         数据脚本（不含数据）
  manage.py                      唯一入口
  knettf_common.py               配置、连接（psycopg2 TCP）、安全检查
  collect/sync.py                增量同步（定时任务执行）
  collect/reseed.py              整库覆盖（手动）
  collect/restore.py             归档还原
  collect/export.py              导出 CSV
  sql/readonly_role.sql          只读角色（已执行；保留作为记录）

lab/traffic/                     实验流量：boutique_locust.py、client-zone.sh、inject_attack.sh（壳子）
model-kit/                       模型接入说明与样本
docs/                            交接、数据规范、本文、LAYOUT
```

---

## 7. 安全规则

1. **线上只读**：同步前验证账号没有写权限、不是超级用户。不满足就拒绝运行，不要绕过。
2. **写入只到 `pg-dev` 的 `vigil_dev`**：脚本写入前验证库名。开发侧没有线上库的写凭据。
3. **数据不进仓库**：快照、归档、导出结果都在 `~/knettf-data`。仓库里出现 CSV、`.gz` 是误操作。
4. **凭据不进仓库、文档、聊天、开发库**：全部放在 `~/.config/knettf/`，权限 600。密码丢了就重设，不要存进数据库。
5. **不在开发环境执行会修改线上的命令**：包括线上迁移、线上 `.env`、重启线上服务。
6. **开发机和线上在同一台机器**：采集期间避免训练、编译、大型测试，以免干扰时间特征。
7. **注入只在攻击方式和速率确认后运行**，并保证注入日志完整。

---

## 8. 已知问题与未决事项

| # | 问题 | 状态 |
|---|---|---|
| 1 | 线上 `vigil` 库里旧的 `vigil_dev` 库仍然存在 | 等 `pg-dev` 稳定运行几天后，由负责人决定是否删除 |
| 2 | 注入未实现 | 等待攻击方式和速率确认 |
| 3 | 线上历史错误标签（约 494 条被标为 1） | 导出时已忽略；清理需要线上写入，待确认 |
| 4 | `restore` 不处理整库覆盖快照 | 可以增加从快照导出的选项 |
| 5 | 交接文档写的是 `ads_ml_ocsvm`，代码默认是 `lof_baseline` | 需要更新交接文档 |
| 6 | Cilium 处置是 stub | 待实现 |
| 7 | `scripts/` 的新架构改动已提交到本地 `dev/soar009`（`a84676e`），尚未推送 | 需要推送并开 PR |

---

## 9. 第一周清单

- [ ] 阅读 LAYOUT.md、HANDOVER.md、data-spec-v1.md、model-kit/README.md。
- [ ] 运行 5.1 的 `check`，理解每一行输出。
- [ ] 查看定时任务状态和日志（5.1）。
- [ ] 确认 `~/knettf-data` 里有数据，仓库里没有。
- [ ] 手动导出一个小时段（5.3），打开 CSV 和 txt 看字段。
- [ ] 找负责人确认：注入的攻击方式、历史标签处理、旧 `vigil_dev` 的删除时间。
- [ ] 把发现的文档错误记下来，更新本文。

---

## 10. 常见问题

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `check` 显示"缺少密码" | 没有加载对应的凭据文件 | 先 `. ~/.config/knettf/dev.env` 和 `reader.env` 再运行 |
| `check` 显示线上"可写=是" | 账号不是只读角色 | 检查 `KNETTF_SRC_USER` 是否为 `knettf_reader` |
| `check` 显示线上连接失败 | 密码错误，或容器未运行 | 密码错误就用 `\password knettf_reader` 重设，并更新 `reader.env` |
| `export` 报"Django 连接指向 …" | 没有加载 `dev.env` | 加载 `dev.env`，`VIGIL_DB_*` 应指向 `127.0.0.1:5433/vigil_dev` |
| 定时任务 `Result=exit-code` | 同步失败 | `journalctl --user -u knettf-snapshot.service -n 50` 看最后的报错 |
| `/vigil` 页面没有新记录 | 线上是采集模式 | 预期行为；需要检测时按 5.5 切换 |
| 归档目录增长很快 | 采集速度变快 | 检查 `KNETTF_MAX_GB`，必要时手动清理 `increments/` 最旧的文件 |
| 编辑器报"无法解析导入" | 解释器不对 | 选择仓库的 `.venv` 解释器，重新加载窗口 |

---

## 附：关键命令速查

```bash
# 加载凭据（一个终端里只需要做一次）
set -a && . ~/.config/knettf/dev.env && . ~/.config/knettf/reader.env && set +a
cd ~/github/knettf

# 状态
.venv/bin/python scripts/manage.py check
systemctl --user list-timers knettf-snapshot.timer --no-pager

# 数据
.venv/bin/python scripts/manage.py collect export --since "YYYY-MM-DD HH:MM" --until "YYYY-MM-DD HH:MM"
.venv/bin/python scripts/manage.py collect restore --merge

# 线上（需要权限）
sudo systemctl restart netsentinel.service
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
```

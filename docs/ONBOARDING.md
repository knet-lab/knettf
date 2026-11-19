# 新人接手手册

> 读者：接手 knettf / NetSentinel 的新同事。
> 目标：读完本文后，你能说清楚数据从哪里来、到哪里去、每一步由什么脚本完成，并且能独立完成日常操作和排查常见问题。
> 本文描述的是 2026-11-20 的状态。如果与代码不一致，以代码为准，并更新本文。

配套文档：
- [LAYOUT.md](LAYOUT.md)：仓库目录结构，哪些东西不在仓库里。
- [HANDOVER.md](HANDOVER.md)：迁移到新环境时要改哪些值（域名、用户、路径）。
- [../model-kit/README.md](../model-kit/README.md)：模型接入规范，35 个特征的定义。
- [data-spec-v1.md](data-spec-v1.md)：流的切分规则（双向流、结束条件、单位）。
- [../lab/README.md](../lab/README.md)：实验集群和仿真流量。

---

## 0. 一分钟概述

- 实验集群（5 台 VM，K8s）里的流量被 eBPF（Cilium/Hubble）抓取，经 Kafka 进入线上平台后端。
- 后端把包切成双向流，计算 35 个特征。
- 现在的线上后端处于**采集模式**：流量写入 `vigil_collectrecord` 表，不再跑检测模型。之前的检测记录停在 2026-11-20 00:16（KST）。
- 每小时一个定时任务，把线上新增的采集记录只读拉到开发库，并压缩归档到本机数据目录。
- 需要数据时，用 `scripts/manage.py` 导出 CSV。
- 异常流量注入还没有实现，目前只有壳子。

---

## 1. 系统组成和位置

| 组件 | 位置 | 说明 |
|---|---|---|
| 宿主机 | 一台 Linux 机器 | 同时运行开发、线上和实验集群，**不能做物理隔离** |
| 开发仓库 | `~/github/knettf`，分支 `dev/soar009` | 你日常修改代码、脚本、文档的地方 |
| 线上部署目录 | `/srv/netsentinel/prod` | 从 `main` 自动部署，**不要在这里改代码** |
| 线上后端 | `netsentinel.service`（uvicorn，`0.0.0.0:8080`） | 通过 Cloudflare Tunnel 对外 |
| 同步定时任务 | `knettf-snapshot.timer` / `.service`（用户级 systemd） | 每小时运行 `manage.py collect sync` |
| 数据库容器 | Docker 容器 `pg`（Postgres 18.x，端口 5432） | 同一个实例里有 `vigil`（线上）和 `vigil_dev`（开发） |
| 数据目录 | `~/knettf-data`（权限 700） | 快照、归档、导出结果，**不在仓库里** |
| 实验环境 | `lab/`，K8s 集群在 libvirt 的 VM 里 | 正常流量、注入壳子 |

查看定时任务和容器：

```bash
systemctl --user list-timers knettf-snapshot.timer --no-pager
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep pg
```

---

## 2. 数据流（从流量到 CSV）

```
K8s 集群（Cilium/Hubble 抓包）
  → flow-shipper → Kafka（ebpf-net-logs）
  → 线上后端 Bridge → vigil/ingest（切流、35 特征、不打标签）
  → 采集模式：写入 vigil_collectrecord（线上库 vigil）
  → 每小时 sync：只读拉取新增 → 压缩归档（increments/）→ 写入 vigil_dev
  → 手动 export：vigil_dev → exports/NN/*.csv + *.txt
  → 手动 restore：increments/*.csv.gz → restored/*.csv（可合并去重）
```

### 2.1 采集（线上后端内）
- 入口：`apps/backend/vigil/ingest/bridge.py`，把 Kafka 消息转成包，再由 `flows.py` 切成双向流，`features.py` 计算特征。
- 采集模式的写入：`apps/backend/vigil/services.py` 的 `collect_batch`，由 `VIGIL_COLLECT_ONLY=True` 启用。
- **标签规则**：采集时不打标签（PR #41 之后）。以前按源 IP 末段打标签的做法会误标正常流量（集群内 Pod IP 的末段也可能在 20–29），已经停用。
- 检测模式（关闭采集模式时）：`VIGIL_MODELS` 默认是 `lof_baseline`，结果写入 `vigil_detectionrecord`，并在 `/vigil` 页面显示。

### 2.2 增量同步（每小时）
`scripts/collect/sync.py`：
1. 读取开发库的最大 `id`，记为 `DST_MAX`；起点取 `DST_MAX − 5000`（重叠，覆盖事务延迟提交的记录）。
2. 线上只读：`COPY (SELECT * FROM vigil_collectrecord WHERE id > 起点) TO STDOUT WITH CSV HEADER`。
3. 压缩归档到 `~/knettf-data/increments/collect-<起点>-<终点>.csv.gz`。
4. 写入开发库：同一事务里 `DELETE id > 起点` 后 `COPY` 导入，并校正序列。
5. 核对：开发库最大 `id` ≥ 本批终点，否则报错退出。
6. 保留：归档目录超过 `KNETTF_MAX_GB`（默认 20GB）时，从最旧的删除。

### 2.3 整库快照（手动）
`scripts/collect/snapshot.py`：`pg_dump -t vigil_collectrecord` → 压缩到 `~/knettf-data/snapshots/` → 导入开发库 → 核对行数。
快照是完整的，适合重建开发库；增量同步则适合日常更新。

### 2.4 导出（手动）
`scripts/collect/export.py`：
- 读取**开发库**（Django 的 `vigil` 连接必须指向 `vigil_dev`，否则拒绝）。
- 输出：`~/knettf-data/exports/NN/{time1}-{time2}.csv` 和 `.txt`（采集时间、数据时段、条数、类型统计）。
- 标签：只用 `--label 0|1` 显式指定，**不沿用**采集时写入的标签（历史数据里有误标）。

### 2.5 还原（手动）
`scripts/collect/restore.py`：把增量归档还原为 CSV。`--merge` 时按第一列 `id` 去重（归档之间有重叠）。
**注意**：只处理增量归档。`id` ≤ 1019 的基础数据只在整库快照里，目前没有脚本能直接导出为 CSV。

### 2.6 注入（未实现）
`lab/traffic/inject_attack.sh`：
- 攻击类型是占位（`syn_flood`、`port_scan`、`http_flood`），函数里只打印 TODO。
- 默认演练模式，不发送流量。要真正执行需要 `ENABLE=1 DRY_RUN=0` 和 `TARGET`。
- 执行后追加一行到 `lab/traffic/inject_log.csv`（起止时间、类型、源、目标）。以后导出时，标签应按这份日志的时间窗口决定。

---

## 3. 数据库

| 库 | 用途 | 谁写 | 主要表 |
|---|---|---|---|
| `vigil`（线上） | 线上后端的数据 | 线上后端（账号 `vigil`） | `vigil_collectrecord`（采集）、`vigil_detectionrecord`（检测，按天分区） |
| `vigil_dev`（开发） | 本机的开发副本 | 脚本（账号 `vigil`，只写这个库） | `vigil_collectrecord`（同步来的副本） |

- `vigil_collectrecord`：流的五元组、`flow_input`（JSON，35 个特征）、`label`（采集时为空）、`created_at`。
- `vigil_detectionrecord`：`managed=False`，DDL 由手写 SQL 管理，见 `apps/backend/vigil/migrations/0001_initial.py`。
- 迁移：`vigil` 库的迁移**不会**被部署自动执行，需要手动执行 `manage.py migrate --database=vigil`。
- 查询线上行数（只读）：

```bash
docker exec pg psql -U vigil -d vigil -Atc "select count(*), max(id), max(created_at) from vigil_collectrecord"
```

---

## 4. 配置

### 4.1 线上后端（`apps/backend/backend/settings.py`，线上 `.env`）
| 变量 | 默认值 | 说明 |
|---|---|---|
| `VIGIL_MODELS` | `vigil.detection.lof_baseline.LofBaselineModel` | 检测模式下启用的模型。默认值走 PR 修改 |
| `VIGIL_COLLECT_ONLY` | `False` | `True` 时只采集，不跑模型，不写检测记录，不做 Cilium 处置 |
| `VIGIL_DB_*` | 开发默认值 | 线上 `.env` 里只覆盖了 `VIGIL_DB_NAME` |
| `VIGIL_KAFKA_GROUP_ID` | `vigil-bridge` | **开发环境必须设为 `vigil-bridge-dev`**，否则和线上抢数据 |

> 线上 `.env` 的密码和密钥不要复制到文档、仓库或聊天里。

### 4.2 脚本（`scripts/knettf_common.py`，环境变量）
| 变量 | 默认值 | 说明 |
|---|---|---|
| `KNETTF_DATA_DIR` | `~/knettf-data` | 数据目录，不能在仓库内或 `/srv/netsentinel` 下 |
| `KNETTF_PG_CONTAINER` | `pg` | Postgres 容器名 |
| `KNETTF_SRC_DB` / `KNETTF_SRC_USER` | `vigil` / `vigil` | 线上来源。**应改为只读角色 `knettf_reader`** |
| `KNETTF_SRC_PASSWORD` | 空 | 只读账号的密码，经环境变量传给容器 |
| `KNETTF_DST_DB` / `KNETTF_DST_USER` | `vigil_dev` / `vigil` | 写入目标，必须是 `vigil_dev` |
| `KNETTF_MAX_GB` | `20` | 归档目录容量上限 |
| `KNETTF_OVERLAP` | `5000` | 增量同步的重叠条数 |

凭据文件：`~/.config/knettf/reader.env`（权限 600，不在仓库里）。定时任务通过 `EnvironmentFile=-%h/.config/knettf/reader.env` 读取。

---

## 5. 日常操作手册

> 所有脚本在开发仓库根目录运行。`sync`、`restore` 只用系统 `python3`；`export` 需要 `.venv/bin/python`。

### 5.1 检查状态（只读，每次接手先做）
```bash
python3 scripts/manage.py check          # 显示配置；检查线上账号是否只读、开发库名是否正确
systemctl --user list-timers knettf-snapshot.timer --no-pager
systemctl --user show knettf-snapshot.service -p Result --no-pager
journalctl --user -u knettf-snapshot.service -n 30 --no-pager
```
`check` 当前会返回 1，因为线上账号还不是只读。这是预期的，直到只读角色建好。

### 5.2 手动增量同步
```bash
python3 scripts/manage.py collect sync
```
在只读角色建好之前，这条命令会被拒绝运行。

### 5.3 整库快照
```bash
python3 scripts/manage.py collect snapshot
```
会覆盖开发库的采集表。开发库的数据可以随时从线上重建，所以这一步相对安全，但仍然要先看 `check` 的结果。

### 5.4 导出 CSV
```bash
.venv/bin/python scripts/manage.py collect export --since "2026-11-20 00:00" --until "2026-11-20 06:00" [--label 0|1] [--kind ns|ew|all]
```
输出在 `~/knettf-data/exports/NN/`。`--label` 不填则为空；**不要**把采集时的标签当作真值。

### 5.5 还原归档
```bash
python3 scripts/manage.py collect restore            # 每个归档一个 CSV
python3 scripts/manage.py collect restore --merge    # 合并去重为一个 CSV
```
输出在 `~/knettf-data/restored/`。

### 5.6 切换采集模式（需要线上权限）
开启采集（停止检测）：
1. 确认 `vigil` 库的迁移已执行：`manage.py showmigrations vigil --database=vigil` 应显示 `[X] 0003_collectrecord`。
2. 在线上 `.env` 中设置 `VIGIL_COLLECT_ONLY=true`（修改前先备份 `.env`）。
3. `sudo systemctl restart netsentinel.service`，然后检查：`systemctl status netsentinel.service`，并确认 `vigil_collectrecord` 在增长，`vigil_detectionrecord` 不再增长。

恢复检测：把 `VIGIL_COLLECT_ONLY` 改为 `false`（或删除该行），重启。已采集的数据保留。

> 以上操作都需要线上权限。不要自行在线上执行迁移或改 `.env`，先与负责人确认。

### 5.7 发布代码
1. 在 `dev/soar009` 上修改，运行 `ops/scripts/check.sh backend`（必要时加 `lab`、`ops`）。
2. 推送到 `origin/dev/soar009`，在 GitHub 上开 PR 到 `main`。
3. CI 通过后合并。合并会触发线上自动部署（约 2 分钟内），部署日志在 `/srv/netsentinel/logs/auto-deploy.log`。
4. 合并后检查：`systemctl is-active netsentinel.service` 为 `active`，`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/` 返回 200。

---

## 6. 代码地图

```
apps/backend/
  backend/settings.py            配置（VIGIL_* 变量在这里）
  backend/db_router.py           数据库路由：kcore → default，vigil → vigil
  vigil/ingest/                  切流、特征、Kafka Bridge
  vigil/services.py              采集/检测写库的入口（collect_batch、detect_batch）
  vigil/models.py                DetectionRecord（检测）、CollectRecord（采集）
  vigil/detection/               检测模型（模型方提供的代码与模型文件）
  vigil/response/cilium.py       Cilium 处置（apply_action 目前是 stub）
  vigil/migrations/              vigil 库的迁移（0003 为采集表）
  vigil/tests/                   测试

scripts/                         数据脚本（不含数据）
  manage.py                      唯一入口
  knettf_common.py               配置、安全检查、数据库访问封装
  collect/sync.py                增量同步
  collect/snapshot.py            整库快照
  collect/restore.py             归档还原
  collect/export.py              导出 CSV
  sql/readonly_role.sql          线上只读角色（由线上管理员执行，脚本不执行）

lab/traffic/                     实验流量：boutique_locust.py、client-zone.sh、inject_attack.sh（壳子）
model-kit/                       模型接入说明与样本（normal_baseline_sample.csv）
docs/                            交接、数据规范、本文、LAYOUT
```

---

## 7. 安全规则（必须遵守）

1. **线上库只读**。同步和快照前会验证连接账号：不能有 INSERT/UPDATE/DELETE/TRUNCATE 权限，不能是超级用户。不满足就拒绝运行。不要绕过这个检查。
2. **写入只到 `vigil_dev`**。脚本写入前验证库名。不要把 `KNETTF_DST_DB` 改成别的库。
3. **数据不进仓库**。快照、归档、导出结果都在 `KNETTF_DATA_DIR`。如果在仓库里看到 CSV、`.sql`、`.gz`，那是误操作，先移出。
4. **不要在开发环境运行会修改线上的命令**，包括 `migrate --database=vigil`、修改线上 `.env`、重启线上服务。这些需要线上权限，先确认。
5. **不要把密码写进仓库、文档或命令行**。凭据放在 `~/.config/knettf/reader.env`（权限 600）。
6. **开发机和线上同一台机器**。采集期间避免训练、编译和大型测试，因为 CPU 抢占会扰动时间特征（`flow_duration`、`iat_*`）。
7. **注入只在有确认的攻击方式和速率后才运行**，并且保证注入日志完整。

---

## 8. 已知问题与未决事项

| # | 问题 | 影响 | 状态 |
|---|---|---|---|
| 1 | 只读角色 `knettf_reader` 未建 | 每小时同步被拒绝运行，开发库不更新 | 等线上管理员执行 `scripts/sql/readonly_role.sql` |
| 2 | 线上和开发库在同一个 Postgres 实例 | 隔离靠运行时验证和账号权限，不是物理隔离 | 可评估另起开发实例 |
| 3 | 注入未实现 | 没有异常流量，无法训练和评估异常检测 | 等待攻击方式和速率确认 |
| 4 | 线上历史错误标签（约 494 条被标为 1） | 历史数据标签不可用于训练 | 导出时已忽略；清理需要线上写入，待确认 |
| 5 | `restore` 不处理整库快照 | `id ≤ 1019` 的基础数据不能直接导出 CSV | 可以增加从快照导出的选项 |
| 6 | 交接文档写的是 `ads_ml_ocsvm`，代码默认是 `lof_baseline` | 文档与实际不一致 | 需要更新交接文档 |
| 7 | Cilium 处置是 stub | `apply_action` 只记录日志，不下发策略 | 待实现 |
| 8 | 线上 `vigil_detectionrecord` 停止增长（检测已关闭） | 页面 `/vigil` 不再有新记录 | 采集模式的预期结果 |

---

## 9. 第一周清单

- [ ] 阅读 LAYOUT.md、HANDOVER.md、data-spec-v1.md 和 model-kit/README.md。
- [ ] 在开发仓库运行 `python3 scripts/manage.py check`，理解每一行输出。
- [ ] 查看定时任务的状态和最近一次日志（见 5.1）。
- [ ] 查看 `~/knettf-data` 的目录结构，确认没有数据在仓库里。
- [ ] 手动运行一次 `export`（时间范围选一个已有数据的小窗口），打开 CSV 和 txt 看一下字段。
- [ ] 在 `vigil_dev` 里执行一次只读查询，确认能读到数据。
- [ ] 找负责人确认：只读角色的执行时间、注入的攻击方式、历史标签的处理方式。
- [ ] 把发现的文档错误或不一致记下来，更新本文。

---

## 10. 常见问题排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `sync` 报"线上连接账号有写权限或是超级用户" | 还在用 `vigil` 账号 | 等只读角色建好，设置 `reader.env` |
| `export` 输出 0 条 | 时间范围不对，或者开发库没有数据 | 检查 `--since`/`--until`（Asia/Seoul），用 `check` 确认开发库名 |
| `export` 报"Django 连接指向 …" | 环境变量指向了别的库 | 检查 `KNETTF_DST_DB`，应为 `vigil_dev` |
| `pg_dump` 或 `psql` 找不到 | 没有用容器里的工具 | 脚本通过 `docker exec pg` 调用，本机不需要安装 |
| 编辑器报"无法解析导入 vigil.detection.base" 或 `common` 相关错误 | 编辑器的 Python 路径不对 | 确认解释器为 `.venv`，重新加载窗口。`scripts/knettf_common.py` 不应与 `apps/backend/common` 重名 |
| `InvalidCursorName` 紧跟着 `UndefinedTable` | 第一个错误是表不存在，第二个是连锁报错 | 先解决表不存在的问题（迁移） |
| 线上 `/vigil` 页面没有新记录 | 采集模式开启，检测停止 | 这是预期行为；需要检测时按 5.6 恢复 |
| 定时任务 `Result=exit-code` | 同步被拒绝，或者网络/容器问题 | 看 `journalctl --user -u knettf-snapshot.service` 的最后几行 |
| 归档目录空间快速增长 | 采集速度变快，或保留上限设置过大 | 检查 `KNETTF_MAX_GB`，必要时手动清理 `increments/` 中最旧的文件 |

---

## 附：关键命令速查

```bash
# 状态
python3 scripts/manage.py check
systemctl --user list-timers knettf-snapshot.timer --no-pager
docker exec pg psql -U vigil -d vigil -Atc "select count(*), max(id) from vigil_collectrecord"       # 线上（只读）
docker exec pg psql -U vigil -d vigil_dev -Atc "select count(*), max(id) from vigil_collectrecord"   # 开发

# 数据
python3 scripts/manage.py collect sync
python3 scripts/manage.py collect snapshot
python3 scripts/manage.py collect restore --merge
.venv/bin/python scripts/manage.py collect export --since "YYYY-MM-DD HH:MM" --until "YYYY-MM-DD HH:MM"

# 线上（需要权限）
sudo systemctl restart netsentinel.service
systemctl is-active netsentinel.service
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
```

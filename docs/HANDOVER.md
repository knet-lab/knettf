# 交接与迁移说明

> 2026-11 起，原维护团队不再负责线上部署。之后域名、Cloudflare 账号、Linux 用户都会更换。
> 这份文档说明：现在的系统是什么状态、哪些值和当前环境绑定、换到新环境要改什么。

---

## 1. 现状一览

```
一台 Linux 宿主机，同时是：开发环境 + 线上平台 + 实验集群
├─ 实验环境（lab/）：5 台 VM 组成的 K8s 集群 + 流量仿真
│     每个节点 eBPF（Cilium/Hubble）抓包 → flow-shipper（过滤 + 去重）→ Kafka（ebpf-net-logs）
└─ 平台（apps/）：Django 后端 + Vue 前端（域名 → Cloudflare Tunnel → 本机 8080）
      ingest 把包切成流（35 个特征）→ 检测模型 → PostgreSQL → /vigil 页面
```

| 部分 | 状态 |
|---|---|
| 采集链路 | ✅ 每节点直连本地 Hubble socket，无重复、不采集自身流量 |
| 流切分（`vigil/ingest`） | ✅ 双向流、RST 立即结束、双方 FIN 后收下挥手尾包再结束（参照 Zeek）+ 空闲 60s / 活跃 120s 超时、微秒单位 |
| 正常流量基线 | ✅ Online Boutique（`04-deploy-baseline.sh`）+ 宿主机仿真客户端区（`lab/traffic/client-zone.sh`） |
| 检测模型 | ⚠️ 现模型 `ads_ml_ocsvm` 把确定正常的流量几乎 100% 判为攻击；原因在训练数据（见第 5 节） |
| 模型接入 | ✅ 独立接入包 [`model-kit/`](../model-kit/README.md)，模型方不需要懂平台即可开发、自测 |

日常操作：
- 重建实验环境：`lab/cluster/` 下按顺序 `00 → 01 → 02 → 03 → 04`（03、04 幂等，可重复跑）
- 南北向流量：`sudo bash lab/traffic/client-zone.sh up && sudo bash lab/traffic/client-zone.sh start`
- 开发流程：分支 → PR → CI（`ops/scripts/check.sh`）→ 合并 main → 自动部署（每 2 分钟检查一次）

---

## 2. 和当前环境绑定的值（迁移时必须处理）

### 2.1 必须改，否则部署失败

| 值 | 现在 | 出现位置 |
|---|---|---|
| 域名 | `knettf.com` | `ops/deploy/cloudflared-knettf.yml`、`README.md`、帮助页面；后端通过线上 `.env` 的 `CSRF_EXTRA_ORIGINS` 配置（代码里没有写死） |
| Cloudflare Tunnel | 隧道名、凭证文件路径 | `ops/deploy/cloudflared-knettf.yml`、`ops/deploy/systemd/cloudflared-knettf.service` |
| 运行用户 | `netsentinel` | `ops/deploy/systemd/*.service`、`ops/deploy/sudoers.netsentinel`、`ops/deploy/cron.netsentinel` |
| 部署目录 | `/srv/netsentinel/{prod,lab-repo,models,logs}` | `ops/scripts/{deploy,auto-deploy}.sh`、`lab/sync-to-srv.sh`、`ops/deploy/systemd/*`、`settings.py`（`VIGIL_ADS_ML_CONFIG`）；运行 `lab/cluster/03` 时用环境变量 `NETSENTINEL_BACKEND_DIR` 指向 `prod/apps/backend` |
| GitHub 仓库 | `knet-lab/knettf` | `ops/scripts/auto-deploy.sh`（查询 CI 结果的 API 地址） |
| 无效路径 | `/Users/soar009/.../terraform`（Mac 路径） | `settings.py` 的 `TF_BIN`，在 Linux 上本来就无效，应改为环境变量 |

用以下命令查找全部位置：

```bash
git grep -nIE 'knettf\.com|cloudflare|/srv/netsentinel|User=netsentinel|knet-lab|soar009|/Users/' -- . ':!*.lock' ':!docs/archive'
```

### 2.2 不用改（实验环境内部地址）

`192.168.100.0/24`（VM）、`192.168.100.200-250`（MetalLB）、`172.30.0.0/16`（仿真客户端区）、`10.0.0.0/8`（Pod）都是实验环境内部的私有地址，跟着脚本走。只有新机器上的网段冲突时才需要改：`lab/cluster/01-setup-vms.sh`、`02-setup-cluster.sh`、`host-firewall-ccnp.yaml`、`lab/traffic/client-zone.sh`、`apps/backend/vigil/ingest/features.py`。

### 2.3 文档里的个人信息

帮助页面（`apps/frontend/src/views/help/pages/` 下的 prepare、access、handover、index、firstday 等）多处写了原维护者的 Linux 账户和 GitHub 账户，交接后需要改成通用说法。

---

## 3. 迁移到新环境的步骤

1. **准备宿主机**：Ubuntu，开启 KVM/libvirt，`/home/vm-images` 所在分区可用 ≥ 420 GB（详见 `lab/README.md`）。
2. **创建运行用户和目录**：新建服务账户（替代 `netsentinel`）和部署目录（替代 `/srv/netsentinel`），按第 2.1 节修改 systemd 单元和脚本里的路径与用户。
3. **数据库**：PostgreSQL（现为 Docker 容器 `pg`），在后端 `.env` 里配置 `VIGIL_DB_*`。
4. **模型文件**：放到新的模型目录，在 `.env` 里设置 `VIGIL_ADS_ML_CONFIG`（以及 `VIGIL_MODELS`）。
5. **实验集群**：`lab/cluster/00 → 04`。
6. **域名和 Cloudflare**：在新账号下创建 Tunnel，把新域名指向本机 8080；修改 `ops/deploy/cloudflared-*.yml` 和对应的 systemd 单元。
7. **自动部署**（可选）：修改 `auto-deploy.sh` 里的仓库地址，启用 `netsentinel-autodeploy.timer`。如果不再需要自动部署，停用这个 timer 即可。
8. **验证**：`ops/scripts/check.sh` 通过；网站可访问；`/vigil` 页面有检测记录。

---

## 3.1 原维护者离开前的检查清单

原维护者的开发目录和 Linux 账户最终会删除。删除前逐项确认：

| # | 事项 | 原因 |
|---|---|---|
| 1 | `sudo bash lab/traffic/client-zone.sh down` | 仿真客户端的 locust 进程从**原维护者的开发目录**、以原维护者身份运行，目录删除后会失效。新操作者在自己的仓库里重新 `up` + `start` |
| 2 | 新操作者用**自己的 SSH 密钥**按 `lab/cluster/00 → 04` 重建集群（或按帮助页面“准备”一节复制 kubeconfig） | `02-setup-cluster.sh` 用运行者的 `$HOME/.ssh/id_rsa` 创建 VM 登录；kubeconfig 也在运行者的 `$HOME/.kube/` 下。原账户删除后，旧集群将无法登录 VM |
| 3 | 需要保留的数据移出原账户的家目录，或明确放弃 | 例如旧检测记录的备份、模型方提供的原始数据集；它们不在 Git 里 |
| 4 | 确认没有以原维护者身份运行的服务或定时任务：`ps -u <用户>`、`systemctl list-units 'knettf-*'`、`crontab -l -u <用户>` | 线上服务（`netsentinel.service`、`netsentinel-autodeploy.timer`、cloudflared）以服务账户运行，不依赖个人账户；实验和仿真脚本以操作者身份运行 |
| 5 | GitHub 仓库和组织的权限转给新维护者 | 自动部署从 GitHub main 拉取代码 |

线上部署目录（`/srv/netsentinel/prod`、`/srv/netsentinel/lab-repo`）是从 GitHub 拉取的独立副本，**不依赖任何人的开发目录**。

---

## 4. 单机共用的注意事项

这台机器同时跑开发、线上和实验集群：

- 在开发环境运行 `manage.py`，默认连的是**线上数据库**。
- 开发环境运行后端时必须设置 `VIGIL_KAFKA_GROUP_ID=vigil-bridge-dev`，否则会和线上抢 Kafka 数据。
- VM 没有绑核。大量编译、训练、测试会和集群抢 CPU，**会扰动采集到的时间特征**。采集数据期间要避开这类任务。
- 重建实验集群期间，线上检测会中断。

---

## 5. 遗留问题

| 问题 | 说明 |
|---|---|
| 现模型把正常流量判为攻击 | TON_IoT 版本：测试集和训练集是同一份；特征来自 Zeek，eBPF 大部分采不到。eBPF 版本：训练数据里正常和攻击可以只靠 IP / 端口区分；IP 编码器只认识训练时的地址；protocol 编码不一致（模型认 `'6'`，平台送 `"TCP"`）。详见 `model-kit/README.md` 第 7 节 |
| 缺少原始训练数据 | 线上模型降维前的 35 特征训练数据不在仓库里，需要向模型方索取 |
| 东西向单包流（已修复） | 原因是双方 FIN 后立即输出流，挥手最后的 ACK 单独成了一条单包流（约 30%）。已改为收下尾包再结束，线上实测降到约 5%（剩下多为 RST 之后零星的包）。`model-kit/data/` 样本已于 2026-11-16 重新导出 |
| 少量流方向判断 | 服务刚启动时，大端口服务（如 gRPC 50051）的长连接可能判反，运行一段时间后会自动修正 |
| 跨节点包重复计数（已修复） | 跨节点 Pod→Pod 的包经 overlay 隧道，曾在源节点 FROM_ENDPOINT 和目的节点 FROM_NETWORK 各计一次，跨节点流（约占包量 90%）包数翻倍、包间隔被打乱。已在 `vigil/ingest/flows.py` 修复，`model-kit/data/` 已用修复后的数据重新导出。2026-11-15 之前存库的检测记录仍是旧口径，不要和之后的数据混用 |
| 自动标签误标 | `ingest/features.py` 按源 IP 最后一段打 label（20–29 → 1，50–64 → 0），本意是宿主机伪造源 `192.168.100.x`，但仿真客户端 `172.30.*.20–29` 的正常流量也会被标成 1。导出训练数据时用 `export_flows.py --label` 显式指定 |
| 字节特征 | Hubble 没有包长。长期方案：换成不依赖 CNI 的 eBPF 流采集（如 NetObserv eBPF Agent），在内核里聚合流并补上字节和包间隔统计，再打包成 Helm chart |

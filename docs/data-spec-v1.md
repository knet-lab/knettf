# 数据规范 v1：采集、切流、特征、标签

本文是环境方对外提供流数据的规范，模型方训练和推理都以此为准。内容与当前代码一致：

- 切流：`apps/backend/vigil/ingest/flows.py`
- 特征：`apps/backend/vigil/ingest/features.py`（`compute_flow`）
- 字段与类型：`apps/backend/vigil/detection/base.py`（`DetectionInput`）

| 项 | 内容 |
|---|---|
| 版本 | v1 |
| 生效日期 | 2026-11-19 |
| 负责方 | 环境方（采集、切流、特征计算、标签）；模型方（预处理、每类最少样本数、训练） |

**变更规则**：v1 发出后不改动。切流规则、特征的名称 / 类型 / 单位 / 含义、标签规则任何一项变化，都升版本号（v2 …），走 PR，并通知模型方。代码改动必须与本文同步。

---

## 1. 数据来源

```
K8s 实验集群
  → Cilium/Hubble（eBPF）：每个包在每个观测点产生一条事件
  → flow-shipper（每节点）：过滤 + 去重 → Kafka
  → 平台后端：按第 3 节切流，按第 4 节计算特征
```

**采集不到的信息**（v1 不提供）：

- 包长和字节数：Hubble 不提供，因此没有任何字节相关特征。
- 应用层内容：HTTP、DNS、TLS 等字段。

## 2. 过滤与去重

### 2.1 不参与切流的事件

| 类别 | 规则 |
|---|---|
| 采集链路自身 | 任一端在 `kube-system` 命名空间；任一端是 Kafka、flow-shipper、hubble-relay |
| Kafka 端口 | 任一端口是 9092 / 9093 / 9094 |
| 节点管理流量 | 一端是节点 IP 或宿主机网关，另一端也在集群内（Pod、节点、LoadBalancer VIP） |
| LoadBalancer VIP | 观测点为 `FROM_NETWORK` 且目的是 VIP 的事件（DNAT 前地址），只保留随后以 Pod 地址记录的那一条 |
| loopback | 任一端是 `127.*` 或 `::1` |
| 残缺事件 | 缺源或目的 IP；TCP/UDP 缺任一端口 |

保留的是：Pod↔Pod（东西向）和外部↔集群（南北向）的流量。

### 2.2 去重

同一个包会在多个观测点各上报一次，只计"第一次被看到"的那一次：

- 计数的观测点：`FROM_ENDPOINT`、`FROM_NETWORK`、`FROM_HOST`、`FROM_STACK`、`FROM_PROXY`、`FROM_CRYPTO`；事件没有观测点信息时照常计数。
- 不计数：其余观测点（`FROM_OVERLAY`、`TO_*` 等）。
- 源地址是 Pod 的包出现在 `FROM_NETWORK`：说明是跨节点隧道送达，源节点已计过，不再计数。

## 3. 切流规则

### 3.1 流的键与方向

- **键**：双向五元组（两端 IP、两端端口、协议）。两个端点排序后作为键，A→B 与 B→A 属于同一条流。
- **发起方**（决定 `src`、`fwd`），按以下优先级判断：
  1. 同一连接上一段输出时记下的发起方（超时切开的后续段、关闭后零星的包沿用）
  2. TCP 握手：只带 SYN 的一方是发起方；SYN+ACK 的发送方是服务端
  3. 之前从握手学到的服务端 (IP, 端口)
  4. Hubble 的 `is_reply`：回包的发送方是服务端
  5. 端口：端口号小的一方是服务端
- **fwd** = 发起方发出的包，**bwd** = 响应方发出的包。

### 3.2 流的结束

| 条件 | 处理 |
|---|---|
| 出现 RST | 立即输出（RST 包计入本流） |
| 双方都发过 FIN | 进入"关闭中"；收到下一个不带 FIN 的包（挥手最后的 ACK）后输出，该包计入本流 |
| 关闭中超过 2 秒没有新包 | 输出 |
| 关闭中出现新的 SYN（端口复用） | 旧流输出，SYN 开始新的一条 |
| 空闲 60 秒没有新包 | 输出 |
| 流持续 120 秒（从首包算） | 输出一段，后续包开始新的一条，沿用原发起方 |
| 单条流达到 10,000 个包 | 输出一段，后续包开始新的一条，沿用原发起方 |
| 同时打开的流超过 200,000 条 | 最久没有新包的那条先输出 |

时间用 Hubble 事件自带的时间戳（内核记录的时间）。

说明：原版 CICFlowMeter 在第一个 FIN 处就切流，挥手尾包会变成单包流；v1 按 Zeek 的做法把尾包留在原连接里。

## 4. 特征（35 个）

| # | 名称 | 类型 | 定义 | 单位 / 取值 |
|---|---|---|---|---|
| 1 | `src_ip` | str | 发起方 IP | |
| 2 | `dst_ip` | str | 响应方 IP | |
| 3 | `protocol` | str | 传输层协议 | `"TCP"` / `"UDP"` / `"ICMPv4"` / `"ICMPv6"` / `"OTHER"`（文字，不是协议号） |
| 4 | `src_port` | int | 发起方端口 | ICMP 为 0 |
| 5 | `dst_port` | int | 响应方端口 | ICMP 为 0 |
| 6 | `flow_duration` | float | 末包时间 − 首包时间 | 微秒，保留 1 位小数；最小 1.0 |
| 7 | `total_packets` | int | 总包数 | |
| 8 | `fwd_packets` | int | 发起方发出的包数 | |
| 9 | `bwd_packets` | int | 响应方发出的包数 | |
| 10 | `fwd_ratio` | float | fwd_packets / total_packets | 0–1，保留 4 位小数 |
| 11 | `packets_per_second` | float | total_packets / 时长（秒） | 每秒，保留 4 位小数 |
| 12 | `iat_mean` | float | 相邻两包时间间隔的均值（双向合并，按时间排序） | 微秒，保留 1 位小数 |
| 13 | `iat_std` | float | 相邻两包时间间隔的标准差（总体标准差，除以 n） | 微秒，保留 1 位小数 |
| 14 | `iat_min` | float | 相邻两包时间间隔的最小值 | 微秒，保留 1 位小数 |
| 15 | `iat_max` | float | 相邻两包时间间隔的最大值 | 微秒，保留 1 位小数 |
| 16 | `syn_count` | int | 带 SYN 标志的包数 | |
| 17 | `ack_count` | int | 带 ACK 标志的包数 | |
| 18 | `fin_count` | int | 带 FIN 标志的包数 | |
| 19 | `rst_count` | int | 带 RST 标志的包数 | |
| 20 | `psh_count` | int | 带 PSH 标志的包数 | |
| 21 | `urg_count` | int | 带 URG 标志的包数 | |
| 22 | `syn_ratio` | float | syn_count / total_packets | 0–1，保留 4 位小数 |
| 23 | `ack_ratio` | float | ack_count / total_packets | 同上 |
| 24 | `fin_ratio` | float | fin_count / total_packets | 同上 |
| 25 | `rst_ratio` | float | rst_count / total_packets | 同上 |
| 26 | `reply_count` | int | Cilium 标记为回包（`is_reply`）的包数 | |
| 27 | `reply_ratio` | float | reply_count / total_packets | 0–1，保留 4 位小数 |
| 28 | `forwarded_count` | int | Cilium 判定为 `FORWARDED` 的包数 | |
| 29 | `drop_count` | int | total_packets − forwarded_count（所有非 `FORWARDED` 的包） | |
| 30 | `drop_ratio` | float | drop_count / total_packets | 0–1，保留 4 位小数 |
| 31 | `is_bidirectional` | int | 双方都发过包 | 0 / 1 |
| 32 | `is_tcp` | int | 协议为 TCP | 0 / 1 |
| 33 | `is_udp` | int | 协议为 UDP | 0 / 1 |
| 34 | `is_icmp` | int | 协议为 ICMPv4 或 ICMPv6 | 0 / 1 |
| 35 | `is_well_known_port` | int | dst_port < 1024 | 0 / 1 |

边界情况：

- 只有 1 个包的流：`iat_*` 全部为 0，`flow_duration` 为 1.0。
- 只有 1 个间隔（2 个包）的流：`iat_std` 为 0。
- 非 TCP 的流：所有 TCP 标志计数和比例为 0。

注意：

- 1–5 是标识类特征，取值与具体环境的地址分配有关，换环境后分布会变。是否用于训练由模型方决定。
- 26–30 依赖 Cilium 的标记和集群的网络策略，策略不同时分布会变。

## 5. 标签

| 项 | v1 |
|---|---|
| 字段 | `label`，str，只在数据集里有，推理时不使用 |
| 取值 | `"0"` 正常 / `"1"` 攻击 / `""` 未知 |
| 打标方式 | 导出时按采集时间段整体指定：`model-kit/export_flows.py --since … --until … --label 0` 或 `--label 1` |
| 攻击类别 | 待定（环境方确定，见第 7 节） |

后端在入库时也会自动打标（按源 IP 最后一段：20–29 为 `"1"`，50–64 为 `"0"`），这个规则会误标仿真客户端的正常流量，**不作为数据集标签使用**。数据集一律用导出时显式指定的标签。

## 6. 交付格式

- CSV，一行一条流，列依次为第 4 节的 35 个特征、`label`、`kind`。
- `kind` 是流的区域，不是特征：`ns` = 南北向（外部↔集群），`ew` = 东西向（Pod↔Pod）。
- `export_flows.py` 的 `--since` / `--until` 按记录的入库时间筛选（流结束后入库），不是流的首包时间。不加 `--label` 时会沿用入库时的自动标签，所以导出数据集时必须指定 `--label`。
- 正常数据样本：`model-kit/data/normal_baseline_sample.csv`。
- 更多数据用 `model-kit/export_flows.py` 从平台数据库导出。

## 7. 待确定事项

| 事项 | 负责方 | 状态 |
|---|---|---|
| 攻击类别（名称、数量）及攻击流的打标规则 | 环境方 | 待定 |
| 是否使用 35 个特征中的全部（特别是 1–5、26–30） | 模型方 | 待确认 |
| 预处理参数（标准化、缩放器等） | 模型方 | 待确认 |
| 每类最少样本数（按流计） | 模型方 | 待确认 |
| 训练集与测试集的划分方式（按时段或场景隔离） | 双方 | 待定 |

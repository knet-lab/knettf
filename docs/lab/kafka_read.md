# kafka_read.py 使用说明

从 Kafka 主题 `ebpf-net-logs` 消费 Hubble 原始流量事件，支持多维度筛选与格式化打印。

---

## 数据来源

```
Cilium/Hubble  →  flow-shipper（每节点，gRPC 读本节点 Hubble）  →  Kafka (ebpf-net-logs)  →  kafka_read.py
```

flow-shipper 输出的消息与 `hubble observe --output=json` 格式相同，**不对字段做任何删改**。
但默认会在节点上过滤采集链路自身流量、并按后端规则去重（同一个包的多个观测点只保留一条），需要全部原始事件时把 `lab/manifests/flow-shipper.yaml` 里的 `SHIPPER_DEDUP` 设为 `0` 后重跑 03。

---

## Kafka 消息结构

每条消息是一个完整的 Hubble 流量事件 JSON，顶层结构如下：

```json
{
  "flow": {
    "time": "2026-04-09T06:08:26.728213207Z",
    "uuid": "6a1f8667-55fb-44ab-9524-4e08dfc38190",
    "verdict": "FORWARDED",
    "traffic_direction": "INGRESS",
    "IP": {
      "source": "10.0.1.130",
      "destination": "10.0.3.44",
      "ipVersion": "IPv4"
    },
    "ethernet": {
      "source": "4a:d3:8b:fa:75:05",
      "destination": "4a:d3:8b:fa:75:05"
    },
    "l4": {
      "TCP": {
        "source_port": 54808,
        "destination_port": 4240,
        "flags": { "ACK": true }
      }
    },
    "source": {
      "identity": 6,
      "labels": ["reserved:remote-node"],
      "namespace": "default",
      "pod_name": "my-pod-abc"
    },
    "destination": {
      "identity": 4,
      "labels": ["reserved:health"],
      "namespace": "kube-system",
      "pod_name": "cilium-xyz"
    },
    "source_service": { "name": "my-svc", "namespace": "default" },
    "destination_service": { "name": "cilium-health", "namespace": "kube-system" },
    "Type": "L3_L4",
    "node_name": "k8s-master",
    "node_labels": ["kubernetes.io/hostname=k8s-master"],
    "event_type": { "type": 4, "sub_type": 4 },
    "trace_observation_point": "TO_OVERLAY",
    "trace_reason": "ESTABLISHED",
    "is_reply": false,
    "interface": { "index": 5, "name": "cilium_vxlan" },
    "Summary": "TCP Flags: ACK"
  },
  "node_name": "k8s-master",
  "time": "2026-04-09T06:08:26.728213207Z"
}
```

### 字段说明

| 字段路径 | 类型 | 说明 |
|---------|------|------|
| `flow.time` | string | 事件时间（RFC3339 纳秒精度） |
| `flow.uuid` | string | 事件唯一 ID |
| `flow.verdict` | string | `FORWARDED` / `DROPPED` / `ERROR` / `AUDIT` |
| `flow.traffic_direction` | string | `INGRESS` / `EGRESS` |
| `flow.IP.source` | string | 源 IP |
| `flow.IP.destination` | string | 目标 IP |
| `flow.IP.ipVersion` | string | `IPv4` / `IPv6` |
| `flow.ethernet.source` | string | 源 MAC |
| `flow.ethernet.destination` | string | 目标 MAC |
| `flow.l4.TCP.source_port` | int | TCP 源端口 |
| `flow.l4.TCP.destination_port` | int | TCP 目标端口 |
| `flow.l4.TCP.flags` | object | TCP 标志位（ACK/SYN/FIN/RST/PSH/URG） |
| `flow.l4.UDP.*` | object | UDP 端口（同 TCP 结构） |
| `flow.l4.ICMPv4/ICMPv6` | object | ICMP 类型与 code |
| `flow.source.identity` | int | Cilium 端点 identity |
| `flow.source.labels` | array | 端点 labels |
| `flow.source.namespace` | string | 源 K8s namespace |
| `flow.source.pod_name` | string | 源 Pod 名 |
| `flow.source_service.name` | string | 源 Service 名 |
| `flow.destination.*` | — | 目标端点信息（同 source 结构） |
| `flow.destination_service.name` | string | 目标 Service 名 |
| `flow.Type` | string | `L3_L4` / `L7` / `SOCK` |
| `flow.node_name` | string | 产生事件的节点 |
| `flow.trace_observation_point` | string | 观测点（`TO_OVERLAY` / `FROM_ENDPOINT` 等） |
| `flow.trace_reason` | string | `ESTABLISHED` / `NEW` / `FIRST_REPLY` 等 |
| `flow.is_reply` | bool | 是否为回包方向 |
| `flow.interface.name` | string | 网卡名（`eth0` / `cilium_vxlan` 等） |
| `flow.drop_reason` | int | 丢包原因代码（verdict=DROPPED 时有值） |
| `flow.drop_reason_desc` | string | 丢包原因描述 |
| `flow.Summary` | string | L4/L7 摘要（如 `TCP Flags: ACK`） |

---

---

## 输出字段说明

每条匹配事件共输出 **21 个字段**，全部列于下表，并标注所属 OSI 层级。

| 字段名 | OSI 层 | 用途 | 说明 |
|--------|--------|------|------|
| `timestamp` | — | 事件发生时间 | Hubble 记录的报文捕获时间，已转换为本地时区（KST），精度纳秒级。格式：`YYYY-MM-DD HH:MM:SS KST` |
| `verdict` | — | 策略执行结果 | `FORWARDED`：正常放行；`DROPPED`：被网络策略丢弃；`ERROR`：转发错误；`AUDIT`：审计模式（不实际丢弃） |
| `direction` | — | 流量方向 | `INGRESS`：进入端点；`EGRESS`：从端点发出 |
| `trace_point` | — | 内核观测位置 | Cilium eBPF 钩子捕获点，如 `TO_ENDPOINT`、`FROM_ENDPOINT`、`TO_OVERLAY` 等 |
| `trace_reason` | L4 | 连接跟踪状态 | `NEW`：新建连接；`ESTABLISHED`：已建立；`FIRST_REPLY`：首个回包。为空表示非连接跟踪流量 |
| `node` | — | 所在节点 | 产生此流量事件的 K8s 节点主机名 |
| `src_ip` | L3 | 源 IP 地址 | 报文发送方 IP，集群内为 Pod CIDR 地址段 |
| `dst_ip` | L3 | 目标 IP 地址 | 报文接收方 IP |
| `protocol` | L4 | 传输层协议 | `TCP` / `UDP` / `ICMPv4` / `ICMPv6` / `OTHER` |
| `src_port` | L4 | 源端口 | TCP/UDP 源端口号，ICMP 等协议为 `None` |
| `dst_port` | L4 | 目标端口 | TCP/UDP 目标端口号，可结合 `dst_service` 判断访问的服务类型 |
| `tcp_flags` | L4 | TCP 标志位 | 仅 TCP 有效，字典形式，如 `{'SYN': True}`、`{'ACK': True}`、`{'FIN': True, 'ACK': True}`。用于判断连接阶段（握手/传输/挥手） |
| `is_reply` | L4 | 是否为回包 | `True`：此报文是对请求的响应；`False`：主动发出的请求；`None`：无法判断 |
| `src_namespace` | L7 | 源 Pod 命名空间 | K8s namespace，集群外来源（物理节点、外网）通常为 `None` |
| `src_pod` | L7 | 源 Pod 名称 | 发起连接的 Pod 全名，节点或外部流量为 `None` |
| `src_service` | L7 | 源 Service 名称 | 源端点关联的 K8s Service，多数主动发起的连接此项为 `None` |
| `dst_namespace` | L7 | 目标 Pod 命名空间 | 目标端点的 K8s namespace |
| `dst_pod` | L7 | 目标 Pod 名称 | 接收连接的 Pod 全名 |
| `dst_service` | L7 | 目标 Service 名称 | 目标端点关联的 K8s Service，可用于识别访问了哪个服务 |
| `interface` | L2 | 捕获网卡 | Cilium 捕获报文的网络接口。`lxcXXXX`：Pod veth 接口；`cilium_vxlan`：VXLAN 隧道；`eth0`：节点物理网卡 |
| `summary` | L4/L7 | 协议摘要 | Hubble 自动生成的可读摘要。TCP 显示标志位（如 `TCP Flags: SYN`）；L7 层显示 HTTP 方法、状态码、DNS 查询等 |

### OSI 层级分布

| OSI 层 | 字段 |
|--------|------|
| **L2** 数据链路层 | `interface` |
| **L3** 网络层 | `src_ip`、`dst_ip` |
| **L4** 传输层 | `protocol`、`src_port`、`dst_port`、`tcp_flags`、`is_reply`、`trace_reason` |
| **L7** 应用层 | `src_namespace`、`src_pod`、`src_service`、`dst_namespace`、`dst_pod`、`dst_service` |
| **元数据** | `timestamp`、`verdict`、`direction`、`trace_point`、`node`、`summary` |

---

## 运行方式

```bash
python3 kafka_read.py [选项]
```

默认从头读取所有历史消息并持续监听新消息，按 `Ctrl+C` 停止。

---

## 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--verdict` | 按判定结果筛选 | `--verdict DROPPED` |
| `--direction` | 按流量方向筛选 | `--direction INGRESS` |
| `--protocol` | 按协议筛选 | `--protocol TCP` |
| `--src` | 源 IP 前缀匹配 | `--src 10.0.1` |
| `--dst` | 目标 IP 前缀匹配 | `--dst 10.0.4` |
| `--src-ns` | 源 namespace 子串匹配 | `--src-ns kube-system` |
| `--dst-ns` | 目标 namespace 子串匹配 | `--dst-ns default` |
| `--src-pod` | 源 Pod 名子串匹配 | `--src-pod nginx` |
| `--dst-pod` | 目标 Pod 名子串匹配 | `--dst-pod coredns` |
| `--node` | 节点名子串匹配 | `--node worker1` |
| `--drop-only` | 只看 DROPPED 流量（等价于 `--verdict DROPPED`） | `--drop-only` |
| `-n N` | 最多从 Kafka 读取 N 条原始消息后退出 | `-n 100` |

> 所有参数可自由组合，均为 AND 逻辑。

---

## 输出格式

每条匹配的流量事件输出如下：

```
[2026-04-09T06:08:26.728213207Z] FORWARDED | INGRESS | TCP | TO_OVERLAY | node=k8s-master
  10.0.1.130:54808  ->  10.0.3.44:4240  flags={'ACK': True}  is_reply=False
  src: ns=default  pod=my-pod-abc  svc=my-svc
  dst: ns=kube-system  pod=cilium-xyz  svc=cilium-health
  iface=cilium_vxlan  trace_reason=ESTABLISHED
  summary: TCP Flags: ACK
```

字段顺序：`[时间] verdict | direction | protocol | 观测点 | 节点`

---

## 使用示例

```bash
# 看所有流量
python3 kafka_read.py

# 只看丢包事件
python3 kafka_read.py --drop-only

# 只看入向 TCP 流量
python3 kafka_read.py --direction INGRESS --protocol TCP

# 只看来自 kube-system 的流量
python3 kafka_read.py --src-ns kube-system

# 目标 IP 在 10.0.4 段，只取前 20 条
python3 kafka_read.py --dst 10.0.4 -n 20

# 看 DROPPED 且来自特定节点
python3 kafka_read.py --drop-only --node k8s-worker1

# 组合：看 default namespace 中 nginx pod 发出的 TCP 请求
python3 kafka_read.py --src-ns default --src-pod nginx --protocol TCP
```

---

## 配置说明

脚本顶部常量可按需修改：

```python
KAFKA_POD        = "kafka-broker-0"       # Kafka Pod 名
KAFKA_NAMESPACE  = "default"              # Kafka 所在 namespace
KAFKA_TOPIC      = "ebpf-net-logs"        # 消费的 topic
BOOTSTRAP_SERVER = "localhost:9092"       # Pod 内访问地址
```

读取方式通过 `kubectl exec` 进入 Kafka Pod 调用 `kafka-console-consumer.sh`，无需在本机安装 Kafka 客户端。



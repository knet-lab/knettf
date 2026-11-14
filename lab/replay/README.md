# traffic_scripts — 流量重放与采集说明

## 目录作用

本目录实现了一套**完整的流量重放 → Kafka 采集**流水线，用于在 knetsentinel 测试环境中还原真实网络流量，并通过 Hubble/Cilium 将采集结果写入 CSV，供后续模型训练或分析使用。

---

## 目录结构

```
traffic_scripts/
├── test set_20000(1).csv     # 原始流量数据集（~20000 条 flow）
├── ip_mapping.json           # 原始 IP → 测试环境 IP 的映射表
├── record_send_uuid.txt      # 发包记录（JSONL），每条 flow/packet 对应 UUID
├── read_result.csv           # Kafka 采集结果输出
├── send.log                  # send_from_csv.py 的运行日志
├── read.log                  # read_kafka.py 的运行日志
├── send.pid                  # 发包进程 PID（由 start_send.sh 写入）
├── send.done                 # 发包完成标记（由 send_from_csv.py 写入）
└── scripts/
    ├── start_send.sh             # 启动发包的后台脚本
    ├── start_read.sh             # 启动 Kafka 采集的后台脚本
    ├── send_requests/
    │   ├── config.py             # 发包配置（接口、路径、参数）
    │   └── send_from_csv.py      # 主发包程序
    └── read_kafka/
        ├── config.py             # 采集配置（Kafka 连接、IP 过滤、输出字段）
        └── read_kafka.py         # Kafka 消费程序
```

---

## 工作流程

```
start_send.sh          start_read.sh
      │                       │
      ▼                       │（等待 send.pid 出现后启动）
send_from_csv.py              ▼
  1. 读取 CSV             read_kafka.py
  2. 绑定 src IP 到         1. 订阅 Kafka topic
     virbr-k8s 网卡         2. 过滤 src_ip 在
  3. 逐 flow 构造包            192.168.100.50-64
     并用 scapy 发送         3. 写入 read_result.csv
  4. 记录 UUID → JSONL      4. 检测到 send.done 后
  5. 写入 send.done →          再排水 15s 后退出
     触发 read 退出
  6. 释放绑定的 IP
```

---

## IP 映射机制

原始 CSV 中的 IP 地址无法直接在测试环境使用，`ip_mapping.json` 将其映射到两类地址：

| 类型 | 地址段 | 说明 |
|------|--------|------|
| **源 IP（normal）** | `192.168.100.50–64` | 动态绑定到 `virbr-k8s` 网卡，发包完成后释放 |
| **目标 IP** | `192.168.100.10–14` | k8s 集群节点（master/node1–4），无需绑定 |

`read_kafka.py` 只采集 `src_ip` 在 `192.168.100.50–64` 范围内的流量，所有采集记录的 `label` 固定为 `0`（normal）。

---

## 使用方法

### 启动发包 + 采集

```bash
# 终端 1：启动发包（需要 root，用于绑定 IP 和发 raw packet）
sudo bash scripts/start_send.sh

# 终端 2：启动 Kafka 采集（无需 root）
bash scripts/start_read.sh
```

两个脚本均通过 `nohup` 后台运行，关闭终端后进程继续。

### 查看进度

```bash
tail -f send.log    # 发包进度
tail -f read.log    # 采集进度
```

### 限制发包数量（调试用）

```bash
sudo bash scripts/start_send.sh --max-packets 10
```

---

## 输出文件

### `record_send_uuid.txt`（JSONL）

每行对应一个 flow，记录发包的完整信息，用于后续与 Kafka 采集结果对齐：

```json
{
  "flow_uuid": "...",
  "csv_row_index": 42,
  "original_src": "10.32.0.2",
  "original_dst": "192.168.2.1",
  "mapped_src": "192.168.100.50",
  "mapped_dst": "192.168.100.10",
  "protocol": "6",
  "src_port": "12345",
  "dst_port": "80",
  "total_packets_csv": 5,
  "total_packets_sent": 5,
  "tcp_flags": "S",
  "packet_uuids": ["...", "..."]
}
```

### `read_result.csv`

Kafka 采集结果，字段：`timestamp`, `verdict`, `direction`, `summary`, `src_ip`, `dst_ip`, `protocol`, `src_port`, `dst_port`, `tcp_flags`, `is_reply`, `trace_reason`, `label`

---

## uv 安装与使用

### 安装 uv

```bash
# Linux / macOS（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装后重新加载 PATH
source ~/.bashrc   # 或 source ~/.zshrc
```

验证安装：

```bash
uv --version
```

---

### 初始化项目虚拟环境

在 `traffic_request/` 目录下初始化（只需执行一次）：

```bash
cd /path/to/traffic_request

# 创建 pyproject.toml 并添加依赖
uv init --no-readme
uv add scapy kafka-python
```

这会在当前目录生成 `pyproject.toml`、`uv.lock` 和 `.venv/`。

---

### 运行脚本

使用 `uv run` 运行脚本，uv 会自动使用项目的虚拟环境，无需手动激活：

```bash
# 运行发包脚本
sudo uv run scripts/send_requests/send_from_csv.py

# 运行 Kafka 采集脚本
uv run scripts/read_kafka/read_kafka.py
```

> `send_from_csv.py` 需要 root 权限（raw socket），`sudo` 时需确保 uv 在 root 的 PATH 中，
> 或改用 `sudo $(which uv) run ...`。

---

### 常用 uv 命令速查

| 命令 | 说明 |
|------|------|
| `uv add <包名>` | 添加依赖并更新 uv.lock |
| `uv remove <包名>` | 移除依赖 |
| `uv sync` | 按 uv.lock 同步环境（换机器后首次运行） |
| `uv run <脚本>` | 在项目环境中运行脚本 |
| `uv pip list` | 查看已安装的包 |
| `uv lock --upgrade` | 升级所有依赖到最新版本 |

---

## 注意事项

- `start_send.sh` 必须以 **root** 运行（raw socket 发包 + `ip addr` 绑定）
- `start_read.sh` 依赖集群内 `kubectl exec` 可用，需提前确认 kubeconfig 配置正确
- 发包结束后 `send.done` 文件会自动出现，`read_kafka.py` 检测到后等待 15 秒排水再退出
- 跳过地址：源 `0.0.0.0`、目标 `255.255.255.255` / `0.0.0.32`（DHCP 广播等无法重放）

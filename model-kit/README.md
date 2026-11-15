# 模型接入包（model-kit）

把你的检测模型接进 NetSentinel 平台，只需要写一个 Python 类。
这个文件夹在你自己的电脑上就能跑，**不需要 Django、数据库或集群**。

```
model-kit/
├── README.md                  ← 本说明
├── my_model.py                ← 模型模板：复制它，改成你的模型
├── try_my_model.py            ← 自测脚本：检查接口 + 在数据上跑一遍
├── base.py                    ← 平台接口定义（副本，不要改）
├── export_flows.py            ← 从平台导出数据（在服务器上由我们运行）
└── data/
    └── normal_baseline_sample.csv   ← 我们环境里的正常流量样本（35 个特征）
```

---

## 1. 平台在做什么（一张图）

```
K8s 集群里的真实流量
  → eBPF（Cilium）在每个节点抓包
  → Kafka
  → 平台把包切成“流”，算出 35 个特征      ← 我们负责
  → 你的模型：predict(一条流) → 是否攻击      ← 你负责
  → 结果存库，显示在 knettf.com/vigil
```

**你只需要关心中间那一步：输入一条流的 35 个特征，输出判断结果。**

---

## 2. 一条“流”是什么

一条流 = **一对端点之间的一次完整通信**（例如浏览器连一次网站：握手 → 请求 → 响应 → 关闭）。

- **双向**：请求和回包在同一条流里。
- **方向**：`src` 是发起连接的一方（客户端），`dst` 是被连接的一方（服务端）。正向 `fwd` = 客户端发出的包，反向 `bwd` = 服务端发出的包。
- **什么时候结束**：TCP 关闭（FIN/RST）时立即结束；否则 60 秒没有新包结束；长连接每 120 秒切一段。
  （与 CICFlowMeter 的做法一致）

---

## 3. 输入：35 个特征

模型拿到的 `flow` 对象，每个特征都是一个属性：`flow.flow_duration`、`flow.syn_count` …

| # | 特征 | 类型 | 单位 / 含义 |
|---|---|---|---|
| 1–2 | `src_ip`, `dst_ip` | str | 客户端 IP、服务端 IP |
| 3 | `protocol` | str | **`"TCP"` / `"UDP"` / `"ICMPv4"` / `"ICMPv6"`（文字，不是协议号 6/17）** |
| 4–5 | `src_port`, `dst_port` | int | 客户端端口、服务端端口 |
| 6 | `flow_duration` | float | **微秒**：末包时间 − 首包时间 |
| 7 | `total_packets` | int | 总包数 |
| 8–9 | `fwd_packets`, `bwd_packets` | int | 客户端发出的包数、服务端发出的包数 |
| 10 | `fwd_ratio` | float | fwd / total |
| 11 | `packets_per_second` | float | **每秒**包数 |
| 12–15 | `iat_mean`, `iat_std`, `iat_min`, `iat_max` | float | **微秒**：相邻两个包的时间间隔统计；只有 1 个包时为 0 |
| 16–21 | `syn_count` … `urg_count` | int | 带该 TCP 标志的包数（SYN/ACK/FIN/RST/PSH/URG） |
| 22–25 | `syn_ratio` … `rst_ratio` | float | 上面的计数 / total |
| 26–27 | `reply_count`, `reply_ratio` | int / float | Cilium 标记为“回包”的包数及比例 |
| 28–30 | `forwarded_count`, `drop_count`, `drop_ratio` | int / float | 被网络策略放行 / 丢弃的包数 |
| 31 | `is_bidirectional` | 0/1 | 双方都发过包 |
| 32–34 | `is_tcp`, `is_udp`, `is_icmp` | 0/1 | 协议 |
| 35 | `is_well_known_port` | 0/1 | dst_port < 1024 |
| — | `label` | str | 只在数据集里有：`"0"` 正常 / `"1"` 攻击 / `""` 未知。**推理时不要用它** |

**采不到的特征**：eBPF（Hubble）里没有包长，所以**没有字节数**相关特征；也没有应用层内容（HTTP、DNS、TLS）。

---

## 4. 输出：DetectionResult

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `model_name` | ✓ | str | 和 `name` 一致 |
| `is_attack` | ✓ | bool | 是否攻击 |
| `confidence` | ✓ | float | 0.0 ~ 1.0 |
| `attack_type` | | str / None | 攻击类型名，正常时为 `None` |
| `raw_output` | | dict | 想保存的中间结果（存进数据库，**必须能转成 JSON**） |
| `explanation` | | str | 一句话说明，显示在页面上 |

> ⚠️ 常见错误：`is_attack` 用了 `numpy.bool_`、`confidence` 用了 `numpy.float64`。请用 `bool(...)`、`float(...)` 转一下。自测脚本会检查出来。

---

## 5. 接入步骤

### 第 1 步：写模型

复制 `my_model.py`，按 `TODO` 改：
- `name`：模型名（英文、无空格，例如 `zsl_ocsvm_v2`）
- `__init__`：从 `model_dir` 加载模型文件（只加载一次）
- `predict`：一条流 → `DetectionResult`

### 第 2 步：本地自测

```bash
python try_my_model.py --model my_model.py:MyModel --model-dir ./my_model_files
```

它会：
1. **检查接口**（和平台上线前的检查规则相同）；
2. 在 `data/normal_baseline_sample.csv` 上跑一遍，告诉你判为攻击的比例、耗时，有标签时算准确率。

也可以用 `--data 你的数据.csv` 换成自己的数据（列名和上面的特征表一致即可）。

### 第 3 步：交给我们

发给我们三样东西：
1. 你的模型文件，例如 `my_model.py`；
2. 模型资源目录，例如 `my_model_files/`（.joblib / .pt 等）；
3. 依赖说明：用到了哪些库、什么版本。

**平台环境**：Python 3.12，scikit-learn 1.7.2，numpy 2.4，pandas 3.0，joblib 1.5（没有 torch，需要的话告诉我们）。
**请用相同版本的 scikit-learn 保存模型**，不同版本的 joblib 文件可能加载失败。

我们负责上线：代码放进 `apps/backend/vigil/detection/`，模型文件放到服务器的 `/srv/netsentinel/models/`，在配置里登记后重启。多个模型可以同时运行，页面上分别显示结果。

---

## 6. 数据

- `data/normal_baseline_sample.csv`：我们实验环境里的**正常流量**（`label=0`）。
  - 来源：Online Boutique 电商演示应用（11 个微服务）+ 10 个仿真外部客户端（不同网络延迟）
  - `kind` 列：`ns` = 外部客户端 → 集群；`ew` = 集群内服务之间
  - 已知：约 1/4 的 `ew` 流只有 1 个包、没有回包（长连接上的零星包），训练时可以按需过滤（`total_packets > 1`）
- 需要更多数据（更长时间、只要某一类）时告诉我们，我们在服务器上用 `export_flows.py` 导出。

---

## 7. 需要和你确认的事

现在部署的模型（`ads_ml_ocsvm`）在上面的正常数据上**几乎全部判为攻击**。我们查过采集和切流，认为原因在训练数据与我们环境的差异。请帮忙确认：

1. **protocol**：模型的编码器只认 `'0' / '6' / '17'`，平台送的是 `"TCP"`。哪个是对的？
2. **IP 特征**：模型对 `src_ip` / `dst_ip` 做了编码，只认识训练时的几个地址。换了环境就全是“未知”。能否去掉 IP 特征重新训练？
3. **训练数据**：能否提供降维（PCA）之前的原始 35 特征训练数据？以及它是在什么环境、用什么超时切的流？
4. **时间单位**：我们按微秒输出 `flow_duration` 和 `iat_*`，和你的训练数据一致吗？
5. **用我们的正常数据重新训练**：样本已在 `data/` 里，可以先试试。

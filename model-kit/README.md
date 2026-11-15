# 模型接入指南（model-kit）

这份指南说明：检测模型怎么写、怎么测试、代码和模型文件放在哪里、怎么上线到平台、怎么更新和回滚。

平台对模型只有一个要求：**写一个 Python 类，输入一条流的 35 个特征，输出判断结果。**
平台的采集、切流、存库、页面展示都已经做好，不需要改。

```
model-kit/
├── README.md                    ← 本指南
├── my_model.py                  ← 模型模板：复制并改写
├── try_my_model.py              ← 自测：检查接口 + 在数据上跑一遍
├── base.py                      ← 平台接口定义（副本，不要改）
├── export_flows.py              ← 从平台数据库导出更多数据
└── data/normal_baseline_sample.csv   ← 实验环境的正常流量样本
```

---

## 1. 平台怎么调用模型

```
K8s 实验集群里的流量
  → eBPF（Cilium/Hubble）在每个节点抓包 → Kafka
  → 平台后端把包切成“流”，算出 35 个特征
  → 依次调用每个已登记的模型：model.predict(一条流)
  → 结果存入数据库，显示在网站的 /vigil 页面
```

- 平台启动时加载模型（只加载一次），之后每来一条流就调用一次 `predict`（或批量调用 `predict_batch`）。
- 可以同时登记多个模型，页面上分别显示每个模型的结果。

---

## 2. 一条“流”是什么

一条流 = **一对端点之间的一次完整通信**（例如浏览器访问一次网站：握手 → 请求 → 响应 → 关闭）。

- **双向**：请求和回包在同一条流里。
- **方向**：`src` 是发起连接的一方（客户端），`dst` 是被连接的一方（服务端）。`fwd` = 客户端发出的包，`bwd` = 服务端发出的包。
- **结束时机**：RST 立即结束；双方都发过 FIN 后，收下挥手最后的 ACK 再结束（最多等 2 秒）；60 秒没有新包时结束；长连接每 120 秒切一段。
  原版 CICFlowMeter 在 FIN 处就切流，挥手尾包会变成大量单包流（已知缺陷）；这里按 Zeek 的做法把尾包留在原连接里。

---

## 3. 输入：35 个特征

`predict(flow)` 里，每个特征都是 `flow` 的属性，例如 `flow.flow_duration`、`flow.syn_count`。

| # | 特征 | 类型 | 单位 / 含义 |
|---|---|---|---|
| 1–2 | `src_ip`, `dst_ip` | str | 客户端 IP、服务端 IP |
| 3 | `protocol` | str | **`"TCP"` / `"UDP"` / `"ICMPv4"` / `"ICMPv6"`（文字，不是协议号 6/17）** |
| 4–5 | `src_port`, `dst_port` | int | 客户端端口、服务端端口（ICMP 为 0） |
| 6 | `flow_duration` | float | **微秒**：末包时间 − 首包时间 |
| 7 | `total_packets` | int | 总包数 |
| 8–9 | `fwd_packets`, `bwd_packets` | int | 客户端发出的包数、服务端发出的包数 |
| 10 | `fwd_ratio` | float | fwd / total |
| 11 | `packets_per_second` | float | **每秒**包数 |
| 12–15 | `iat_mean`, `iat_std`, `iat_min`, `iat_max` | float | **微秒**：相邻两包的时间间隔；只有 1 个包时为 0 |
| 16–21 | `syn_count` … `urg_count` | int | 带该 TCP 标志的包数（SYN/ACK/FIN/RST/PSH/URG） |
| 22–25 | `syn_ratio` … `rst_ratio` | float | 上面的计数 / total |
| 26–27 | `reply_count`, `reply_ratio` | int / float | Cilium 标记为“回包”的包数及比例 |
| 28–30 | `forwarded_count`, `drop_count`, `drop_ratio` | int / float | 被网络策略放行 / 丢弃的包数 |
| 31 | `is_bidirectional` | 0/1 | 双方都发过包 |
| 32–34 | `is_tcp`, `is_udp`, `is_icmp` | 0/1 | 协议 |
| 35 | `is_well_known_port` | 0/1 | dst_port < 1024 |
| — | `label` | str | 只在数据集里有：`"0"` 正常 / `"1"` 攻击 / `""` 未知。**推理时不要使用** |

**采集不到的信息**：eBPF（Hubble）不提供包长，所以没有字节数相关特征；也没有应用层内容（HTTP、DNS、TLS）。

---

## 4. 输出：DetectionResult

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `model_name` | ✓ | str | 与 `name` 一致 |
| `is_attack` | ✓ | bool | 是否攻击 |
| `confidence` | ✓ | float | 0.0 ~ 1.0 |
| `attack_type` | | str / None | 攻击类型名；正常时为 `None` |
| `raw_output` | | dict | 想保存的中间结果，存入数据库，**必须能转成 JSON** |
| `explanation` | | str | 一句话说明，显示在页面上 |

> ⚠️ 常见错误：`is_attack` 是 `numpy.bool_`、`confidence` 是 `numpy.float64`。用 `bool(...)`、`float(...)` 转换。自测脚本会检查出来。

---

## 5. 开发：写模型并自测

这一步不需要平台、数据库或集群，任何装了 Python 3.12 的电脑都可以。

**① 复制模板**

```bash
cp my_model.py zsl_ocsvm.py        # 文件名 = 模型模块名，用小写英文和下划线
```

**② 改写模板里标了 `TODO` 的地方**

| 位置 | 改成什么 |
|---|---|
| 类名 `MyModel` | 例如 `ZslOcsvmModel` |
| `MODEL_DIR_ENV` | 模型目录的环境变量名，例如 `ZSL_OCSVM_DIR` |
| `name` | 模型名，例如 `zsl_ocsvm_v2`（页面上显示这个名字） |
| `__init__` | 从 `self.model_dir` 加载模型文件 |
| `predict` | 一条流 → `DetectionResult` |

**③ 把模型文件放进一个目录**，例如 `./zsl_ocsvm_files/`（`.joblib`、`.pt`、配置文件等）。

**④ 自测**

```bash
python try_my_model.py --model zsl_ocsvm.py:ZslOcsvmModel --model-dir ./zsl_ocsvm_files
python try_my_model.py --model zsl_ocsvm.py:ZslOcsvmModel --model-dir ./zsl_ocsvm_files --data 其他数据.csv
```

输出：
1. **接口检查**：与平台上线前的检查规则相同。必须显示 `✓ 通过`。
2. **运行结果**：判为攻击的比例、每条耗时；数据有 `label` 列时给出准确率；按南北向 / 东西向分别统计。

**版本要求**：平台使用 Python 3.12、scikit-learn 1.7.2、numpy 2.4、pandas 3.0、joblib 1.5（没有 torch）。**用相同版本的 scikit-learn 保存模型**，否则 joblib 文件在平台上可能加载失败。

---

## 6. 上线：放进平台

以下操作在平台所在的服务器上进行。路径中的占位符：

| 占位符 | 含义 | 当前的值（迁移后以实际为准，见 `docs/HANDOVER.md`） |
|---|---|---|
| `<仓库>` | 开发目录（git clone 的位置） | 例如 `~/github/knettf` |
| `<部署目录>` | 线上运行的代码 | `/srv/netsentinel/prod` |
| `<模型目录>` | 存放模型文件的位置 | `/srv/netsentinel/models` |
| `<服务>` | 后端的 systemd 服务名 | `netsentinel.service` |

**前提**：Linux 账户加入服务账户的用户组（当前为 `netsentinel` 组），才能写模型目录、改线上配置、重启服务。

### ① 放代码（通过 GitHub PR）

```bash
cd <仓库>
git checkout -b model/zsl-ocsvm
cp <model-kit 工作目录>/zsl_ocsvm.py apps/backend/vigil/detection/zsl_ocsvm.py
```

- 代码放在 `apps/backend/vigil/detection/` 下。模板里的导入语句在平台里会自动使用平台的接口，不需要改。
- 需要新的 Python 库时：在 `<仓库>` 根目录运行 `uv add 库名==版本`，会更新 `pyproject.toml` 和 `uv.lock`。
- **模型文件不要放进 Git。**

在开发目录里做上线前检查：

```bash
cd <仓库>/apps/backend
ZSL_OCSVM_DIR=/path/to/zsl_ocsvm_files \
  ../../.venv/bin/python manage.py check_model --model vigil.detection.zsl_ocsvm.ZslOcsvmModel
```

显示 `✓` 后提交，开 Pull Request。CI 检查通过、合并到 `main` 后，**平台会在几分钟内自动部署新代码**（不需要手动拉代码）。

### ② 放模型文件

每个版本一个目录，用 `current` 链接指向正在使用的版本，方便切换和回滚：

```bash
mkdir -p <模型目录>/zsl_ocsvm/v1-20261201
cp -r ./zsl_ocsvm_files/* <模型目录>/zsl_ocsvm/v1-20261201/
ln -sfn v1-20261201 <模型目录>/zsl_ocsvm/current
```

### ③ 登记模型

编辑线上配置文件 `<部署目录>/apps/backend/backend/.env`，加入两行：

```bash
# 模型目录（变量名与 MODEL_DIR_ENV 一致）
ZSL_OCSVM_DIR=<模型目录>/zsl_ocsvm/current
# 要加载的模型，逗号分隔。保留原模型就把它也写上；只写新模型则只运行新模型
VIGIL_MODELS=vigil.detection.ads_ml.AdsMLModel,vigil.detection.zsl_ocsvm.ZslOcsvmModel
```

### ④ 线上检查，然后重启

```bash
cd <部署目录>/apps/backend
../../.venv/bin/python manage.py check_model          # 检查 .env 里登记的全部模型，必须全部 ✓
sudo systemctl restart <服务>
```

### ⑤ 确认生效

- 打开网站的 `/vigil` 页面，几分钟内应出现新模型名的检测记录。
- 没有出现时查看日志：`sudo journalctl -u <服务> -n 100 | grep -i model`。加载失败会显示 `model ... not loaded: 原因`，失败的模型不会影响平台其他部分。

---

## 7. 更新与回滚

| 操作 | 步骤 |
|---|---|
| **只换模型文件**（代码不变） | 新建 `<模型目录>/zsl_ocsvm/v2-日期/` 并放入文件 → `ln -sfn v2-日期 <模型目录>/zsl_ocsvm/current` → 重启服务 |
| **回滚模型文件** | `ln -sfn v1-日期 <模型目录>/zsl_ocsvm/current` → 重启服务 |
| **改模型代码** | 按第 6 节 ① 提交 PR，合并后自动部署 |
| **停用某个模型** | 从 `.env` 的 `VIGIL_MODELS` 里删掉 → 重启服务 |

---

## 8. 开发时的注意事项

平台、实验集群和开发环境运行在**同一台服务器**上：

- 在开发目录运行 `manage.py`，默认连接的是**线上数据库**。只做查询，不要写入或删除。
- 在开发目录启动后端（`manage.py runserver 8090`）前，确认 `<仓库>/apps/backend/backend/.env` 里有 `VIGIL_KAFKA_GROUP_ID=vigil-bridge-dev`，否则会和线上抢数据。
- 不要占用 8080 端口（线上服务）。
- 大量训练会和实验集群抢 CPU，影响采集到的时间特征。采集数据期间不要训练，或者限制训练使用的 CPU 核数。

---

## 9. 数据

### 现成的样本

`data/normal_baseline_sample.csv`：实验环境里的**正常流量**（`label=0`）。

- 来源：Online Boutique 电商演示应用（11 个微服务）+ 10 个仿真外部客户端（不同网络延迟）
- `kind` 列：`ns` = 外部客户端 → 集群；`ew` = 集群内服务之间
- 采集时间：2026-11-15 22:39–23:02（KST），共 8387 条；修复跨节点包重复计数之后导出，之前版本的样本已作废
- 已知：约 30% 的 `ew` 流只有 1 个包、没有回包（长连接上的零星包），训练时可以按需过滤（`total_packets > 1`）

### 导出更多数据

```bash
cd <部署目录>/apps/backend
../../.venv/bin/python <仓库>/model-kit/export_flows.py \
    --since "2026-12-01 09:00" --until "2026-12-01 18:00" --label 0 --kind all --out ~/flows.csv
```

- `--label`：只在确定这段时间里只有正常流量（`0`）或只有攻击流量（`1`）时使用。
- `--kind`：`ns` / `ew` / `all`。
- 只读，不会修改数据库。

### 产生流量

- 正常流量：`lab/cluster/04-deploy-baseline.sh`（集群内）和 `lab/traffic/client-zone.sh`（仿真外部客户端，需要 sudo）。详见 `lab/README.md`。

---

## 10. 现有模型的已知问题

现有模型 `ads_ml_ocsvm` 在上面的正常数据上**几乎全部判为攻击**。采集和切流已经检查过，问题来自训练数据和实验环境的差异：

1. **protocol**：模型的编码器只认 `'0' / '6' / '17'`，平台输入的是 `"TCP"`。
2. **IP 特征**：模型对 `src_ip` / `dst_ip` 做了编码，只认识训练时的几个地址，换环境后全部变成“未知”。建议去掉 IP 特征。
3. **训练数据**：TON_IoT 版本的测试集与训练集是同一份；eBPF 版本的训练数据里，正常流量和攻击流量只靠 IP / 端口就能区分。
4. **时间单位**：平台输出的 `flow_duration`、`iat_*` 是微秒，训练数据需要使用同样的单位。

建议用 `data/` 里的正常数据（以及第 9 节导出的更多数据）重新训练，并在训练集以外的数据上评估。

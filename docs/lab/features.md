# 特征对比：聚合前 vs 聚合后

## 聚合前（packet 级别）— 8 个 ML 特征

来源：`kafka_read_csv.py` → `dataset.csv`，每行 = 一个包事件

| 字段 | 说明 |
|------|------|
| `timestamp` | 包事件发生时间 |
| `src_ip` | 源 IP 地址 |
| `dst_ip` | 目标 IP 地址 |
| `src_port` | 源端口 |
| `dst_port` | 目标端口 |
| `protocol` | 协议类型（TCP / UDP / ICMP） |
| `verdict` | Cilium 对这个包的判决：放行还是丢弃 |
| `direction` | 包的方向：进来（INGRESS）还是出去（EGRESS） |
| `tcp_flags` | 这个包携带的 TCP 标志位（SYN/ACK/FIN 等） |
| `is_reply` | 这个包是否是对方的回包 |
| `trace_reason` | Cilium 记录这个包的原因（策略命中、新连接等） |
| `summary` | Hubble 描述文本（如 "TCP Flags: SYN"） |
| `label` | 0=正常 / 1=攻击 |

---

## 聚合后（flow 级别）— 30 个 ML 特征

来源：`aggregate_flows.py` → `flows.csv`，每行 = 一条连接的统计汇总

| 类别 | 特征 | 说明 |
|------|------|------|
| 五元组 | `src_ip` | 源 IP 地址 |
| | `dst_ip` | 目标 IP 地址 |
| | `src_port` | 源端口 |
| | `dst_port` | 目标端口 |
| | `protocol` | 协议类型（TCP / UDP / ICMP） |
| 时间 | `flow_duration` | 这条流从第一个包到最后一个包经过了多少秒 |
| 包数量/速率 | `total_packets` | 这条流一共抓到多少个包 |
| | `fwd_packets` | 其中正向（INGRESS）有多少个 |
| | `bwd_packets` | 其中反向（EGRESS）有多少个 |
| | `fwd_ratio` | 正向包占总包数的比例 |
| | `packets_per_second` | 每秒平均发了多少个包（速率） |
| IAT | `iat_mean` | 相邻两个包之间的平均间隔时间 |
| | `iat_std` | 包间隔的波动程度（越小说明越均匀，典型 flood 特征） |
| | `iat_min` | 最短的包间隔 |
| | `iat_max` | 最长的包间隔 |
| TCP Flags 计数 | `syn_count` | 这条流里 SYN 包的数量 |
| | `ack_count` | ACK 包的数量 |
| | `fin_count` | FIN 包的数量（正常关闭连接） |
| | `rst_count` | RST 包的数量（强制断开） |
| | `psh_count` | PSH 包的数量（携带数据） |
| | `urg_count` | URG 包的数量（紧急数据，正常流量极少） |
| TCP Flags 比例 | `syn_ratio` | SYN 占所有包的比例（SYN flood 时接近 1.0） |
| | `ack_ratio` | ACK 占比 |
| | `fin_ratio` | FIN 占比 |
| | `rst_ratio` | RST 占比 |
| 回复 | `reply_count` | 收到对方回包的次数 |
| | `reply_ratio` | 回包比例（SYN flood 时几乎为 0，因为目标无法响应） |
| 判决 | `forwarded_count` | 被 Cilium 放行的包数 |
| | `drop_count` | 被 Cilium 丢弃的包数 |
| | `drop_ratio` | 丢弃比例 |
| 方向 | `is_bidirectional` | 是否存在双向通信（只有单向说明对方没有响应） |
| 协议 | `is_tcp` | 是否是 TCP 流量 |
| | `is_udp` | 是否是 UDP 流量 |
| | `is_icmp` | 是否是 ICMP 流量 |
| 端口 | `is_well_known_port` | 目标端口是否小于 1024（知名服务端口） |

---

## 对比

| | 聚合前 | 聚合后 |
|---|---|---|
| 粒度 | 包级别 | 流级别 |
| ML 特征数 | 8 | 30 |
| 时序信息 | 无 | 有（IAT、速率、duration）|
| 缺失 | 包大小、速率、持续时间 | 包大小（Hubble 不提供） |

# 捕获样例

```
[2026-04-23 02:04:02 KST] FORWARDED | INGRESS | TCP |  | node=k8s-master
  192.168.100.20:12345  ->  192.168.100.10:6443  flags={'SYN': True}  is_reply=False
  src: ns=None  pod=None  svc=None
  dst: ns=None  pod=None  svc=None
  summary: TCP Flags: SYN

[2026-04-23 02:05:28 KST] FORWARDED | INGRESS | TCP |  | node=k8s-node4
  192.168.100.29:12345  ->  192.168.100.14:80  flags={'SYN': True}  is_reply=False
  src: ns=None  pod=None  svc=None
  dst: ns=None  pod=None  svc=None
  summary: TCP
```

---

# 通用网络特征（11个）

| 字段 | OSI 层 | 说明 | 示例值 |
|---|---|---|---|
| `timestamp` | 元数据 | 事件捕获时间 | `2026-04-23 02:05:28 KST` |
| `verdict` | 元数据 | 策略执行结果（FORWARDED / DROPPED） | `FORWARDED` |
| `direction` | 元数据 | 流量方向（INGRESS / EGRESS） | `INGRESS` |
| `summary` | 元数据 | 协议摘要 | `TCP Flags: SYN` |
| `src_ip` | L3 | 源 IP 地址 | `192.168.100.20` |
| `dst_ip` | L3 | 目标 IP 地址 | `192.168.100.10` |
| `protocol` | L4 | 传输层协议 | `TCP` |
| `src_port` | L4 | 源端口 | `12345` |
| `dst_port` | L4 | 目标端口 | `6443` |
| `tcp_flags` | L4 | TCP 标志位 | `{'SYN': True}` |
| `is_reply` | L4 | 是否为回包 | `False` |

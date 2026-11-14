"""
kafka_read.py  —  消费 ebpf-net-logs，打印并筛选 Hubble 原始流量事件

筛选条件（可组合，不填则不限制）：
  --verdict    FORWARDED | DROPPED | ...
  --direction  INGRESS | EGRESS
  --protocol   TCP | UDP | ICMPv4 | ICMPv6
  --src        源 IP 前缀，如 10.0.1
  --dst        目标 IP 前缀
  --src-ns     源 namespace
  --dst-ns     目标 namespace
  --src-pod    源 pod 名（子串匹配）
  --dst-pod    目标 pod 名（子串匹配）
  --node       节点名（子串匹配）
  --drop-only  只看 DROPPED 流量（等价于 --verdict DROPPED）
  -n           最多读取 N 条消息（默认无限）
"""

import subprocess
import json
import sys
import argparse
from datetime import datetime, timezone


KAFKA_POD        = "kafka-broker-0"
KAFKA_NAMESPACE  = "default"
KAFKA_TOPIC      = "ebpf-net-logs"
BOOTSTRAP_SERVER = "localhost:9092"


def get_protocol(l4: dict) -> str:
    if "TCP"    in l4: return "TCP"
    if "UDP"    in l4: return "UDP"
    if "ICMPv4" in l4: return "ICMPv4"
    if "ICMPv6" in l4: return "ICMPv6"
    return "OTHER"


def get_port(l4: dict, side: str) -> int | None:
    """side: 'source_port' or 'destination_port'"""
    for proto in ("TCP", "UDP"):
        if proto in l4 and side in l4[proto]:
            return l4[proto][side]
    return None


def matches(flow: dict, args: argparse.Namespace) -> bool:
    verdict   = flow.get("verdict", "")
    direction = flow.get("traffic_direction", "")
    l4        = flow.get("l4", {})
    protocol  = get_protocol(l4)
    src_ip    = flow.get("IP", {}).get("source", "")
    dst_ip    = flow.get("IP", {}).get("destination", "")
    src_ns    = flow.get("source", {}).get("namespace", "") or ""
    dst_ns    = flow.get("destination", {}).get("namespace", "") or ""
    src_pod   = flow.get("source", {}).get("pod_name", "") or ""
    dst_pod   = flow.get("destination", {}).get("pod_name", "") or ""
    node      = flow.get("node_name", "") or ""

    if args.drop_only and verdict != "DROPPED":
        return False
    if args.verdict   and verdict   != args.verdict:
        return False
    if args.direction and direction != args.direction:
        return False
    if args.protocol  and protocol  != args.protocol:
        return False
    if args.src       and not src_ip.startswith(args.src):
        return False
    if args.dst       and not dst_ip.startswith(args.dst):
        return False
    if args.src_ns    and args.src_ns not in src_ns:
        return False
    if args.dst_ns    and args.dst_ns not in dst_ns:
        return False
    if args.src_pod   and args.src_pod not in src_pod:
        return False
    if args.dst_pod   and args.dst_pod not in dst_pod:
        return False
    if args.node      and args.node not in node:
        return False
    return True


def fmt_ts(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_str


def print_flow(event: dict, flow: dict):
    ts        = fmt_ts(flow.get("time", ""))
    verdict   = flow.get("verdict", "")
    direction = flow.get("traffic_direction", "")
    node      = flow.get("node_name") or event.get("node_name", "")
    l4        = flow.get("l4", {})
    protocol  = get_protocol(l4)
    src_ip    = flow.get("IP", {}).get("source", "")
    dst_ip    = flow.get("IP", {}).get("destination", "")
    src_port  = get_port(l4, "source_port")
    dst_port  = get_port(l4, "destination_port")
    src_ns    = flow.get("source", {}).get("namespace")
    src_pod   = flow.get("source", {}).get("pod_name")
    dst_ns    = flow.get("destination", {}).get("namespace")
    dst_pod   = flow.get("destination", {}).get("pod_name")
    src_svc   = (flow.get("source_service") or {}).get("name")
    dst_svc   = (flow.get("destination_service") or {}).get("name")
    iface     = (flow.get("interface") or {}).get("name")
    trace_pt  = flow.get("trace_observation_point", "")
    trace_rsn = flow.get("trace_reason", "")
    is_reply  = flow.get("is_reply")
    drop_rsn  = flow.get("drop_reason_desc") or flow.get("drop_reason")
    summary   = flow.get("Summary", "")
    tcp_flags = (l4.get("TCP") or {}).get("flags")

    print(
        f"[{ts}] {verdict} | {direction} | {protocol} | {trace_pt} | node={node}\n"
        f"  {src_ip}:{src_port}  ->  {dst_ip}:{dst_port}"
        + (f"  flags={tcp_flags}" if tcp_flags else "")
        + (f"  is_reply={is_reply}" if is_reply is not None else "") + "\n"
        f"  src: ns={src_ns}  pod={src_pod}  svc={src_svc}\n"
        f"  dst: ns={dst_ns}  pod={dst_pod}  svc={dst_svc}\n"
        + (f"  iface={iface}  trace_reason={trace_rsn}\n" if iface or trace_rsn else "")
        + (f"  DROP: {drop_rsn}\n" if drop_rsn else "")
        + (f"  summary: {summary}\n" if summary else "")
    )


def consume(args: argparse.Namespace):
    cmd = [
        "kubectl", "exec", "-n", KAFKA_NAMESPACE, KAFKA_POD, "--",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP_SERVER,
        "--topic", KAFKA_TOPIC,
    ]
    if args.from_beginning:
        cmd.append("--from-beginning")
    if args.n:
        cmd += ["--max-messages", str(args.n)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    count = 0
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                flow  = event.get("flow", {})
                if not flow:
                    continue
                if matches(flow, args):
                    print_flow(event, flow)
                    count += 1
            except json.JSONDecodeError as e:
                print(f"[parse error] {e} | {line[:120]}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait()
        print(f"\n--- {count} flow(s) printed ---")


def main():
    p = argparse.ArgumentParser(description="Hubble flow consumer from Kafka")
    p.add_argument("--verdict",    help="FORWARDED | DROPPED | ...")
    p.add_argument("--direction",  help="INGRESS | EGRESS")
    p.add_argument("--protocol",   help="TCP | UDP | ICMPv4 | ICMPv6")
    p.add_argument("--src",        help="源 IP 前缀")
    p.add_argument("--dst",        help="目标 IP 前缀")
    p.add_argument("--src-ns",     dest="src_ns",  help="源 namespace（子串）")
    p.add_argument("--dst-ns",     dest="dst_ns",  help="目标 namespace（子串）")
    p.add_argument("--src-pod",    dest="src_pod", help="源 pod 名（子串）")
    p.add_argument("--dst-pod",    dest="dst_pod", help="目标 pod 名（子串）")
    p.add_argument("--node",       help="节点名（子串）")
    p.add_argument("--drop-only",      dest="drop_only",      action="store_true", help="只看 DROPPED")
    p.add_argument("--from-beginning", dest="from_beginning", action="store_true", help="从头读取历史消息")
    p.add_argument("-n",               type=int, help="最多读取 N 条消息")
    args = p.parse_args()

    print(f"Topic: {KAFKA_TOPIC}  |  Pod: {KAFKA_NAMESPACE}/{KAFKA_POD}")
    print(f"Filter: verdict={args.verdict}  direction={args.direction}  "
          f"protocol={args.protocol}  src={args.src}  dst={args.dst}  "
          f"drop_only={args.drop_only}\n")
    consume(args)


if __name__ == "__main__":
    main()

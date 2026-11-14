# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""monitor.py — simulate send.log + 后端检测记录对比

NetSentinel 后端已移除 ws/vigil/ 推送，改为轮询 GET /api/vigil/records/（JWT 认证）。
"""

import argparse
import csv
import json
import pathlib
import signal
import threading
import time
from collections import defaultdict
from datetime import datetime

import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import timezone

BACKEND    = os.environ.get("NETSENTINEL_BACKEND", "http://localhost:8080")
RECORDS_API = "/api/vigil/records/"
POLL_INTERVAL = 1.0
REPORT_DIR = pathlib.Path(__file__).parent
IDLE_STOP  = 5   # simulate 停发后等待秒数

MODES = {
    1: {"label": "正常流量",   "script": "simulate_1.py"},
    2: {"label": "混合流量",   "script": "simulate_2.py"},
    3: {"label": "全攻击流量", "script": "simulate_3.py"},
}


class State:
    def __init__(self):
        self.lock     = threading.Lock()
        self.sends:   list[dict] = []
        self.results: list[dict] = []
        self.seen_ids: set       = set()
        self.t0 = time.time()


# ── Tail 线程 ──────────────────────────────────────────────────────────────

def tail_thread(log_path: pathlib.Path, state: State, stop: threading.Event):
    while not log_path.exists():
        if stop.is_set():
            return
        time.sleep(0.3)

    last_ts = time.time()
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        while not stop.is_set():
            line = f.readline()
            if not line:
                if time.time() - last_ts >= IDLE_STOP:
                    print(f"\n[monitor] simulate 已停发，自动结束", flush=True)
                    stop.set()
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line.startswith("SEND|"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            try:
                with state.lock:
                    state.sends.append({
                        "ground":      parts[1],
                        "src_ip":      parts[2],
                        "dst_ip":      parts[3],
                        "dst_port":    int(parts[4]),
                        "attack_type": parts[5],
                        "ts":          float(parts[6]),
                    })
                last_ts = time.time()
            except (ValueError, IndexError):
                continue


# ── 轮询线程 ──────────────────────────────────────────────────────────────

def _fetch(backend: str, token: str, params: dict) -> dict:
    url = backend.rstrip("/") + RECORDS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["data"]


def _add_record(state: State, rec: dict) -> None:
    rid = rec.get("id")
    if rid in state.seen_ids:
        return
    state.seen_ids.add(rid)
    state.results.append({
        "src_ip":      rec.get("src_ip", ""),
        "dst_ip":      rec.get("dst_ip", ""),
        "dst_port":    int(rec.get("dst_port") or 0),
        "is_attack":   bool(rec.get("is_attack")),
        "attack_type": rec.get("attack_type") or "",
        "confidence":  float(rec.get("confidence") or 0.0),
        "agg_ms":      rec.get("aggregation_ms"),
        "inf_ms":      rec.get("inference_ms"),
        "created_at":  rec.get("created_at", ""),
        "ts":          time.time(),
    })


def poll_once(state: State, backend: str, token: str, time_from: str) -> None:
    offset = 0
    while True:
        data = _fetch(backend, token, {"time_from": time_from, "limit": 500, "offset": offset})
        recs = data.get("records", [])
        with state.lock:
            for rec in recs:
                _add_record(state, rec)
        offset += len(recs)
        if not recs or offset >= data.get("total", 0):
            break


def poll_thread(state: State, stop: threading.Event, backend: str, token: str, time_from: str):
    first_err = True
    while not stop.is_set():
        try:
            poll_once(state, backend, token, time_from)
            first_err = True
            print(f"  [API] 已收 {len(state.results)} 条  {int(time.time()-state.t0)}s", end="\r", flush=True)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            if first_err:
                print(f"[monitor] 拉取检测记录失败: {e}", flush=True)
                first_err = False
        stop.wait(POLL_INTERVAL)


# ── 报告 ───────────────────────────────────────────────────────────────────

def _ground_maps(sends):
    fc: dict = defaultdict(lambda: {"attack": 0, "normal": 0})
    ic: dict = defaultdict(lambda: {"attack": 0, "normal": 0})
    for s in sends:
        g = s["ground"]
        if g not in ("attack", "normal"):
            continue
        fc[(s["src_ip"], s["dst_ip"], s["dst_port"])][g] += 1
        ic[s["src_ip"]][g] += 1
    flow_g = {k: ("attack" if v["attack"] >= v["normal"] else "normal") for k, v in fc.items()}
    ip_g   = {k: ("attack" if v["attack"] >= v["normal"] else "normal") for k, v in ic.items()}
    return flow_g, ip_g


def _lookup(r, flow_g, ip_g):
    return flow_g.get((r["src_ip"], r["dst_ip"], r["dst_port"])) \
        or ip_g.get(r["src_ip"], "unknown")


def _stats(vals, fmt=".2f", unit=""):
    if not vals:
        return "-", "-", "-"
    return (f"{sum(vals)/len(vals):{fmt}}{unit}",
            f"{min(vals):{fmt}}{unit}",
            f"{max(vals):{fmt}}{unit}")


def make_report(state: State, mode: int, elapsed: int) -> str:
    with state.lock:
        sends   = list(state.sends)
        results = list(state.results)

    cfg = MODES[mode]
    flow_g, ip_g = _ground_maps(sends)

    tp = fp = tn = fn = unk = 0
    for r in results:
        g = _lookup(r, flow_g, ip_g)
        if   g == "attack" and r["is_attack"]:     tp += 1
        elif g == "attack" and not r["is_attack"]: fn += 1
        elif g == "normal" and r["is_attack"]:     fp += 1
        elif g == "normal" and not r["is_attack"]: tn += 1
        else:                                       unk += 1

    total = tp + fp + tn + fn
    prec  = tp / (tp + fp)        if (tp + fp) else 0.0
    rec   = tp / (tp + fn)        if (tp + fn) else 0.0
    f1    = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0
    acc   = (tp + tn) / total     if total else 0.0

    lats     = [r["ts"] - state.t0 for r in results]
    agg_vals = [r["agg_ms"] for r in results if r["agg_ms"] is not None]
    inf_vals = [r["inf_ms"] for r in results if r["inf_ms"] is not None]

    type_count: dict = defaultdict(int)
    for r in results:
        if r["attack_type"]:
            type_count[r["attack_type"]] += 1

    send_atk = sum(1 for s in sends if s["ground"] == "attack")
    send_nor = sum(1 for s in sends if s["ground"] == "normal")

    L = [
        "=" * 62,
        "  NetSentinel 检测报告",
        f"  生成时间 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  测试模式 : {cfg['script']} — {cfg['label']}",
        f"  运行时长 : {elapsed} 秒",
        "=" * 62,
        "",
        "── 模拟流量发送情况 ─────────────────────────────────────",
        f"  发送总数 : {len(sends)}  条",
        f"  攻击流量 : {send_atk} 条",
        f"  正常流量 : {send_nor} 条",
        "",
        "── 模型检测结果 ─────────────────────────────────────────",
        f"  收到结果 : {len(results)} 条  (来源未知: {unk} 条)",
        "",
        "── 混淆矩阵 ─────────────────────────────────────────────",
        f"  TP（攻击正确检出）: {tp:>6}",
        f"  FN（攻击漏报）    : {fn:>6}",
        f"  FP（正常误报）    : {fp:>6}",
        f"  TN（正常正确放行）: {tn:>6}",
        "",
        "── 检测性能指标 ─────────────────────────────────────────",
        f"  准确率  Accuracy : {acc:.2%}",
        f"  精确率 Precision : {prec:.2%}",
        f"  召回率   Recall  : {rec:.2%}",
        f"  综合指标 F1      : {f1:.2%}",
        "",
        "── 攻击类型分布 ─────────────────────────────────────────",
    ]
    for t, c in sorted(type_count.items(), key=lambda x: -x[1]):
        L.append(f"  {t:<34} {c:>4} 次")

    L += [
        "",
        "── 端到端延迟（结果到达 - 监控启动）────────────────────",
        "  均值 {0}   最小 {1}   最大 {2}".format(*_stats(lats, unit="s")),
        "",
        "── 流量聚合耗时 ─────────────────────────────────────────",
        "  均值 {0}   最小 {1}   最大 {2}".format(*_stats(agg_vals, fmt=".0f", unit="ms")),
        "",
        "── 模型推理耗时 ─────────────────────────────────────────",
        "  均值 {0}   最小 {1}   最大 {2}".format(*_stats(inf_vals, fmt=".1f", unit="ms")),
        "",
        "── 检测明细（前 100 条）─────────────────────────────────",
        f"  {'真实标签':<8} {'源IP':<18} {'检测':<5} {'攻击类型':<28} 置信度",
        "  " + "-" * 66,
    ]
    for r in results[:100]:
        g   = _lookup(r, flow_g, ip_g)
        det = "攻击" if r["is_attack"] else "正常"
        L.append(f"  {g:<8} {r['src_ip']:<18} {det:<5} "
                 f"{r['attack_type'] or '正常':<28} {r['confidence']:.3f}")
    L.append("=" * 62)
    return "\n".join(L)


def write_csv(state: State, mode: int):
    with state.lock:
        sends   = list(state.sends)
        results = list(state.results)

    flow_g, ip_g = _ground_maps(sends)
    path = REPORT_DIR / f"monitor_detail_{mode}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "真实标签", "源IP", "目标IP", "目标端口",
            "是否攻击", "攻击类型", "置信度", "聚合耗时ms", "推理耗时ms", "时间",
        ])
        w.writeheader()
        for r in results:
            w.writerow({
                "真实标签":  _lookup(r, flow_g, ip_g),
                "源IP":      r["src_ip"],
                "目标IP":    r["dst_ip"],
                "目标端口":  r["dst_port"],
                "是否攻击":  r["is_attack"],
                "攻击类型":  r["attack_type"],
                "置信度":    r["confidence"],
                "聚合耗时ms": r["agg_ms"] if r["agg_ms"] is not None else "",
                "推理耗时ms": r["inf_ms"] if r["inf_ms"] is not None else "",
                "时间":      r["created_at"],
            })
    print(f"[monitor] 明细 CSV → {path}  ({len(results)} 行)")


# ── 主流程 ─────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log",  default=str(REPORT_DIR / "send.log"))
    p.add_argument("--mode", type=int, choices=[1, 2, 3], default=None)
    p.add_argument("--backend", default=BACKEND, help="NetSentinel 后端地址（默认 $NETSENTINEL_BACKEND 或 http://localhost:8080）")
    p.add_argument("--token", default=os.environ.get("NETSENTINEL_TOKEN"), help="JWT access token（默认 $NETSENTINEL_TOKEN）")
    args = p.parse_args()

    if args.mode is None:
        for k, v in MODES.items():
            print(f"  {k} → {v['label']}")
        while True:
            c = input("模式 [1/2/3]: ").strip()
            if c in ("1", "2", "3"):
                mode = int(c)
                break
    else:
        mode = args.mode

    if not args.token:
        p.error("需要 JWT：--token <JWT> 或环境变量 NETSENTINEL_TOKEN")

    state = State()
    time_from = datetime.fromtimestamp(state.t0, tz=timezone.utc).isoformat()
    print(f"[monitor] 模式={mode}  轮询 {args.backend}{RECORDS_API}（created_at >= {time_from}）", flush=True)

    stop  = threading.Event()

    threading.Thread(target=poll_thread, args=(state, stop, args.backend, args.token, time_from), daemon=True).start()
    threading.Thread(target=tail_thread, args=(pathlib.Path(args.log), state, stop),  daemon=True).start()

    def _sig(*_):
        stop.set()
    signal.signal(signal.SIGINT,  _sig)
    signal.signal(signal.SIGTERM, _sig)

    stop.wait()

    # 最后再拉一次，补齐停发后落库的记录
    try:
        poll_once(state, args.backend, args.token, time_from)
    except Exception as e:
        print(f"\n[monitor] 最后一次拉取失败: {e}", flush=True)

    elapsed = int(time.time() - state.t0)
    print(f"\n[monitor] 生成报告...", flush=True)
    report = make_report(state, mode, elapsed)
    path   = REPORT_DIR / f"monitor_report_{mode}.txt"
    path.write_text(report, encoding="utf-8")
    write_csv(state, mode)
    print("\n" + report)
    print(f"\n[monitor] 报告 → {path}")


if __name__ == "__main__":
    main()

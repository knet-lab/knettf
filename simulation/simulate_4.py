#!/usr/bin/env python3
"""simulate_4 — 从 CSV 直接注入预聚合 flow 特征到检测管道（跳过 Kafka/bridge）"""

import csv
import os
import sys
import time

# ── Django 环境初始化 ─────────────────────────────────────────────────────────
BACKEND_DIR = os.path.join(os.path.dirname(__file__), '../../github/NetSentinel/backend')
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from vigil import services  # noqa: E402（必须在 django.setup() 之后）

# ── 参数 ──────────────────────────────────────────────────────────────────────
CSV_PATH   = os.path.join(os.path.dirname(__file__), 'simulate4.csv')
BATCH_SIZE = 200   # 每批送给模型的 flow 数量
PROTO_MAP  = {'6': 'TCP', '17': 'UDP', '0': 'OTHER'}


def load_flows(path: str) -> list[dict]:
    flows = []
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            flows.append({
                'src_ip':   row['src_ip'],
                'dst_ip':   row['dst_ip'],
                'src_port': int(row['src_port']),
                'dst_port': int(row['dst_port']),
                'protocol': PROTO_MAP.get(row['protocol'], row['protocol']),

                'flow_duration':      float(row['flow_duration']),
                'total_packets':      int(row['total_packets']),
                'fwd_packets':        int(row['fwd_packets']),
                'bwd_packets':        int(row['bwd_packets']),
                'fwd_ratio':          float(row['fwd_ratio']),
                'packets_per_second': float(row['packets_per_second']),

                'iat_mean': float(row['iat_mean']),
                'iat_std':  float(row['iat_std']),
                'iat_min':  float(row['iat_min']),
                'iat_max':  float(row['iat_max']),

                'syn_count': int(row['syn_count']),
                'ack_count': int(row['ack_count']),
                'fin_count': int(row['fin_count']),
                'rst_count': int(row['rst_count']),
                'psh_count': int(row['psh_count']),
                'urg_count': int(row['urg_count']),

                'syn_ratio': float(row['syn_ratio']),
                'ack_ratio': float(row['ack_ratio']),
                'fin_ratio': float(row['fin_ratio']),
                'rst_ratio': float(row['rst_ratio']),

                'reply_count':     int(row['reply_count']),
                'reply_ratio':     float(row['reply_ratio']),
                'forwarded_count': int(row['forwarded_count']),
                'drop_count':      int(row['drop_count']),
                'drop_ratio':      float(row['drop_ratio']),

                'is_bidirectional':   int(row['is_bidirectional']),
                'is_tcp':  int(row['is_tcp']),
                'is_udp':  int(row['is_udp']),
                'is_icmp': int(row['is_icmp']),
                'is_well_known_port': int(row['is_well_known_port']),

                'label': '',
            })
    return flows


def main():
    flows = load_flows(CSV_PATH)
    total   = len(flows)
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f'[simulate_4] {total} flows → {batches} batches × {BATCH_SIZE}', flush=True)

    t0 = time.time()
    done = attacks = normal = 0

    for i in range(0, total, BATCH_SIZE):
        batch   = flows[i:i + BATCH_SIZE]
        results = services.detect_batch(batch)
        done   += len(results)
        attacks += sum(1 for r in results if r.get('is_attack'))
        normal  += sum(1 for r in results if not r.get('is_attack'))
        pct = done / total * 100
        print(f'  [{pct:5.1f}%] {done}/{total}  attacks={attacks}  normal={normal}', flush=True)

    elapsed = time.time() - t0
    print(f'[simulate_4] 完成  total={done}  attacks={attacks}  normal={normal}  elapsed={elapsed:.1f}s', flush=True)


if __name__ == '__main__':
    main()

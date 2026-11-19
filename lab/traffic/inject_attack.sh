#!/usr/bin/env bash
# 异常流量注入（壳子）。具体攻击方式未定，目前所有攻击函数都是占位，不会发送任何流量。
#
# 设计约定：
#   - 默认演练模式（DRY_RUN=1）：只打印将要执行的动作，不发包、不写日志。
#   - 真正执行需要 ENABLE=1 且 DRY_RUN=0。
#   - 每次注入在 INJECT_LOG（默认 lab/traffic/inject_log.csv）记录一行：
#       start_utc,end_utc,attack_type,src_ip,target,note
#     导出标签时按这份日志决定时间窗口，不按源 IP 末段打标签。
#   - 攻击源：README 规定的 192.168.100.20-29（宿主机别名地址），目标：集群内 my-nginx（TARGET 环境变量）。
#
# 用法：
#   bash lab/traffic/inject_attack.sh run <攻击类型> <持续秒数>     # 默认演练
#   ENABLE=1 DRY_RUN=0 bash lab/traffic/inject_attack.sh run <攻击类型> <持续秒数>
#   bash lab/traffic/inject_attack.sh list                         # 列出已登记的攻击类型
#
# 攻击类型（待定，先登记名字）：syn_flood、port_scan、http_flood

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INJECT_LOG="${INJECT_LOG:-$HERE/inject_log.csv}"
TARGET="${TARGET:-}"
SRC_IPS="${SRC_IPS:-192.168.100.20-192.168.100.29}"
DRY_RUN="${DRY_RUN:-1}"
ENABLE="${ENABLE:-0}"

ATTACK_TYPES=(syn_flood port_scan http_flood)

log()  { echo "[inject] $*"; }
die()  { echo "[inject] ❌ $*" >&2; exit 1; }

# ── 占位：每种攻击的具体实现待定 ──────────────────────────────────────────
attack_syn_flood()  { log "TODO syn_flood：目标 $TARGET，持续 $1 秒，源 $SRC_IPS"; }
attack_port_scan()  { log "TODO port_scan：目标 $TARGET，持续 $1 秒，源 $SRC_IPS"; }
attack_http_flood() { log "TODO http_flood：目标 $TARGET，持续 $1 秒，源 $SRC_IPS"; }

is_known_type() {
    local t
    for t in "${ATTACK_TYPES[@]}"; do [ "$t" = "$1" ] && return 0; done
    return 1
}

run_attack() {
    local type="$1" secs="$2"
    is_known_type "$type" || die "未知攻击类型：$type（可用：${ATTACK_TYPES[*]}）"
    [[ "$secs" =~ ^[0-9]+$ ]] || die "持续秒数必须是整数"
    [ -n "$TARGET" ] || die "请设置 TARGET（集群内 my-nginx 的地址）"

    if [ "$DRY_RUN" = "1" ] || [ "$ENABLE" != "1" ]; then
        log "演练模式：不会发送流量。将执行 $type，持续 ${secs}s，目标 $TARGET"
        log "真正执行请设置 ENABLE=1 DRY_RUN=0"
        return 0
    fi

    local start end
    start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    "attack_$type" "$secs"
    end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    [ -f "$INJECT_LOG" ] || echo "start_utc,end_utc,attack_type,src_ip,target,note" > "$INJECT_LOG"
    echo "$start,$end,$type,$SRC_IPS,$TARGET," >> "$INJECT_LOG"
    log "已记录到 $INJECT_LOG"
}

case "${1:-}" in
    run)  run_attack "${2:-}" "${3:-}" ;;
    list) printf '%s\n' "${ATTACK_TYPES[@]}" ;;
    *)    sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 1 ;;
esac

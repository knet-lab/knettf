#!/bin/bash
# 04-deploy-baseline.sh
# 部署"正常流量基线"：Online Boutique（Google 开源微服务演示应用，Apache-2.0）
#
#   · 命名空间 boutique，清单固定版本：lab/manifests/boutique-v0.10.7.yaml（上游原样）
#   · 东西向流量：应用自带 loadgenerator（locust）在集群内模拟用户
#   · 南北向流量：frontend-external（LoadBalancer，MetalLB 分配 IP），
#                 由宿主机上的仿真客户端区访问（lab/traffic/client-zone.sh，需 sudo）
#   · externalTrafficPolicy=Local：保留客户端真实源 IP（否则被 SNAT 成节点 IP）
#
# 幂等：可重复运行。前置：03-deploy-5nodes.sh 已成功。
# 用法：bash 04-deploy-baseline.sh [--users N]   （集群内 loadgenerator 用户数，默认 10）
set -e

log()  { echo "";  echo "=== $* ==="; }
ok()   { echo "  ✅ $*"; }
info() { echo "  ℹ️  $*"; }
die()  { echo "  ❌ $*"; exit 1; }
trap 'echo ""; echo "❌ 出错。已部署资源保留，修复后重新运行 bash 04-deploy-baseline.sh"' ERR

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOUTIQUE_YAML="${LAB_DIR}/manifests/boutique-v0.10.7.yaml"
NS=boutique
USERS=10
while [ $# -gt 0 ]; do
  case "$1" in
    --users) USERS="$2"; shift 2 ;;
    *) die "未知参数：$1" ;;
  esac
done

log "Step 1: 前置检查"
NODE_READY=$(kubectl get node --no-headers 2>/dev/null | grep -c " Ready " || true)
[ "$NODE_READY" -ge 5 ] || die "就绪节点 ${NODE_READY}/5，请先完成 00→03"
kubectl get ipaddresspool -A --no-headers 2>/dev/null | grep -q . || die "没有 MetalLB 地址池，请先完成 03"
[ -f "$BOUTIQUE_YAML" ] || die "找不到 $BOUTIQUE_YAML"
ok "节点 ${NODE_READY}/5 Ready，MetalLB 就绪"

log "Step 2: 部署 Online Boutique（ns=${NS}）"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$NS" apply -f "$BOUTIQUE_YAML" >/dev/null
kubectl -n "$NS" patch svc frontend-external --type merge \
  -p '{"spec":{"externalTrafficPolicy":"Local"}}' >/dev/null
kubectl -n "$NS" set env deployment/loadgenerator USERS="$USERS" >/dev/null
ok "已 apply；frontend-external 使用 externalTrafficPolicy=Local；loadgenerator USERS=${USERS}"

log "Step 3: 等待所有 Deployment 就绪（首次需拉镜像，最多 10 分钟）"
for d in $(kubectl -n "$NS" get deploy -o name); do
  kubectl -n "$NS" rollout status "$d" --timeout=600s >/dev/null || die "$d 未就绪"
done
ok "$(kubectl -n "$NS" get deploy --no-headers | wc -l) 个 Deployment 就绪"

log "Step 4: 前端 LoadBalancer IP"
for _ in $(seq 1 30); do
  LB_IP=$(kubectl -n "$NS" get svc frontend-external -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [ -n "$LB_IP" ] && break
  sleep 2
done
[ -n "$LB_IP" ] || die "frontend-external 没有分配到 IP"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${LB_IP}/" || true)
[ "$code" = "200" ] || die "http://${LB_IP}/ 返回 ${code}"
ok "frontend: http://${LB_IP}/ （HTTP 200）"

# 写入 lab/.env，供 client-zone.sh 使用
ENV_FILE="${LAB_DIR}/.env"
touch "$ENV_FILE"
sed -i '/^BOUTIQUE_URL=/d' "$ENV_FILE"
echo "BOUTIQUE_URL=http://${LB_IP}" >> "$ENV_FILE"
ok "BOUTIQUE_URL 已写入 lab/.env"

echo ""
echo "下一步（南北向流量，需 sudo）：sudo bash ${LAB_DIR}/traffic/client-zone.sh up && sudo bash ${LAB_DIR}/traffic/client-zone.sh start"

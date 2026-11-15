#!/bin/bash
# 03-deploy-5nodes.sh
# 部署 Kafka + Vector + nginx 测试服务
#
# Kafka 架构（kafka-5nodes.yaml）：
#   kafka-controller Pod  → k8s-master，process.roles=controller
#   kafka-broker StatefulSet x4 → node1~4，process.roles=broker
#   LB Services: kafka-0-external ~ kafka-3-external（4个，对应4个broker）
#
# 严格执行顺序：
#   Step 3  只创建 Services（含4个 LB Services），不含 Pod/StatefulSet
#   Step 4  等 MetalLB 为 kafka-0~3-external 分配 IP
#   Step 5  用真实 MetalLB IP 创建 kafka-node-ips ConfigMap（key: node-0~3）
#   Step 6  apply 完整 kafka-5nodes.yaml（幂等，StatefulSet 此时能读到 ConfigMap）
#   Step 7  等 controller Running → 等 4个 broker Running
#
set -e

log()  { echo "";  echo "=== $* ==="; }
ok()   { echo "  ✅ $*"; }
info() { echo "  ℹ️  $*"; }
die()  { echo "  ❌ $*"; exit 1; }

trap 'echo ""; echo "❌ 出错。集群和已部署资源保留，修复后重新运行 bash 03-deploy-5nodes.sh"' ERR

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # 本脚本在 lab/cluster/ 下
KAFKA_YAML="${LAB_DIR}/manifests/kafka-5nodes.yaml"
VECTOR_YAML="${LAB_DIR}/manifests/vector-5nodes.yaml"
HOSTFW_YAML="${LAB_DIR}/cluster/host-firewall-ccnp.yaml"

# ══════════════════════════════════════════════
# Step 1: 前置检查
# ══════════════════════════════════════════════
log "Step 1: 前置检查"

NODE_READY=$(kubectl get node --no-headers 2>/dev/null | grep -c " Ready " || true)
[ "$NODE_READY" -lt 5 ] && die "就绪节点 ${NODE_READY}/5，请先确认 bash 02-setup-cluster.sh 成功完成"
ok "节点：${NODE_READY}/5 Ready"

SC=$(kubectl get storageclass local-path --no-headers 2>/dev/null | wc -l)
[ "$SC" -lt 1 ] && die "StorageClass local-path 不存在，请检查 02 Step 11"
ok "StorageClass local-path 就绪"

METALLB_CTRL=$(kubectl get pods -n metallb-system --no-headers 2>/dev/null \
  | grep "controller" | grep -c "Running" || true)
[ "$METALLB_CTRL" -lt 1 ] && die "MetalLB controller 未 Running，请检查 02 Step 10"
ok "MetalLB 就绪"

HUBBLE_RELAY=$(kubectl get pods -n kube-system --no-headers 2>/dev/null \
  | grep "hubble-relay" | grep -c "Running" || true)
[ "$HUBBLE_RELAY" -lt 1 ] && die "hubble-relay 未 Running，请检查 02 Step 8-9"
ok "Hubble Relay 就绪"

kubectl get node -o wide

# ══════════════════════════════════════════════
# Step 2: 检查 YAML 文件存在
# ══════════════════════════════════════════════
log "Step 2: 检查部署文件"

[ -f "$KAFKA_YAML" ]  || die "找不到 KAFKA_YAML: ${KAFKA_YAML}"
[ -f "$VECTOR_YAML" ] || die "找不到 VECTOR_YAML: ${VECTOR_YAML}"
ok "KAFKA_YAML  : ${KAFKA_YAML}"
ok "VECTOR_YAML : ${VECTOR_YAML}"
[ -f "$HOSTFW_YAML" ] || die "找不到 HOSTFW_YAML: ${HOSTFW_YAML}"
ok "HOSTFW_YAML : ${HOSTFW_YAML}"

# ══════════════════════════════════════════════
# Step 3: 只创建 Kafka Services
# 从 kafka-5nodes.yaml 提取 kind: Service 部分 apply
# 让 MetalLB 先分配 IP，ConfigMap 才能写入真实 IP
# ══════════════════════════════════════════════
log "Step 3: 创建 Kafka Services（不含 Pod/StatefulSet）"

python3 - << PYEOF
import subprocess, sys

with open("${KAFKA_YAML}") as f:
    raw = f.read()

docs = raw.split("---")
svc_docs = [d for d in docs if "kind: Service" in d and d.strip()]

if not svc_docs:
    print("ERROR: 未找到任何 Service 文档", file=sys.stderr)
    sys.exit(1)

combined = "---\n" + "\n---\n".join(svc_docs)
result = subprocess.run(
    ["kubectl", "apply", "-f", "-"],
    input=combined, text=True, capture_output=True
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)
print(f"apply 了 {len(svc_docs)} 个 Service")
PYEOF

ok "Kafka Services 已创建"

# MetalLB L2 speaker 需要几秒感知新 Service 并开始分配
info "等待 MetalLB 感知新 Service（10s）..."
sleep 10

# ══════════════════════════════════════════════
# Step 4: 等待 MetalLB 为 4 个 LB Service 分配 IP
# ══════════════════════════════════════════════
log "Step 4: 等待 MetalLB 分配 LoadBalancer IP"

declare -a KAFKA_EXTERNAL_IPS
for i in $(seq 0 3); do
  info "等待 kafka-${i}-external 获取 IP..."
  IP_FOUND=false
  for attempt in $(seq 1 36); do
    IP=$(kubectl get svc "kafka-${i}-external" \
      -o jsonpath='{.status.loadBalancer.ingress[0].ip}' \
      2>/dev/null || true)
    if [ -n "$IP" ]; then
      KAFKA_EXTERNAL_IPS[$i]="$IP"
      info "  kafka-${i}-external → ${IP}"
      IP_FOUND=true
      break
    fi
    echo "    等待 kafka-${i}-external IP... ($attempt/36)"
    sleep 5
  done
  if [ "$IP_FOUND" = "false" ]; then
    die "kafka-${i}-external 180s 内未获得 IP，检查 MetalLB"
  fi
done
ok "所有 LoadBalancer IP 分配完成"

# ══════════════════════════════════════════════
# Step 5: 创建 kafka-node-ips ConfigMap
# key 名称与 kafka-5nodes.yaml broker init container 完全一致：
#   node-0 ~ node-3，nodeport-0 ~ nodeport-3
# ══════════════════════════════════════════════
log "Step 5: 创建 kafka-node-ips ConfigMap"

kubectl create configmap kafka-node-ips \
  --from-literal=node-0="${KAFKA_EXTERNAL_IPS[0]}" \
  --from-literal=node-1="${KAFKA_EXTERNAL_IPS[1]}" \
  --from-literal=node-2="${KAFKA_EXTERNAL_IPS[2]}" \
  --from-literal=node-3="${KAFKA_EXTERNAL_IPS[3]}" \
  --from-literal=nodeport-0="9094" \
  --from-literal=nodeport-1="9094" \
  --from-literal=nodeport-2="9094" \
  --from-literal=nodeport-3="9094" \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -

for i in $(seq 0 3); do
  info "broker-${i} EXTERNAL → ${KAFKA_EXTERNAL_IPS[$i]}:9094"
done
ok "kafka-node-ips ConfigMap 就绪"

# 让 API server 将 ConfigMap 写入 etcd 并同步到各节点缓存，
# 防止 StatefulSet Pod 启动时 init container 读不到 ConfigMap
info "等待 ConfigMap 同步到集群（5s）..."
sleep 5

# ══════════════════════════════════════════════
# Step 6: apply 完整 kafka-5nodes.yaml
# Services 已存在 → apply 幂等跳过
# kafka-controller Pod + kafka-broker StatefulSet 新建
# ══════════════════════════════════════════════
log "Step 6: 部署 Kafka（controller + broker）"

kubectl apply -f "$KAFKA_YAML"

# apply 是异步的：Pod 需要被调度、镜像需要拉取
# 先等调度器处理，再开始轮询状态
info "等待 kafka-controller 被调度（15s）..."
sleep 15

# 等 controller Pod Running
# 修复点：原代码用 &&...&& break 链，set -e 下不稳定，改为 if 块
info "等待 kafka-controller Running（最多 3 分钟）..."
CTRL_READY=false
for attempt in $(seq 1 36); do
  STATUS=$(kubectl get pod kafka-controller -n default \
    --no-headers 2>/dev/null | awk '{print $3}' || true)
  if [ "$STATUS" = "Running" ]; then
    ok "kafka-controller Running"
    CTRL_READY=true
    break
  fi
  echo "    等待 kafka-controller... ($attempt/36) 当前状态: ${STATUS:-Pending}"
  sleep 5
done
if [ "$CTRL_READY" = "false" ]; then
  die "kafka-controller 启动超时，查看: kubectl logs kafka-controller"
fi

# controller Running 后等几秒让它完成 KRaft metadata 初始化
# broker 要连上 controller 才能完成 format，太早启动 rollout 可能误判
info "等待 kafka-controller 完成 KRaft 初始化（15s）..."
sleep 15

# 等 broker StatefulSet 4 副本就绪
info "等待 kafka-broker StatefulSet 就绪（4 副本，最多 6 分钟）..."
kubectl rollout status statefulset/kafka-broker -n default --timeout=360s
ok "Kafka 集群就绪（1 controller + 4 broker）"

# ══════════════════════════════════════════════
# Step 7: 创建 Vector Kafka Secret
# name/key 与 vector-5nodes.yaml secretKeyRef 完全一致
# ══════════════════════════════════════════════
log "Step 7: 创建 Vector Kafka Secret"

kubectl create secret generic vector-kafka-secret \
  --from-literal=bootstrap_servers="kafka-svc.default.svc.cluster.local:9092" \
  -n kube-system \
  --dry-run=client -o yaml | kubectl apply -f -
ok "Secret vector-kafka-secret 就绪"
info "bootstrap: kafka-svc.default.svc.cluster.local:9092（ClusterIP，集群内直连）"

# ══════════════════════════════════════════════
# Step 8: 部署 Vector DaemonSet
# ══════════════════════════════════════════════
log "Step 8: 部署 Vector"

VECTOR_CFG_OLD=$(kubectl -n kube-system get cm vector-config -o jsonpath='{.data.vector\.yaml}' 2>/dev/null | sha256sum)
kubectl apply -f "$VECTOR_YAML"
VECTOR_CFG_NEW=$(kubectl -n kube-system get cm vector-config -o jsonpath='{.data.vector\.yaml}' | sha256sum)
# Vector 不监听 ConfigMap 变化：配置变了必须重启 Pod，否则继续跑旧配置
if [ "$VECTOR_CFG_OLD" != "$VECTOR_CFG_NEW" ] && kubectl -n kube-system get ds vector >/dev/null 2>&1; then
  info "vector-config 有变化，重启 Vector 以加载新配置"
  kubectl -n kube-system rollout restart daemonset/vector
fi

# DaemonSet 刚创建，Pod 还在 ContainerCreating（init container 要 cp hubble binary）
info "等待 Vector Pod 出现（15s）..."
sleep 15

info "等待 Vector DaemonSet 就绪（5个节点，最多 3 分钟）..."
kubectl rollout status daemonset/vector -n kube-system --timeout=180s
ok "Vector 就绪"

# 确认 Vector 能连上 hubble-relay 且没有立即崩溃
info "观察 Vector 日志（10s 稳定检查）..."
sleep 10
VECTOR_RESTARTS=$(kubectl get pods -n kube-system -l app=vector \
  --no-headers 2>/dev/null | awk '{sum+=$4} END {print sum+0}')
if [ "$VECTOR_RESTARTS" -gt 5 ]; then
  info "⚠️  Vector Pod 重启次数偏高（${VECTOR_RESTARTS}），检查: kubectl logs -n kube-system -l app=vector"
else
  ok "Vector Pod 稳定（重启总计 ${VECTOR_RESTARTS} 次）"
fi

# ══════════════════════════════════════════════
# Step 8b: host 可见性策略
#   02 已开启 hostFirewall；这条 CCNP 让发往节点 IP 的流量（含宿主机伪造源 IP
#   .20~.29 / .50~.64 打到 master:6443、worker:80）经过 host endpoint，被 Hubble 记录
# ══════════════════════════════════════════════
log "Step 8b: 应用 host-visibility 策略"
kubectl apply -f "$HOSTFW_YAML"
ok "CiliumClusterwideNetworkPolicy/host-visibility 已应用"

# ══════════════════════════════════════════════
# Step 9: 部署 nginx 测试服务
# ══════════════════════════════════════════════
log "Step 9: 部署 nginx 测试服务"

kubectl create deployment my-nginx --image=nginx 2>/dev/null \
  && ok "nginx deployment 已创建" \
  || info "nginx deployment 已存在，跳过"

kubectl expose deployment my-nginx \
  --type=LoadBalancer --port=80 2>/dev/null \
  && ok "nginx Service 已创建" \
  || info "nginx Service 已存在，跳过"

# 等 nginx Pod Running 后 MetalLB 才会分配 IP
info "等待 nginx Pod 就绪..."
kubectl rollout status deployment/my-nginx -n default --timeout=120s

info "等待 nginx EXTERNAL-IP（MetalLB 分配，最多 2 分钟）..."
NGINX_IP=""
for i in $(seq 1 24); do
  NGINX_IP=$(kubectl get svc my-nginx \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  if [ -n "$NGINX_IP" ]; then
    break
  fi
  echo "    等待中... ($i/24)"
  sleep 5
done
[ -z "$NGINX_IP" ] && die "nginx EXTERNAL-IP 未分配，检查 MetalLB"
ok "nginx EXTERNAL-IP: ${NGINX_IP}"

# ══════════════════════════════════════════════
# Step 10: 启动 Hubble port-forward（宿主机调试用）
# ══════════════════════════════════════════════
log "Step 10: 启动 Hubble port-forward"

pkill -f "port-forward.*hubble-relay" 2>/dev/null || true
# 等旧进程完全退出，避免端口占用
sleep 3

HUBBLE_SVC_PORT=$(kubectl get svc hubble-relay -n kube-system \
  -o jsonpath='{.spec.ports[0].port}' 2>/dev/null)
[ -z "$HUBBLE_SVC_PORT" ] && die "无法读取 hubble-relay Service port"
info "hubble-relay Service port: ${HUBBLE_SVC_PORT}"

kubectl port-forward -n kube-system svc/hubble-relay \
  4245:"${HUBBLE_SVC_PORT}" > /tmp/hubble-pf.log 2>&1 &
HUBBLE_PF_PID=$!

# 等待 port-forward 进程建立连接（通常 1-2s）
info "等待 port-forward 建立（5s）..."
sleep 5

if ! kill -0 "$HUBBLE_PF_PID" 2>/dev/null; then
  die "hubble port-forward 启动失败，查看 /tmp/hubble-pf.log"
fi
ok "hubble port-forward 就绪 (PID=${HUBBLE_PF_PID}, localhost:4245 → ${HUBBLE_SVC_PORT})"

# ══════════════════════════════════════════════
# Step 11: 更新 /etc/hosts
# ══════════════════════════════════════════════
log "Step 11: 更新 /etc/hosts"

sudo sed -i '/kafka-svc\.default\.svc\.cluster\.local/d' /etc/hosts
echo "${KAFKA_EXTERNAL_IPS[0]}  kafka-svc.default.svc.cluster.local" \
  | sudo tee -a /etc/hosts > /dev/null
ok "/etc/hosts 更新完成"

# ══════════════════════════════════════════════
# Step 12: 写入 lab/.env
# ══════════════════════════════════════════════
log "Step 12: 写入 lab/.env"

# 集群外 bootstrap：4个 broker 的 MetalLB IP:9094
BOOTSTRAP_EXTERNAL=""
for i in $(seq 0 3); do
  BOOTSTRAP_EXTERNAL="${BOOTSTRAP_EXTERNAL}${KAFKA_EXTERNAL_IPS[$i]}:9094,"
done
BOOTSTRAP_EXTERNAL="${BOOTSTRAP_EXTERNAL%,}"

# 只更新本脚本负责的键，保留其他脚本写入的内容（如 04 的 BOUTIQUE_URL）
ENV_FILE="${LAB_DIR}/.env"
touch "$ENV_FILE"
sed -i -E '/^(BOOTSTRAP_SERVERS|GROUP_ID|AUTO_OFFSET_RESET|TOPICS)=/d' "$ENV_FILE"
cat >> "$ENV_FILE" << ENVEOF
BOOTSTRAP_SERVERS=${BOOTSTRAP_EXTERNAL}
GROUP_ID=ebpf-log-consumer-group
AUTO_OFFSET_RESET=earliest
TOPICS='["ebpf-net-logs"]'
ENVEOF
ok ".env 已更新"

info "nginx 的 MetalLB IP 是 ${NGINX_IP}；若和 traffic/send_request.py 里的 DESTINATION_IP 不同，需要手动改"

# ══════════════════════════════════════════════
# 完成摘要
# ══════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                         部署完成                                ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  kafka-controller : k8s-master (process.roles=controller)       ║"
for i in $(seq 0 3); do
  printf "║  kafka-broker-%-1d   : %-18s:9094  (MetalLB)\n" \
    "$i" "${KAFKA_EXTERNAL_IPS[$i]}"
done
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  集群内 bootstrap : kafka-svc.default.svc.cluster.local:9092   ║"
echo "║  集群外 bootstrap : ${BOOTSTRAP_EXTERNAL}"
printf  "║  nginx 攻击目标   : http://%-34s║\n" "${NGINX_IP}"
printf  "║  Hubble gRPC      : localhost:4245  (PID %-8s)          ║\n" "${HUBBLE_PF_PID}"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "── 验证命令 ────────────────────────────────────────────────────────"
echo ""
echo "# 1. 产生攻击流量"
echo "     curl http://${NGINX_IP}"
echo ""
echo "# 2. Hubble 实时观察"
echo "     hubble observe --follow --server localhost:4245 | grep 192.168.100.1"
echo ""
echo "# 3. 验证 Kafka 4 broker 连通"
echo "     kubectl exec -n default kafka-broker-0 -- \\"
echo "       /opt/kafka/bin/kafka-broker-api-versions.sh \\"
echo "       --bootstrap-server kafka-svc.default.svc.cluster.local:9092"
echo ""
echo "# 4. 验证 topic 有数据"
echo "     kubectl exec -n default kafka-broker-0 -- \\"
echo "       /opt/kafka/bin/kafka-console-consumer.sh \\"
echo "       --bootstrap-server kafka-svc.default.svc.cluster.local:9092 \\"
echo "       --topic ebpf-net-logs --from-beginning --max-messages 5"
echo ""
echo "# 5. Vector 日志"
echo "     kubectl logs -n kube-system -l app=vector --tail=50"
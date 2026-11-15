#!/bin/bash
# 02-setup-cluster.sh
# 在 5 个 VM 上初始化 Kubernetes 集群
# 安装顺序：containerd → kubeadm init → worker join →
#           kubeconfig → Cilium+Hubble → MetalLB → local-path-provisioner
#
# 幂等设计：每个关键 Step 先检测是否已完成，已完成则跳过
#
set -e

log()  { echo "";  echo "=== $* ==="; }
ok()   { echo "  ✅ $*"; }
info() { echo "  ℹ️  $*"; }
die()  { echo "  ❌ $*"; exit 1; }

# ══════════════════════════════════════════════
# 配置（与 00/01 保持一致）
# ══════════════════════════════════════════════
MASTER_IP="192.168.100.10"
NODE_IPS=("192.168.100.11" "192.168.100.12" "192.168.100.13" "192.168.100.14")
NODE_NAMES=("k8s-node1" "k8s-node2" "k8s-node3" "k8s-node4")
ALL_IPS=("$MASTER_IP" "${NODE_IPS[@]}")

# helm chart 版本必须固定：不固定会装到当天最新版。
#   MetalLB 0.16.x 的 CRD 用了 CEL isIP()（K8s ≥ 1.31 才支持），在 1.28 上安装失败。
#   Cilium 1.19.3 是这套环境长期验证过的版本。
# 升级 K8s 版本时再一起评估这两个版本。
CILIUM_VERSION="1.19.3"
METALLB_VERSION="0.14.9"

SSH_USER="k8s"
SSH_KEY="$HOME/.ssh/id_rsa"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes"

POD_CIDR="10.244.0.0/16"
METALLB_IP_RANGE="192.168.100.200-192.168.100.250"

# ══════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════
run_on() {
  local HOST=$1; shift
  # shellcheck disable=SC2086
  ssh $SSH_OPTS -i "$SSH_KEY" "${SSH_USER}@${HOST}" "$@"
}

# 带重试的 SSH 等待（最多 N 次，每次间隔 5s）
wait_for_ssh() {
  local HOST=$1
  local MAX=${2:-24}   # 默认 24 次 = 2 分钟
  info "等待 ${HOST} SSH 就绪（最多 $((MAX * 5))s）..."
  for attempt in $(seq 1 "$MAX"); do
    run_on "$HOST" "echo ok" &>/dev/null && return 0
    echo "    等待中... ($attempt/$MAX)"
    sleep 5
  done
  die "${HOST} SSH 超时，请检查节点状态"
}

# 等待 kubectl rollout，带前置 sleep 让 Pod 有时间被调度
wait_rollout() {
  local KIND=$1        # daemonset / deployment / statefulset
  local NAME=$2
  local NS=${3:-default}
  local TIMEOUT=${4:-300s}
  local PRESLEEP=${5:-5}  # 等待 Pod 出现的前置 sleep
  info "等待 ${KIND}/${NAME} 就绪（ns=${NS}，pre-sleep=${PRESLEEP}s）..."
  sleep "$PRESLEEP"
  kubectl rollout status "${KIND}/${NAME}" -n "$NS" --timeout="$TIMEOUT"
  ok "${KIND}/${NAME} 就绪"
}

# ══════════════════════════════════════════════
# Step 0: 确保 VM 出网 NAT 规则存在
# VM 用 NAT 网桥出网，需要宿主机有 MASQUERADE 规则
# libvirt 有时不自动生成，这里幂等补上（先删再加，防止重复）
# 不重启任何 VM 和网桥
# ══════════════════════════════════════════════
log "Step 0: 确保 VM 出网 NAT 规则存在"

HOST_NIC="enp6s0"        # 宿主机出网网卡
VM_SUBNET="192.168.100.0/24"

# 开启 ip_forward
sudo sysctl -w net.ipv4.ip_forward=1 -q
echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-ipforward.conf > /dev/null
ok "ip_forward 已开启"

# 先删再加，保证幂等不重复
sudo iptables -t nat -D POSTROUTING   -s "${VM_SUBNET}" ! -d "${VM_SUBNET}"   -o "${HOST_NIC}" -j MASQUERADE 2>/dev/null || true
sudo iptables -D FORWARD -s "${VM_SUBNET}" -j ACCEPT 2>/dev/null || true
sudo iptables -D FORWARD -d "${VM_SUBNET}" -j ACCEPT 2>/dev/null || true

sudo iptables -t nat -A POSTROUTING   -s "${VM_SUBNET}" ! -d "${VM_SUBNET}"   -o "${HOST_NIC}" -j MASQUERADE
sudo iptables -A FORWARD -s "${VM_SUBNET}" -j ACCEPT
sudo iptables -A FORWARD -d "${VM_SUBNET}" -j ACCEPT
ok "NAT / FORWARD 规则已就绪"

# 验证 VM 出网（用 curl 走 TCP，不用 ping，避免 ICMP 被屏蔽的误判）
info "验证 VM 出网（从 k8s-master curl pkgs.k8s.io）..."
NET_OK=false
for attempt in $(seq 1 6); do
  if run_on "$MASTER_IP"     "curl -sf --max-time 10 -o /dev/null https://pkgs.k8s.io" &>/dev/null; then
    ok "VM 出网正常"
    NET_OK=true
    break
  fi
  echo "    等待网络就绪... ($attempt/6)"
  sleep 5
done
[ "$NET_OK" = "false" ] && die "VM 无法访问外网，请检查 NAT 规则或上游网络"

# ══════════════════════════════════════════════
# Step 1: 验证所有节点 SSH 连通
# ══════════════════════════════════════════════
log "Step 1: 验证所有节点 SSH 连通"

for IP in "${ALL_IPS[@]}"; do
  wait_for_ssh "$IP" 12   # 1 分钟超时，01 已等过 SSH，正常应秒通
  ok "${IP} 连通"
done

# ══════════════════════════════════════════════
# Step 2: 修复 hostname
# cloud-init 有时写入不及时，强制设一遍
# ══════════════════════════════════════════════
log "Step 2: 修复节点 hostname"

run_on "$MASTER_IP" "sudo hostnamectl set-hostname k8s-master"
for i in "${!NODE_IPS[@]}"; do
  run_on "${NODE_IPS[$i]}" "sudo hostnamectl set-hostname ${NODE_NAMES[$i]}"
done
ok "hostname 修复完成"

# hostname 修复后让 systemd-resolved 刷新（/etc/hosts 由 cloud-init 写入，短暂延迟）
sleep 3

# ══════════════════════════════════════════════
# Step 3: 所有节点基础配置（幂等）
# swap off、内核模块、containerd、kubeadm/kubelet/kubectl
#
# 修复点：gpg --dearmor 写文件时若文件已存在会返回非零，
#         加 || true 防止 set -e 误退出
# ══════════════════════════════════════════════
log "Step 3: 所有节点基础配置"

for IP in "${ALL_IPS[@]}"; do
  info "配置节点 ${IP}..."
  run_on "$IP" bash << 'SCRIPT'
set -e

# ── swap ──────────────────────────────────────
sudo swapoff -a
sudo sed -i '/\bswap\b/d' /etc/fstab

# ── 内核模块 ──────────────────────────────────
sudo modprobe overlay
sudo modprobe br_netfilter
printf 'overlay\nbr_netfilter\n' \
  | sudo tee /etc/modules-load.d/k8s.conf > /dev/null

# ── sysctl ────────────────────────────────────
printf 'net.bridge.bridge-nf-call-iptables=1\nnet.bridge.bridge-nf-call-ip6tables=1\nnet.ipv4.ip_forward=1\n' \
  | sudo tee /etc/sysctl.d/k8s.conf > /dev/null
sudo sysctl --system -q

# ── containerd ────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y -qq containerd apt-transport-https curl gnupg ca-certificates

sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable  containerd

# 等待 containerd socket 出现再继续
for attempt in $(seq 1 15); do
  [ -S /run/containerd/containerd.sock ] && break
  echo "    等待 containerd socket... ($attempt/15)"
  sleep 2
done
[ -S /run/containerd/containerd.sock ] || { echo "containerd socket 超时"; exit 1; }

# ── kubernetes 源 ─────────────────────────────
sudo mkdir -p /etc/apt/keyrings
# gpg --dearmor 目标文件已存在时会报错，|| true 防止 set -e 退出
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key \
  | sudo gpg --batch --yes --dearmor \
    -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg || true

# 等待 gpg 文件落盘（NFS/虚拟磁盘可能有延迟）
sleep 1

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' \
  | sudo tee /etc/apt/sources.list.d/kubernetes.list > /dev/null

sudo apt-get update -qq
sudo apt-get install -y -qq kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
sudo systemctl enable kubelet
echo "节点基础配置完成"
SCRIPT
  ok "${IP} 基础配置完成"

  # 节点间错开，避免所有节点同时刷 APT 源
  sleep 2
done

# ══════════════════════════════════════════════
# Step 4: 初始化 control-plane（幂等）
# 检测 /etc/kubernetes/admin.conf 是否已存在
# ══════════════════════════════════════════════
log "Step 4: 初始化 control-plane (${MASTER_IP})"

ALREADY_INIT=$(run_on "$MASTER_IP" \
  "test -f /etc/kubernetes/admin.conf && echo yes || echo no")

if [ "$ALREADY_INIT" = "yes" ]; then
  info "control-plane 已初始化，跳过 kubeadm init"
else
  run_on "$MASTER_IP" bash << SCRIPT
set -e
sudo kubeadm init \
  --apiserver-advertise-address=${MASTER_IP} \
  --pod-network-cidr=${POD_CIDR} \
  --skip-phases=addon/kube-proxy \
  --cri-socket=unix:///run/containerd/containerd.sock

mkdir -p \$HOME/.kube
sudo cp  /etc/kubernetes/admin.conf \$HOME/.kube/config
sudo chown \$(id -u):\$(id -g) \$HOME/.kube/config
echo "kubeadm init 完成"
SCRIPT
  ok "control-plane 初始化完成"
fi

# kubeadm init 完成后 API server 需要几秒稳定，再拷 kubeconfig
info "等待 API server 稳定（10s）..."
sleep 10

# ══════════════════════════════════════════════
# Step 5: 同步 kubeconfig 到宿主机
# 后续所有 kubectl / helm 命令都在宿主机运行
# ══════════════════════════════════════════════
log "Step 5: 同步 kubeconfig 到宿主机"

mkdir -p ~/.kube
# shellcheck disable=SC2086
scp $SSH_OPTS \
  -i "$SSH_KEY" \
  "${SSH_USER}@${MASTER_IP}:~/.kube/config" \
  ~/.kube/config

# 确保 server 地址指向 master IP（不是 localhost）
sed -i "s|server: https://.*:6443|server: https://${MASTER_IP}:6443|g" \
  ~/.kube/config

ok "kubeconfig 已同步"

# 等待 API server 接受本地 kubectl 请求（刚拿到 kubeconfig 时可能 TLS 未完全就绪）
info "等待 kubectl 可访问 API server..."
for attempt in $(seq 1 24); do
  kubectl get node &>/dev/null && break
  echo "    API server 未就绪... ($attempt/24)"
  sleep 5
done
kubectl get node &>/dev/null || die "kubectl 无法访问 API server，请检查 master 节点"
kubectl get node

# ══════════════════════════════════════════════
# Step 6: worker 节点加入集群（幂等）
# 检测节点是否已在集群中再决定是否 join
# ══════════════════════════════════════════════
log "Step 6: worker 节点加入集群"

# 生成新的 join command（token 24h 有效）
JOIN_CMD=$(run_on "$MASTER_IP" "sudo kubeadm token create --print-join-command")
info "join 命令已生成"

for i in "${!NODE_IPS[@]}"; do
  NODE_IP="${NODE_IPS[$i]}"
  NODE_NAME="${NODE_NAMES[$i]}"

  ALREADY_JOINED=$(kubectl get node "$NODE_NAME" \
    --no-headers 2>/dev/null | wc -l)

  if [ "$ALREADY_JOINED" -gt 0 ]; then
    info "${NODE_NAME} 已在集群中，跳过"
  else
    info "加入 ${NODE_NAME} (${NODE_IP})..."
    run_on "$NODE_IP" "sudo ${JOIN_CMD}"
    ok "${NODE_NAME} join 命令已执行"

    # 等待节点出现在 API server（join 是异步的，API server 需要几秒处理）
    info "等待 ${NODE_NAME} 出现在集群中..."
    for attempt in $(seq 1 18); do
      COUNT=$(kubectl get node "$NODE_NAME" --no-headers 2>/dev/null | wc -l)
      [ "$COUNT" -gt 0 ] && break
      echo "    等待节点注册... ($attempt/18)"
      sleep 5
    done
    COUNT=$(kubectl get node "$NODE_NAME" --no-headers 2>/dev/null | wc -l)
    [ "$COUNT" -gt 0 ] || die "${NODE_NAME} 90s 内未注册到集群"
    ok "${NODE_NAME} 已注册到集群"
  fi
done

# ══════════════════════════════════════════════
# Step 7: 安装 helm（宿主机，幂等）
# ══════════════════════════════════════════════
log "Step 6b: kubelet 磁盘上限（容器日志轮转 + 镜像回收）"
# 每个容器日志最多 3×20Mi；节点磁盘超 70% 开始回收镜像，回到 50%
for IP in "${ALL_IPS[@]}"; do
  run_on "$IP" bash << 'KCFG'
set -e
F=/var/lib/kubelet/config.yaml
sudo sed -i '/^containerLogMaxSize:/d;/^containerLogMaxFiles:/d;/^imageGCHighThresholdPercent:/d;/^imageGCLowThresholdPercent:/d' $F
printf 'containerLogMaxSize: 20Mi\ncontainerLogMaxFiles: 3\nimageGCHighThresholdPercent: 70\nimageGCLowThresholdPercent: 50\n' | sudo tee -a $F >/dev/null
sudo systemctl restart kubelet
# journald 系统日志上限 200M
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\n' | sudo tee /etc/systemd/journald.conf.d/size.conf >/dev/null
sudo systemctl restart systemd-journald
KCFG
done
ok "kubelet 磁盘上限已配置"

log "Step 7: 检查 / 安装 helm"

if command -v helm &>/dev/null; then
  ok "helm 已安装：$(helm version --short)"
else
  info "安装 helm..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
    | bash
  ok "helm 安装完成：$(helm version --short)"
fi

# ══════════════════════════════════════════════
# Step 8: 安装 Cilium + Hubble（幂等）
#
# 关键参数说明：
#   kubeProxyReplacement=true   → Cilium 完全替代 kube-proxy
#   k8sServiceHost/Port         → 避免 ClusterIP 鸡蛋问题
#   hubble.relay.service.type=ClusterIP → relay 仅集群内可达
#   hubble.relay.servicePort=4245      → Service port 与 relay gRPC port 对齐（1.19 的参数名；
#                                         旧写法 service.port 会被静默忽略）
#   mtu=1450                    → virbr-k8s NAT 下安全值（宿主 MTU 1500）
#   bpf.monitorAggregation=none → 每个包都上报事件（medium 只在连接建立/标志变化/
#                                  每 5s 上报，事件数 ≠ 包数）。需要 master ≥ 6 vCPU（见 01）
#   hubble.eventBufferCapacity  → 事件量变大后加大环形缓冲，减少 lost events
#   hubble.metrics.enabled      → 流量指标（:9965），供常驻监测使用
#   hostFirewall.enabled=true   → host-firewall-ccnp.yaml（host-visibility）依赖它，
#                                  否则发往节点 IP 的伪造源流量 Hubble 看不到
# ══════════════════════════════════════════════
log "Step 8: 安装 Cilium + Hubble"

CILIUM_EXISTS=$(helm list -n kube-system --short 2>/dev/null | grep -c "^cilium$" || true)

if [ "$CILIUM_EXISTS" -gt 0 ]; then
  info "Cilium 已安装，跳过"
else
  helm repo add cilium https://helm.cilium.io/ 2>/dev/null || true
  helm repo update cilium

  helm install cilium cilium/cilium \
    --version "${CILIUM_VERSION}" \
    --namespace kube-system \
    --set kubeProxyReplacement=true \
    --set k8sServiceHost="${MASTER_IP}" \
    --set k8sServicePort=6443 \
    --set hubble.enabled=true \
    --set hubble.relay.enabled=true \
    --set hubble.relay.service.type=ClusterIP \
    --set hubble.relay.servicePort=4245 \
    --set hubble.ui.enabled=true \
    --set bpf.monitorAggregation=none \
    --set hostFirewall.enabled=true \
    --set hubble.eventBufferCapacity=65535 \
    --set hubble.metrics.enabled="{dns,drop,tcp,flow,port-distribution,icmp}" \
    --set mtu=1450
  ok "Cilium helm install 完成"

  # helm install 是异步的：DaemonSet 刚被创建，Pod 还没调度
  # 先等 Cilium CRD / DaemonSet 出现，再等 rollout
  info "等待 Cilium DaemonSet 出现（15s）..."
  sleep 15
fi

# hubble-relay 端口由 helm 的 hubble.relay.servicePort=4245 设置。
# 不要再 kubectl patch：patch 会让该字段归 kubectl-patch 管理，之后 helm upgrade
# （server-side apply）会因端口合并 / 字段冲突失败。

# 打印实际端口，方便排查
HUBBLE_PORT=$(kubectl get svc hubble-relay -n kube-system \
  -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "unknown")
HUBBLE_TARGET=$(kubectl get svc hubble-relay -n kube-system \
  -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null || echo "unknown")
ok "hubble-relay Service port=${HUBBLE_PORT} targetPort=${HUBBLE_TARGET}"

# ══════════════════════════════════════════════
# Step 9: 等待 Cilium 就绪 → 节点全部 Ready
# ══════════════════════════════════════════════
log "Step 9: 等待 Cilium 就绪"

# Cilium agent 在每个节点上都要装载 eBPF 程序，耗时较长
# 先等 300s rollout，再等节点 Ready
wait_rollout daemonset  cilium        kube-system 300s 10
wait_rollout deployment hubble-relay  kube-system 300s 5

info "等待所有节点 Ready（最多 300s）..."
kubectl wait --for=condition=Ready node --all --timeout=300s
ok "所有节点 Ready"
kubectl get node -o wide

# 再次确认 hubble-relay Service 端口（rollout 后 Service 可能被重建）
HUBBLE_PORT=$(kubectl get svc hubble-relay -n kube-system \
  -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "unknown")
info "hubble-relay Service port: ${HUBBLE_PORT}（03 的 port-forward 会转到宿主机 4245）"

# ══════════════════════════════════════════════
# Step 10: 安装 MetalLB（幂等）
# IP 池：192.168.100.200-250
# ══════════════════════════════════════════════
log "Step 10: 安装 MetalLB"

METALLB_EXISTS=$(helm list -n metallb-system --short 2>/dev/null | grep -c "^metallb$" || true)

if [ "$METALLB_EXISTS" -gt 0 ]; then
  info "MetalLB 已安装，跳过"
else
  helm repo add metallb https://metallb.github.io/metallb 2>/dev/null || true
  helm repo update metallb

  helm install metallb metallb/metallb \
    --version "${METALLB_VERSION}" \
    --namespace metallb-system \
    --create-namespace
  ok "MetalLB helm install 完成"

  # MetalLB controller Deployment 刚创建，Pod 还在 Pending
  info "等待 MetalLB Pod 出现（15s）..."
  sleep 15
fi

info "等待 MetalLB controller 就绪..."
wait_rollout deployment  metallb-controller  metallb-system  300s  5
wait_rollout daemonset   metallb-speaker     metallb-system  300s  5
ok "MetalLB 就绪"

# IP 池配置（apply 幂等）
kubectl apply -f - << YAML
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: k8s-pool
  namespace: metallb-system
spec:
  addresses:
    - ${METALLB_IP_RANGE}
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: k8s-l2
  namespace: metallb-system
spec:
  ipAddressPools:
    - k8s-pool
YAML

# MetalLB webhook 需要几秒完成 CRD 校验，太快 apply 会 400 报错
# 等待 webhook pod ready 再 apply
info "等待 MetalLB webhook 就绪（10s）..."
sleep 10
ok "MetalLB IP 池配置完成 (${METALLB_IP_RANGE})"

# ══════════════════════════════════════════════
# Step 11: 安装 local-path-provisioner（幂等）
# Kafka volumeClaimTemplates 需要默认 StorageClass
# 裸金属 / VM 集群没有云厂商 CSI，必须手动装
# ══════════════════════════════════════════════
log "Step 11: 安装 local-path-provisioner"

SC_EXISTS=$(kubectl get storageclass local-path \
  --no-headers 2>/dev/null | wc -l)

if [ "$SC_EXISTS" -gt 0 ]; then
  info "local-path StorageClass 已存在，跳过安装"
else
  kubectl apply -f \
    https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.28/deploy/local-path-storage.yaml

  # apply 后 Deployment 需要几秒被调度
  info "等待 local-path-provisioner Pod 出现（10s）..."
  sleep 10

  wait_rollout deployment local-path-provisioner local-path-storage 300s 5
  ok "local-path-provisioner 就绪"
fi

# 确保设为默认（幂等）
kubectl patch storageclass local-path \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}' \
  2>/dev/null || true
ok "StorageClass local-path 已设为默认"
kubectl get storageclass

# ══════════════════════════════════════════════
# 完成
# ══════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                      集群初始化完成                             ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
printf  "║  %-12s  %s  (control-plane)\n" "k8s-master" "$MASTER_IP"
for i in "${!NODE_NAMES[@]}"; do
  printf "║  %-12s  %s\n" "${NODE_NAMES[$i]}" "${NODE_IPS[$i]}"
done
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  CNI      : Cilium + Hubble Relay (ClusterIP)                   ║"
echo "║  LB       : MetalLB  ${METALLB_IP_RANGE}                         ║"
echo "║  Storage  : local-path (default StorageClass)                   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  下一步   : bash 03-deploy-5nodes.sh                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
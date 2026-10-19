#!/bin/bash
# 00-clear.sh
# 完全清理实验环境，幂等，可重复运行
# 不使用 set -e：清理脚本任何一步失败都应继续往下走

log()  { echo ""; echo "=== $* ==="; }
ok()   { echo "  ✅ $*"; }
info() { echo "  ℹ️  $*"; }
warn() { echo "  ⚠️  $*"; }

ERRORS=0
fail() { warn "$*"; ERRORS=$((ERRORS + 1)); }

VM_NAMES=(k8s-master k8s-node1 k8s-node2 k8s-node3 k8s-node4)
VM_IPS=(192.168.100.10 192.168.100.11 192.168.100.12 192.168.100.13 192.168.100.14)
VM_IMAGE_DIR="/home/vm-images"

# ══════════════════════════════════════════════
# 1. 终止后台进程（先停，防止进程持有文件锁）
# ══════════════════════════════════════════════
log "清理后台进程"
pkill -f "port-forward.*hubble-relay" 2>/dev/null && ok "hubble port-forward 已终止" || info "无 hubble port-forward 进程"
pkill -f "minikube tunnel"            2>/dev/null && ok "minikube tunnel 已终止"      || info "无 minikube tunnel 进程"

# 等待进程真正退出，避免后续 virsh 操作遇到文件锁
sleep 2

# ══════════════════════════════════════════════
# 2. 停止并删除 VM
# ══════════════════════════════════════════════
log "清理 VM"
for VM in "${VM_NAMES[@]}"; do
  if virsh dominfo "$VM" &>/dev/null; then
    virsh destroy  "$VM" 2>/dev/null || true   # 已关机时 destroy 报错，忽略
    # 等待 QEMU 进程真正退出，否则 undefine 可能因磁盘被占用而失败
    sleep 3
    virsh undefine "$VM" --remove-all-storage 2>/dev/null \
      && ok "VM $VM 已删除" \
      || fail "VM $VM undefine 失败"
  else
    info "VM $VM 不存在，跳过"
  fi
done

# 确保所有 QEMU 进程退出后再动网桥
sleep 2

# ══════════════════════════════════════════════
# 3. 删除虚拟网桥
# ══════════════════════════════════════════════
log "清理虚拟网桥"
for NET in virbr-k8s minikube; do
  if virsh net-info "$NET" &>/dev/null; then
    virsh net-destroy  "$NET" 2>/dev/null || true
    sleep 1
    virsh net-undefine "$NET" 2>/dev/null \
      && ok "网桥 $NET 已删除" \
      || fail "网桥 $NET undefine 失败"
  else
    info "网桥 $NET 不存在，跳过"
  fi
done

# ══════════════════════════════════════════════
# 4. 删除 VM 磁盘
#    virsh undefine --remove-all-storage 只删 libvirt 跟踪的卷
#    手动再清一遍确保干净
# ══════════════════════════════════════════════
log "清理 VM 磁盘"
for VM in "${VM_NAMES[@]}"; do
  DISK="${VM_IMAGE_DIR}/${VM}.qcow2"
  if [ -f "$DISK" ]; then
    sudo rm -f "$DISK" \
      && ok "磁盘 $DISK 已删除" \
      || fail "磁盘 $DISK 删除失败"
  else
    info "磁盘 $DISK 不存在，跳过"
  fi
done

# ══════════════════════════════════════════════
# 5. 删除 cloud image（强制重新下载，防止损坏缓存）
#    同时清理旧路径（历史上可能放在 /var/lib/libvirt/images/）
# ══════════════════════════════════════════════
log "清理 cloud image"
BASE_IMAGE="${VM_IMAGE_DIR}/ubuntu-22.04-cloudimg.qcow2"
LEGACY_IMAGE="/var/lib/libvirt/images/ubuntu-22.04-cloudimg.qcow2"

for IMG in "$BASE_IMAGE" "$LEGACY_IMAGE"; do
  if [ -f "$IMG" ]; then
    sudo rm -f "$IMG" \
      && ok "cloud image 已删除: $IMG" \
      || fail "cloud image 删除失败: $IMG"
  else
    info "cloud image 不存在，跳过: $IMG"
  fi
done

# ══════════════════════════════════════════════
# 6. 清理 cloud-init 临时文件
#    cidata iso 挂在 /tmp，virsh undefine 不会删
# ══════════════════════════════════════════════
log "清理临时文件"
sudo rm -f  /tmp/cidata-*.iso        && ok "cidata iso 已清理"   || fail "cidata iso 清理失败"
sudo rm -rf /tmp/cidata-k8s-*        && ok "cidata 目录已清理"    || fail "cidata 目录清理失败"
sudo rm -f  /tmp/k8s-network.xml     && ok "network xml 已清理"   || true
sudo rm -f  /tmp/vm-*.xml            && ok "vm xml 已清理"        || true
sudo rm -f  /tmp/k8s-master-*.xml    && ok "patched xml 已清理"   || true
sudo rm -f  /tmp/k8s-node*.xml       && ok "patched xml 已清理"   || true

# ══════════════════════════════════════════════
# 7. 清理 kubeconfig
# ══════════════════════════════════════════════
log "清理 kubeconfig"
rm -f ~/.kube/config \
  && ok "kubeconfig 已清理" \
  || fail "kubeconfig 清理失败"

# ══════════════════════════════════════════════
# 8. 清理 /etc/hosts
# ══════════════════════════════════════════════
log "清理 /etc/hosts"
sudo sed -i '/k8s-master/d'  /etc/hosts
sudo sed -i '/k8s-node/d'    /etc/hosts
sudo sed -i '/kafka-svc/d'   /etc/hosts
ok "/etc/hosts 已清理"

# ══════════════════════════════════════════════
# 9. 清理 SSH known_hosts
# ══════════════════════════════════════════════
log "清理 SSH known_hosts"
for IP in "${VM_IPS[@]}"; do
  ssh-keygen -R "$IP" 2>/dev/null && ok "known_hosts: $IP 已清理" || true
done

# ══════════════════════════════════════════════
# 结果
# ══════════════════════════════════════════════
echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "✅ 环境清理完成，可以运行 bash 01-setup-vms.sh"
else
  echo "⚠️  清理完成，但有 ${ERRORS} 处警告，请检查上方输出"
  echo "   通常不影响重新部署，可继续运行 bash 01-setup-vms.sh"
fi
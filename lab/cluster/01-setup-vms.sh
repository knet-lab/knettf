#!/bin/bash
# 01-setup-vms.sh
# 在宿主机上创建 5 个 KVM 虚拟机，供 K8s 集群使用
#
# ── IP 分配策略 ────────────────────────────────────────────────
#   放弃 netplan 静态 IP（网卡名 enp1s0 不可靠，cloud-init 时序问题多）
#   改用：virsh 网络 DHCP host 条目（MAC → IP 绑定）+ cloud-init DHCP
#   好处：网卡名随便叫什么都行，IP 由 libvirt DHCP 固定分配
# ──────────────────────────────────────────────────────────────
set -e

log()  { echo "";  echo "=== $* ==="; }
ok()   { echo "  ✅ $*"; }
info() { echo "  ℹ️  $*"; }
warn() { echo "  ⚠️  $*"; }
die()  { echo "  ❌ $*"; exit 1; }

# ══════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════
VM_IMAGE_DIR="/home/vm-images"
BASE_IMAGE="${VM_IMAGE_DIR}/ubuntu-22.04-cloudimg.qcow2"
BASE_IMAGE_URL="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
# 更轻量级
# BASE_IMAGE_URL="https://cloud-images.ubuntu.com/minimal/releases/jammy/release/ubuntu-22.04-minimal-cloudimg-amd64.img" 

BRIDGE_NAME="virbr-k8s"
BRIDGE_SUBNET="192.168.100"
BRIDGE_HOST_IP="${BRIDGE_SUBNET}.1"

VM_VCPUS=2
VM_RAM_MB=8192

VM_NAMES=( k8s-master k8s-node1 k8s-node2 k8s-node3 k8s-node4 )
VM_IPS=(
  "${BRIDGE_SUBNET}.10"
  "${BRIDGE_SUBNET}.11"
  "${BRIDGE_SUBNET}.12"
  "${BRIDGE_SUBNET}.13"
  "${BRIDGE_SUBNET}.14"
)
VM_DISKS=( 120 60 60 60 60 )

# 固定 MAC 地址，与 DHCP host 绑定一一对应
VM_MACS=(
  "52:54:00:10:00:01"
  "52:54:00:11:00:01"
  "52:54:00:12:00:01"
  "52:54:00:13:00:01"
  "52:54:00:14:00:01"
)

# ══════════════════════════════════════════════
# Step 1: 检查依赖
# ══════════════════════════════════════════════
log "Step 1: 检查依赖"

PKGS_NEEDED=()
for pkg in virtinst qemu-utils genisoimage wget python3; do
  dpkg -l "$pkg" &>/dev/null || PKGS_NEEDED+=("$pkg")
done
if [ ${#PKGS_NEEDED[@]} -gt 0 ]; then
  info "安装缺失依赖: ${PKGS_NEEDED[*]}"
  sudo apt-get update -qq
  sudo apt-get install -y "${PKGS_NEEDED[@]}"
fi

sudo systemctl enable --now libvirtd

info "等待 libvirtd socket 就绪..."
for attempt in $(seq 1 15); do
  virsh list &>/dev/null && break
  echo "    libvirtd 未就绪，等待... ($attempt/15)"
  sleep 2
done
virsh list &>/dev/null || die "libvirtd socket 超时，请检查 systemctl status libvirtd"
ok "依赖就绪"

# ══════════════════════════════════════════════
# Step 2: 检查 libvirt 组权限
# ══════════════════════════════════════════════
log "Step 2: 检查 libvirt 组权限"

if ! groups | grep -qw libvirt; then
  info "将 $USER 加入 libvirt / kvm 组..."
  sudo usermod -aG libvirt "$USER"
  sudo usermod -aG kvm     "$USER"
  info "组权限已更新，用 sg libvirt 重新执行本脚本..."
  exec sg libvirt -c "bash $0 $*"
fi
ok "libvirt 组权限就绪（用户: $USER）"

# ══════════════════════════════════════════════
# Step 3: 检查磁盘空间
# ══════════════════════════════════════════════
log "Step 3: 检查 ${VM_IMAGE_DIR} 磁盘空间"

sudo mkdir -p "$VM_IMAGE_DIR"
sudo chown root:libvirt "$VM_IMAGE_DIR"
sudo chmod 775          "$VM_IMAGE_DIR"

AVAIL_G=$(df -BG "$VM_IMAGE_DIR" | awk 'NR==2 {gsub(/G/,""); print $4}')
info "${VM_IMAGE_DIR} 可用: ${AVAIL_G}GB"
[ "${AVAIL_G}" -lt 420 ] \
  && die "空间不足（需要 ≥420GB，当前 ${AVAIL_G}GB）"
ok "磁盘空间充足（${AVAIL_G}GB 可用）"

# ══════════════════════════════════════════════
# Step 4: 创建虚拟网桥 virbr-k8s
# 关键改动：在 DHCP 里为每台 VM 的 MAC 绑定固定 IP
# VM 用 DHCP 启动，永远拿到相同的 IP，无需 netplan
# ══════════════════════════════════════════════
log "Step 4: 创建虚拟网桥 ${BRIDGE_NAME}（含 MAC→IP DHCP 绑定）"

if virsh net-info "${BRIDGE_NAME}" &>/dev/null; then
  info "网桥 ${BRIDGE_NAME} 已存在，跳过创建"
else
  # 构建 DHCP host 条目
  DHCP_HOSTS=""
  for i in "${!VM_NAMES[@]}"; do
    DHCP_HOSTS="${DHCP_HOSTS}      <host mac='${VM_MACS[$i]}' name='${VM_NAMES[$i]}' ip='${VM_IPS[$i]}'/>\n"
  done

  # 写网络 XML，用 python 避免 heredoc 变量展开问题
  python3 - << PYEOF
import xml.etree.ElementTree as ET, re

bridge  = "${BRIDGE_NAME}"
host_ip = "${BRIDGE_HOST_IP}"
subnet  = "${BRIDGE_SUBNET}"
hosts_raw = """${DHCP_HOSTS}"""

network  = ET.Element("network")
name_el  = ET.SubElement(network, "name")
name_el.text = bridge

fwd = ET.SubElement(network, "forward")
fwd.set("mode", "nat")

br = ET.SubElement(network, "bridge")
br.set("name", bridge)
br.set("stp",  "on")
br.set("delay","0")

ip_el = ET.SubElement(network, "ip")
ip_el.set("address", host_ip)
ip_el.set("netmask", "255.255.255.0")

dhcp = ET.SubElement(ip_el, "dhcp")
rng  = ET.SubElement(dhcp, "range")
rng.set("start", f"{subnet}.50")
rng.set("end",   f"{subnet}.99")

for line in hosts_raw.strip().splitlines():
    line = line.strip()
    if not line:
        continue
    mac = re.search(r"mac=\'([^\']+)\'", line) or re.search(r'mac=\"([^\"]+)\"', line)
    nm  = re.search(r"name=\'([^\']+)\'", line) or re.search(r'name=\"([^\"]+)\"', line)
    ip  = re.search(r"ip=\'([^\']+)\'", line) or re.search(r'ip=\"([^\"]+)\"', line)
    if mac and nm and ip:
        h = ET.SubElement(dhcp, "host")
        h.set("mac",  mac.group(1))
        h.set("name", nm.group(1))
        h.set("ip",   ip.group(1))

ET.indent(network, space="  ")
ET.ElementTree(network).write("/tmp/k8s-network.xml", encoding="unicode", xml_declaration=False)
print("network XML 已生成")
print(open("/tmp/k8s-network.xml").read())
PYEOF

  info "网络 XML 内容："
  cat /tmp/k8s-network.xml

  virsh net-define    /tmp/k8s-network.xml
  virsh net-start     "${BRIDGE_NAME}"
  virsh net-autostart "${BRIDGE_NAME}"
  ok "网桥 ${BRIDGE_NAME} 创建完成（含 DHCP MAC 绑定）"
fi

# 等待网桥接口出现
info "等待网桥接口 ${BRIDGE_NAME} 就绪..."
for attempt in $(seq 1 15); do
  ip link show "${BRIDGE_NAME}" &>/dev/null && break
  echo "    网桥接口未就绪... ($attempt/15)"
  sleep 2
done
ip link show "${BRIDGE_NAME}" &>/dev/null \
  || die "网桥接口 ${BRIDGE_NAME} 未出现"
ok "网桥接口 ${BRIDGE_NAME} 已就绪"

# ══════════════════════════════════════════════
# Step 5: 下载 Ubuntu 22.04 cloud image
# ══════════════════════════════════════════════
log "Step 5: 下载 Ubuntu 22.04 cloud image"

if [ -f "$BASE_IMAGE" ]; then
  VSIZE=$(sudo qemu-img info "$BASE_IMAGE" 2>/dev/null \
    | awk '/virtual size/{print $3}')
  if [ -n "$VSIZE" ] && [ "$VSIZE" != "0" ]; then
    ok "cloud image 已存在且完整（virtual size=${VSIZE}），跳过下载"
  else
    info "cloud image 损坏，删除后重新下载"
    sudo rm -f "$BASE_IMAGE"
  fi
fi

if [ ! -f "$BASE_IMAGE" ]; then
  info "下载 Ubuntu 22.04 cloud image（约 660MB）..."
  sudo wget --progress=bar:force -O "$BASE_IMAGE" "$BASE_IMAGE_URL" \
    || die "下载失败，请检查网络"
  sudo chown root:libvirt "$BASE_IMAGE"
  sudo chmod 664          "$BASE_IMAGE"
  ok "下载完成"
fi

sudo qemu-img info "$BASE_IMAGE" \
  | grep -E "file format|virtual size|disk size"

# ══════════════════════════════════════════════
# Step 6: 准备 SSH 密钥
# ══════════════════════════════════════════════
log "Step 6: 准备 SSH 密钥"

if [ ! -f ~/.ssh/id_rsa ]; then
  ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
  ok "SSH 密钥已生成: ~/.ssh/id_rsa"
else
  ok "SSH 密钥已存在: ~/.ssh/id_rsa"
fi
SSH_PUB_KEY=$(cat ~/.ssh/id_rsa.pub)

# ══════════════════════════════════════════════
# Step 7: 批量创建 VM
#
# cloud-init 改动：
#   - 删除 write_files netplan 静态 IP（网卡名不可靠）
#   - 改为纯 DHCP（libvirt 已绑定 MAC→IP，效果等同静态）
#   - 保留 growpart/resize2fs 扩容
# ══════════════════════════════════════════════
log "Step 7: 创建 VM"

for i in "${!VM_NAMES[@]}"; do
  VM_NAME="${VM_NAMES[$i]}"
  VM_IP="${VM_IPS[$i]}"
  VM_MAC="${VM_MACS[$i]}"
  VM_DISK_GB="${VM_DISKS[$i]}"
  DISK_PATH="${VM_IMAGE_DIR}/${VM_NAME}.qcow2"
  CIDATA_DIR="/tmp/cidata-${VM_NAME}"
  CIDATA_ISO="/tmp/cidata-${VM_NAME}.iso"

  if virsh dominfo "$VM_NAME" &>/dev/null; then
    info "VM ${VM_NAME} 已存在，跳过"
    continue
  fi

  info "─── 创建 ${VM_NAME}  IP=${VM_IP}  MAC=${VM_MAC}  磁盘=${VM_DISK_GB}GB"

  sudo qemu-img create \
    -f qcow2 -F qcow2 \
    -b "$BASE_IMAGE" \
    "$DISK_PATH" "${VM_DISK_GB}G"
  sudo chown root:libvirt "$DISK_PATH"
  sudo chmod 664          "$DISK_PATH"
  info "差量磁盘已创建: ${DISK_PATH}"

  rm -rf "$CIDATA_DIR"
  mkdir -p "$CIDATA_DIR"

  # user-data：只做用户/SSH/扩容，不做 netplan
  cat > "${CIDATA_DIR}/user-data" << UDEOF
#cloud-config
hostname: ${VM_NAME}
manage_etc_hosts: true

users:
  - name: k8s
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    ssh_authorized_keys:
      - ${SSH_PUB_KEY}

runcmd:
  - swapoff -a
  - sed -i '/\bswap\b/d' /etc/fstab
  - systemctl disable --now ufw || true
  - growpart /dev/vda 1 || true
  - resize2fs /dev/vda1 || true

package_update: false
package_upgrade: false
UDEOF

  cat > "${CIDATA_DIR}/meta-data" << MDEOF
instance-id: ${VM_NAME}
local-hostname: ${VM_NAME}
MDEOF

  genisoimage \
    -output  "$CIDATA_ISO" \
    -volid   cidata \
    -joliet -rock \
    "${CIDATA_DIR}/user-data" \
    "${CIDATA_DIR}/meta-data" \
    2>/dev/null
  info "cloud-init iso 已生成: ${CIDATA_ISO}"

  # 指定固定 MAC，与 DHCP host 绑定对应
  virt-install \
    --name         "$VM_NAME" \
    --memory       $VM_RAM_MB \
    --vcpus        $VM_VCPUS \
    --disk         path="${DISK_PATH}",format=qcow2,bus=virtio \
    --disk         path="${CIDATA_ISO}",device=cdrom \
    --network      network=${BRIDGE_NAME},model=virtio,mac="${VM_MAC}",driver.queues=${VM_VCPUS} \
    --graphics     none \
    --os-variant   ubuntu22.04 \
    --noautoconsole \
    --import
  ok "VM ${VM_NAME} 已启动（MAC=${VM_MAC}）"

  sleep 3
done

# ══════════════════════════════════════════════
# Step 8: 等待所有 VM SSH 就绪
#
# 内置自动诊断：每 2 分钟检查一次：
#   - VM 运行状态
#   - DHCP 租约（是否拿到正确 IP）
#   - ping 连通性
#   - SSH 详细报错
# ══════════════════════════════════════════════
log "Step 8: 等待所有 VM SSH 就绪（最多 8 分钟）"

info "等待 VM 完成 cloud-init 初始化（45s）..."
sleep 45

# 诊断函数：SSH 超时时自动运行
diagnose_vm() {
  local VM_NAME=$1
  local VM_IP=$2
  local VM_MAC=$3

  warn "── 自动诊断 ${VM_NAME} ──"

  local STATE
  STATE=$(virsh domstate "$VM_NAME" 2>/dev/null || echo "unknown")
  info "  VM 状态: ${STATE}"

  info "  DHCP 租约（该 VM）："
  virsh net-dhcp-leases "${BRIDGE_NAME}" 2>/dev/null | grep -i "${VM_MAC}" \
    || warn "    未找到该 VM 的 DHCP 租约"

  info "  所有 DHCP 租约："
  virsh net-dhcp-leases "${BRIDGE_NAME}" 2>/dev/null || true

  if ping -c 2 -W 2 "${VM_IP}" &>/dev/null; then
    info "  ping ${VM_IP} ✅（IP 有响应，SSH 服务可能还未启动）"
  else
    warn "  ping ${VM_IP} ❌（VM 没有拿到正确 IP 或网络未就绪）"
  fi

  info "  SSH 详细连接："
  ssh \
    -v \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 \
    -o BatchMode=yes \
    -i ~/.ssh/id_rsa \
    "k8s@${VM_IP}" "echo ok" 2>&1 | tail -15 || true
}

for i in "${!VM_NAMES[@]}"; do
  VM_NAME="${VM_NAMES[$i]}"
  VM_IP="${VM_IPS[$i]}"
  VM_MAC="${VM_MACS[$i]}"
  info "等待 ${VM_NAME} (${VM_IP} / ${VM_MAC})..."

  READY=false

  for attempt in $(seq 1 96); do
    if ssh \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=5 \
        -o BatchMode=yes \
        -i ~/.ssh/id_rsa \
        "k8s@${VM_IP}" "echo ok" &>/dev/null; then
      ok "${VM_NAME} SSH 就绪（第 ${attempt} 次尝试）"
      READY=true
      break
    fi

    # 每 2 分钟自动诊断一次
    if [ $((attempt % 24)) -eq 0 ]; then
      diagnose_vm "$VM_NAME" "$VM_IP" "$VM_MAC"

      # 如果 DHCP 分配了错误 IP，尝试重启网络
      LEASE_IP=$(virsh net-dhcp-leases "${BRIDGE_NAME}" 2>/dev/null \
        | grep -i "${VM_MAC}" | awk '{print $5}' | cut -d/ -f1 || true)
      if [ -n "$LEASE_IP" ] && [ "$LEASE_IP" != "$VM_IP" ]; then
        warn "  VM 拿到了错误 IP: ${LEASE_IP}（期望 ${VM_IP}），尝试重启 libvirt 网络..."
        virsh net-destroy "${BRIDGE_NAME}" 2>/dev/null || true
        sleep 2
        virsh net-start   "${BRIDGE_NAME}" 2>/dev/null || true
        sleep 3
      fi
    fi

    echo "    等待中... ($attempt/96)"
    sleep 5
  done

  if [ "$READY" = "false" ]; then
    diagnose_vm "$VM_NAME" "$VM_IP" "$VM_MAC"
    die "${VM_NAME} SSH 超时（8 分钟）。诊断信息见上方输出。"
  fi

  # 确认实际 IP
  ACTUAL_IP=$(ssh \
    -o StrictHostKeyChecking=no -o BatchMode=yes -i ~/.ssh/id_rsa \
    "k8s@${VM_IP}" \
    "hostname -I | awk '{print \$1}'" 2>/dev/null || echo "unknown")
  info "  ${VM_NAME} 实际 IP: ${ACTUAL_IP}（期望: ${VM_IP}）"

  sleep 2
done

# ══════════════════════════════════════════════
# Step 9: 验证各节点磁盘实际大小
# ══════════════════════════════════════════════
log "Step 9: 验证各节点磁盘"

for i in "${!VM_NAMES[@]}"; do
  DISK_INFO=$(ssh \
    -o StrictHostKeyChecking=no -o BatchMode=yes -i ~/.ssh/id_rsa \
    "k8s@${VM_IPS[$i]}" \
    "df -h / | awk 'NR==2'" 2>/dev/null || echo "无法获取")
  info "${VM_NAMES[$i]}  期望=${VM_DISKS[$i]}GB  实际: ${DISK_INFO}"
done

# ══════════════════════════════════════════════
# 完成
# ══════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                      VM 创建完成                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
for i in "${!VM_NAMES[@]}"; do
  printf "║  %-12s  %-18s  %3sGB  %s\n" \
    "${VM_NAMES[$i]}" "${VM_IPS[$i]}" "${VM_DISKS[$i]}" "${VM_MACS[$i]}"
done
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  镜像目录 : ${VM_IMAGE_DIR}"
echo "║  网桥     : ${BRIDGE_NAME}  (${BRIDGE_HOST_IP})"
echo "║  IP 分配  : libvirt DHCP MAC 绑定（无 netplan 静态 IP）"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  下一步   : bash 02-setup-cluster.sh                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
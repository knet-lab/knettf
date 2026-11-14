#!/bin/bash
# diagnose-host.sh - 宿主机环境诊断

echo "=================================================="
echo "【1】磁盘情况"
echo "=================================================="
df -h
echo ""
lsblk

echo ""
echo "=================================================="
echo "【2】网络接口"
echo "=================================================="
ip addr show
echo ""
ip link show

echo ""
echo "=================================================="
echo "【3】libvirt 网络"
echo "=================================================="
virsh net-list --all
echo ""
virsh net-dumpxml virbr-k8s 2>/dev/null || echo "virbr-k8s 不存在"

echo ""
echo "=================================================="
echo "【4】网桥情况"
echo "=================================================="
bridge link show 2>/dev/null || brctl show 2>/dev/null || echo "无网桥工具"

echo ""
echo "=================================================="
echo "【5】VM 状态"
echo "=================================================="
virsh list --all
echo ""
virsh domiflist k8s-master 2>/dev/null || echo "k8s-master 不存在"

echo ""
echo "=================================================="
echo "【6】DHCP 租约"
echo "=================================================="
virsh net-dhcp-leases virbr-k8s 2>/dev/null

echo ""
echo "=================================================="
echo "【7】宿主机 iptables（NAT 规则）"
echo "=================================================="
sudo iptables -t nat -L -n 2>/dev/null | grep -E "virbr|MASQ|192.168.100"

echo ""
echo "=================================================="
echo "【8】cloud image 信息"
echo "=================================================="
sudo qemu-img info /var/lib/libvirt/images/ubuntu-22.04-cloudimg.qcow2
echo ""
sudo qemu-img info /var/lib/libvirt/images/k8s-master-test.qcow2 2>/dev/null || \
sudo qemu-img info /var/lib/libvirt/images/k8s-master.qcow2 2>/dev/null || \
echo "k8s-master 磁盘不存在"

echo ""
echo "=================================================="
echo "【9】宿主机内核和 KVM"
echo "=================================================="
uname -r
lsmod | grep kvm
ls /dev/kvm && echo "KVM 设备存在" || echo "KVM 设备不存在"

echo ""
echo "=================================================="
echo "【10】libvirt 版本"
echo "=================================================="
virsh version
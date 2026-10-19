<template>
  <div v-pre>
        <h1>集群与 Shell 脚本</h1>
    <div class="meta">读完你能：画出宿主机、网桥、VM、集群组件的关系；读懂 00 / 01 / 02 / 03 四个脚本每一步在做什么、为什么这样做；看懂 Kafka、Vector、靶机的清单；知道宿主机上 systemd、cloudflared、crontab、PostgreSQL 容器的配置。<br>
      脚本在 <span class="tag tag-k">K</span> <code>~/knetsentinel/kubeadm-cluster/</code>，都以普通用户运行（内部按需 <code>sudo</code>），<b>不要</b> <code>sudo bash</code> 整个脚本（kubeconfig 会写到 root 家目录）。逐步的开关机 / 重建命令见 <a href="/help/power">开关机 · 重建 · 备份</a>。</div>

    <section id="ip">
      <h2>5.1 IP 规划（全部在 192.168.100.0/24）</h2>
      <p>整个系统的很多地方按 IP 段做判断，先把这张表记住：</p>
      <div class="table-wrap"><table>
        <tr><th>地址</th><th>是谁</th><th>谁定的</th><th>哪里依赖它</th></tr>
        <tr><td><code>.1</code></td><td>宿主机在网桥 virbr-k8s 上的地址（网关）</td><td>01 脚本</td><td>bridge 过滤（基础设施）；入口 B 的 WS 地址；VM 出网 NAT</td></tr>
        <tr><td><code>.10</code></td><td>k8s-master（API <code>:6443</code>）</td><td>01：MAC <code>52:54:00:10:00:01</code> 绑定</td><td>kubeconfig；Cilium <code>k8sServiceHost</code></td></tr>
        <tr><td><code>.11 ~ .14</code></td><td>k8s-node1 ~ node4</td><td>01：MAC <code>52:54:00:1N:00:01</code></td><td>攻击脚本目标</td></tr>
        <tr><td><code>.16 ~ .29</code></td><td>伪造攻击源（<code>.20-.29</code> 实际使用）</td><td><code>traffic/spoof_attack.py</code>、<code>handle_addr.py</code></td><td>bridge 打标签 label=1</td></tr>
        <tr><td><code>.50 ~ .64</code></td><td>伪造正常源</td><td><code>traffic/send_request.py</code>、<code>send_normal_scapy.py</code></td><td>bridge 打标签 label=0。注意它和 DHCP 动态池 .50-.99 重叠</td></tr>
        <tr><td><code>.50 ~ .99</code></td><td>libvirt DHCP 动态池</td><td>01 网络 XML</td><td>没有绑定 MAC 的机器拿这里的地址</td></tr>
        <tr><td><code>.170 ~ .184</code></td><td>simulation 攻击源</td><td><code>simulation/</code></td><td>不在标签规则内，label 为空</td></tr>
        <tr><td><code>.200 ~ .203</code></td><td>kafka-0~3-external（<code>:9094</code>）</td><td>MetalLB 按创建顺序分配</td><td><b>bridge.py 写死</b>、<code>~/knetsentinel/.env</code>、检测器 ConfigMap</td></tr>
        <tr><td><code>.204</code></td><td>my-nginx（<code>:80</code>）</td><td>MetalLB</td><td><code>send_request.py</code> 写死</td></tr>
        <tr><td><code>.210 ~ .214</code></td><td>靶机 http-api / mysql-sim / ftp-sim / udp-echo / dns-sim</td><td><code>targets.yaml</code> 注解指定</td><td>实验脚本</td></tr>
        <tr><td><code>.200 ~ .250</code></td><td>MetalLB 地址池</td><td>02 脚本</td><td>bridge 视为基础设施</td></tr>
        <tr><td><code>10.244.0.0/16</code></td><td>Pod 网段</td><td>02：<code>--pod-network-cidr</code></td><td>bridge 视 <code>10.*</code> 为基础设施</td></tr>
      </table></div>
      <div class="note">MetalLB 按 Service <b>创建顺序</b>分配地址。03 脚本先单独创建 4 个 Kafka Service，就是为了让它们拿到 .200-.203。如果先建了别的 LoadBalancer，Kafka 地址就会变，必须同步修改 <code>bridge.py</code>。</div>
    </section>

    <section id="host">
      <h2>5.2 宿主机前提</h2>
      <ul>
        <li>Ubuntu，支持 KVM（<code>kvm-ok</code> 或 <code>ls /dev/kvm</code>），能 sudo，能访问外网。</li>
        <li>出网网卡 <code>enp6s0</code>（02 脚本写死在 <code>HOST_NIC</code>，换机器要改；<code>ip route get 1.1.1.1</code> 查）。</li>
        <li><code>~/vm-images</code> 所在分区可用 ≥ 420GB（01 脚本检查；master 120G + 4×60G，qcow2 稀疏分配，实际占用小得多）。</li>
        <li>工具：<code>virtinst qemu-utils genisoimage wget python3</code>（01 自动装）、<code>kubectl</code>、<code>helm</code>（02 自动装）、<code>docker</code>、<code>uv</code>、<code>pnpm</code>、<code>terraform</code>、<code>tflint</code>、<code>tfsec</code>、<code>trivy</code>、checkov（在 <code>~/terraform/.venv</code>）、<code>hubble</code> CLI（可选）。</li>
        <li>SSH 密钥 <code>~/.ssh/id_rsa</code>（01 没有就生成），公钥会写进每台 VM 的 <code>k8s</code> 用户。</li>
      </ul>
    </section>

    <section id="s00">
      <h2>5.3 00-clear.sh：彻底清理（不可逆）</h2>
      <p>按顺序：杀掉 hubble <code>port-forward</code>、minikube tunnel 后台进程 → <code>virsh destroy/undefine</code> 5 台 VM → 删网络 virbr-k8s → 删 <code>~/vm-images</code> 下 VM 磁盘 → 删 cloud image → 删 <code>/tmp/cidata-*</code>、<code>/tmp/k8s-network.xml</code> → 删 <code>~/.kube/config</code> → 从 <code>/etc/hosts</code> 删 k8s 相关行 → 从 <code>known_hosts</code> 删 .10-.14。</p>
      <div class="danger">执行后集群、Kafka 中的数据、kubeconfig 全部消失。执行前按 <a href="/help/power#rebuild-cluster">重建整个集群</a> 第 1 步备份 <code>~/knetsentinel</code> 整个目录（它不在 Git 里）。</div>
    </section>

    <section id="s01">
      <h2>5.4 01-setup-vms.sh：建网桥和 5 台 VM</h2>
      <div class="table-wrap"><table>
        <tr><th>Step</th><th>做什么</th><th>为什么 / 要点</th></tr>
        <tr><td>配置区</td><td><code>VM_VCPUS=2</code>、<code>VM_RAM_MB=8192</code>、磁盘 <code>120 60 60 60 60</code>、IP 和 MAC 数组</td><td>改规格就改这里</td></tr>
        <tr><td>1</td><td>检查并安装依赖，启动 <code>libvirtd</code>，等 socket 就绪</td><td></td></tr>
        <tr><td>2</td><td>当前用户不在 libvirt 组 → 加入 libvirt、kvm 组，用 <code>exec sg libvirt</code> 重新执行自己</td><td>免得要求重新登录</td></tr>
        <tr><td>3</td><td>建 <code>~/vm-images</code>（root:libvirt 775），检查可用空间 ≥ 420GB</td><td></td></tr>
        <tr><td>4</td><td>用内嵌 Python 生成网络 XML：NAT 模式、网桥 virbr-k8s、<code>.1/24</code>、DHCP 池 .50-.99、5 条 <code>&lt;host mac name ip&gt;</code> 绑定；<code>net-define</code>、<code>net-start</code>、<code>net-autostart</code></td><td><b>用 DHCP 绑定代替 netplan 静态 IP</b>：VM 网卡名不可靠，cloud-init 写 netplan 时序问题多；绑定后效果等同静态</td></tr>
        <tr><td>5</td><td>下载 Ubuntu 22.04 cloud image 到 <code>~/vm-images/ubuntu-22.04-cloudimg.qcow2</code></td><td>已存在则跳过</td></tr>
        <tr><td>6</td><td>准备 SSH 密钥</td><td></td></tr>
        <tr><td>7</td><td>每台 VM：<code>qemu-img create -b 基础镜像</code> 建差量盘 → 写 cloud-init <code>user-data</code>（用户 k8s、免密 sudo、公钥、关 swap、关 ufw、growpart 扩容）和 <code>meta-data</code> → <code>genisoimage</code> 打成 cidata ISO → <code>virt-install --import</code>，指定固定 MAC，<code>driver.queues=2</code></td><td>差量盘：5 台共用一个只读基础镜像，<b>基础镜像不能删</b>；已存在的 VM 跳过（幂等）</td></tr>
        <tr><td>8</td><td>等待 5 台 SSH 就绪（最多 8 分钟），每 2 分钟自动诊断一次（DHCP 租约、VM 状态）</td><td></td></tr>
        <tr><td>9</td><td>SSH 进去看各节点 <code>/</code> 实际大小</td><td>确认 growpart 生效</td></tr>
      </table></div>
      <p>成功后：<code>ssh k8s@192.168.100.10</code> 能免密登录。VM <b>没有</b>设置 autostart（宿主机重启后要手动开，<a href="/help/power#startup">开机恢复</a>）。</p>
    </section>

    <section id="s02">
      <h2>5.5 02-setup-cluster.sh：装 Kubernetes</h2>
      <p>全部步骤幂等，失败后可直接重跑。<code>run_on IP 命令</code> 是脚本里的 SSH 封装；<code>wait_rollout</code> 等待 DaemonSet / Deployment 就绪。</p>
      <div class="table-wrap"><table>
        <tr><th>Step</th><th>做什么</th><th>为什么 / 要点</th></tr>
        <tr><td>0</td><td>开 <code>ip_forward</code>（写 <code>/etc/sysctl.d/99-ipforward.conf</code>）；先删再加 iptables：<code>nat POSTROUTING -s 192.168.100.0/24 ! -d 同网段 -o enp6s0 -j MASQUERADE</code>、<code>FORWARD -s/-d 网段 ACCEPT</code>；从 master curl pkgs.k8s.io 验证出网</td><td>libvirt 有时不生成 NAT 规则；<b>这些 iptables 规则重启后丢失</b></td></tr>
        <tr><td>1</td><td>确认 5 个节点 SSH 通</td><td></td></tr>
        <tr><td>2</td><td><code>hostnamectl set-hostname</code> 强制设一次</td><td>cloud-init 偶尔不及时，节点名错了 kubeadm join 会冲突</td></tr>
        <tr><td>3</td><td>每个节点：关 swap；加载 <code>overlay</code>、<code>br_netfilter</code>；sysctl 开桥接 iptables 和转发；装 containerd 并设 <code>SystemdCgroup = true</code>；加 pkgs.k8s.io v1.28 源；装并 <code>apt-mark hold</code> kubelet kubeadm kubectl</td><td>K8s 节点的标准前置；<code>SystemdCgroup</code> 必须与 kubelet 一致，否则 Pod 反复重启</td></tr>
        <tr><td>4</td><td>master 上 <code>kubeadm init --apiserver-advertise-address=.10 --pod-network-cidr=10.244.0.0/16 --skip-phases=addon/kube-proxy</code>（已有 admin.conf 则跳过）</td><td><b>跳过 kube-proxy</b>，因为 Cilium 要完全替代它</td></tr>
        <tr><td>5</td><td>scp master 的 kubeconfig 到宿主机 <code>~/.kube/config</code>，server 改为 <code>https://192.168.100.10:6443</code>，等 kubectl 可用</td><td>之后所有 kubectl / helm 都在宿主机执行</td></tr>
        <tr><td>6</td><td>生成 join 命令（token 24 小时），未加入的 worker 执行 join</td><td></td></tr>
        <tr><td>7</td><td>宿主机没有 helm 就安装</td><td></td></tr>
        <tr><td>8</td><td>helm 装 Cilium：<code>kubeProxyReplacement=true</code>、<code>k8sServiceHost=.10</code>、<code>k8sServicePort=6443</code>、<code>hubble.enabled</code>、<code>hubble.relay.enabled</code>、relay Service ClusterIP <code>4245</code>、<code>hubble.ui.enabled</code>、<code>bpf.monitorAggregation=medium</code>、<code>mtu=1450</code>；再 patch <code>hubble-relay</code> Service 端口为 4245</td><td>没有 kube-proxy 时 Cilium 无法通过 ClusterIP 找到 API server，所以要直接给 IP；Vector 写死连 <code>:4245</code>；MTU 1450 给封装留余量</td></tr>
        <tr><td>9</td><td>等 cilium DS、hubble-relay 就绪 → 等所有节点 Ready</td><td>节点在网络插件就绪前一直 NotReady</td></tr>
        <tr><td>10</td><td>helm 装 MetalLB → 等 controller、speaker → apply <code>IPAddressPool k8s-pool</code>（.200-.250）+ <code>L2Advertisement k8s-l2</code></td><td>MetalLB webhook 没就绪时 apply 会 400，重跑即可</td></tr>
        <tr><td>11</td><td>装 local-path-provisioner 并设为默认 StorageClass</td><td>Kafka broker 的 PVC 需要它</td></tr>
      </table></div>
      <p>成功后：<code>kubectl get nodes</code> 5 个 Ready；<code>kubectl -n kube-system get ds cilium</code> 5/5。</p>
    </section>

    <section id="s03">
      <h2>5.6 03-deploy-5nodes.sh：数据管道</h2>
      <div class="table-wrap"><table>
        <tr><th>Step</th><th>做什么</th><th>为什么 / 要点</th></tr>
        <tr><td>1</td><td>前置检查：5 节点 Ready、有 local-path、MetalLB controller 和 hubble-relay Running</td><td>缺一个就退出</td></tr>
        <tr><td>2</td><td>确认 <code>kafka-5nodes.yaml</code>、<code>vector-5nodes.yaml</code> 存在</td><td>路径写死在脚本开头</td></tr>
        <tr><td>3</td><td>用 Python 从 Kafka 清单里<b>只挑出 Service 文档</b>先 apply</td><td>先拿到 IP 才能配置 broker 的对外地址</td></tr>
        <tr><td>4</td><td>等 <code>kafka-0..3-external</code> 都拿到 LoadBalancer IP（每个最多 180 秒）</td><td></td></tr>
        <tr><td>5</td><td>创建 ConfigMap <code>kafka-node-ips</code>：<code>node-0..3</code> = 4 个 IP，<code>nodeport-0..3</code> = 9094</td><td>broker 的 init 容器读它生成 <code>advertised.listeners</code></td></tr>
        <tr><td>6</td><td>apply 完整 Kafka 清单 → 等 <code>kafka-controller</code> Running → 等 15 秒 KRaft 初始化 → 等 <code>sts/kafka-broker</code> 4 副本（最多 6 分钟）</td><td></td></tr>
        <tr><td>7</td><td>Secret <code>kube-system/vector-kafka-secret</code>：<code>bootstrap_servers=kafka-svc.default.svc.cluster.local:9092</code></td><td>Vector 在集群内走 9092，不走外部地址</td></tr>
        <tr><td>8</td><td>apply Vector → 等 DS → 检查重启次数 &gt; 5 告警</td><td></td></tr>
        <tr><td>9</td><td><code>kubectl create deployment my-nginx --image=nginx</code> + <code>expose --type=LoadBalancer --port=80</code> → 等 IP（.204）</td><td>正常流量的目标</td></tr>
        <tr><td>10</td><td>后台 <code>kubectl port-forward svc/hubble-relay 4245</code>，日志 <code>/tmp/hubble-pf.log</code></td><td>只给宿主机上 <code>hubble observe</code> 调试用，Vector 不依赖它；宿主机重启后不会自动恢复</td></tr>
        <tr><td>11</td><td><code>/etc/hosts</code> 加 <code>192.168.100.200 kafka-svc.default.svc.cluster.local</code></td><td>宿主机脚本用集群内域名时能解析</td></tr>
        <tr><td>12</td><td>重写 <code>~/knetsentinel/.env</code>：<code>BOOTSTRAP_SERVERS=.200:9094,...</code>、<code>GROUP_ID=ebpf-log-consumer-group</code>、<code>AUTO_OFFSET_RESET=earliest</code>、<code>TOPICS='["ebpf-net-logs"]'</code></td><td>knetsentinel 的 Python 脚本读它</td></tr>
      </table></div>
    </section>

    <section id="kafka">
      <h2>5.7 Kafka 清单 <code>kafka-svc/kafka-5nodes.yaml</code></h2>
      <div class="table-wrap"><table>
        <tr><th>对象</th><th>说明</th></tr>
        <tr><td>Service <code>kafka-headless</code></td><td>无头服务，给 StatefulSet 每个 Pod 一个 DNS 名 <code>kafka-broker-N.kafka-headless.default.svc.cluster.local</code></td></tr>
        <tr><td>Service <code>kafka-svc</code></td><td>ClusterIP，集群内客户端入口 <code>:9092</code>（Vector 用）</td></tr>
        <tr><td>Service <code>kafka-controller-svc</code></td><td>controller 的 <code>:9093</code></td></tr>
        <tr><td>Service <code>kafka-0..3-external</code></td><td>LoadBalancer，selector 按 <code>statefulset.kubernetes.io/pod-name</code> 一对一指向某个 broker，端口 9094</td></tr>
        <tr><td>Pod <code>kafka-controller</code></td><td><code>apache/kafka:4.0.2</code>，KRaft 控制器，<code>listeners=CONTROLLER://0.0.0.0:9093</code>。<b>裸 Pod + emptyDir</b>：删了不会重建，元数据丢失</td></tr>
        <tr><td>StatefulSet <code>kafka-broker</code>（4 副本）</td><td>init 容器（busybox）读 Pod 序号和 <code>kafka-node-ips</code>，生成 <code>KAFKA_NODE_ID</code> 和 <code>advertised.listeners=PLAINTEXT://kafka-broker-N.kafka-headless...:9092,EXTERNAL://192.168.100.20N:9094</code>（broker-0..3 对应 .200–.203）；主容器 <code>listeners=PLAINTEXT://:9092,EXTERNAL://:9094</code>；副本因子 3、<code>min.insync.replicas=2</code>；每个 10Gi PVC（local-path）</td></tr>
      </table></div>
      <div class="learn"><b>为什么要两个 listener</b>：集群内的客户端（Vector）用 PLAINTEXT 和 DNS 名；集群外的客户端（宿主机上的后端 bridge）只能访问 MetalLB 的 IP，所以 broker 必须把自己的“外部 IP:9094”告诉客户端。这就是 03 脚本必须先拿 IP 再建 broker 的原因。</div>
      <p>常用：</p>
<pre><code>kubectl exec kafka-broker-0 -- /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic ebpf-net-logs
kubectl exec kafka-broker-0 -- /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group vigil-bridge   <span class="c"># 看 LAG（积压）</span>
kubectl exec kafka-broker-0 -- /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic ebpf-net-logs --max-messages 1</code></pre>
    </section>

    <section id="vector">
      <h2>5.8 Vector 清单 <code>cilium-vector/vector-5nodes.yaml</code></h2>
      <ul>
        <li>ConfigMap <code>vector-config</code>：source <code>hubble_flows</code>（<code>type: exec</code>，streaming，进程退出 5 秒后重启）→ transform <code>parse_flow</code>（VRL <code>parse_json(.message)</code>，失败 abort）→ sink <code>kafka_output</code>（topic <code>ebpf-net-logs</code>，json，批 500 / 1 秒，内存缓冲 5 万，满了 <code>drop_newest</code>）。</li>
        <li>ServiceAccount + ClusterRole（pods / nodes / namespaces 只读）+ Binding。</li>
        <li>DaemonSet <code>vector</code>（kube-system），<code>tolerations: operator Exists</code>（容忍所有污点），所以 5 个节点各一个。init 容器从 <code>quay.io/cilium/hubble:v0.13.0</code> 把 <code>hubble</code> 二进制拷进共享卷；主容器 <code>timberio/vector:0.38.0-distroless-libc</code>，环境变量 <code>KAFKA_BOOTSTRAP</code> 来自 <code>vector-kafka-secret</code>，<code>VECTOR_LOG=warn</code>。</li>
      </ul>
      <p>注意每个节点上的 Vector 都连同一个 hubble-relay 拿<b>全集群</b>的事件，理论上同一事件会被写 5 次。若 Kafka 里出现重复事件，原因在这里。<code>cilium-vector/vector.yaml</code> 是旧 minikube 版本，不用。</p>
    </section>

    <section id="others">
      <h2>5.9 其他清单</h2>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>内容</th></tr>
        <tr><td><code>cluster-setup/targets.yaml</code></td><td>命名空间 <code>targets</code>，5 个 DaemonSet + LoadBalancer：<code>http-api</code> .210（http-echo）、<code>mysql-sim</code> .211、<code>ftp-sim</code> .212、<code>udp-echo</code> .213、<code>dns-sim</code> .214（alpine 模拟）。地址用注解 <code>metallb.universe.tf/loadBalancerIPs</code> 指定</td></tr>
        <tr><td><code>cluster-setup/host-firewall-ccnp.yaml</code></td><td><code>CiliumClusterwideNetworkPolicy host-visibility</code>：对所有节点的 host endpoint 放行来自 cluster/host/remote-node、<code>192.168.100.0/24</code>、<code>10.244.0.0/16</code> 的入站。作用是让 Hubble 能看到发往节点本身的伪造源 IP 流量</td></tr>
        <tr><td><code>cluster-setup/init*.sh</code>、<code>minikube-check.sh</code></td><td>旧 minikube 时代的脚本，不再使用</td></tr>
        <tr><td><code>ingress-controller/my-nginx-ingress.yaml</code></td><td>nginx Ingress 示例</td></tr>
        <tr><td><code>hubble-scripts/last_record.sh</code></td><td>空文件</td></tr>
        <tr><td><code>kubeadm-cluster/host-info.sh</code></td><td>宿主机诊断（CPU、内存、磁盘、网卡、KVM），输出 <code>host-info.log</code></td></tr>
      </table></div>
    </section>

    <section id="hostsvc">
      <h2>5.10 宿主机上的服务（NetSentinel 侧）</h2>
      <h3>后端：<code>~/.config/systemd/user/netsentinel.service</code></h3>
<pre class="on-prod"><code>[Service]
WorkingDirectory=/home/soar009/netsentinel-prod/backend      <span class="c"># 线上目录 <span class="vp">~/netsentinel-prod</span>，不是开发目录</span>
Environment=DJANGO_SETTINGS_MODULE=backend.settings
ExecStart=/home/soar009/netsentinel-prod/.venv/bin/uvicorn backend.asgi:application --host 0.0.0.0 --port 8080
Restart=always          RestartSec=3       <span class="c"># 挂了 3 秒后自动拉起</span>
TimeoutStopSec=8        KillMode=mixed     <span class="c"># 停止时先 SIGTERM，8 秒后强杀</span>
TasksMax=500  MemoryMax=3G  MemorySwapMax=0 <span class="c"># 超 3G 内存直接被杀（然后自动重启）</span>
[Install]
WantedBy=default.target</code></pre>
      <p>用户服务要在用户未登录时也运行，需要 <code>loginctl enable-linger soar009</code>（已开）。改了 unit 文件后 <code>systemctl --user daemon-reload</code>。</p>
      <h3>公网：<code>cloudflared-knettf.service</code> + <code>~/.cloudflared/netsentinel.yml</code></h3>
<pre><code>tunnel: 491d938b-...           credentials-file: ~/.cloudflared/491d938b-....json
ingress:
  - hostname: knettf.com   service: http://localhost:8080
  - service: http_status:404</code></pre>
      <p>Cloudflare 侧需要 knettf.com 的 DNS 指向这个隧道。WebSocket 经隧道可以正常工作。</p>
      <h3>PostgreSQL：Docker 容器 <code>pg</code></h3>
      <p>镜像 <code>postgres</code>（当前 18.4），<code>--restart unless-stopped</code>，端口 <code>5432:5432</code>，数据卷挂在 <code>/var/lib/postgresql</code>。库 / 用户 / 密码 <code>vigil / vigil / vigil123</code>。注意 <code>unless-stopped</code>：你手动 <code>docker stop pg</code> 后，开机<b>不会</b>自动启动它。</p>
      <h3>crontab</h3>
<pre class="on-prod"><code>0 0 * * * <span class="vp">~/netsentinel-prod</span>/.venv/bin/python <span class="vp">~/netsentinel-prod</span>/backend/manage.py rotate_partitions --database vigil &gt;&gt; /tmp/rotate_partitions.log 2&gt;&amp;1</code></pre>
      <p>必须用 <code class="vp">~/netsentinel-prod</code>：开发目录 <code class="vn">~/github/NetSentinel</code> 的默认库是 <code>vigil_dev</code>，用它跑分区会建错库。按宿主机本地时间 0 点执行，而分区边界是 UTC。只要每天都跑，明天的分区总会提前建好。<code>/tmp</code> 下的日志重启后清空。</p>
    </section>

    <section id="bootstrap">
      <h2>5.11 从零到可用的完整顺序</h2>
      <p>换一台新机器或全部重建时按这个顺序（依赖关系的详细说明见 <a href="/help/index#order">系统总览 · 构建顺序</a>）：</p>
<pre class="on-both"><code><span class="c"># —— K：集群 ——</span>
cd ~/knetsentinel/kubeadm-cluster
bash 01-setup-vms.sh
bash 02-setup-cluster.sh
bash 03-deploy-5nodes.sh
kubectl apply -f ~/knetsentinel/cluster-setup/targets.yaml
kubectl apply -f ~/knetsentinel/cluster-setup/host-firewall-ccnp.yaml
cd ~/knetsentinel &amp;&amp; uv sync

<span class="c"># —— N：数据库 ——</span>
docker run -d --name pg --restart unless-stopped -p 5432:5432 \
  -e POSTGRES_USER=vigil -e POSTGRES_PASSWORD=vigil123 -e POSTGRES_DB=vigil postgres
docker exec pg psql -U vigil -c "CREATE DATABASE vigil_dev"      <span class="c"># 开发库</span>

<span class="c"># —— N：开发目录 <span class="vn">~/github/NetSentinel</span> ——</span>
git clone git@github.com:Wk-P/NetSentinel.git <span class="vn">~/github/NetSentinel</span>
cd <span class="vn">~/github/NetSentinel</span> &amp;&amp; uv sync
printf 'ENVIRONMENT=linux_development\nVIGIL_KAFKA_GROUP_ID=vigil-bridge-dev\n' &gt; <span class="vn">~/github/NetSentinel</span>/backend/backend/.env
printf 'VITE_API_BASE=/api\nVITE_WS_BASE=\n' &gt; <span class="vn">~/github/NetSentinel</span>/frontend/.env
cd <span class="vn">~/github/NetSentinel</span>/backend &amp;&amp; ../.venv/bin/python manage.py migrate &amp;&amp; ../.venv/bin/python manage.py migrate --database=vigil

<span class="c"># —— N：线上目录 <span class="vp">~/netsentinel-prod</span> ——</span>
git clone <span class="vn">~/github/NetSentinel</span> <span class="vp">~/netsentinel-prod</span>                                   <span class="c"># origin 指向开发目录，deploy.sh 从这里 pull</span>
cd <span class="vp">~/netsentinel-prod</span> &amp;&amp; uv sync --frozen
cp -a <span class="vn">~/github/NetSentinel</span>/backend/vigil/ml/ads_ml <span class="vp">~/netsentinel-prod</span>/backend/vigil/ml/   <span class="c"># 模型不在 Git 里</span>
cp <span class="vn">~/github/NetSentinel</span>/frontend/.env <span class="vp">~/netsentinel-prod</span>/frontend/.env
<span class="c"># 线上 .env：ENVIRONMENT=linux_development、DEBUG=False、SECRET_KEY=&lt;随机&gt;、</span>
<span class="c"># ALLOWED_HOSTS=knettf.com,localhost,127.0.0.1,192.168.100.1、CSRF_EXTRA_ORIGINS=https://knettf.com、VIGIL_DB_NAME=vigil</span>
python3 -c "import secrets;print('SECRET_KEY='+secrets.token_urlsafe(50))"   <span class="c"># 生成 SECRET_KEY</span>
vi <span class="vp">~/netsentinel-prod</span>/backend/backend/.env &amp;&amp; chmod 600 <span class="vp">~/netsentinel-prod</span>/backend/backend/.env
cd <span class="vp">~/netsentinel-prod</span>/backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py migrate --database=vigil
../.venv/bin/python manage.py users_init
../.venv/bin/python manage.py autotf_init
../.venv/bin/python manage.py generate_bridge_token --write-env
../.venv/bin/python manage.py collectstatic --noinput
cd <span class="vp">~/netsentinel-prod</span>/frontend &amp;&amp; pnpm install --frozen-lockfile &amp;&amp; pnpm build

<span class="c"># —— N：服务 ——</span>
systemctl --user daemon-reload
systemctl --user enable --now netsentinel cloudflared-knettf
loginctl enable-linger $USER
(crontab -l; echo "0 0 * * * <span class="vp">~/netsentinel-prod</span>/.venv/bin/python <span class="vp">~/netsentinel-prod</span>/backend/manage.py rotate_partitions --database vigil &gt;&gt; /tmp/rotate_partitions.log 2&gt;&amp;1") | crontab -

<span class="c"># —— 联通 ——</span>
systemctl --user restart netsentinel      <span class="c"># Kafka 就绪后重启，bridge 才能连上</span>
<span class="c"># 网页登录 → Kubernetes → Add，粘贴 ~/.kube/config</span>
cd ~/knetsentinel &amp;&amp; sudo .venv/bin/python3 traffic/spoof_attack.py --packets 50   <span class="c"># 端到端验证</span></code></pre>
      <p>systemd unit 和 cloudflared 配置不在任何仓库里，新机器上要从备份恢复（<a href="/help/power#backup">备份与恢复</a>）或照 5.10 重写；cloudflared 隧道凭证 JSON 需要在 Cloudflare 账号里重新生成。</p>
    </section>
  </div>
</template>

<template>
  <div v-pre>
        <h1>系统总览</h1>
    <div class="meta">开发参考的第一页：系统由哪两个项目组成、数据怎么流动、东西放在哪、从零搭起来的顺序、两个项目之间的契约。改代码之前先读这一页。<br>
      <span class="tag tag-k">K</span> = knetsentinel（<code>~/knetsentinel</code>），<span class="tag tag-n">N</span> = NetSentinel（开发目录 <code class="vn">~/github/NetSentinel</code>，线上目录 <code class="vp">/srv/netsentinel/prod</code>），<span class="tag tag-b">K+N</span> = 两边都涉及。改代码在 <code class="vn">~/github/NetSentinel</code>，看线上数据、日志、模型在 <code class="vp">/srv/netsentinel/prod</code>，见 <a href="#envs">0.5 开发与生产</a>。用自己的账户登录时 <code>~</code> 是你自己的家目录，路径见 <a href="/help/prepare">接手准备</a>。</div>

    <section id="what">
      <h2>0.1 这个系统做什么</h2>
      <p>一句话：<b>在一个自建的 Kubernetes 实验集群里抓网络流量，用机器学习模型判断哪些是攻击，并在网页上管理集群、扫描 Terraform 配置、查看检测结果。</b></p>
      <p>它由两个独立的项目组成：</p>
      <div class="table-wrap"><table>
        <tr><th>项目</th><th>是什么</th><th>里面主要有什么</th><th>怎么运行</th></tr>
        <tr><td><span class="tag tag-k">K</span> knetsentinel</td><td>“实验场”：搭集群、产生流量、采集数据</td><td>KVM 建 5 台虚拟机的 shell 脚本；kubeadm 装 K8s；Cilium/Hubble 观测流量；Vector 把流量事件送进 Kafka；发正常 / 攻击包的 Python 脚本；数据集采集与离线评估</td><td>手动执行 shell 和 Python 脚本</td></tr>
        <tr><td><span class="tag tag-n">N</span> NetSentinel</td><td>“平台”：网页 + 后端 + 检测模型</td><td>Django 后端（三个应用：kcore 集群管理、autotf Terraform 扫描、vigil 流量检测）；Vue 3 前端；OCSVM 检测模型；集群内检测器镜像</td><td>一个常驻服务 <code>netsentinel</code>（uvicorn，端口 8080），公网经 cloudflared 映射到 <code>https://knettf.com</code></td></tr>
      </table></div>
      <p>网页上有三大功能，对应后端三个应用：</p>
      <div class="table-wrap"><table>
        <tr><th>网页菜单</th><th>前端页面</th><th>后端应用</th><th>做什么</th></tr>
        <tr><td><b>Kubernetes</b></td><td><code>/kcore</code></td><td><code>kcore</code></td><td>登记集群（粘贴 kubeconfig），查看 Namespace / Pod / Deployment / Service / ConfigMap / DaemonSet，看 Pod 实时日志，编辑 YAML，重启、删除</td></tr>
        <tr><td><b>Terraform Scan</b></td><td><code>/autotf</code></td><td><code>autotf</code></td><td>上传或在线编写 <code>.tf</code> 文件，用 terraform validate / tflint / checkov / tfsec / trivy 扫描安全问题，没有 HIGH 级问题时才允许 <code>terraform apply</code></td></tr>
        <tr><td><b>AI Vigil</b></td><td><code>/vigil</code>、<code>/vigil/log</code></td><td><code>vigil</code></td><td>展示模型对集群流量的实时检测结果：总数、攻击数、攻击类型分布、每条流的 35 个特征和判断依据</td></tr>
        <tr><td><b>Help</b></td><td><code>/help</code></td><td>—</td><td>本手册与英文用户手册</td></tr>
        <tr><td>（无菜单入口）</td><td><code>/admin</code></td><td><code>kcore</code> + <code>autotf</code></td><td>管理后台：用户、全部集群、全部 Terraform 配置、扫描工具</td></tr>
      </table></div>
    </section>

    <section id="big">
      <h2>0.2 全景图：一个数据包走到网页上的全过程</h2>
      <p>理解这张图就理解了一半项目。左边全部在 <span class="tag tag-k">K</span> 的实验集群里，右边全部在 <span class="tag tag-n">N</span> 的后端进程里。</p>
<pre><code>宿主机（Ubuntu，物理网卡 enp6s0）
│
├─ 网桥 virbr-k8s 192.168.100.1/24 ──────────── K 01-setup-vms.sh 创建
│    │
│    ├─ VM k8s-master .10   ┐
│    ├─ VM k8s-node1  .11   │  K 02-setup-cluster.sh：kubeadm v1.28 + Cilium(eBPF) + Hubble
│    ├─ VM k8s-node2  .12   │                         + MetalLB(.200-.250) + local-path
│    ├─ VM k8s-node3  .13   │
│    └─ VM k8s-node4  .14   ┘
│
│   ① 发包脚本（K traffic/）把伪造源 IP .20-.29（攻击）/ .50-.64（正常）临时挂到 virbr-k8s 上发包
│        │
│        ▼
│   ② Cilium 在每个节点用 eBPF 看到这个包 → Hubble 把它变成一条“flow 事件”（JSON）
│        │
│        ▼
│   ③ Vector（每节点一个 Pod）执行 hubble observe --follow --output=json，把事件写入
│      Kafka topic ebpf-net-logs                       ← K 03-deploy-5nodes.sh 部署
│        │
│        ▼  Kafka 外部地址 192.168.100.200-203:9094（MetalLB 分配）
│
└─ NetSentinel 后端进程（systemd 服务 netsentinel，uvicorn :8080）
      │
      ④ vigil/bridge.py 的 bridge 线程：消费 Kafka → 按 5 元组把包聚成“流” → 计算 35 个特征
      │
      ⑤ drainer 线程：把一批流交给 vigil/services.detect_batch()
      │       → ads_ml 模型：预处理 → PCA → One-Class SVM 判异常 → 零样本学习猜攻击类型
      │       → cilium/policy.py：给出建议动作 drop / rate_limit / alert / ignore（目前只记日志）
      │       → INSERT 到 PostgreSQL 表 vigil_detectionrecord（按天分区）
      │
      ⑥ 前端 /vigil 每 30 秒、/vigil/log 每 15 秒调 REST 接口读取 → 浏览器显示</code></pre>
      <p>另外两条与流量无关的链路：</p>
      <ul>
        <li><b>集群管理</b>：浏览器 → <code>/api/kcore/...</code> → 后端用你登记的 kubeconfig 调 Kubernetes API → 结果返回网页。Pod 日志走 WebSocket <code>/ws/clusters/&lt;id&gt;/pods/&lt;ns&gt;/&lt;pod&gt;/logs/</code>。</li>
        <li><b>Terraform 扫描</b>：浏览器上传 <code>.tf</code> → 后端存到 <code>backend/terraform/</code> → 扫描时复制到临时目录，依次调用 5 个命令行工具，解析它们的 JSON / SARIF 输出 → 汇总成报告存进 SQLite。</li>
      </ul>
    </section>

    <section id="flow">
      <h2>0.3 检测的三条入口</h2>
      <p>流量最终都写进 PostgreSQL 表 <code>vigil_detectionrecord</code>，但有三条入口。<b>当前实际在运行的是入口 A</b>（后端日志中持续有 <code>vigil.bridge: queue: N flows → M attack(s)</code>）。</p>
      <pre><code>数据包 → Cilium eBPF → Hubble Relay :4245 → Vector DaemonSet → Kafka topic <b>ebpf-net-logs</b>
                                                                   │
        ┌──────────────────────────────────────────────────────────┼──────────────────────────────┐
        ▼ 入口 A（默认，随后端自动启动）                           ▼ 入口 B（集群内 Pod）          ▼ 入口 C（宿主机脚本）
  N backend/vigil/bridge.py                               N detector/detector.py            K kafka/vigil_bridge.py
  Kafka 外部地址 .200-.203:9094                           镜像 soar009/netsentinel-detector  按 5 元组聚合 30 特征
  group=vigil-bridge, offset=latest                        group=vigil-detector               POST /api/vigil/detect/batch/
  线程内聚合 → flow_queue → drainer 线程                   Pod 内自己推理                     (JWT)
  → services.detect_batch()                                → WS ws/detector/push/
        │                                                   (Bearer VIGIL_BRIDGE_TOKEN)
        └───────────────► ads_ml OCSVM 推理 → Cilium 策略(stub) → INSERT vigil_detectionrecord ◄──────┘
                                                                   │
                                     前端 /vigil、/vigil/log 轮询 REST 接口读取（每 15 秒）</code></pre>
      <div class="note"><b>不要同时开两条以上入口</b>：A、B、C 各自独立消费 Kafka 并写库，同一条流会被重复记录。入口 A 无开关，只要后端以 uvicorn 启动就会运行（判断逻辑见 <code>vigil/apps.py</code> 的 <code>_should_start_bridge()</code>）。</div>
      <p>离线评估另有一条旁路：<code>K simulation/simulate_4.py</code> 直接 <code>django.setup()</code> 导入 <code>N backend</code> 的 <code>vigil.services</code>，把 CSV 中的流特征批量送入模型。这是两个项目之间唯一的代码级耦合，路径写死为 <code>../../github/NetSentinel/backend</code>。</p>
    </section>

    <section id="where">
      <h2>0.4 东西都在哪里</h2>
      <div class="table-wrap"><table>
        <tr><th>东西</th><th>位置</th><th>说明</th></tr>
        <tr><td>网页（公网）</td><td><code>https://knettf.com</code></td><td>cloudflared 隧道 → 本机 <code>localhost:8080</code></td></tr>
        <tr><td>网页（本机 / 内网）</td><td><code>http://localhost:8080</code>、<code>http://&lt;宿主机 IP&gt;:8080</code></td><td>同一个后端进程，既提供 API 也提供前端页面</td></tr>
        <tr><td>后端源码</td><td><code class="vn">~/github/NetSentinel/backend/</code></td><td>Django 项目，<code>manage.py</code> 在这里；线上运行的是 <code class="vp">/srv/netsentinel/prod/backend/</code> 里同一份代码的已提交版本</td></tr>
        <tr><td>前端源码</td><td><code class="vn">~/github/NetSentinel/frontend/src/</code></td><td>Vue 3 + TypeScript + Element Plus</td></tr>
        <tr><td>前端构建产物</td><td><code class="vp">/srv/netsentinel/prod/frontend/dist/</code></td><td><code>deploy.sh -frontend</code> 在 <code class="vp">/srv/netsentinel/prod</code> 里构建；后端直接从这里提供页面</td></tr>
        <tr><td>手册源文件</td><td><code class="vn">~/github/NetSentinel/frontend/src/views/help/pages/</code></td><td>每页一个 Vue 组件，由 <code>HelpView.vue</code> 按 <code>/help/&lt;页&gt;</code> 加载</td></tr>
        <tr><td>Python 环境</td><td><code class="vn">~/github/NetSentinel/.venv/</code>（开发）、<code class="vp">/srv/netsentinel/prod/.venv/</code>（线上）</td><td>都用 <code>uv sync</code> 按 <code>uv.lock</code> 生成，Python 3.12</td></tr>
        <tr><td>default 数据库</td><td><code class="vp">/srv/netsentinel/prod/backend/db.sqlite3</code>（开发用 <code class="vn">~/github/NetSentinel/backend/db.sqlite3</code>）</td><td>SQLite：用户、集群、Terraform 配置、扫描报告</td></tr>
        <tr><td>vigil 数据库</td><td>Docker 容器 <code>pg</code>，<code>127.0.0.1:5432</code>，线上库 <code>vigil</code>、开发库 <code>vigil_dev</code>，用户 <code>vigil</code></td><td>PostgreSQL：检测记录（按天分区）</td></tr>
        <tr><td>模型文件</td><td><code class="vp">/srv/netsentinel/prod/backend/vigil/ml/ads_ml/trained/</code></td><td>OCSVM 流水线、攻击原型、训练数据</td></tr>
        <tr><td>后端服务定义</td><td><code>~/.config/systemd/user/netsentinel.service</code></td><td>用户级 systemd 服务</td></tr>
        <tr><td>集群脚本</td><td><code>~/knetsentinel/kubeadm-cluster/</code></td><td>00 清理 / 01 建 VM / 02 装集群 / 03 部署数据管道</td></tr>
        <tr><td>集群凭证</td><td><code>~/.kube/config</code></td><td>宿主机上 <code>kubectl</code> 用它；登记集群时把它的内容贴到网页上</td></tr>
        <tr><td>VM 磁盘</td><td><code>~/vm-images/</code></td><td>5 个 qcow2 + Ubuntu 22.04 cloud image</td></tr>
      </table></div>
      <h3>项目目录以外的相关位置</h3>
      <div class="table-wrap"><table>
        <tr><th>位置 / 对象</th><th>内容</th><th>归属</th></tr>
        <tr><td><code>/etc/systemd/system/netsentinel.service</code></td><td>系统服务，以 <code>netsentinel</code> 账户运行 uvicorn <code>backend.asgi:application</code> :8080，WorkingDirectory=<code class="vp">/srv/netsentinel/prod/backend/</code>，<code>Restart=always</code>，MemoryMax=3G，已 enable</td><td><span class="tag tag-n">N</span></td></tr>
        <tr><td><code>/etc/systemd/system/cloudflared-knettf.service</code><br><code>/etc/cloudflared/knettf/config.yml</code></td><td>knettf.com 公网隧道，以 <code>netsentinel</code> 账户运行</td><td><span class="tag tag-n">N</span></td></tr>
        <tr><td>Docker 容器 <code>pg</code></td><td>PostgreSQL :5432，restart=<code>unless-stopped</code>；库 / 用户 <code>vigil</code>；数据卷 <code>/home/docker-data/volumes/fe9ba015…/_data</code></td><td><span class="tag tag-n">N</span></td></tr>
        <tr><td><code>/etc/cron.d/netsentinel</code></td><td><code class="vp">0 0 * * * netsentinel /srv/netsentinel/prod/.venv/bin/python /srv/netsentinel/prod/backend/manage.py rotate_partitions --database vigil &gt;&gt; /srv/netsentinel/logs/rotate_partitions.log</code>（必须用 <code class="vp">/srv/netsentinel/prod</code>：<code class="vn">~/github/NetSentinel</code> 的默认库是 vigil_dev）</td><td><span class="tag tag-n">N</span></td></tr>
        <tr><td><code>/usr/bin/terraform</code>、<code>tflint</code>、<code>tfsec</code>、<code>trivy</code>、<code>~/terraform/.venv/bin/checkov</code></td><td>autotf 扫描与 apply 依赖的外部二进制</td><td><span class="tag tag-n">N</span></td></tr>
        <tr><td><code>~/vm-images/</code></td><td>★ k8s-master / node1~4 的 qcow2 + Ubuntu 22.04 cloud image</td><td><span class="tag tag-k">K</span></td></tr>
        <tr><td>libvirt（<code>qemu:///system</code>）</td><td>网络 <code>virbr-k8s</code>（autostart=yes）、VM <code>k8s-master</code>、<code>k8s-node1~4</code>（autostart=<b>否</b>）</td><td><span class="tag tag-k">K</span></td></tr>
        <tr><td><code>~/.kube/config</code></td><td>宿主机访问集群的凭证（server 192.168.100.10:6443）</td><td><span class="tag tag-k">K</span></td></tr>
        <tr><td><code>/etc/hosts</code></td><td>k8s-master / node、<code>kafka-svc.default.svc.cluster.local</code></td><td><span class="tag tag-k">K</span></td></tr>
        <tr><td><code>/etc/sysctl.d/99-ipforward.conf</code>；iptables NAT/FORWARD</td><td>VM 出网；iptables 规则<b>未持久化</b></td><td><span class="tag tag-k">K</span></td></tr>
        <tr><td>Docker Hub <code>soar009/netsentinel-detector:latest</code></td><td>入口 B 镜像</td><td><span class="tag tag-b">K+N</span></td></tr>
      </table></div>
    </section>

    <section id="envs">
      <h2>0.5 开发与生产</h2>
      <p>同一台宿主机上有两份 NetSentinel：<code class="vn">~/github/NetSentinel</code> 是开发目录（平时改代码的地方），<code class="vp">/srv/netsentinel/prod</code> 是线上目录（归 <code>netsentinel</code> 账户和组，GitHub knet-lab/NetSentinel 的 clone，只放已 push 的 main）。两边的数据库、<code>.env</code>、<code>.venv</code>、<code>dist</code> 完全分开。</p>
      <div class="table-wrap"><table>
        <tr><th></th><th>开发 <code class="vn">~/github/NetSentinel</code></th><th>线上 <code class="vp">/srv/netsentinel/prod</code></th></tr>
        <tr><td>后端</td><td><code class="vn">cd ~/github/NetSentinel/backend &amp;&amp; ../.venv/bin/python manage.py runserver 8090</code></td><td>systemd <code>netsentinel</code>，uvicorn :8080</td></tr>
        <tr><td>前端</td><td><code class="vn">cd ~/github/NetSentinel/frontend &amp;&amp; pnpm dev</code> → <code>http://localhost:5173</code>（代理到 :8090）</td><td><code class="vp">/srv/netsentinel/prod/frontend/dist</code>，<code>https://knettf.com</code></td></tr>
        <tr><td>DEBUG</td><td>开（默认值）</td><td>关（<code class="vp">/srv/netsentinel/prod/backend/backend/.env</code> 里 <code>DEBUG=False</code>）</td></tr>
        <tr><td>default 库</td><td><code class="vn">~/github/NetSentinel/backend/db.sqlite3</code></td><td><code class="vp">/srv/netsentinel/prod/backend/db.sqlite3</code></td></tr>
        <tr><td>vigil 库</td><td><code>vigil_dev</code>（默认值）</td><td><code>vigil</code>（<code>.env</code> 里 <code>VIGIL_DB_NAME=vigil</code>）</td></tr>
        <tr><td>Kafka consumer group</td><td><code>vigil-bridge-dev</code>（开发 <code>.env</code> 设置）</td><td><code>vigil-bridge</code>（默认值）</td></tr>
        <tr><td>定时任务</td><td>无</td><td><code>/etc/cron.d/netsentinel</code> 每天 0 点 <code>rotate_partitions</code></td></tr>
      </table></div>
      <p>上线流程：在 <code class="vn">~/github/NetSentinel</code> 改代码、<code>git commit</code> 并 <code>git push</code> 到 GitHub → <code class="vn">cd ~/github/NetSentinel &amp;&amp; scripts/deploy.sh -all</code>。脚本在 <code class="vp">/srv/netsentinel/prod</code> 里从 GitHub <code>git pull</code>、<code>uv sync</code>、构建、迁移、重启，详见 <a href="/help/deploy">改动上线</a>。没 push 的改动不会上线。运行 <code>deploy.sh</code> 的账户必须在 <code>netsentinel</code> 组里（加组后要重新登录）。</p>
      <div class="note"><b>规则</b>：不要在 <code class="vp">/srv/netsentinel/prod</code> 里改代码或 commit（下次部署 <code>git pull --ff-only</code> 会失败）；查线上数据、日志、模型结果、跑运维命令（改密码、补分区等）用 <code class="vp">/srv/netsentinel/prod</code>；开发调试只用 <code class="vn">~/github/NetSentinel</code>。开发后端一定要带 <code>vigil-bridge-dev</code> 这个 group，否则会和线上分走 Kafka 分区，线上漏收流量。</div>
    </section>


    <section id="order">
      <h2>0.6 整体构建顺序（从零到可用）</h2>
      <p>整套系统有严格的先后依赖：<b>后一步依赖前一步的产物</b>，顺序错了会出现拿不到 IP、broker 起不来、bridge 连不上 Kafka、token 不一致等问题。下图为依赖关系，表格为逐步顺序。日常开机恢复只是其中一部分，见 <a href="/help/power#startup">开机恢复</a>。</p>
      <pre><code> 阶段 0 宿主机准备
   │
   ▼
 阶段 1 <span class="c">[K]</span> 01-setup-vms.sh ── 网桥 virbr-k8s + 5 台 VM（固定 IP .10-.14）
   │
   ▼
 阶段 2 <span class="c">[K]</span> 02-setup-cluster.sh
   │    宿主机 NAT → 各节点 containerd/kubeadm → kubeadm init → kubeconfig → worker join
   │    → Cilium+Hubble（网络就绪，节点才 Ready）→ MetalLB（IP 池）→ local-path（默认 StorageClass）
   ▼
 阶段 3 <span class="c">[K]</span> 03-deploy-5nodes.sh
   │    Kafka Service 先建 → MetalLB 分配 .200-.203 → ConfigMap kafka-node-ips
   │    → controller → 4 个 broker（PVC 依赖 local-path）→ Vector（依赖 Kafka + hubble-relay:4245）
   │    → my-nginx → port-forward → /etc/hosts → 重写 .env
   ▼
 阶段 4 <span class="c">[K]</span> 可选：targets.yaml（靶机 .210-.214）、host-firewall-ccnp.yaml
   │
   │                         ┌──────────── 阶段 5～8 可与阶段 1～4 并行准备，但阶段 9 之前必须都完成
   ▼                         ▼
 阶段 5 <span class="c">[N]</span> 依赖与数据库：uv sync → 启动容器 pg → migrate（default）→ migrate --database=vigil
   ▼
 阶段 6 <span class="c">[N]</span> 初始化数据：users_init → autotf_init → generate_bridge_token --write-env
   ▼
 阶段 7 <span class="c">[N]</span> 前端：pnpm install → pnpm build（产出 dist，后端才能提供页面）
   ▼
 阶段 8 <span class="c">[N]</span> 服务：systemd netsentinel（:8080）→ cloudflared → crontab rotate_partitions
   ▼
 阶段 9 <span class="c">[K+N]</span> 联通：确认 Kafka 有数据 → 重启后端（bridge 连 Kafka）→ 前端登记集群 kubeconfig
   ▼
 阶段 10 <span class="c">[K+N]</span> 可选入口 B：detector/build.sh → Secret detector-secret → 部署检测器
   ▼
 阶段 11 <span class="c">[K]</span> 验证与实验：发包 → 查检测记录 → 采数据集 / 评估</code></pre>

      <div class="table-wrap"><table>
        <tr><th>#</th><th>阶段</th><th>项目</th><th>命令 / 操作</th><th>前置条件</th><th>产出（被后续步骤依赖）</th><th>顺序错了会怎样</th></tr>
        <tr><td>0</td><td>宿主机准备</td><td>—</td><td>KVM 可用、sudo、≥420GB 磁盘、外网、kubectl / helm / docker / uv / pnpm / terraform 等工具</td><td>—</td><td>运行环境</td><td>后续脚本中途失败</td></tr>
        <tr><td>1</td><td>建 VM</td><td><span class="tag tag-k">K</span></td><td><code>bash kubeadm-cluster/01-setup-vms.sh</code></td><td>0</td><td>网桥 <code>virbr-k8s</code>、5 台 VM、SSH 可登录</td><td>—</td></tr>
        <tr><td>2</td><td>装集群</td><td><span class="tag tag-k">K</span></td><td><code>bash kubeadm-cluster/02-setup-cluster.sh</code></td><td>1：VM 可 SSH 且能出网</td><td><code>~/.kube/config</code>、5 节点 Ready、Cilium/Hubble、MetalLB 池 .200-.250、默认 StorageClass</td><td>先装 MetalLB 再装 Cilium：节点 NotReady，MetalLB 无法调度；IP 池过早 apply 会被 webhook 拒绝（重跑 02 即可）</td></tr>
        <tr><td>3</td><td>数据管道</td><td><span class="tag tag-k">K</span></td><td><code>bash kubeadm-cluster/03-deploy-5nodes.sh</code></td><td>2：MetalLB、local-path、hubble-relay 就绪（脚本会先检查）</td><td>Kafka 外部地址 .200-.203:9094、topic <code>ebpf-net-logs</code> 有数据、<code>~/knetsentinel/.env</code>、<code>/etc/hosts</code></td><td>ConfigMap 晚于 broker 建立：broker 拿不到外部地址而启动失败；Vector 早于 Kafka：写入失败不断重试</td></tr>
        <tr><td>4</td><td>靶机与策略</td><td><span class="tag tag-k">K</span></td><td><code>kubectl apply -f cluster-setup/targets.yaml</code>；<code>host-firewall-ccnp.yaml</code></td><td>2（MetalLB）</td><td>靶机 .210-.214；宿主机流量可被 Hubble 看到</td><td>缺 targets：<code>simulation/</code> 发包无目标</td></tr>
        <tr><td>5</td><td>后端依赖与数据库</td><td><span class="tag tag-n">N</span></td><td><code>uv sync</code>；确认容器 <code>pg</code> 运行（库 / 用户 vigil）；<code>manage.py migrate</code>；<code>manage.py migrate --database=vigil</code></td><td>0；<code>backend/backend/.env</code> 中有 <code>ENVIRONMENT</code></td><td><code>db.sqlite3</code> 表结构；<code>vigil_detectionrecord</code> 分区表 + 91 个分区</td><td>漏了 vigil 迁移：检测写库全部失败；pg 未启动：migrate 报连接错误</td></tr>
        <tr><td>6</td><td>初始化数据</td><td><span class="tag tag-n">N</span></td><td><code>manage.py users_init</code> → <code>autotf_init</code> → <code>generate_bridge_token --write-env</code></td><td>5（表已建）</td><td>admin 等账号、5 个扫描工具、<code>VIGIL_BRIDGE_TOKEN</code> 写入 <code>backend/backend/.env</code></td><td>autotf_init 时扫描工具未安装：版本记为 unknown，扫描时报 tool not found；token 在服务启动后才生成：需重启服务才能读到</td></tr>
        <tr><td>7</td><td>前端构建</td><td><span class="tag tag-n">N</span></td><td><code>cd frontend &amp;&amp; pnpm install &amp;&amp; pnpm build</code></td><td>0（Node / pnpm）</td><td><code>frontend/dist/</code></td><td>缺 dist：网页白屏 / 报错，但 API 可用</td></tr>
        <tr><td>8</td><td>启动服务</td><td><span class="tag tag-n">N</span></td><td><code>sudo systemctl enable --now netsentinel cloudflared-knettf</code>；安装 <code>/etc/cron.d/netsentinel</code>（<code>rotate_partitions</code>）</td><td>5、6、7</td><td>:8080 页面与 API；公网访问；每日分区</td><td>没装 cron：约 1 天后分区用完，检测无法入库</td></tr>
        <tr><td>9</td><td>联通</td><td><span class="tag tag-b">K+N</span></td><td>确认 Kafka 有数据 → <code>sudo systemctl restart netsentinel</code> → 前端添加集群（粘贴 <code>~/.kube/config</code>）</td><td>3 和 8</td><td>入口 A 开始消费并入库；<code>/kcore</code> 可管理集群</td><td>后端先于 Kafka 启动：bridge 线程报错退出，必须在 Kafka 就绪后重启后端</td></tr>
        <tr><td>10</td><td>入口 B（可选）</td><td><span class="tag tag-b">K+N</span></td><td><code>N: bash detector/build.sh</code> → <code>K: kubectl create ns netsentinel</code> → 创建 Secret <code>detector-secret</code>（值 = <code>VIGIL_BRIDGE_TOKEN</code>）→ <code>kubectl apply -f detector/detector-deployment.yaml</code></td><td>3、6（token）、8（WS 地址可达）</td><td>集群内检测器推送结果</td><td>Secret 早于 token 生成或 token 后来重新生成：WS 以 4401 拒绝连接。与入口 A 同时运行会重复入库</td></tr>
        <tr><td>11</td><td>验证与实验</td><td><span class="tag tag-k">K</span></td><td><code>uv sync</code> → <code>sudo .venv/bin/python3 traffic/spoof_attack.py --packets 200</code> → 查 <code>/vigil/log</code> 或 SQL</td><td>9（或 10）</td><td>检测记录、数据集、评估报告</td><td>—</td></tr>
      </table></div>

      <p>改了某一层之后怎么让它生效，见 <a href="/help/deploy">改动上线</a>。</p>
    </section>

    <section id="contract">
      <h2>0.7 跨项目契约（改一端必须查另一端）</h2>
      <div class="table-wrap"><table>
        <tr><th>契约</th><th>knetsentinel 侧</th><th>NetSentinel 侧</th><th>改动时注意</th></tr>
        <tr><td>Kafka topic 名与地址</td><td><code>cilium-vector/vector-5nodes.yaml</code>（sink topic）、<code>.env</code></td><td><code>vigil/bridge.py</code> 常量 <code>KAFKA_BOOTSTRAP</code>、<code>KAFKA_TOPIC</code>（写死）；<code>detector.py</code> 环境变量</td><td>MetalLB 分配的 .200-.203 若变化，入口 A 必须改代码并重启</td></tr>
        <tr><td>Hubble 流事件 JSON 结构</td><td>Vector <code>exec hubble observe --output=json</code></td><td><code>bridge.py</code> 读取 <code>flow.IP / l4 / traffic_direction / verdict / is_reply / time</code></td><td>升级 Hubble 版本后需验证字段</td></tr>
        <tr><td>35 个流特征</td><td><code>dataset/aggregate_flows.py</code>、<code>kafka/vigil_bridge.py</code>、<code>docs/features.md</code></td><td><code>vigil/serializers.py FlowInputSerializer</code>、<code>ml/models/base.py DetectionInput</code>、<code>runner.py flow_from_dict</code>、<code>bridge.py compute_flow</code></td><td>五处必须同名同义；见 <a href="/help/db#features">特征表</a></td></tr>
        <tr><td>标签规则</td><td>攻击源 .20-.29 → 1、正常源 .50-.64 → 0</td><td><code>bridge.py _hubble_to_packet()</code> 同样规则</td><td><code>simulation/</code> 用的 .170-.184 不在规则内，label 为空</td></tr>
        <tr><td>检测器推送</td><td>Secret <code>detector-secret</code>（key <code>django-token</code>）→ 环境变量 <code>DJANGO_TOKEN</code></td><td><code>DetectorPushConsumer._auth()</code> 与 <code>settings.VIGIL_BRIDGE_TOKEN</code> 做<b>字符串全等</b>比较</td><td>两边必须是同一个字符串；不是校验 JWT 签名</td></tr>
        <tr><td>REST 批量检测</td><td><code>kafka/vigil_bridge.py --token &lt;JWT&gt;</code></td><td><code>POST /api/vigil/detect/batch/</code></td><td>JWT access 默认 2 小时过期；长期运行用 <code>generate_bridge_token</code> 生成 10 年 token</td></tr>
        <tr><td>评估监听 WebSocket</td><td><code>simulation/monitor/monitor.py</code> 连接 <code>ws://localhost:8080/ws/vigil/</code></td><td><b>后端没有这个路由</b>（只有 <code>ws/detector/push/</code> 和 Pod 日志）</td><td>monitor 目前连不上；需在 <code>vigil/routing.py</code> 补广播 consumer 或改 monitor 轮询 REST</td></tr>
        <tr><td>离线导入</td><td><code>simulation/simulate_4.py</code></td><td><code>vigil.services.detect_batch(flows, model_name)</code></td><td>移动目录或改函数签名都会破坏</td></tr>
        <tr><td>模型文件</td><td>—</td><td><code>backend/vigil/ml/ads_ml/</code> → <code>detector/build.sh</code> rsync 到 <code>detector/ads_ml/</code></td><td>改模型后入口 A 重启后端，入口 B 重新 build + rollout</td></tr>
      </table></div>
    </section>

    <section id="tree">
      <h2>0.8 目录树</h2>
      <p>★ 表示数据或状态，删除前必须备份；☆ 表示构建或运行时生成，可以重新生成。</p>
      <details><summary><span class="tag tag-n">N</span> ~/github/NetSentinel（<code>/srv/netsentinel/prod</code> 结构相同）</summary>
<pre class="on-prod"><code>~/github/NetSentinel/
├── pyproject.toml · uv.lock · .python-version   后端 Python 依赖（uv，Python 3.12）
├── .venv/                       ☆ 虚拟环境（uv sync 生成）；线上 systemd 执行 <span class="vp">/srv/netsentinel/prod</span>/.venv/bin/uvicorn
├── .env                         仓库根 .env（VIGIL_BRIDGE_TOKEN），实际 settings 不读这个
├── backend/
│   ├── manage.py
│   ├── backend/
│   │   ├── settings.py          配置：DB、JWT、CORS、Channels、TF_BIN、WHITENOISE_ROOT；DEBUG / 密钥 / 库名从 .env 读
│   │   ├── .env               ★ settings 真正读取的 .env（不进 Git，开发和线上各一份，见 0.5）
│   │   ├── urls.py              HTTP 路由总表 + SPA 兜底 spa_view
│   │   ├── asgi.py              HTTP + WebSocket 路由（kcore.routing + vigil.routing）
│   │   ├── wsgi.py              未使用（服务走 ASGI）
│   │   └── db_router.py         kcore→default(SQLite)，vigil→vigil(PostgreSQL)，其余→default
│   ├── common/
│   │   ├── response.py          统一响应 ResponseMixin {status, code, message, data}
│   │   ├── exceptions.py        DRF 异常 → 统一响应
│   │   ├── permissions.py       check_owner()：本人或 is_staff 才放行
│   │   ├── middleware.py        /api/ 与 /auth/ 免 CSRF
│   │   ├── kclient.py           KubeClient：kubernetes Python 客户端封装、apply YAML、重启
│   │   └── ctypto.py · pdfgen.py  空文件（预留）
│   ├── kcore/                   用户 & K8s 集群管理
│   │   ├── models.py            User、KubeCluster
│   │   ├── views.py · serializers.py · services.py · urls.py
│   │   ├── consumers.py · routing.py    Pod 日志 WebSocket
│   │   └── management/commands/ users_init.py · users_clear.py
│   ├── autotf/                  Terraform 配置、扫描、apply、报告
│   │   ├── models.py            TerraformConfig、TerraformTool、ScanReport
│   │   ├── services.py          ScanService / ApplyService（subprocess 调 terraform、tflint、checkov…）
│   │   ├── views.py             含 HTML / PDF 报告渲染（reportlab）
│   │   └── management/commands/ autotf_init.py（注册 5 个扫描工具）· autotf_clear.py
│   ├── vigil/                   流量检测
│   │   ├── apps.py              ready() 中启动 bridge 线程
│   │   ├── bridge.py            入口 A：Kafka 消费 → 聚合 → flow_queue → drainer
│   │   ├── services.py          detect_flow / detect_batch / get_stats / list_models
│   │   ├── consumers.py · routing.py   入口 B：ws/detector/push/
│   │   ├── views.py · serializers.py · urls.py · models.py（DetectionRecord, managed=False）
│   │   ├── migrations/0001_initial.py   手写 SQL：分区表 + 91 个日分区
│   │   ├── management/commands/ generate_bridge_token.py · rotate_partitions.py
│   │   └── ml/
│   │       ├── models/          base.py（DetectionInput / DetectionResult）· registry.py · runner.py
│   │       │                    ads_ml_model.py（ads_ml_ocsvm）· example_threshold.py（未注册）
│   │       ├── cilium/policy.py 检测结果 → drop / rate_limit / alert / ignore（apply_action 是 stub）
│   │       └── ads_ml/        ★ main.py · config.yaml · trained/（模型文件）· utils/ · results/
│   ├── db.sqlite3             ★ default 库：用户、集群、Terraform 配置与报告、Django 内置表
│   ├── autotf.sqlite3 · vigil.sqlite3   旧库文件，当前配置未使用
│   ├── db_backup_20261011_023307/     ★ SQLite 备份
│   ├── terraform/             ★ 上传的 .tf 文件（FileField upload_to='terraform/'，相对 WorkingDirectory）
│   └── docs/                    autotf 需求 / 开发文档、kcore 接口文档、开发日志
├── frontend/
│   ├── package.json · pnpm-lock.yaml · vite.config.ts（dev 代理 /api、/ws → 127.0.0.1:8090 开发后端）
│   ├── .env.production
│   ├── public/                  favicon
│   ├── src/
│   │   ├── main.ts · App.vue · router/index.ts（路由 + 登录 / 管理员守卫）
│   │   ├── stores/auth.ts       token / refreshToken / user 存 localStorage，401 自动刷新
│   │   ├── stores/kcore.ts      集群与资源状态
│   │   ├── components/          NavComponent.vue · RollingNumber.vue
│   │   └── views/               Login · Kcore · AutoTF · Vigil · VigilLog · Help · admin/*
│   └── dist/                  ☆ pnpm build 产物，后端通过 WhiteNoise 直接提供
├── detector/                    入口 B 镜像：detector.py · Dockerfile · build.sh · requirements.txt · ads_ml/(☆ build 时同步)
├── terraform/main.tf            Terraform 示例
├── structure/                   架构图 SVG、数据库图 HTML、设计文档 PDF
└── p.md · p1.md · policy.md     笔记</code></pre>
      </details>
      <details><summary><span class="tag tag-k">K</span> ~/knetsentinel</summary>
<pre><code>~/knetsentinel/
├── pyproject.toml · uv.lock · .python-version
├── .venv/                     ☆ 发包 / 采集用环境（scapy、confluent-kafka、aiohttp、websockets）
├── .env                       ★ Kafka 外部地址 BOOTSTRAP_SERVERS / GROUP_ID / TOPICS（03 脚本重写）
├── README.md                    最完整的环境说明（19KB）
├── kubeadm-cluster/             ★ 集群生命周期脚本
│   ├── 00-clear.sh              不可逆清理：VM、网桥、磁盘、cloud image、kubeconfig、/etc/hosts、known_hosts
│   ├── 01-setup-vms.sh          网桥 virbr-k8s（DHCP MAC→IP 绑定）+ 5 台 VM + cloud-init
│   ├── 02-setup-cluster.sh      宿主机 NAT、containerd、kubeadm v1.28、Cilium/Hubble、MetalLB、local-path
│   ├── 03-deploy-5nodes.sh      Kafka KRaft + Vector + my-nginx + port-forward + /etc/hosts + .env
│   └── host-info.sh · host-info.log   宿主机诊断
├── kafka-svc/kafka-5nodes.yaml  1 controller（master，emptyDir）+ 4 broker（StatefulSet，10Gi PVC）
├── cilium-vector/               vector-5nodes.yaml（在用）· vector.yaml（旧 minikube）
├── cluster-setup/               targets.yaml（靶机 .210-.214）· host-firewall-ccnp.yaml · 旧 minikube 脚本
├── detector/detector-deployment.yaml   入口 B 的 Deployment（命名空间 netsentinel）
├── ingress-controller/my-nginx-ingress.yaml
├── hubble-scripts/last_record.sh
├── traffic/                     发包：send_request · send_normal_scapy · spoof_attack · handle_addr · run_traffic_only.sh
├── dataset/                   ★ dataset.csv · dataset_v1.csv + dataset_collector · aggregate_flows · run_dataset_collection.sh
├── kafka/                       kafka_read · kafka_read_csv · vigil_bridge（入口 C）· run_*.sh · *.log
├── traffic_request/           ★ CSV 重放：scripts/ · ip_mapping.json · read_result.csv · record_send_uuid.txt
├── simulation/                ★ run.sh · simulate_1~4.py · gen_simulate4_csv.py · monitor/ · 测试 CSV
├── docs/                        features.md（特征定义）· kafka_read.md · spoof_attack_summary.md
├── logs/                        历史运行日志
└── flows.csv · flows_30.csv · flows_30_2.csv   ★ 聚合后的流特征</code></pre>
      </details>
    </section>

    <section id="terms">
      <h2>0.9 术语表</h2>
      <p>后面各章会反复用到这些词，先过一遍，不必全记住。</p>
      <dl class="terms">
        <dt>KVM / libvirt / virsh</dt><dd>Linux 自带的虚拟化。libvirt 是管理层，<code>virsh</code> 是它的命令行。本项目的 VM 在 <code>qemu:///system</code> 下，所以命令是 <code>virsh -c qemu:///system ...</code>。</dd>
        <dt>cloud-init</dt><dd>VM 第一次开机时自动执行的初始化（建用户、放 SSH 公钥、关 swap、扩容磁盘）。01 脚本为每台 VM 生成一个 cidata ISO 挂进去。</dd>
        <dt>kubeadm</dt><dd>官方的 K8s 集群安装工具。<code>kubeadm init</code> 在 master 上建控制面，<code>kubeadm join</code> 让 worker 加入。</dd>
        <dt>kubeconfig</dt><dd>访问 K8s 集群的“钥匙”文件，包含 API 地址（本项目 <code>https://192.168.100.10:6443</code>）、CA 证书和客户端证书。</dd>
        <dt>Namespace / Pod / Deployment / DaemonSet / StatefulSet / Service / ConfigMap / Secret</dt><dd>K8s 基本对象。Pod 是运行中的容器；Deployment 管理无状态 Pod 副本；DaemonSet 每个节点跑一个；StatefulSet 给每个副本固定名字和磁盘；Service 给一组 Pod 一个稳定地址；ConfigMap / Secret 存配置和密钥。</dd>
        <dt>Cilium</dt><dd>K8s 网络插件（CNI），用 eBPF 在内核里处理网络包。本项目让它完全替代 kube-proxy。</dd>
        <dt>eBPF</dt><dd>在内核里运行小程序的技术，Cilium 用它看到每个网络包。</dd>
        <dt>Hubble / hubble-relay</dt><dd>Cilium 的可观测组件。每个节点产生 flow 事件，hubble-relay（端口 4245）把全集群的事件汇总，<code>hubble observe</code> 命令从它读取。</dd>
        <dt>Vector</dt><dd>日志搬运工具。本项目里它以 DaemonSet 运行，执行 <code>hubble observe</code> 并把输出写入 Kafka。</dd>
        <dt>Kafka / topic / consumer group / offset</dt><dd>消息队列。消息写入 topic（本项目 <code>ebpf-net-logs</code>）；消费者以 group 为单位读取，各 group 互不影响；offset 是读到哪里的位置。本项目 Kafka 用 KRaft 模式：1 个 controller + 4 个 broker。</dd>
        <dt>MetalLB</dt><dd>在没有云厂商的集群里给 <code>type: LoadBalancer</code> 的 Service 分配真实 IP。本项目地址池 <code>192.168.100.200-250</code>。</dd>
        <dt>local-path</dt><dd>把节点本地目录当磁盘用的 StorageClass，Kafka broker 的 PVC 依赖它。</dd>
        <dt>flow（流）</dt><dd>同一个 5 元组（源 IP、目的 IP、源端口、目的端口、协议）的一组包。模型的输入单位是“流”，不是单个包。</dd>
        <dt>35 个特征</dt><dd>从一条流算出来的数字和字符串，例如持续时间、包数、SYN 比例、包间隔均值等，详见 <a href="/help/detect">检测链路与模型</a>。</dd>
        <dt>OCSVM</dt><dd>One-Class SVM，只用正常数据训练的异常检测模型，偏离“正常”的样本判为攻击。</dd>
        <dt>ZSL（零样本学习）</dt><dd>判为攻击后，拿样本和各攻击类型的“原型向量”算余弦相似度，猜它是哪种攻击；都不像就是 <code>Unknown_Attack</code>。</dd>
        <dt>Django / DRF</dt><dd>Python Web 框架和它的 REST 扩展（Django REST Framework）。</dd>
        <dt>ASGI / uvicorn / Channels</dt><dd>ASGI 是支持 WebSocket 的 Python Web 服务接口；uvicorn 是运行它的服务器；Channels 让 Django 能处理 WebSocket。</dd>
        <dt>JWT（access / refresh）</dt><dd>登录后拿到的令牌。access 有效 2 小时，每个请求都带上；refresh 有效 7 天，用来换新的 access。</dd>
        <dt>Vue 3 / Pinia / Vue Router / Element Plus / Vite</dt><dd>前端框架 / 状态管理 / 路由 / UI 组件库 / 构建工具。</dd>
        <dt>uv / pnpm</dt><dd>Python 和 Node 的包管理器。</dd>
        <dt>systemd 系统服务</dt><dd>开机自启的常驻服务，用 <code>sudo systemctl</code> 管理，<code>sudo journalctl -u &lt;名字&gt;</code> 看日志。NetSentinel 的两个服务以 <code>netsentinel</code> 账户运行；my-code 仍是 soar009 的 user 服务（<code>systemctl --user</code>）。</dd>
        <dt>cloudflared</dt><dd>Cloudflare 隧道客户端，把本机 8080 安全地映射到公网域名。</dd>
        <dt>SARIF</dt><dd>静态分析工具通用的 JSON 结果格式，checkov / tfsec / trivy 都输出它。</dd>
      </dl>
    </section>
  </div>
</template>

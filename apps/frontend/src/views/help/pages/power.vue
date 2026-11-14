<template>
  <div v-pre>
        <h1>开关机 · 重建 · 备份</h1>
    <div class="meta">宿主机关机前、开机后、组件坏到只能重建时，按本页逐步做。每一步都写了为什么要这么做、做完应该看到什么。<br></div>

    <section id="auto">
      <h2>开机后哪些会自动起来</h2>
      <div class="table-wrap"><table>
        <tr><th>组件</th><th>开机自动恢复</th><th>备注</th></tr>
        <tr><td>后端 <code>netsentinel</code>、隧道 <code>cloudflared-knettf</code></td><td>是</td><td>但后端起来时集群还没开，bridge 会连不上 Kafka 而退出，<b>集群起来后必须重启后端</b></td></tr>
        <tr><td>PostgreSQL 容器 <code>pg</code></td><td>是（<code>unless-stopped</code>）</td><td>手动 <code>docker stop</code> 过的不会自启</td></tr>
        <tr><td>/etc/cron.d 定时任务、网桥 <code>virbr-k8s</code></td><td>是</td><td></td></tr>
        <tr><td>5 台 VM</td><td><b>否</b></td><td>需要手动启动</td></tr>
        <tr><td>iptables NAT / FORWARD</td><td><b>否</b></td><td>02 脚本临时加的，没有持久化</td></tr>
        <tr><td>Kafka、Vector、MetalLB</td><td>随 VM 起来</td><td><code>kafka-controller</code> 是裸 Pod，被删了不会重建</td></tr>
      </table></div>
    </section>

    <section id="shutdown">
      <h2>计划关机（宿主机关机 / 重启前）</h2>
      <div class="task"><h4><span class="n">1</span>停掉所有实验脚本</h4>
        <div class="do"><div>在各个终端里 <span class="kbd">Ctrl</span>+<span class="kbd">C</span>，然后确认没有残留：<pre><code>pgrep -af 'simulate_|vigil_bridge|dataset_collector|start_send|start_read|monitor.py'</code></pre></div></div>
        <div class="why"><div>脚本被关机强行打断时，会留下绑在网桥上的伪造 IP 和写了一半的 CSV。</div></div>
        <div class="res"><div>没有输出。有的话 <code>sudo kill &lt;pid&gt;</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>清理伪造源 IP</h4>
        <div class="do"><div><pre><code>cd /srv/netsentinel/lab && sudo .venv/bin/python3 traffic/handle_addr.py --action delete
ip -4 addr show virbr-k8s | grep inet</code></pre></div></div>
        <div class="why"><div>发包脚本会临时把 .20-.29、.50-.64 等地址加到网桥上。残留的地址会让下次实验的标签和流量混在一起。</div></div>
        <div class="res"><div>只剩 <code>192.168.100.1/24</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>先关 4 台 worker，再关 master</h4>
        <div class="do"><div><pre><code>for v in k8s-node1 k8s-node2 k8s-node3 k8s-node4; do virsh -c qemu:///system shutdown $v; done
watch -n 5 "virsh -c qemu:///system list --all"     # 4 台都 shut off 后 Ctrl+C
virsh -c qemu:///system shutdown k8s-master</code></pre></div></div>
        <div class="why"><div>正常关机能让 etcd、Kafka 把数据写完。先关 worker 再关 master，worker 关机时控制面还在，Pod 能正常终止。</div></div>
        <div class="res"><div>1～2 分钟内全部 <code>shut off</code>。超过 5 分钟还没关，再执行一次 shutdown；仍然不行才用 <code>virsh -c qemu:///system destroy</code>（相当于拔电源，可能损坏数据）。</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>关闭宿主机</h4>
        <div class="do"><div><pre><code>sudo reboot     # 或 sudo poweroff</code></pre></div></div>
        <div class="why"><div>后端和 pg 交给 systemd 和 Docker 自动停止即可。<b>不要</b>手动 <code>docker stop pg</code>：手动停过的容器开机后不会自启。</div></div>
        <div class="res"><div>机器关机。重大变更或长时间停机前，先做 <a href="#backup">备份</a>。</div></div>
      </div>
    </section>

    <section id="startup">
      <h2>开机恢复（宿主机重启后）</h2>
      <div class="task"><h4><span class="n">1</span>确认自动恢复的部分</h4>
        <div class="do"><div><pre class="on-prod"><code>sudo systemctl is-active netsentinel cloudflared-knettf
docker ps --filter name=pg --format '{{.Names}} {{.Status}}'
virsh -c qemu:///system net-list --all | grep virbr-k8s
sysctl net.ipv4.ip_forward</code></pre></div></div>
        <div class="why"><div>先确认地基在，后面的步骤才有意义。</div></div>
        <div class="res"><div><code>active active</code>；<code>pg Up</code>；<code>virbr-k8s active yes</code>；<code>ip_forward = 1</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>恢复 VM 出网的 iptables 规则</h4>
        <div class="do"><div><pre><code>sudo iptables -t nat -C POSTROUTING -s 192.168.100.0/24 ! -d 192.168.100.0/24 -o enp6s0 -j MASQUERADE 2&gt;/dev/null \
  || sudo iptables -t nat -A POSTROUTING -s 192.168.100.0/24 ! -d 192.168.100.0/24 -o enp6s0 -j MASQUERADE
sudo iptables -C FORWARD -s 192.168.100.0/24 -j ACCEPT 2&gt;/dev/null || sudo iptables -A FORWARD -s 192.168.100.0/24 -j ACCEPT
sudo iptables -C FORWARD -d 192.168.100.0/24 -j ACCEPT 2&gt;/dev/null || sudo iptables -A FORWARD -d 192.168.100.0/24 -j ACCEPT</code></pre></div></div>
        <div class="why"><div>规则没有持久化，重启后就没了；VM 没有这些规则就无法出网拉镜像。命令是幂等的（先 <code>-C</code> 检查，没有才 <code>-A</code> 添加），可以重复执行。</div></div>
        <div class="res"><div>没有报错。出口网卡若不是 <code>enp6s0</code>，用 <code>ip route get 1.1.1.1</code> 查实际网卡。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>启动 master，等 apiserver 就绪</h4>
        <div class="do"><div><pre><code>virsh -c qemu:///system start k8s-master
until kubectl get --raw=/readyz &gt;/dev/null 2&gt;&amp;1; do sleep 5; done; echo apiserver ready</code></pre></div></div>
        <div class="why"><div>worker 要向 master 注册，master 没就绪时启动 worker，节点会长时间 NotReady。</div></div>
        <div class="res"><div>1～3 分钟后输出 <code>apiserver ready</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>启动 worker</h4>
        <div class="do"><div><pre><code>for v in k8s-node1 k8s-node2 k8s-node3 k8s-node4; do virsh -c qemu:///system start $v; done
kubectl wait --for=condition=Ready node --all --timeout=600s</code></pre></div></div>
        <div class="why"><div>Kafka broker 和 Vector 都跑在 worker 上。</div></div>
        <div class="res"><div>5 行 <code>condition met</code>。超时：<code>virsh -c qemu:///system net-dhcp-leases virbr-k8s</code> 看 VM 是否拿到 .10-.14 的 IP。</div></div>
      </div>
      <div class="task"><h4><span class="n">5</span>等核心组件就绪</h4>
        <div class="do"><div><pre><code>kubectl -n kube-system rollout status ds/cilium --timeout=300s
kubectl -n kube-system rollout status deploy/hubble-relay --timeout=300s
kubectl -n metallb-system rollout status deploy/metallb-controller --timeout=300s
kubectl get pod kafka-controller
kubectl rollout status sts/kafka-broker --timeout=600s
kubectl -n kube-system rollout status ds/vector --timeout=300s</code></pre></div></div>
        <div class="why"><div>按依赖顺序等：Cilium（网络）→ hubble-relay（产生事件）→ MetalLB（Kafka 外部地址）→ Kafka → Vector（往 Kafka 写）。</div></div>
        <div class="res"><div>全部 <code>successfully rolled out</code>，<code>kafka-controller 1/1 Running</code>。<br><span class="bad">kafka-controller 不存在</span>：只能 <a href="#rebuild-kafka">重建 Kafka</a>。</div></div>
      </div>
      <div class="task"><h4><span class="n">6</span>核对 MetalLB 地址没变</h4>
        <div class="do"><div><pre><code>kubectl get svc -A | grep LoadBalancer</code></pre></div></div>
        <div class="why"><div>后端连 Kafka 用的地址是写死在 <code>bridge.py</code> 里的 .200-.203，地址一变，bridge 就连不上。</div></div>
        <div class="res"><div>kafka-0~3-external = 192.168.100.200~203；my-nginx = .204；targets = .210~.214。<br><span class="bad">Kafka 地址变了</span>：重跑 <code>/srv/netsentinel/lab/cluster/03-deploy-5nodes.sh</code>，并改 <code>bridge.py</code> 的 <code>KAFKA_BOOTSTRAP</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">7</span>重启后端，让 bridge 重新连上 Kafka</h4>
        <div class="do"><div><pre class="on-prod"><code>sudo systemctl restart netsentinel
sleep 20; sudo journalctl -u netsentinel --since '-1 min' | grep -E 'AdsMLModel|bridge|drainer'</code></pre></div></div>
        <div class="why"><div>后端在第 1 步之前就已经启动了，那时 Kafka 还不在，bridge 线程已经退出且不会重连。<b>这一步最容易忘，忘了检测就一直没有数据。</b></div></div>
        <div class="res"><div>能看到 <code>AdsMLModel loaded</code>、<code>vigil bridge + drainer threads started</code>、<code>bridge starting → bootstrap=...</code>，没有 <code>bridge error</code>。</div></div>
      </div>
      <div class="task" id="verify"><h4><span class="n">8</span>端到端验证</h4>
        <div class="do"><div><pre><code>cd /srv/netsentinel/lab && sudo .venv/bin/python3 traffic/spoof_attack.py --packets 200
sleep 15
docker exec pg psql -U vigil vigil -c "select created_at, src_ip, is_attack, attack_type from vigil_detectionrecord order by created_at desc limit 5;"</code></pre></div></div>
        <div class="why"><div>前面每一步只证明各自那一环正常；从发包到入库走一遍，才能证明整条链路是通的。</div></div>
        <div class="res"><div>出现源 IP 为 192.168.100.20~29、刚写入的记录；网页 <code>/vigil/log</code> 15 秒内能看到。</div></div>
      </div>
      <div class="ok">可选的一次性改进：<code>for v in k8s-master k8s-node{1..4}; do virsh -c qemu:///system autostart $v; done</code> 让 VM 开机自启；<code>sudo apt install iptables-persistent &amp;&amp; sudo netfilter-persistent save</code> 持久化 iptables。做了之后第 2～4 步可以省掉，但第 7 步（重启后端）仍然要做。</div>
    </section>

    <section id="rebuild">
      <h2>重建</h2>
      <div class="danger">重建前必须先做 <a href="#backup">备份</a>。knetsentinel 的脚本在 Git 里，但数据（<code>dataset/</code>、<code>logs/</code>、<code>*.csv</code>）<b>不在 Git 里</b>，删了就找不回来。</div>
      <div class="table-wrap"><table>
        <tr><th>重建什么</th><th>会丢失</th><th>耗时</th></tr>
        <tr><td><a href="#rebuild-kafka">Kafka / Vector</a></td><td>topic 中还没消费的事件</td><td>10 分钟</td></tr>
        <tr><td><a href="#rebuild-cluster">整个 K8s 集群</a></td><td>全部 VM、集群状态、Kafka、kubeconfig</td><td>1～2 小时</td></tr>
        <tr><td><a href="#rebuild-db">default 库</a></td><td>用户、集群记录、Terraform 配置与报告</td><td>5 分钟</td></tr>
        <tr><td><a href="#rebuild-vigil">vigil 库</a></td><td>全部检测记录</td><td>5 分钟</td></tr>
        <tr><td><a href="#rebuild-env">运行环境（.venv / dist）</a></td><td>不丢数据</td><td>5 分钟</td></tr>
      </table></div>

      <h3 id="rebuild-kafka">重建 Kafka</h3>
      <div class="task"><h4><span class="n">1</span>导出需要保留的数据</h4>
        <div class="do"><div><pre><code>cd /srv/netsentinel/lab && uv run python lab/collect/kafka_read_csv.py --output backup_$(date +%F).csv --max-attack 1000000 --max-normal 1000000</code></pre></div></div>
        <div class="why"><div>删掉 PVC 后，topic 里的数据就没了。</div></div>
        <div class="res"><div>生成 CSV（不需要保留数据时可以跳过这一步）。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>删除 Kafka 资源和 PVC</h4>
        <div class="do"><div><pre><code>kubectl delete -f /srv/netsentinel/lab/manifests/kafka-5nodes.yaml --ignore-not-found
kubectl delete pvc -l app=kafka-broker --ignore-not-found
kubectl get pods,pvc | grep kafka</code></pre></div></div>
        <div class="why"><div>controller 元数据丢失后，broker 用旧 PVC 往往注册失败，全部删掉重来最稳妥。</div></div>
        <div class="res"><div>最后一条没有输出。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>重新部署、核对地址、重启后端</h4>
        <div class="do"><div><pre class="on-prod"><code>cd /srv/netsentinel/lab/cluster && bash 03-deploy-5nodes.sh
kubectl get svc | grep 'kafka-.-external'
sudo systemctl restart netsentinel</code></pre></div></div>
        <div class="why"><div>03 脚本是幂等的：先建 Service 拿到 MetalLB IP，再部署 controller、broker、Vector。后端要重启，bridge 才会连上新的 Kafka。</div></div>
        <div class="res"><div>地址是 .200-.203，后端日志没有 <code>bridge error</code>。地址变了就先改 <code>bridge.py</code> 再重启。</div></div>
      </div>

      <h3 id="rebuild-cluster">重建整个集群</h3>
      <div class="task"><h4><span class="n">1</span>备份并停后端</h4>
        <div class="do"><div><pre class="on-prod"><code>tar czf /srv/netsentinel/backups/lab_backup_$(date +%F).tgz -C /srv/netsentinel --exclude='lab/.venv' lab
kubectl get svc -A -o wide &gt; /home/NEWUSER/svc_before_rebuild.txt
cp /home/NEWUSER/.kube/config /home/NEWUSER/kubeconfig_before_rebuild
sudo systemctl stop netsentinel</code></pre></div></div>
        <div class="why"><div>00 脚本会删掉 VM 磁盘和 kubeconfig。先停后端，免得重建期间 bridge 不停地报错。</div></div>
        <div class="res"><div>备份文件已生成，服务 inactive。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>按顺序跑 00 → 01 → 02 → 03</h4>
        <div class="do"><div><pre><code>cd /srv/netsentinel/lab/cluster
bash 00-clear.sh            # 不可逆：删 VM、网桥、磁盘、kubeconfig、/etc/hosts 条目
bash 01-setup-vms.sh        # 网桥 + 5 台 VM
bash 02-setup-cluster.sh    # kubeadm + Cilium/Hubble + MetalLB + local-path
bash 03-deploy-5nodes.sh    # Kafka + Vector + my-nginx
kubectl apply -f /srv/netsentinel/lab/cluster/targets.yaml
kubectl apply -f /srv/netsentinel/lab/cluster/host-firewall-ccnp.yaml</code></pre>以普通用户运行，<b>不要</b> <code>sudo bash</code>（kubeconfig 会写到 root 的家目录）。</div></div>
        <div class="why"><div>每一步都依赖上一步的产物（详见 <a href="/help/index#order">系统总览 · 构建顺序</a>）。01 需要 ≥ 420GB 空闲磁盘和外网。</div></div>
        <div class="res"><div>5 个节点 Ready，Kafka 地址 .200-.203。MetalLB webhook 偶尔会拒绝 IP 池，重跑 02 即可。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>让 NetSentinel 对上新集群</h4>
        <div class="do"><div><ol>
          <li><code>sudo systemctl start netsentinel</code></li>
          <li>登录网页 → 删掉旧的集群记录 → 用同样的名字重新添加，粘贴新的 <code>/home/NEWUSER/.kube/config</code>。</li>
          <li>用了入口 B 的话，重建 Secret <code>detector-secret</code> 并部署检测器（<a href="/help/detect">检测链路</a> 入口 B 一节）。</li>
          <li>做一次 <a href="#verify">端到端验证</a>。</li>
        </ol></div></div>
        <div class="why"><div>集群的 CA 和证书全部换新，网页上存的旧 kubeconfig 已经失效，Kubernetes 页会全部报错。</div></div>
        <div class="res"><div>网页 Kubernetes 页能列出 Namespaces；检测有新记录。</div></div>
      </div>

      <h3 id="rebuild-db">重置 default 库（用户 / 集群 / Terraform）</h3>
<pre class="on-prod"><code>sudo systemctl stop netsentinel
cd <span class="vp">/srv/netsentinel/prod</span>/backend && cp db.sqlite3 db.sqlite3.bak_$(date +%F_%H%M)
<span class="c"># 方式一：只清业务数据</span>
../.venv/bin/python manage.py autotf_clear &amp;&amp; ../.venv/bin/python manage.py users_clear
<span class="c"># 方式二：整库重建</span>
rm db.sqlite3 &amp;&amp; ../.venv/bin/python manage.py migrate
<span class="c"># 初始化</span>
../.venv/bin/python manage.py users_init           # admin / alice / bob
../.venv/bin/python manage.py autotf_init          # 注册 5 个扫描工具
../.venv/bin/python manage.py generate_bridge_token --write-env
sudo systemctl start netsentinel</code></pre>
      <p><b>为什么要重新生成 token</b>：vigil-bridge 服务账号也跟着删掉了。<b>结果</b>：<code>autotf_clear</code> 会删除整个 <code>apps/backend/terraform/</code> 目录；部署了入口 B 的话，要同步更新 Secret <code>detector-secret</code>。</p>

      <h3 id="rebuild-vigil">重置 vigil 库（检测记录）</h3>
<pre class="on-prod"><code>sudo systemctl stop netsentinel
cd <span class="vp">/srv/netsentinel/prod</span>/backend
../.venv/bin/python manage.py migrate vigil zero --database=vigil   # DROP TABLE ... CASCADE
../.venv/bin/python manage.py migrate vigil --database=vigil        # 重建父表 + 91 个分区
sudo systemctl start netsentinel</code></pre>
      <p>只想清数据、不动表结构：<code>docker exec pg psql -U vigil vigil -c "TRUNCATE vigil_detectionrecord;"</code>。</p>

      <h3 id="rebuild-env">重建运行环境</h3>
<pre class="on-both"><code>sudo systemctl stop netsentinel
cd <span class="vp">/srv/netsentinel/prod</span> &amp;&amp; rm -rf .venv frontend/node_modules apps/frontend/dist &amp;&amp; uv sync --frozen
/srv/netsentinel/prod/ops/scripts/deploy.sh -all       # 重新部署当前 prod，不发布新提交</code></pre>
      <p>这几个目录都可以重新生成，不会丢数据。开发目录 <code class="vn">/home/NEWUSER/github/knettf</code> 的环境坏了同理：<code class="vn">cd /home/NEWUSER/github/knettf &amp;&amp; rm -rf .venv &amp;&amp; uv sync --frozen</code>，不影响线上。</p>
    </section>

    <section id="backup">
      <h2>备份与恢复</h2>
      <div class="table-wrap"><table>
        <tr><th>对象</th><th>备份命令</th><th>恢复</th></tr>
        <tr><td>default 库</td><td><code class="vp">sqlite3 /srv/netsentinel/prod/apps/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"</code></td><td>停服务 → 覆盖 <code>db.sqlite3</code> → 启服务</td></tr>
        <tr><td>vigil 库</td><td><code>docker exec pg pg_dump -U vigil -Fc vigil &gt; /srv/netsentinel/backups/vigil_$(date +%F).dump</code></td><td>见下方</td></tr>
        <tr><td>上传的 .tf 文件</td><td><code class="vp">tar czf tf_$(date +%F).tgz -C /srv/netsentinel/prod/apps/backend terraform</code></td><td>解压回 <code>backend/</code></td></tr>
        <tr><td>后端 .env</td><td><code class="vp">cp /srv/netsentinel/prod/apps/backend/backend/.env /home/NEWUSER/netsentinel_env_$(date +%F)</code></td><td>复制回去，重启后端</td></tr>
        <tr><td>模型文件</td><td><code class="vp">tar czf ads_ml_$(date +%F).tgz -C /srv/netsentinel models/ads_ml</code></td><td>解压回去，重启后端</td></tr>
        <tr><td>knetsentinel 全部</td><td><code>tar czf /srv/netsentinel/backups/lab_$(date +%F).tgz -C /srv/netsentinel --exclude='lab/.venv' lab</code></td><td>解压，<code>uv sync</code></td></tr>
        <tr><td>kubeconfig</td><td><code>cp /home/NEWUSER/.kube/config /home/NEWUSER/kubeconfig_$(date +%F)</code></td><td>集群没重建时才有用</td></tr>
        <tr><td>systemd / cloudflared</td><td><code>sudo tar czf /srv/netsentinel/backups/sys_$(date +%F).tgz /etc/systemd/system/netsentinel.service /etc/systemd/system/cloudflared-knettf.service /etc/cloudflared/knettf /etc/cron.d/netsentinel /etc/sudoers.d/netsentinel</code></td><td>解压，<code>sudo systemctl daemon-reload</code></td></tr>
        <tr><td>定时任务</td><td>在上一行的 <code>/etc/cron.d/netsentinel</code> 里，源文件 <code>deploy/cron.netsentinel</code></td><td>解压或从仓库重装</td></tr>
      </table></div>
      <h3>恢复 vigil 库</h3>
<pre class="on-prod"><code>sudo systemctl stop netsentinel
docker exec -i pg pg_restore -U vigil -d vigil --clean --if-exists &lt; /srv/netsentinel/backups/vigil_2026-10-16.dump
sudo systemctl start netsentinel
docker exec pg psql -U vigil vigil -Atc "select count(*) from vigil_detectionrecord;"</code></pre>
      <p>恢复之后检查明天的分区还在不在（<a href="/help/health">健康检查</a> 第 3 步）：备份里可能没有新日期的分区。</p>
    </section>
  </div>
</template>

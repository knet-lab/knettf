<template>
  <div v-pre>
        <h1>排障与日志</h1>
    <div class="meta">先用“排查顺序”定位是哪一层出了问题，再到“现象对照表”里找对应的处理办法。</div>

    <section id="order">
      <h2>排查顺序：从外到内</h2>
      <p>每一层用一条命令确认。上一层不通，就不用往下查了。</p>
<pre class="on-prod"><code>浏览器打不开 knettf.com
  ├─ curl localhost:8080 正常？ ── 否 → 后端问题：sudo journalctl -u netsentinel -n 100 看启动报错
  │                                      （常见：<span class="vp">/srv/netsentinel/prod</span>/.venv 坏了、pg 没起、<span class="vp">/srv/netsentinel/prod</span> 的 .env 缺 ENVIRONMENT、settings 语法错）
  │                                      （返回 400：用了不在 ALLOWED_HOSTS 里的域名 / IP，改 <span class="vp">/srv/netsentinel/prod</span>/backend/backend/.env）
  └─ 是 → 隧道问题：sudo systemctl status cloudflared-knettf

网页能开，但某个功能报错
  ├─ 浏览器 F12 → Network，找失败的 /api/ 请求，看状态码和响应里的 message
  ├─ 401 → token 过期且 refresh 也过期 → 重新登录
  ├─ 403 → 不是资源的 owner，也不是管理员
  ├─ 404 → URL 拼错（末尾斜杠？）或对象不存在
  ├─ 500 → journalctl 看 Traceback
  └─ Kubernetes 页全部失败 → 集群没开机 / kubeconfig 过期

检测没有新数据
  Kafka 有数据？（健康检查第 5 步）
    ├─ 否 → 集群侧：Vector / hubble-relay（kubectl logs）
    └─ 是 → 后端日志有 bridge error？
              ├─ 是 → Kafka 恢复后重启后端
              └─ 否 → 有 drainer failed？
                        ├─ 是 → 看后面的异常，多数是缺分区
                        └─ 否 → 发包的源 IP 是不是被当成基础设施流量过滤掉了？</code></pre>
      <div class="learn">九成情况下，“检测没数据”的原因是 bridge 线程退出了：Kafka 出错时它会直接退出、<b>不会重连</b>，重启后端就好。</div>
    </section>

    <section id="table">
      <h2>现象对照表</h2>
      <div class="table-wrap"><table>
        <tr><th>现象</th><th>检查</th><th>原因 → 处理</th></tr>
        <tr><td>网页打不开</td><td><code>sudo systemctl status netsentinel</code>；<code>sudo journalctl -u netsentinel -n 100</code></td><td><code>.venv</code> 损坏、PostgreSQL 不可用、settings 语法错误 → 修好后重启</td></tr>
        <tr><td>公网打不开、本机正常</td><td><code>sudo journalctl -u cloudflared-knettf -n 50</code></td><td>隧道断开 → 重启隧道；检查 <code>/etc/cloudflared/knettf/config.yml</code></td></tr>
        <tr><td>白屏 / 404</td><td><code class="vp">ls /srv/netsentinel/prod/frontend/dist/index.html</code>；浏览器开发者工具看 <code>/assets/*.js</code> 是否 404</td><td>dist 不存在 → <code>/srv/netsentinel/prod/scripts/deploy.sh -frontend</code>（重新部署当前 prod）；dist 在但 js 404 → 构建后没重启（DEBUG=False 时 WhiteNoise 只在启动时扫描），<code>sudo systemctl restart netsentinel</code></td></tr>
        <tr><td>登录后马上掉线</td><td>F12 看 <code>/api/auth/token/refresh/</code></td><td>refresh 过期（7 天）→ 重新登录，清 localStorage</td></tr>
        <tr><td>日志 <code>bridge error</code></td><td><code>nc -zv 192.168.100.200 9094</code></td><td>Kafka 连不上 → 恢复 Kafka 后重启后端</td></tr>
        <tr><td>日志 <code>drainer failed</code> + <code>no partition of relation</code></td><td>分区缺失</td><td><code>manage.py rotate_partitions --database vigil</code>；当天的分区缺失就用 SQL 手动建</td></tr>
        <tr><td>Detection model 为空</td><td><code>journalctl ... | grep 'AdsMLModel not loaded'</code></td><td><code>trained/</code> 文件缺失，或 scikit-learn 版本和训练时不一致（固定 1.7.2）</td></tr>
        <tr><td>推理很慢</td><td>记录里的 <code>raw_output.inference_ms</code></td><td>每条流都会重新加载模型，属已知问题（<a href="/help/issues">已知问题</a>）</td></tr>
        <tr><td>Kafka 无数据</td><td><code>kubectl -n kube-system logs -l app=vector --tail=50</code>；<code>kubectl -n kube-system get svc hubble-relay</code></td><td>hubble-relay 端口必须是 4245；必要时 <code>rollout restart ds/vector</code></td></tr>
        <tr><td>Hubble 看不到伪造源 IP</td><td><code>ip addr show virbr-k8s</code></td><td>源 IP 没绑上；apply <code>host-firewall-ccnp.yaml</code></td></tr>
        <tr><td>broker CrashLoop</td><td><code>kubectl logs kafka-broker-N</code>；<code>kubectl logs kafka-controller</code></td><td>controller 元数据丢失 → <a href="/help/power#rebuild-kafka">重建 Kafka</a></td></tr>
        <tr><td>节点 NotReady</td><td><code>ssh k8s@192.168.100.1X 'systemctl status kubelet containerd'</code></td><td>swap 被打开、磁盘满、containerd 挂了</td></tr>
        <tr><td>VM 拿不到 IP / SSH 超时</td><td><code>virsh -c qemu:///system net-dhcp-leases virbr-k8s</code></td><td><code>virsh -c qemu:///system net-destroy virbr-k8s &amp;&amp; virsh -c qemu:///system net-start virbr-k8s</code>，再重启 VM</td></tr>
        <tr><td>VM 无法出网</td><td><code>sudo iptables -t nat -S | grep 192.168.100</code></td><td>规则丢了 → <a href="/help/power#startup">开机恢复</a> 第 2 步</td></tr>
        <tr><td>Kubernetes 页全部 502</td><td>集群是否重建过</td><td>kubeconfig 过期 → 网页上重新添加集群</td></tr>
        <tr><td>某个扫描工具结果为空</td><td>报告里有 <code>tool not found</code></td><td>服务进程的 PATH 里找不到这个工具 → 安装，或在 TF Tools 里停用</td></tr>
        <tr><td>Terraform Apply 按钮灰色</td><td>鼠标悬停看提示</td><td>没扫描 / 扫描没完成 / 有 HIGH 问题 → 先修复再扫描</td></tr>
        <tr><td>后端被 OOM 重启</td><td><code>sudo journalctl -u netsentinel | grep -i memory</code></td><td>MemoryMax=3G；flow_queue 积压或大查询</td></tr>
      </table></div>
    </section>

    <section id="logs">
      <h2>日志在哪</h2>
      <div class="table-wrap"><table>
        <tr><th>来源</th><th>命令 / 位置</th><th>值得搜的关键字</th></tr>
        <tr><td>后端（含 bridge、drainer、模型、WebSocket）</td><td><code>sudo journalctl -u netsentinel -f</code></td><td><code>AdsMLModel loaded</code>、<code>bridge starting</code>、<code>queue: N flows</code>、<code>bridge error</code>、<code>drainer failed</code>、<code>detector pod connected</code></td></tr>
        <tr><td>隧道</td><td><code>sudo journalctl -u cloudflared-knettf -f</code></td><td></td></tr>
        <tr><td>分区轮转</td><td><code>/srv/netsentinel/logs/rotate_partitions.log</code>（重启后清空）</td><td><code>rotate_partitions done</code></td></tr>
        <tr><td>PostgreSQL</td><td><code>docker logs --tail 100 pg</code></td><td></td></tr>
        <tr><td>模型最近一次推理</td><td><code class="vp">/srv/netsentinel/prod/backend/vigil/ml/ads_ml/results/Anomaly_Detection_Report.csv</code></td><td></td></tr>
        <tr><td>Vector / Kafka / hubble-relay</td><td><code>kubectl -n kube-system logs -l app=vector --tail=50</code>；<code>kubectl logs kafka-broker-0</code>；<code>kubectl -n kube-system logs deploy/hubble-relay</code></td><td></td></tr>
        <tr><td>入口 B 检测器</td><td><code>kubectl -n netsentinel logs deploy/netsentinel-detector -f</code></td><td><code>connected to Django</code></td></tr>
        <tr><td>knetsentinel 脚本</td><td><code>/srv/netsentinel/knetsentinel/logs/</code>、<code>/srv/netsentinel/knetsentinel/kafka/*.log</code>、<code>/srv/netsentinel/knetsentinel/traffic_request/*.log</code>、<code>/srv/netsentinel/knetsentinel/simulation/monitor/send.log</code></td><td></td></tr>
      </table></div>
    </section>

    <section id="dont">
      <h2>不要做的事</h2>
      <div class="table-wrap"><table>
        <tr><th>不要</th><th>因为</th></tr>
        <tr><td>删除 <code>kafka-controller</code> Pod、任何 Namespace</td><td>controller 是裸 Pod，删了不会重建，只能重建 Kafka</td></tr>
        <tr><td>同时开两条检测入口（A / B / C）</td><td>各自独立消费 Kafka 并写库，同一条流会被记录两次</td></tr>
        <tr><td>在 <code class="vp">/srv/netsentinel/prod</code> 里跑 <code>manage.py runserver</code>，或在没设 <code>VIGIL_KAFKA_GROUP_ID=vigil-bridge-dev</code> 的开发环境跑</td><td>会再启动一个 bridge，和线上同一个 consumer group，分走 Kafka 分区，线上漏收流量</td></tr>
        <tr><td>在 <code class="vp">/srv/netsentinel/prod</code> 里改代码、<code>git commit</code> 或 <code>git pull</code> GitHub</td><td><code>deploy.sh</code> 检测到生产目录有本地改动会直接拒绝部署；线上只能由 <code>deploy.sh</code> 从 GitHub 的 prod 更新</td></tr>
        <tr><td>把 <code>/etc/cron.d/netsentinel</code> 的 <code>rotate_partitions</code> 改成开发目录</td><td>开发目录默认连 <code>vigil_dev</code>，分区会建到开发库，线上过零点全部写入失败</td></tr>
        <tr><td><code>sudo bash</code> 跑集群脚本</td><td>kubeconfig 会写到 root 的家目录</td></tr>
        <tr><td><code>docker stop pg</code></td><td>手动停过的容器开机后不会自启</td></tr>
        <tr><td>在生产库上跑 <code>users_clear</code> / <code>autotf_clear</code></td><td>会清空全部用户和 Terraform 数据</td></tr>
        <tr><td>Apply 不了解的 Terraform 配置</td><td>会真实创建资源，而且不保留 tfstate，没法从网页 destroy</td></tr>
        <tr><td>删 <code>/home/vm-images/ubuntu-22.04-cloudimg.qcow2</code></td><td>5 台 VM 的基础镜像</td></tr>
      </table></div>
    </section>
  </div>
</template>

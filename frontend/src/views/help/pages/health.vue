<template>
  <div v-pre>
        <h1>每日健康检查</h1>
    <div class="meta">每天一次，约 5 分钟：命令行 2 分钟 + 网页 3 分钟。每一步写明怎么做、为什么查它、正常应该看到什么；结果对不上就按该步的处理办法走，处理不了再去 <a href="/help/trouble">排障与日志</a>。<br>
      先设好路径变量：<code>export N=~/github/NetSentinel K=~/knetsentinel</code>。前提：已通过 <a href="/help/prepare#ready">准备完成验收</a>。服务还在 soar009 名下时，先 <code>sudo -iu soar009</code>（见 <a href="/help/prepare#transition">接手准备 2.1</a>）。</div>

    <section id="cli">
      <h2>命令行检查（按顺序，从外到内）</h2>
      <p>顺序有讲究：前一步不通，后一步的结果就没有意义。</p>

      <div class="task"><h4><span class="n">1</span>服务和端口在不在</h4>
        <div class="do"><div><pre><code>systemctl --user is-active netsentinel cloudflared-knettf
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/</code></pre></div></div>
        <div class="why"><div><code>netsentinel</code> 是后端（同时提供网页），<code>cloudflared-knettf</code> 把它映射到 knettf.com。任何一个挂了，网站就打不开。</div></div>
        <div class="res"><div>两行 <code>active</code>，再一行 <code>200</code>。<br><span class="bad">不是</span>：<code>journalctl --user -u netsentinel -n 50</code> 看启动报错。</div></div>
      </div>

      <div class="task"><h4><span class="n">2</span>模型已加载、bridge 在消费 Kafka</h4>
        <div class="do"><div><pre><code>journalctl --user -u netsentinel --since today | grep -E 'AdsMLModel (loaded|not loaded)' | tail -1
journalctl --user -u netsentinel --since '-10 min' | grep -E 'vigil.bridge|bridge error' | tail -3</code></pre></div></div>
        <div class="why"><div>服务“活着”不等于检测在工作。模型没加载就不会出检测结果；bridge 线程连不上 Kafka 会直接退出且<b>不会重连</b>，这时服务看起来正常，但数据已经停了。</div></div>
        <div class="res"><div>第一行是 <code>AdsMLModel loaded</code>；第二条有最近 10 分钟的 <code>queue: N flows → M attack(s)</code>（有流量时），没有 <code>bridge error</code>。<br><span class="bad">有 bridge error 或很久没有 bridge 日志</span>：先做第 5 步确认 Kafka 有数据，再 <code>systemctl --user restart netsentinel</code>。</div></div>
      </div>

      <div class="task"><h4><span class="n">3</span>数据库在写入、明天的分区已建好</h4>
        <div class="do"><div><pre><code>docker exec pg psql -U vigil vigil -Atc "select max(created_at) from vigil_detectionrecord;"
docker exec pg psql -U vigil vigil -Atc "select to_regclass('vigil_detectionrecord_'||to_char(now()+interval '1 day','YYYY_MM_DD'));"
tail -1 /tmp/rotate_partitions.log</code></pre></div></div>
        <div class="why"><div>检测记录按天分区存放。明天的分区如果不存在，过了零点所有写入都会失败（日志里是 <code>drainer failed</code>）。分区由 crontab 里的 <code>rotate_partitions</code> 每天 0 点创建。</div></div>
        <div class="res"><div>第一行是几分钟内的时间（有实验时）；第二行输出一个表名，不是空行；第三行含 <code>rotate_partitions done</code>。<br><span class="bad">第二行为空</span>：<code>cd $N/backend && ../.venv/bin/python manage.py rotate_partitions --database vigil</code>，再用 <code>crontab -l</code> 查定时任务还在不在。</div></div>
      </div>

      <div class="task"><h4><span class="n">4</span>集群正常</h4>
        <div class="do"><div><pre><code>virsh -c qemu:///system list --all
kubectl get nodes
kubectl get pods -A | grep -vE 'Running|Completed'</code></pre></div></div>
        <div class="why"><div>流量数据来自 5 台 VM 组成的 K8s 集群（Cilium → Vector → Kafka），任何一环不在，后端就收不到数据。VM <b>不会</b>随宿主机开机自启。</div></div>
        <div class="res"><div>5 台 VM <code>running</code>，5 个节点 <code>Ready</code>，最后一条只输出表头。<br><span class="bad">VM shut off</span>：宿主机重启过，按 <a href="/help/power#startup">开机恢复</a> 做。<span class="bad">有 Pending / CrashLoopBackOff</span>：<code>kubectl describe pod</code> 看原因，再查 <a href="/help/trouble">排障表</a>。</div></div>
      </div>

      <div class="task"><h4><span class="n">5</span>Kafka 里有新数据</h4>
        <div class="do"><div><pre><code>kubectl exec kafka-broker-0 -- /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka-svc.default.svc.cluster.local:9092 --topic ebpf-net-logs --max-messages 2 --timeout-ms 15000</code></pre></div></div>
        <div class="why"><div>第 2 步看到 bridge 没数据时，用这一步判断问题在集群这边（Vector / Hubble 没写进 Kafka）还是在后端这边。</div></div>
        <div class="res"><div>输出 2 行 Hubble JSON。<br><span class="bad">超时无输出</span>：问题在集群侧，查 Vector 日志（<a href="/help/trouble">排障表</a>“Kafka 无数据”一行）。</div></div>
      </div>

      <div class="task"><h4><span class="n">6</span>磁盘空间</h4>
        <div class="do"><div><pre><code>df -h / /home ~/vm-images /home/docker-data | sort -u
du -sh $N/backend/vigil/ml/ads_ml/results</code></pre></div></div>
        <div class="why"><div>pg 数据、Kafka、VM 磁盘都在本机。磁盘满会让数据库和集群同时出问题。<code>results/</code> 下的推理报告每条推理追加一行，会持续变大。</div></div>
        <div class="res"><div>使用率低于 85%。<br><span class="bad">超过</span>：先清 <code>/tmp</code>、旧日志、<code>results/</code> 下的 CSV。</div></div>
      </div>
    </section>

    <section id="web">
      <h2>网页检查</h2>
      <p>登录 <code>https://knettf.com</code>，逐项看。命令行检查管的是“系统在不在跑”，网页检查管的是“数据和账号对不对”。</p>
      <div class="table-wrap"><table>
        <tr><th>看哪里</th><th>正常</th><th>为什么看 / 不正常时</th></tr>
        <tr><td>能否打开并登录</td><td>能登录</td><td>打不开但命令行第 1 步正常 → 隧道问题，<code>systemctl --user status cloudflared-knettf</code></td></tr>
        <tr><td><span class="ui">AI Vigil</span> 左侧 Detection model</td><td><code>ads_ml_ocsvm</code></td><td>显示 No models registered = 模型加载失败，查日志 <code>AdsMLModel not loaded</code></td></tr>
        <tr><td>检测日志最新一条的时间</td><td>有实验时在几分钟内</td><td>有流量却没新记录 → bridge 多半已退出，重启后端</td></tr>
        <tr><td>Attack Rate、攻击类型</td><td>与实验计划相符</td><td>没做实验却有大量攻击、陌生源 IP → 截图上报</td></tr>
        <tr><td>管理后台 <span class="ui">Users</span></td><td>都认识</td><td>注册接口对公网开放，任何人都能注册 → 陌生账号删除并上报</td></tr>
        <tr><td><span class="ui">Kubernetes</span> → <code>default</code>、<code>kube-system</code> 的 Pods</td><td>全部 Running</td><td>看 Logs 并截图</td></tr>
        <tr><td>管理后台 <span class="ui">TF Tools</span></td><td>5 个都 Enabled</td><td>被停用的工具扫描时会被跳过 → 问清原因后恢复</td></tr>
      </table></div>
    </section>
  </div>
</template>

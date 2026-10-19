<template>
  <div v-pre>
        <h1>实验脚本</h1>
    <div class="meta">读完你能：发正常 / 攻击流量并在网页上看到检测结果；采集带标签的数据集并聚合成特征；直接从 Kafka 读事件；跑端到端仿真和离线评估。<br>
      全部在 <span class="tag tag-k">K</span> <code>~/knetsentinel</code> 下执行，Python 环境是 <code>~/knetsentinel/.venv</code>（<code>cd ~/knetsentinel &amp;&amp; uv sync</code> 生成，依赖 scapy、confluent-kafka、aiohttp、websockets、python-dotenv）。</div>

    <section id="principle">
      <h2>6.1 发包原理：为什么能“伪造源 IP”</h2>
      <p>宿主机在网桥 virbr-k8s 上本来只有 <code>192.168.100.1</code>。发包脚本先用 <code>ip addr add 192.168.100.23/24 dev virbr-k8s</code> 把要伪造的地址临时加到网桥上，再用 scapy 构造 <code>IP(src=.23, dst=.11)</code> 的包从网桥发出。因为和 VM 在同一个二层网络，回包能找回来，Cilium/Hubble 看到的就是原始源 IP。发完再 <code>ip addr del</code>。</p>
      <ul>
        <li>需要 root（加地址、原始套接字），所以用 <code>sudo .venv/bin/python3 ...</code>（不能 <code>sudo uv run</code>，root 环境里通常没有 uv）。</li>
        <li>脚本被 <span class="kbd">Ctrl</span>+<span class="kbd">C</span> 或 kill 中断时可能来不及删地址。检查：<code>ip -4 addr show virbr-k8s</code>，应只有 <code>.1/24</code>。</li>
        <li>清理 .16-.29：<code>sudo .venv/bin/python3 traffic/handle_addr.py --action delete</code>。<b>它不管 .50-.64 和 .170-.184</b>，这些要手动：<code>for i in $(seq 50 64); do sudo ip addr del 192.168.100.$i/24 dev virbr-k8s 2&gt;/dev/null; done</code>。</li>
        <li>要让 Hubble 看到发往节点本身（而不是 Pod）的包，集群里需有 <code>host-firewall-ccnp.yaml</code>（<a href="/help/infra">《集群与 Shell 脚本》</a> 5.9）。</li>
      </ul>
    </section>

    <section id="traffic">
      <h2>6.2 traffic/：发包</h2>
      <div class="table-wrap"><table>
        <tr><th>脚本</th><th>源 IP → 目标</th><th>流量内容</th><th>参数</th></tr>
        <tr><td><code>spoof_attack.py</code></td><td>.20-.29 → master:6443、node1-4:80</td><td>TCP SYN flood（固定 sport 12345）。每“轮”把 10 源 × 5 目标 = 50 个组合打乱各发 1 包</td><td><code>--packets N</code>：轮数（默认 25000），总包数 = N × 50</td></tr>
        <tr><td><code>send_normal_scapy.py</code></td><td>.50-.64 → 5 个节点</td><td>混合：TCP SYN 到 80/443/22/6443、DNS 查询、NTP、syslog、ICMP echo、TCP ACK</td><td><code>--packets N</code>：轮数，每轮 15 × 5 个包</td></tr>
        <tr><td><code>send_request.py</code></td><td>.50-.64 → my-nginx .204:80</td><td>真实 <code>curl --interface</code> HTTP 请求（完整 TCP 握手）</td><td><code>--repeat N</code>（默认 1）、<code>--delay 秒</code>（默认 0.05）</td></tr>
        <tr><td><code>run_traffic_only.sh</code></td><td>以上两者</td><td>先 <code>send_normal_scapy.py</code> 再 <code>spoof_attack.py</code></td><td><code>--normal-repeat N</code>（默认 1000）、<code>--attack-packets N</code>（默认 25000）</td></tr>
        <tr><td><code>handle_addr.py</code></td><td>—</td><td>批量加 / 删 .16-.29</td><td><code>--action add|delete</code></td></tr>
      </table></div>
<pre><code>cd ~/knetsentinel
sudo .venv/bin/python3 traffic/spoof_attack.py --packets 200          <span class="c"># 1 万个攻击包，约 1 分钟</span>
sudo .venv/bin/python3 traffic/send_request.py --repeat 10 --delay 0.5
sudo bash traffic/run_traffic_only.sh --normal-repeat 5 --attack-packets 200</code></pre>
      <p>预期：网页 <b>AI Vigil → Detection Log</b> 15 秒内出现对应源 IP 的记录；攻击流 Ground Truth = 1，正常流 = 0。</p>
    </section>

    <section id="kafka">
      <h2>6.3 kafka/：直接看 Kafka 里的事件</h2>
      <div class="table-wrap"><table>
        <tr><th>脚本</th><th>用途</th><th>常用参数</th></tr>
        <tr><td><code>kafka_read.py</code></td><td>实时打印 Hubble 事件（人读的格式），带过滤</td><td><code>--src</code>/<code>--dst</code> IP 前缀、<code>--protocol</code>、<code>--verdict</code>、<code>--direction</code>、<code>--src-ns</code>/<code>--dst-ns</code>/<code>--src-pod</code>/<code>--dst-pod</code>、<code>--node</code>、<code>--drop-only</code>、<code>--from-beginning</code>、<code>-n N</code></td></tr>
        <tr><td><code>kafka_read_csv.py</code></td><td>把事件写成带标签 CSV（按源 IP 打标签）</td><td><code>-o 文件</code>、<code>--max-attack</code>、<code>--max-normal</code>、<code>--from-beginning</code>、<code>-n</code></td></tr>
        <tr><td><code>vigil_bridge.py</code></td><td>入口 C（<a href="/help/detect">《检测链路与模型》</a> 4.10）</td><td><code>--backend</code>、<code>--token</code>、<code>--window</code>、<code>--batch-size</code>、<code>--from-beginning</code></td></tr>
        <tr><td><code>run_kafka_read.sh</code></td><td>跑 <code>kafka_read.py</code> 并追加日志到 <code>kafka_read_result.log</code></td><td></td></tr>
        <tr><td><code>run_spoof_capture.sh</code></td><td>边发攻击边抓，输出 <code>spoof_attack_captured.log</code></td><td></td></tr>
      </table></div>
<pre><code>cd ~/knetsentinel
uv run python kafka/kafka_read.py --src 192.168.100.2 -n 20     <span class="c"># 看 20 条攻击源发出的事件</span></code></pre>
      <p>这些脚本从 <code>~/knetsentinel/.env</code> 读 Kafka 外部地址（03 脚本生成）。<code>GROUP_ID=ebpf-log-consumer-group</code>，与后端的 <code>vigil-bridge</code> 互不影响。</p>
    </section>

    <section id="dataset">
      <h2>6.4 dataset/：采集训练数据</h2>
      <h3>一键采集 <code>run_dataset_collection.sh</code></h3>
      <ol>
        <li>以普通用户身份后台启动 <code>dataset_collector.py</code>（它通过 <code>kubectl exec kafka-broker-0 -- kafka-console-consumer.sh</code> 读 Kafka，需要用户的 kubeconfig，所以不能是 root）。只保留源 IP 在 .20-.29（label=1）和 .50-.64（label=0）的事件，每个事件一行，11 个字段：<code>timestamp, verdict, direction, summary, src_ip, dst_ip, protocol, src_port, dst_port, tcp_flags, is_reply, label</code>。</li>
        <li>等 CSV 表头出现（消费者已连上）。</li>
        <li><code>send_request.py --repeat 1000 --delay 0.02</code> 发正常流量。</li>
        <li><code>spoof_attack.py</code>（默认 25000 轮）发攻击。</li>
        <li>等 20 秒让 Kafka 消费追上，停止采集器。目标数：攻击 16 万、正常 5 万（达到即自动停）。</li>
      </ol>
<pre><code>cd ~/knetsentinel
sudo bash dataset/run_dataset_collection.sh dataset/new.csv
wc -l dataset/new.csv</code></pre>
      <h3>聚合成流特征 <code>aggregate_flows.py</code></h3>
<pre><code>uv run python dataset/aggregate_flows.py -i dataset/new.csv -o flows_new.csv -t 5</code></pre>
      <p>按 5 元组分组，同一流相邻包间隔超过 <code>-t</code> 秒（默认 5）就切成新流，然后算与 <code>bridge.py compute_flow()</code> 同名的特征。输出就是模型训练用的格式（<code>flows.csv</code>、<code>flows_30.csv</code> 都是这样来的）。特征定义见 <code>~/knetsentinel/docs/features.md</code>。</p>
      <p><code>test_50_packets.sh</code>：发 50 个包的小规模冒烟测试。<code>dataset.csv</code>、<code>dataset_v1.csv</code> 是历史采集结果，<b>不在 Git 中，别删</b>。</p>
    </section>

    <section id="replay">
      <h2>6.5 traffic_request/：用公开数据集重放流量</h2>
      <p>把一个外部数据集（<code>test set_20000(1).csv</code>，约 2 万条流）按 <code>ip_mapping.json</code> 把原始 IP 映射到 .50-.64 → .10-.14，用 scapy 逐流重放，同时从 Kafka 采回 Hubble 看到的结果，用于对比“原始特征”和“我们管道算出的特征”。</p>
<pre><code>cd ~/knetsentinel/traffic_request
sudo bash scripts/start_send.sh [--max-packets 10]   <span class="c"># 终端 1，nohup 后台，写 send.pid、send.log，结束写 send.done</span>
bash scripts/start_read.sh                           <span class="c"># 终端 2，等 send.pid 出现后开始读，看到 send.done 再排水 15 秒退出</span>
tail -f send.log read.log</code></pre>
      <p>输出：<code>record_send_uuid.txt</code>（每条流的发送记录 JSONL）、<code>read_result.csv</code>（采集结果，label 固定 0）、<code>joined_result.csv</code>（<code>scripts/aggregate.py</code> 对齐后的结果）。详细说明见该目录的 <code>README.md</code>。</p>
    </section>

    <section id="sim">
      <h2>6.6 simulation/：端到端仿真与离线评估</h2>
      <div class="table-wrap"><table>
        <tr><th>脚本</th><th>做什么</th></tr>
        <tr><td><code>simulate_1.py</code></td><td>正常流量 90 秒：源 .50-.59，50 个并发 worker，用 curl / nc 访问靶机 http-api .210:8080、mysql .211:3306、ftp .212:21、udp .213:9999、dns .214:53</td></tr>
        <tr><td><code>simulate_2.py</code></td><td>混合 90 秒：正常 30 并发（.50-.59）+ 攻击 20 并发（.170-.184）</td></tr>
        <tr><td><code>simulate_3.py</code></td><td>全攻击 90 秒：9 种攻击——DoS SYN、DoS GET、DDoS SYN、TCP 序列预测、Slowloris、Slow-body、Slow-read、Slow-range、凭证劫持（暴力 POST）</td></tr>
        <tr><td><code>simulate_4.py</code></td><td><b>离线</b>：读 <code>simulate4.csv</code>（预聚合的特征），每 200 条调用一次 <code>vigil.services.detect_batch()</code>，不经过 Kafka。它通过 <code>sys.path</code> 导入 <span class="tag tag-n">N</span> 后端代码，路径写死 <code>../../github/NetSentinel/backend</code></td></tr>
        <tr><td><code>gen_simulate4_csv.py</code></td><td>生成 <code>simulate4.csv</code></td></tr>
        <tr><td><code>run.sh 1|2|3</code></td><td>先后台启动 <code>monitor/monitor.py --mode N</code>，2 秒后跑 <code>simulate_N.py</code>（输出到 <code>monitor/send.log</code>），等 monitor 生成报告</td></tr>
        <tr><td><code>monitor/monitor.py</code></td><td>连 <code>ws://localhost:8080/ws/vigil/</code> 收检测结果，与 send.log 对比，输出 <code>monitor_report_N.txt</code>、<code>monitor_detail_N.csv</code></td></tr>
      </table></div>
      <div class="danger">后端<b>没有</b> <code>ws/vigil/</code> 这个路由（只有 <code>ws/detector/push/</code> 和 Pod 日志），所以 <code>run.sh</code> 的 monitor 目前连不上、拿不到结果。评估改用 SQL 或 REST：<br>
        <code>docker exec pg psql -U vigil vigil -c "select src_ip, is_attack, attack_type, count(*) from vigil_detectionrecord where created_at &gt; now() - interval '5 min' group by 1,2,3 order by 4 desc;"</code></div>
<pre class="on-dev"><code><span class="c"># 在线仿真（结果用上面的 SQL 看）</span>
cd ~/knetsentinel &amp;&amp; sudo .venv/bin/python3 simulation/simulate_3.py

<span class="c"># 离线评估：必须用 NetSentinel 的 venv，因为要导入 Django 和模型</span>
cd ~/knetsentinel/simulation &amp;&amp; <span class="vn">~/github/NetSentinel</span>/.venv/bin/python simulate_4.py</code></pre>
      <p>注意 .170-.184 不在 bridge 的标签规则里，仿真流量的 label 为空，算准确率时要用源 IP 自己判断。</p>
    </section>

    <section id="eval">
      <h2>6.7 评估常用 SQL</h2>
<pre><code>docker exec -it pg psql -U vigil vigil

<span class="c">-- 最近 10 分钟：按真实标签 × 预测的混淆矩阵</span>
select label, is_attack, count(*) from vigil_detectionrecord
 where created_at &gt; now() - interval '10 min' and label is not null group by 1,2 order by 1,2;

<span class="c">-- 攻击类型分布</span>
select attack_type, count(*) from vigil_detectionrecord
 where is_attack and created_at &gt; now() - interval '1 hour' group by 1 order by 2 desc;

<span class="c">-- 推理耗时</span>
select avg((raw_output-&gt;&gt;'inference_ms')::float), max((raw_output-&gt;&gt;'inference_ms')::float)
  from vigil_detectionrecord where created_at &gt; now() - interval '10 min';

<span class="c">-- 导出某天 CSV</span>
\copy (select * from vigil_detectionrecord_2026_10_18) to '/tmp/d.csv' csv header</code></pre>
      <p>（最后一条在容器里写 <code>/tmp</code>，取出：<code>docker cp pg:/tmp/d.csv .</code>。）</p>
    </section>
  </div>
</template>

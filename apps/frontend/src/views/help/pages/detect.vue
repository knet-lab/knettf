<template>
  <div v-pre>
        <h1>4 检测链路与模型</h1>
    <div class="meta">读完你能：讲清楚一条 Hubble 事件怎样变成数据库里的一条检测记录；知道 35 个特征各是什么、怎么算的；读懂模型的四个步骤；会换模型、加模型、排查“没有新数据”。<br>
      涉及文件：<span class="tag tag-n">N</span> <code>apps/backend/vigil/</code>、<code>detector/</code>；<span class="tag tag-k">K</span> <code>lab/manifests/vector-5nodes.yaml</code>、<code>lab/collect/vigil_bridge.py</code>、<code>dataset/aggregate_flows.py</code>。</div>

    <section id="event">
      <h2>4.1 起点：一条 Hubble flow 事件</h2>
      <p>Cilium 在每个节点用 eBPF 观察包，Hubble 把每个包（准确说是每个被观测到的转发 / 丢弃事件）输出成一条 JSON。Vector 在每个节点执行：</p>
<pre><code>hubble observe --follow --output=json --server=hubble-relay.kube-system.svc.cluster.local:4245</code></pre>
      <p>每行输出经 <code>parse_json</code> 后原样写入 Kafka topic <code>ebpf-net-logs</code>（批 500 条或 1 秒，内存缓冲 5 万条，满了丢最新）。后端只用到其中这些字段：</p>
<pre><code>{
  "flow": {
    "time": "2026-10-18T03:12:45.123456789Z",
    "verdict": "FORWARDED",                      <span class="c">// 或 DROPPED 等</span>
    "IP": { "source": "192.168.100.23", "destination": "192.168.100.11" },
    "l4": { "TCP": { "source_port": 12345, "destination_port": 80,
                     "flags": { "SYN": true } } },  <span class="c">// 也可能是 UDP / ICMPv4 / ICMPv6</span>
    "traffic_direction": "INGRESS",              <span class="c">// 或 EGRESS</span>
    "is_reply": false
  }
}</code></pre>
      <p>Hubble 版本升级后要先确认这些字段名没变（<a href="/help/index#contract">系统总览 · 跨项目契约</a>）。</p>
    </section>

    <section id="entries">
      <h2>4.2 三个入口</h2>
      <p>把 Kafka 里的事件变成检测记录有三种方式，<b>同一时间只能开一种</b>，否则同一条流会被记录多次。</p>
      <div class="table-wrap"><table>
        <tr><th></th><th>入口 A（默认，在用）</th><th>入口 B（可选）</th><th>入口 C（可选）</th></tr>
        <tr><td>代码</td><td><span class="tag tag-n">N</span> <code>apps/backend/vigil/bridge.py</code></td><td><span class="tag tag-n">N</span> <code>detector/detector.py</code>（镜像 <code>soar009/netsentinel-detector</code>）</td><td><span class="tag tag-k">K</span> <code>lab/collect/vigil_bridge.py</code></td></tr>
        <tr><td>在哪运行</td><td>后端进程内的两个线程</td><td>集群内 Pod（命名空间 <code>netsentinel</code>）</td><td>宿主机上手动运行的脚本</td></tr>
        <tr><td>Kafka group</td><td><code>vigil-bridge</code>，从 latest 开始</td><td><code>vigil-detector</code></td><td>脚本参数</td></tr>
        <tr><td>聚合方式</td><td>每次 poll 到的一批消息立即聚合</td><td>累计 <code>PKT_BATCH_SIZE</code>（默认 1 万）个包后聚合</td><td>按 5 元组维护状态，<code>--window</code> 秒无新包则结束这条流</td></tr>
        <tr><td>在哪推理</td><td>后端 <code>services.detect_batch()</code></td><td>Pod 内自带的推理代码（与 A 的算法<b>不完全相同</b>，见 <a href="#entryb">入口 B</a>）</td><td>后端 <code>POST /api/vigil/detect/batch/</code></td></tr>
        <tr><td>怎么写库</td><td>直接 ORM</td><td>WebSocket <code>ws/detector/push/</code> 推结果，后端 <code>_save_results()</code> 写库</td><td>经 REST 接口</td></tr>
        <tr><td>认证</td><td>—</td><td><code>Authorization: Bearer &lt;VIGIL_BRIDGE_TOKEN&gt;</code>，与 settings 字符串全等比较</td><td>JWT（<code>--token</code>）</td></tr>
        <tr><td>开关</td><td>没有开关；要关需注释 <code>vigil/apps.py</code> 里的 <code>bridge.start()</code></td><td>部署 / 删除 Deployment</td><td>运行 / 停止脚本</td></tr>
      </table></div>
    </section>

    <section id="bridge">
      <h2>4.3 入口 A 逐行：bridge.py</h2>
      <h3>常量</h3>
<pre><code>KAFKA_BOOTSTRAP = "192.168.100.200:9094,...201,...202,...203:9094"   <span class="c"># 写死，MetalLB 地址变了要改这里</span>
KAFKA_TOPIC     = "ebpf-net-logs"
KAFKA_GROUP_ID  = "vigil-bridge"
CONSUME_BATCH   = 10000            <span class="c"># 每次最多取的消息数</span>
_NODE_IPS    = .10 ~ .15           <span class="c"># 节点</span>
_METALLB_IPS = .200 ~ .250         <span class="c"># LoadBalancer</span>
_KAFKA_PORTS = {9092, 9093, 9094}
_HOST_GW     = 192.168.100.1</code></pre>
      <h3>线程一：<code>run_bridge()</code></h3>
      <ol>
        <li>建 confluent-kafka <code>Consumer</code>：<code>auto.offset.reset=latest</code>（新 group 只读启动后的新消息）、<code>enable.auto.commit=False</code>（手动提交）、<code>session.timeout.ms=6000</code>。</li>
        <li>循环 <code>consume(num_messages=10000, timeout=0.1)</code>。</li>
        <li>对每条消息过滤：
          <ul>
            <li>源或目的 IP 为空 → 跳过</li>
            <li><b>源和目的都是基础设施</b>（<code>10.*</code> Pod 网段、节点、MetalLB、宿主机网关）→ 跳过（集群内部互相通信不检测）</li>
            <li>任一端口是 Kafka 端口 → 跳过（否则 bridge 自己消费 Kafka 的流量会被检测，形成反馈环）</li>
          </ul></li>
        <li>通过的按 <code>_flow_key()</code>（5 元组）放进 <code>open_flows[key]</code>，每个包用 <code>_hubble_to_packet()</code> 转成 <code>{ts, direction, verdict, flags, is_reply, label, 5 元组}</code>。<b>标签规则</b>：源 IP 末段 20-29 → <code>"1"</code>，50-64 → <code>"0"</code>，其他 → <code>""</code>。</li>
        <li>本轮只要有数据就 <code>_flush()</code>：每个 key 调 <code>compute_flow(pkts)</code> 得到一条流，附上 <code>aggregation_ms</code>，整批 <code>flow_queue.put_nowait(batch)</code>，然后异步提交 offset。队列满（2000 批）→ 丢弃该批并打 warning。</li>
        <li>任何异常 → 日志 <code>bridge error: ...</code>，<b>线程退出，不重连</b>。这是“检测停了”的头号原因：集群重启或 Kafka 中断后必须重启后端。</li>
      </ol>
      <div class="learn"><b>理解“流”的边界</b>：入口 A 没有时间窗口，每次 poll（最多等 0.1 秒）拿到的包就聚合一次。一个持续 10 秒的连接会被切成很多条“流”记录，每条只包含那一小段时间里的包。所以 <code>flow_duration</code> 一般很短，<code>total_packets</code> 一般很少。训练数据（<code>dataset/aggregate_flows.py</code>，5 秒超时）的切法不同，这会影响模型效果。</div>
      <h3>线程二：<code>run_drainer()</code></h3>
<pre><code>while True:
    batch = flow_queue.get()                    <span class="c"># 阻塞等待</span>
    close_old_connections()                     <span class="c"># 防止长时间空闲后数据库连接失效</span>
    results = services.detect_batch(batch)      <span class="c"># 推理 + 写库</span>
    logger.info("queue: %d flows → %d attack(s)", ...)
    <span class="c"># 异常 → "drainer failed on batch of N flows"，丢弃这一批，继续下一批</span></code></pre>
      <p><code>start()</code> 用全局 <code>_started</code> + 锁保证只启动一次，两个都是 daemon 线程（进程退出时直接结束）。</p>
    </section>

    <section id="features">
      <h2>4.4 35 个特征：<code>compute_flow()</code></h2>
      <p>一条流 = 同 5 元组的若干包，按 <code>ts</code> 排序后计算。<code>duration = max(最后 ts − 第一个 ts, 1e-6)</code>，<code>iats</code> = 相邻包时间差。</p>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>特征</th><th>类型</th><th>计算</th></tr>
        <tr><td>1-2</td><td><code>src_ip</code>、<code>dst_ip</code></td><td>字符串</td><td>第一个包的源 / 目的 IP。模型里用 OrdinalEncoder 编码（训练时没见过的 IP 编成未知值）</td></tr>
        <tr><td>3-4</td><td><code>src_port</code>、<code>dst_port</code></td><td>int</td><td>TCP / UDP 端口，ICMP 为 0</td></tr>
        <tr><td>5</td><td><code>protocol</code></td><td>字符串</td><td>TCP / UDP / ICMPv4 / ICMPv6 / OTHER，也被编码</td></tr>
        <tr><td>6</td><td><code>flow_duration</code></td><td>秒</td><td>见上</td></tr>
        <tr><td>7</td><td><code>total_packets</code></td><td>int</td><td>包数</td></tr>
        <tr><td>8-9</td><td><code>fwd_packets</code>、<code>bwd_packets</code></td><td>int</td><td><code>traffic_direction == INGRESS</code> 的算 fwd，其余 bwd</td></tr>
        <tr><td>10</td><td><code>fwd_ratio</code></td><td>0-1</td><td>fwd / total</td></tr>
        <tr><td>11</td><td><code>packets_per_second</code></td><td></td><td>total / duration（单包流会非常大：1 / 1e-6）</td></tr>
        <tr><td>12-15</td><td><code>iat_mean / std / min / max</code></td><td>秒</td><td>包间隔统计，单包流全为 0</td></tr>
        <tr><td>16-21</td><td><code>syn / ack / fin / rst / psh / urg_count</code></td><td>int</td><td>TCP flags 中该位为真的包数</td></tr>
        <tr><td>22-25</td><td><code>syn / ack / fin / rst_ratio</code></td><td>0-1</td><td>对应 count / total</td></tr>
        <tr><td>26-27</td><td><code>reply_count</code>、<code>reply_ratio</code></td><td></td><td><code>is_reply</code> 为真的包</td></tr>
        <tr><td>28-30</td><td><code>forwarded_count</code>、<code>drop_count</code>、<code>drop_ratio</code></td><td></td><td>verdict == FORWARDED 的算转发，其余算丢弃</td></tr>
        <tr><td>31</td><td><code>is_bidirectional</code></td><td>0/1</td><td>包里出现过两种方向</td></tr>
        <tr><td>32-34</td><td><code>is_tcp</code>、<code>is_udp</code>、<code>is_icmp</code></td><td>0/1</td><td>协议独热</td></tr>
        <tr><td>35</td><td><code>is_well_known_port</code></td><td>0/1</td><td>dst_port &lt; 1024</td></tr>
        <tr><td>—</td><td><code>label</code></td><td>"0"/"1"/""</td><td>包标签的众数，<b>不送进模型</b>，只存库用于评估</td></tr>
      </table></div>
      <div class="danger"><b>五处必须同步</b>：这 35 个名字和含义在以下位置各写了一遍，改任何一处都要改其他四处：<br>
        ① <code>bridge.py compute_flow()</code> ② <code>ml/models/base.py DetectionInput</code> ③ <code>ml/models/runner.py flow_from_dict()</code>（int / float 字段集合）④ <code>serializers.py FlowInputSerializer</code> ⑤ <code>ml/ads_ml/main.py main()</code> 的参数表。<br>
        还有 <span class="tag tag-k">K</span> 侧的 <code>dataset/aggregate_flows.py</code>、<code>lab/collect/vigil_bridge.py</code> 和 <code>detector/detector.py</code>，以及训练流水线里的 <code>ebpf_35_features</code>。</div>
    </section>

    <section id="service">
      <h2>4.5 服务层：<code>services.detect_flow()</code></h2>
<pre><code>def detect_flow(flow_data):
    model_name     = flow_data.pop("model", None)            <span class="c"># 可选：只用某个模型</span>
    aggregation_ms = flow_data.pop("aggregation_ms", None)
    flow = flow_from_dict(flow_data)                          <span class="c"># dict → DetectionInput，按字段集合转 int/float</span>
    results = [run_one(model_name, flow)] if model_name else run_all(flow)   <span class="c"># 每个注册的模型跑一遍</span>
    inference_ms = ...
    if not flow.src_ip or not flow.dst_ip: return []
    for result in results:
        action = policy_for_result(result, flow_meta)         <span class="c"># 决定 drop/rate_limit/alert/ignore</span>
        apply_action(action)                                  <span class="c"># stub：只打日志 [CILIUM STUB]</span>
        DetectionRecord.objects.create(...)                   <span class="c"># 写 PostgreSQL</span>
    return [...]

def detect_batch(flows, model_name=None):
    with transaction.atomic():      <span class="c"># 注意：这是 default 库的事务，vigil 库的写入不在其中</span>
        for d in flows: results.extend(detect_flow(d))</code></pre>
      <p><code>get_stats()</code>：<code>count()</code> 全表、攻击数、按 <code>attack_type</code> 分组、按 <code>model_name</code> 分组、最近 10 条。<code>list_models()</code>：注册表里的名字。</p>
    </section>

    <section id="model">
      <h2>4.6 模型：ads_ml（OCSVM + 余弦复核 + 零样本学习）</h2>
      <h3>文件</h3>
      <p>代码（<code>main.py</code>、<code>utils/</code>）在 <code>apps/backend/vigil/ml/ads_ml/</code>；线上用的模型文件在版本目录 <code class="vp">/srv/netsentinel/models/ads_ml/current</code>（见 <a href="#newmodel">4.11</a>），表里的 <code>trained/</code> 指那里的文件。</p>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>内容</th></tr>
        <tr><td><code>config.yaml</code></td><td>三个模型文件的路径（相对 config.yaml 所在目录）</td></tr>
        <tr><td><code>trained/ebpf_ocsvm_pipeline.joblib</code></td><td>一个 dict：<code>encoder</code>（OrdinalEncoder）、<code>scaler</code>、<code>use_pca</code>、<code>pca</code>、<code>detector</code>（OneClassSVM）、<code>ebpf_35_features</code>、<code>encode_columns</code>、<code>numeric_columns</code>、<code>encoded_columns</code>、<code>constant_cols</code>、<code>log_features</code>、<code>clip_ranges</code>、<code>selected_features</code></td></tr>
        <tr><td><code>trained/multi_attack_semantic_prototypes_kmeans.joblib</code></td><td>攻击原型：<code>{攻击名: {"prototypes": [{"vector": ndarray}, ...]}}</code>，每类若干 KMeans 中心</td></tr>
        <tr><td><code>trained/step_10_final_train_data.csv</code></td><td>训练集（PCA 后），用于余弦复核</td></tr>
        <tr><td><code>main.py</code></td><td><code>_load_resources(config_path)</code> 读上面三个文件；<code>main()</code> 是单独运行时的入口，后端不调用</td></tr>
        <tr><td><code>utils/data_preprocessing.py</code> · <code>anomaly_detection.py</code> · <code>zero_shot_learning.py</code> · <code>cloud_reporting.py</code></td><td>四个步骤</td></tr>
      </table></div>
      <h3>四个步骤</h3>
      <div class="steps">
        <div class="step"><div class="step-title">预处理 <code>preprocess_data(data, pipeline)</code></div>
          <p>补齐缺失特征为 0 → 拆分类别列和数值列 → 类别列 <code>encoder.transform</code>，数值列转数字、inf/NaN → 0 → 拼接 → 去掉训练时的常量列 → <code>log_features</code> 做 <code>log1p</code> → 按 <code>clip_ranges</code> 截断 → 按 <code>selected_features</code> 重排 → <code>scaler.transform</code> → <code>pca.transform</code>。输出 <code>X_pca</code>。</p></div>
        <div class="step"><div class="step-title">异常检测 <code>ad(X_pca, ocsvm, X_train)</code></div>
          <p><code>ocsvm.predict</code>：-1 → 攻击（1），+1 → 正常（0）。再算 <code>decision_function</code> 的 sigmoid 得到正常分和异常分，两者差 &lt; <code>REVIEW_THRESHOLD=0.10</code> 时视为“拿不准”，进入<b>余弦复核</b>：与训练集所有样本算余弦相似度，取最高 5 个的均值；≥ 0.95 改判正常，≤ 0.90 改判攻击，中间维持原判。</p></div>
        <div class="step"><div class="step-title">零样本学习 <code>zero_shot_learning(X_pca, prediction, prototypes)</code></div>
          <p>正常样本：<code>Normal</code>，相似度 0。攻击样本：与每个攻击类别的每个原型算余弦相似度，取最高的；≥ <code>SEEN_SIM_THRESHOLD=0.50</code> 则为该类（<code>Seen_Attack</code>），否则 <code>Unknown_Attack</code>。</p>
          <p>当前原型里的类别名就是前端日志页写死的 9 个：<code>Dos-TCP SYN flood</code>、<code>ddos-TCP SYN flood</code>、<code>DoS Get</code>、<code>TCP sequence prediction</code>、<code>Slowloris</code>、<code>Slow-body</code>、<code>Slow-read</code>、<code>Slow-range</code>、<code>Credentials hijacking</code>。查看实际名字：</p>
<pre class="on-prod"><code>cd <span class="vp">/srv/netsentinel/prod</span>/backend &amp;&amp; ../.venv/bin/python -c "import joblib;print(list(joblib.load('vigil/ml/ads_ml/trained/multi_attack_semantic_prototypes_kmeans.joblib')))"</code></pre></div>
      </div>
      <h3>模型怎么接入后端</h3>
      <p>后端不直接认识 ads_ml，只认接口 <code>BaseDetectionModel</code>：一个模型就是一个实现了 <code>name</code> 和 <code>predict()</code> 的类。启动时注册表按 <code>.env</code> 的 <code>VIGIL_MODELS</code>（类的完整路径，逗号分隔，默认只有 <code>AdsMLModel</code>）逐个实例化；服务层对每条流调用全部已注册模型，每个模型的结果各写一条记录。这样换模型、加模型都不用改 bridge、服务层和数据库。</p>
<pre class="uml">classDiagram
  direction LR
  class BaseDetectionModel {
    &lt;&lt;abstract&gt;&gt;
    +name str
    +predict(flow DetectionInput) DetectionResult
    +predict_batch(flows) list~DetectionResult~
  }
  class AdsMLModel {
    +name = "ads_ml_ocsvm"
    +config_path Path
    -_pipeline
    -_prototypes
    -_X_train
    +attack_types list~str~
  }
  class ThresholdModel {
    +name = "threshold_v1"
  }
  class ModelRegistry {
    +register(model)
    +get(name) BaseDetectionModel
    +list_models() list~str~
  }
  class DetectionInput {
    src_ip, dst_ip, protocol
    35 个流特征
    label
  }
  class DetectionResult {
    model_name str
    is_attack bool
    confidence float 0~1
    attack_type str or None
    raw_output dict
    explanation str
    recommended_action
  }
  BaseDetectionModel <|-- AdsMLModel
  BaseDetectionModel <|-- ThresholdModel
  ModelRegistry o-- BaseDetectionModel : VIGIL_MODELS
  BaseDetectionModel ..> DetectionInput : 输入
  BaseDetectionModel ..> DetectionResult : 输出</pre>
<ol>
        <li><b>启动时</b>：导入 <code>vigil/ml/models/registry.py</code>，按 <code>VIGIL_MODELS</code> 逐个 <code>import_string(类路径)()</code>。</li>
        <li><b>AdsMLModel 构造</b>：把 <code>VIGIL_ADS_ML_CONFIG</code>（<code>/srv/netsentinel/models/ads_ml/current/config.yaml</code>）解析成实际版本目录，读 <code>config.yaml</code> 和 <code>trained/</code> 下三个文件，留在内存里。失败只记 <code>model ... not loaded</code>，后端照常启动。</li>
        <li><b>每批流</b>：drainer 调 <code>services.detect_batch()</code> → 对每条流 <code>run_all()</code>，每个已注册模型 <code>predict()</code> 一次，返回 <code>DetectionResult</code>。</li>
        <li><b>写库</b>：<code>policy_for_result()</code> 给出建议动作，每个模型的结果各 INSERT 一条到 <code>vigil_detectionrecord</code>。</li>
      </ol>
      <ul>
        <li><b>只加载一次</b>：<code>AdsMLModel</code> 在构造时读完模型文件并留在内存里，之后每条流直接做预处理 → OCSVM → 零样本三步，不再读文件。</li>
        <li><b>版本切换需要重启</b>：构造时把 <code>current</code> 软链接解析成实际目录，所以改软链接不会影响正在运行的进程，重启后才换成新版本。替换到一半的文件也不会被读到。</li>
        <li><b>加载失败不拖垮后端</b>：某个模型构造失败只记 warning，后端照常启动，只是没有它的检测结果（看板 Detection model 为空）。</li>
      </ul>
    </section>

    <section id="policy">
      <h2>4.7 Cilium 反馈：<code>ml/cilium/policy.py</code></h2>
<pre><code>if not result.is_attack or result.confidence &lt; 0.6:  action = "ignore"
else: action = _ATTACK_TYPE_POLICY.get(attack_type or "anomaly", "alert")
_ATTACK_TYPE_POLICY = {"syn_flood": "drop", "flood": "rate_limit", "port_scan": "alert", "anomaly": "alert"}</code></pre>
      <p>注意映射表的键是 <code>syn_flood</code> 这种名字，而模型实际输出的是 <code>Dos-TCP SYN flood</code> 这种，<b>匹配不上</b>，所以实际只会出现 <code>ignore</code> 和 <code>alert</code>。<code>apply_action()</code> 只打 <code>[CILIUM STUB]</code> 日志；文件里留了 <code>_build_cnp_yaml()</code> 生成 <code>CiliumNetworkPolicy</code>（<code>ingressDeny fromCIDRSet src/32</code>）的草稿和用 kubectl apply 的注释代码，要真正封禁从这里接。</p>
    </section>

    <section id="storage">
      <h2>4.8 存储：按天分区的 PostgreSQL 表</h2>
      <ul>
        <li>父表 <code>vigil_detectionrecord</code>，<code>PARTITION BY RANGE (created_at)</code>，主键 <code>(id, created_at)</code>（分区表要求主键包含分区键）。</li>
        <li>子表 <code>vigil_detectionrecord_YYYY_MM_DD</code>，每个覆盖 [当天 00:00 UTC, 次日 00:00 UTC)。</li>
        <li>迁移时预建 91 个（过去 89 天 + 今天 + 明天）；之后每天 0 点由 <code>/etc/cron.d/netsentinel</code> 跑 <code>rotate_partitions</code>：建明天的，删 90 天前那天往前 7 天内的。</li>
        <li>索引建在父表上，自动继承：<code>is_attack</code>、<code>model_name</code>、<code>created_at DESC</code>。</li>
        <li><b>没有对应分区时插入会失败</b>（<code>no partition of relation ... found for row</code>），drainer 丢弃整批。定时任务漏跑一天就会出现。</li>
        <li><code>DetectionRecord</code> 模型 <code>managed=False</code>，Django 不会为它生成迁移。</li>
      </ul>
<pre><code><span class="c"># 有哪些分区、各多少行</span>
docker exec pg psql -U vigil vigil -c "select relname, n_live_tup from pg_stat_user_tables where relname like 'vigil_detectionrecord_%' order by relname desc limit 5;"
<span class="c"># 手动建某天分区</span>
docker exec pg psql -U vigil vigil -c "create table if not exists vigil_detectionrecord_2026_10_19 partition of vigil_detectionrecord for values from ('2026-10-19') to ('2026-10-20');"</code></pre>
    </section>

    <section id="entryb">
      <h2>4.9 入口 B：集群内检测器</h2>
      <h3>构建：<code>detector/build.sh</code></h3>
      <ol>
        <li><code>rsync -a --delete</code> 把 <code>apps/backend/vigil/ml/ads_ml/</code>（排除 <code>__pycache__</code>、<code>results/</code>）同步到 <code>detector/ads_ml/</code>。</li>
        <li><code>docker build -t soar009/netsentinel-detector:latest</code>：基于 <code>python:3.12-slim</code>，用 uv 装 <code>requirements.txt</code>，复制 <code>config.yaml</code>、<code>trained/</code>、<code>utils/</code>、<code>detector.py</code>。</li>
        <li><code>docker push</code> 到 Docker Hub（需已 <code>docker login</code>）。</li>
      </ol>
      <h3>部署清单：<span class="tag tag-k">K</span> <code>detector/detector-deployment.yaml</code></h3>
      <ul>
        <li>Namespace <code>netsentinel</code>；ConfigMap <code>detector-config</code>（<code>KAFKA_BOOTSTRAP</code>、<code>CONSUME_TOPIC</code>、<code>GROUP_ID=vigil-detector</code>、<code>DJANGO_WS_URL=ws://knettf.com:8080/ws/detector/push/</code>，以及 <code>FLOW_TIMEOUT_SEC</code>、<code>BATCH_SIZE</code>——这两个 <code>detector.py</code> 不读）。</li>
        <li><code>hostAliases</code> 把 <code>knettf.com</code> 解析成 <code>192.168.100.1</code>（宿主机），所以 Pod 连的是宿主机 8080，而不是公网。</li>
        <li>Secret <code>detector-secret</code> 的 key <code>django-token</code> → 环境变量 <code>DJANGO_TOKEN</code>，值必须等于后端 <code>.env</code> 的 <code>VIGIL_BRIDGE_TOKEN</code>。</li>
        <li>只调度到 worker；requests 200m / 256Mi，limits 1 CPU / 512Mi；liveness 只检查能 import confluent_kafka。</li>
      </ul>
      <h3>与入口 A 的差异（重要）</h3>
      <div class="note"><code>detector.py</code> 的 <code>_infer()</code> <b>不是</b>调用 <code>ads_ml/main.py</code>，而是自己重写的简化版：异常判断用 <code>decision_function</code> 按训练集最小最大值归一化后与 <code>REVIEW_THRESHOLD</code> 比较，没有余弦复核；ZSL 用 <code>prototypes.values()</code> 直接算相似度（假设原型文件是 <code>{名字: 向量}</code> 结构，而当前文件是 <code>{名字: {"prototypes": [...]}}</code>）。所以 A、B 的结果不可直接对比，部署 B 前要先在本地验证它能跑通。后端收到 B 的结果时 <code>model_name</code> 一律记为 <code>ads_ml_ocsvm</code>。</div>
      <h3>部署步骤</h3>
<pre class="on-both"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>/detector &amp;&amp; bash build.sh
kubectl create ns netsentinel --dry-run=client -o yaml | kubectl apply -f -
kubectl -n netsentinel create secret generic detector-secret \
  --from-literal=django-token="$(grep ^VIGIL_BRIDGE_TOKEN= <span class="vp">/srv/netsentinel/prod</span>/backend/backend/.env | cut -d= -f2-)" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f detector/k8s/detector-deployment.yaml
kubectl -n netsentinel logs deploy/netsentinel-detector -f     <span class="c"># 应看到 connected to Django</span></code></pre>
      <p>同时要关掉入口 A（注释 <code>vigil/apps.py</code> 的 <code>bridge.start()</code> 并重启后端），否则重复入库。后端日志里看到 <code>detector pod connected</code> 和 <code>detector push: saved N result(s)</code> 即正常；WebSocket 被以 4401 关闭 = token 不一致。</p>
    </section>

    <section id="entryc">
      <h2>4.10 入口 C：宿主机脚本 <span class="tag tag-k">K</span> <code>lab/collect/vigil_bridge.py</code></h2>
      <p>按 5 元组维护 <code>FlowState</code>，一条流超过 <code>--window</code>（默认 5 秒）没有新包就结束，凑够 <code>--batch-size</code>（默认 20）条就 <code>POST {backend}/api/vigil/detect/batch/</code>。切流方式与训练数据一致，适合做对比实验。</p>
<pre class="on-prod"><code>cd /srv/netsentinel/lab
TOKEN=$(grep ^VIGIL_BRIDGE_TOKEN= <span class="vp">/srv/netsentinel/prod</span>/backend/backend/.env | cut -d= -f2-)   <span class="c"># 10 年有效的 JWT</span>
uv run python lab/collect/vigil_bridge.py --backend http://localhost:8080 --token "$TOKEN" --window 5 --batch-size 20</code></pre>
      <p>同样要先关入口 A。</p>
    </section>

    <section id="newmodel">
      <h2>4.11 替换模型与新增模型</h2>
      <p>线上模型文件按版本放在 <code class="vp">/srv/netsentinel/models/ads_ml/</code>，每个版本一个目录（含 <code>config.yaml</code> 和 <code>trained/</code>），<code>current</code> 软链接指向正在用的版本，<code>.env</code> 里 <code>VIGIL_ADS_ML_CONFIG=/srv/netsentinel/models/ads_ml/current/config.yaml</code>。这样新旧版本同时在盘上，切换和回滚都只是改一个软链接再重启。</p>
      <h3>替换 ads_ml 模型文件</h3>
<pre class="on-prod"><code>cd /srv/netsentinel/models/ads_ml
mkdir -p v2-20261101/trained                                   <span class="c"># 版本名自定，建议 v序号-日期</span>
cp 新的文件 v2-20261101/trained/                                <span class="c"># ebpf_ocsvm_pipeline.joblib、*_prototypes_*.joblib、训练集 CSV</span>
cp current/config.yaml v2-20261101/                              <span class="c"># 文件名变了就改这份 config.yaml</span>
cd /srv/netsentinel/prod/apps/backend &amp;&amp; ../.venv/bin/python manage.py check_model --config /srv/netsentinel/models/ads_ml/v2-20261101/config.yaml
ln -sfn v2-20261101 /srv/netsentinel/models/ads_ml/current
sudo systemctl restart netsentinel
sudo journalctl -u netsentinel --since '-1 min' | grep 'AdsMLModel loaded from'</code></pre>
      <ul>
        <li><code>check_model</code> 只检查接口：能否加载、<code>predict</code> 返回的字段和类型是否正确。检测效果由训练模型的人负责。</li>
        <li>scikit-learn 要与训练时版本一致（当前锁定 1.7.2，见 <code>pyproject.toml</code>），否则加载失败。</li>
        <li>攻击类别名变了：前端 <code>VigilLogView.vue</code> 的 <code>ATTACK_TYPES</code> 和 <code>ml/cilium/policy.py</code> 的映射要同步改，走正常的 PR 和发布流程。</li>
        <li>回滚：<code>ln -sfn 旧版本目录名 /srv/netsentinel/models/ads_ml/current</code>，再重启。旧版本目录确认不再需要之前不要删。</li>
        <li>入口 B 部署时：<code>detector/build.sh</code> 默认从 <code>current</code> 取模型文件打进镜像，之后 <code>kubectl -n netsentinel rollout restart deploy/netsentinel-detector</code>。</li>
      </ul>
      <h3>新增一个模型（与现有模型并行）</h3>
      <ol>
        <li>在 <code>apps/backend/vigil/ml/models/</code> 下写一个继承 <code>BaseDetectionModel</code> 的类，实现 <code>name</code>（唯一，会存进记录的 <code>model_name</code>）和 <code>predict()</code>；参考 <code>example_threshold.py</code>。需要模型文件就像 <code>AdsMLModel</code> 一样接收 <code>config_path</code>，在构造函数里加载一次。</li>
        <li>检查接口：<code>../.venv/bin/python manage.py check_model --model vigil.ml.models.my_model.MyModel</code></li>
        <li>代码走 PR 和 <code>release.sh -backend</code> 上线。</li>
        <li>在线上 <code>.env</code> 里加：<code>VIGIL_MODELS=vigil.ml.models.ads_ml_model.AdsMLModel,vigil.ml.models.my_model.MyModel</code>，重启。</li>
      </ol>
      <p>结果：<code>/api/vigil/models/</code> 返回两个名字，看板 Model Coverage 出现两行；每条流每个模型各写一条记录，记录数随模型数增加。只想换掉旧模型时，<code>VIGIL_MODELS</code> 里只留新类。<code>POST /api/vigil/detect/</code> 带 <code>"model": "名字"</code> 可以单独调用某个模型。</p>
    </section>
  </div>
</template>

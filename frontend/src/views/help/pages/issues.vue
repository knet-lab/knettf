<template>
  <div v-pre>
        <h1>已知问题与练习</h1>
    <div class="meta">第一部分列出 2026-10-18 核对代码时发现的问题，接手后可按优先级逐个解决。第二部分是一组由浅入深的练习，做完说明你已经掌握了整个项目。</div>

    <section id="security">
      <h2>8.1 安全问题（站点在公网，优先处理）</h2>
      <div class="table-wrap"><table>
        <tr><th>问题</th><th>位置</th><th>影响</th><th>建议</th></tr>
        <tr><td>SECRET_KEY、数据库密码明文；<code>DEBUG=True</code>；<code>ALLOWED_HOSTS=*</code>；<code>CORS_ALLOW_ALL_ORIGINS</code></td><td><code>backend/settings.py</code></td><td>任何能读仓库的人可伪造 JWT；出错时公网可见源码与配置</td><td>全部移入 <code>backend/backend/.env</code>，生产关 DEBUG，限定 hosts 与 CORS</td></tr>
        <tr><td>默认账号弱口令</td><td><code>kcore/management/commands/users_init.py</code></td><td>admin/admin123 公网可登录</td><td>立即改密码</td></tr>
        <tr><td>任何人可注册</td><td><code>UserList</code> POST 为 <code>AllowAny</code></td><td>陌生人可拿到普通账号，进而看全部检测数据</td><td>改为 <code>IsAdminUser</code></td></tr>
        <tr><td>Pod 日志 WebSocket 无鉴权</td><td><code>kcore/consumers.py PodLogConsumer</code></td><td>知道集群 ID 即可读任意 Pod 日志，且不检查 owner</td><td>从 query 取 token 校验，再 <code>check_owner</code></td></tr>
        <tr><td>kubeconfig 明文存库，且接口原样返回</td><td><code>KubeClusterResponseSerializer</code> 含 <code>kubeconfig</code></td><td>任何能列出集群的人拿到集群最高权限</td><td>输出时去掉该字段；存储加密（<code>common/ctypto.py</code> 本就是为此预留的空文件）</td></tr>
        <tr><td>Apply YAML <code>force_conflicts=True</code></td><td><code>common/kclient.py</code></td><td>会强行覆盖其他控制器管理的字段</td><td>默认 False，冲突时提示</td></tr>
        <tr><td>报告链接把 access token 放在 URL</td><td>AutoTFView <code>?token=</code></td><td>进入浏览器历史、代理日志</td><td>改为短期一次性下载 token</td></tr>
      </table></div>
    </section>

    <section id="reliability">
      <h2>8.2 可靠性问题</h2>
      <div class="table-wrap"><table>
        <tr><th>问题</th><th>位置</th><th>影响</th><th>建议</th></tr>
        <tr><td>bridge 出错后线程退出、不重连</td><td><code>vigil/bridge.py run_bridge()</code></td><td>集群重启 / Kafka 抖动后检测停止，必须人工重启后端</td><td>外层加 while True + 退避重试</td></tr>
        <tr><td>每条流都重新加载模型文件</td><td><code>ads_ml/main.py main()</code> 调 <code>_load_resources()</code></td><td>推理慢，流量大时 <code>flow_queue</code> 堆满丢批</td><td>在 <code>AdsMLModel.__init__</code> 缓存资源，<code>predict</code> 直接调 utils</td></tr>
        <tr><td>每条推理都覆盖写报告 CSV</td><td><code>utils/cloud_reporting.py</code></td><td>额外磁盘 IO，且只留最后一条</td><td>在线推理时不写</td></tr>
        <tr><td><code>detect_batch</code> 的事务在 default 库</td><td><code>vigil/services.py</code></td><td>以为整批原子，实际 vigil 库逐条提交</td><td><code>transaction.atomic(using="vigil")</code>，并用 <code>bulk_create</code></td></tr>
        <tr><td>Kafka 地址写死</td><td><code>bridge.py KAFKA_BOOTSTRAP</code></td><td>MetalLB 地址变化要改代码</td><td>从 .env 读</td></tr>
        <tr><td>扫描工具没有超时</td><td><code>autotf/services.py _run_tool()</code></td><td>工具卡住则请求永久挂起，占用线程</td><td><code>communicate(timeout=...)</code></td></tr>
        <tr><td>扫描、Apply 同步执行</td><td>autotf views</td><td>一分钟级的 HTTP 请求，经 Cloudflare 可能超时（约 100 秒）</td><td>改为后台任务 + 轮询（依赖里已有 celery，未使用）</td></tr>
        <tr><td>Terraform 不保留 state</td><td><code>ApplyService</code> 临时目录</td><td>重复 Apply 重复建资源，无法 destroy</td><td>按配置持久化工作目录或配置远程 backend</td></tr>
        <tr><td>rotate_partitions 只回扫 7 天</td><td><code>vigil/management/commands/rotate_partitions.py</code></td><td>漏跑超过 7 天的旧分区永远不会删</td><td>查询 <code>pg_inherits</code> 删除所有早于截止日的分区</td></tr>
        <tr><td>kafka-controller 是裸 Pod + emptyDir</td><td><code>$K/kafka-svc/kafka-5nodes.yaml</code></td><td>被删或节点故障 → Kafka 只能重建</td><td>改 StatefulSet + PVC</td></tr>
        <tr><td>VM 不自启、iptables 不持久</td><td>libvirt、02 脚本</td><td>宿主机重启后需手工恢复</td><td><code>virsh autostart</code>、<code>iptables-persistent</code></td></tr>
        <tr><td>每个节点的 Vector 都从 relay 拉全集群事件</td><td><code>vector-5nodes.yaml</code></td><td>Kafka 里同一事件可能有多份</td><td>改为单副本 Deployment，或每个节点只读本地 Hubble</td></tr>
      </table></div>
    </section>

    <section id="bugs">
      <h2>8.3 功能缺陷</h2>
      <div class="table-wrap"><table>
        <tr><th>现象</th><th>原因</th><th>改法</th></tr>
        <tr><td>管理后台 Dashboard 的 Total Clusters、Total TF Configs 恒为 0</td><td>前端调用不存在的 <code>/api/autotf/tf-configs/all/</code>；用户序列化器没有 <code>cluster_count</code></td><td>后端加汇总接口，或前端复用 ClustersView / TFConfigsView 的拼接逻辑</td></tr>
        <tr><td>新建用户时 Admin 开关无效</td><td><code>UserCreateSerializer.fields</code> 不含 <code>is_staff</code></td><td>管理员调用时允许设置 <code>is_staff</code></td></tr>
        <tr><td>Cilium 动作只有 ignore / alert</td><td><code>policy.py</code> 的映射键（<code>syn_flood</code>）与模型类别名（<code>Dos-TCP SYN flood</code>）不一致</td><td>按实际类别名重写映射</td></tr>
        <tr><td>Cilium 不会真正封禁</td><td><code>apply_action()</code> 是 stub</td><td>用 <code>_build_cnp_yaml()</code> + kclient 的 <code>apply_yaml</code> 实现</td></tr>
        <tr><td>simulation/run.sh 的 monitor 收不到结果</td><td>后端没有 <code>ws/vigil/</code> 路由</td><td>在 <code>vigil/routing.py</code> 加广播 consumer（drainer 写库后 <code>group_send</code>），或 monitor 改为轮询 REST</td></tr>
        <tr><td>入口 B 结果与入口 A 不一致，且可能报错</td><td><code>detector.py _infer()</code> 是简化重写，原型文件结构假设不同</td><td>镜像内直接复用 <code>ads_ml/main.py</code> 的流程</td></tr>
        <tr><td>入口 A 的“流”很碎</td><td>每次 poll 立即聚合，没有时间窗口</td><td>与训练一致：按 5 元组维护状态，超时 5 秒结束</td></tr>
        <tr><td>集群列表接口返回 kubeconfig，网页上没有编辑集群入口</td><td>前端未实现</td><td>加 Edit 对话框调用 PUT</td></tr>
        <tr><td>KcoreView 的 openYaml 不会自动刷新 token</td><td>直接用 <code>fetch</code></td><td>改用 <code>auth.apiFetch</code></td></tr>
        <tr><td><code>handle_addr.py</code> 只清理 .16-.29</td><td>写死范围</td><td>增加 .50-.64、.170-.184</td></tr>
        <tr><td>检测器 ConfigMap 的 <code>FLOW_TIMEOUT_SEC</code>、<code>BATCH_SIZE</code> 不生效</td><td><code>detector.py</code> 读的是 <code>PKT_BATCH_SIZE</code></td><td>统一变量名</td></tr>
      </table></div>
    </section>

    <section id="ex1">
      <h2>8.4 练习一：使用</h2>
      <ol>
        <li>用 admin 登录，新建用户 <code>trainee</code>，再用命令行把它设为管理员，确认 Role 变成 Admin。</li>
        <li>以 trainee 登记实验集群，找到 <code>default</code> 命名空间里 <code>kafka-broker-0</code> 的日志，说出它最后一行在干什么。</li>
        <li>对 <code>my-nginx</code> 做一次 Normal 重启，观察 Pod 名字变化。</li>
        <li>在线新建一个 Terraform 配置（只写一个 <code>terraform {}</code> 块），Full Scan，读懂报告。再故意写一个语法错误，看哪个工具报 HIGH、Apply 按钮的提示是什么。</li>
        <li>在 Detection Log 里筛选最近 1 小时的攻击，打开一条，解释 Confidence、Attack Type、Ground Truth 分别是什么意思。</li>
      </ol>
    </section>

    <section id="ex2">
      <h2>8.5 练习二：代码阅读</h2>
      <ol>
        <li>access token 过期的瞬间，页面同时发出 3 个请求，<code>auth.ts</code> 会调用几次刷新接口？为什么？</li>
        <li>浏览器直接打开 <code>https://knettf.com/vigil/log</code>，从 Cloudflare 到 Vue 组件渲染，依次经过了哪些代码？</li>
        <li>普通用户 bob 请求 <code>GET /api/kcore/clusters/1/</code>（集群 1 属于 alice），返回什么？哪一行代码决定的？</li>
        <li>为什么后端在 <code>manage.py shell</code> 时不启动 bridge，在 uvicorn 下会？</li>
        <li>一个只有 1 个 SYN 包的流，<code>packets_per_second</code>、<code>iat_mean</code>、<code>syn_ratio</code> 各是多少？</li>
        <li>如果把 <code>bridge.py</code> 的标签规则改成 .30-.39 为攻击，还要改哪些地方，实验才能对得上？</li>
        <li>明天的分区不存在时，drainer 日志会出现什么？网页上表现如何？</li>
      </ol>
      <details><summary>参考答案</summary>
        <ol>
          <li>1 次。<code>tryRefresh</code> 用模块级 <code>refreshPromise</code> 合并并发刷新。</li>
          <li>cloudflared → uvicorn → <code>asgi.py</code> http → 中间件（WhiteNoise 找不到 <code>/vigil/log</code> 文件）→ <code>urls.py</code> 的 <code>spa_view</code> 返回 <code>dist/index.html</code> → 浏览器加载 JS → <code>main.ts</code> → router 守卫（检查 token）→ 懒加载 <code>VigilLogView.vue</code> → <code>onMounted</code> 调 <code>/api/vigil/records/</code>。</li>
          <li>403，<code>{"status":"error","code":1,"message":"You do not have permission..."}</code>；<code>common/permissions.py check_owner()</code>。</li>
          <li><code>vigil/apps.py _should_start_bridge()</code>：<code>shell</code> 在排除列表里；uvicorn 时 <code>argv[0]</code> 含 uvicorn。</li>
          <li>duration 取 1e-6，所以 pps = 1 000 000；无间隔，iat_mean = 0；syn_ratio = 1.0。</li>
          <li><code>spoof_attack.py</code> 的 FAKE_IPS、<code>handle_addr.py</code>、<code>dataset_collector.py</code>、<code>kafka_read_csv.py</code>、<code>kafka/vigil_bridge.py</code>、<code>detector.py</code>，以及本手册和运维手册的说明。</li>
          <li><code>drainer failed on batch of N flows</code> + <code>no partition of relation "vigil_detectionrecord" found for row</code>；网页上过了 UTC 0 点后不再有新记录。</li>
        </ol>
      </details>
    </section>

    <section id="ex3">
      <h2>8.6 练习三：动手改</h2>
      <ol>
        <li>按<a href="/help/backend">《后端代码》</a> 3.11 加 <code>/api/vigil/top-sources/</code>，再按<a href="/help/frontend">《前端代码》</a> 2.11 的方式在看板上展示它。</li>
        <li>修复 Dashboard 恒为 0 的问题（8.3 第一条），写一个后端测试。</li>
        <li>给 <code>run_bridge()</code> 加自动重连：停掉一个 Kafka broker 再恢复，确认无需重启后端就能继续入库。</li>
        <li>把模型资源缓存到 <code>AdsMLModel</code> 实例里，用 <code>raw_output.inference_ms</code> 对比改前改后的平均耗时（6.7 的 SQL）。</li>
        <li>完整做一次计划停机和开机恢复（<a href="/help/power">开关机 · 重建 · 备份</a>），记录每一步花的时间。</li>
        <li>在一个不影响他人的时间窗口，按 <a href="/help/power#rebuild-kafka">重建 Kafka</a>，并确认端到端恢复。</li>
      </ol>
      <div class="ok">全部做完，你就能独立负责这个项目了。遇到手册与代码不一致的地方，以代码为准，并更新本手册（<code>frontend/src/views/help/pages/</code>，改完 <code>scripts/deploy.sh -frontend</code>）。</div>
    </section>
  </div>
</template>

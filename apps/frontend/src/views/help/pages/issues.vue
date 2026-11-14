<template>
  <div v-pre>
        <h1>9 已知问题</h1>
    <div class="meta">对照代码发现的问题，按类别列出，接手后可以按优先级逐个解决。解决一项就从这里删掉。</div>

    <section id="security">
      <h2>9.1 安全问题（站点在公网，优先处理）</h2>
      <div class="table-wrap"><table>
        <tr><th>问题</th><th>位置</th><th>影响</th><th>建议</th></tr>
        <tr><td>数据库密码默认值写在代码里；<code>CORS_ALLOW_ALL_ORIGINS</code>（SECRET_KEY / DEBUG / ALLOWED_HOSTS 已从 .env 读，线上已关 DEBUG）</td><td><code>apps/backend/settings.py</code></td><td>能读仓库的人知道 PostgreSQL 密码；任何站点可跨域调用 API</td><td>改 PostgreSQL 密码并只写进线上 .env（<code>VIGIL_DB_PASSWORD</code>）；限定 CORS 来源</td></tr>
        <tr><td>默认账号弱口令</td><td><code>kcore/management/commands/users_init.py</code></td><td>admin/admin123 公网可登录</td><td>立即改密码</td></tr>
        <tr><td>任何人可注册</td><td><code>UserList</code> POST 为 <code>AllowAny</code></td><td>陌生人可拿到普通账号，进而看全部检测数据</td><td>改为 <code>IsAdminUser</code></td></tr>
        <tr><td>Pod 日志 WebSocket 无鉴权</td><td><code>kcore/consumers.py PodLogConsumer</code></td><td>知道集群 ID 即可读任意 Pod 日志，且不检查 owner</td><td>从 query 取 token 校验，再 <code>check_owner</code></td></tr>
        <tr><td>kubeconfig 明文存库，且接口原样返回</td><td><code>KubeClusterResponseSerializer</code> 含 <code>kubeconfig</code></td><td>任何能列出集群的人拿到集群最高权限</td><td>输出时去掉该字段；存储加密（<code>common/ctypto.py</code> 本就是为此预留的空文件）</td></tr>
        <tr><td>Apply YAML <code>force_conflicts=True</code></td><td><code>common/kclient.py</code></td><td>会强行覆盖其他控制器管理的字段</td><td>默认 False，冲突时提示</td></tr>
        <tr><td>报告链接把 access token 放在 URL</td><td>AutoTFView <code>?token=</code></td><td>进入浏览器历史、代理日志</td><td>改为短期一次性下载 token</td></tr>
      </table></div>
    </section>

    <section id="reliability">
      <h2>9.2 可靠性问题</h2>
      <div class="table-wrap"><table>
        <tr><th>问题</th><th>位置</th><th>影响</th><th>建议</th></tr>
        <tr><td>bridge 出错后线程退出、不重连</td><td><code>vigil/bridge.py run_bridge()</code></td><td>集群重启 / Kafka 抖动后检测停止，必须人工重启后端</td><td>外层加 while True + 退避重试</td></tr>
        <tr><td>每条推理都覆盖写报告 CSV</td><td><code>utils/cloud_reporting.py</code></td><td>额外磁盘 IO，且只留最后一条</td><td>在线推理时不写</td></tr>
        <tr><td><code>detect_batch</code> 的事务在 default 库</td><td><code>vigil/services.py</code></td><td>以为整批原子，实际 vigil 库逐条提交</td><td><code>transaction.atomic(using="vigil")</code>，并用 <code>bulk_create</code></td></tr>
        <tr><td>Kafka 地址写死</td><td><code>bridge.py KAFKA_BOOTSTRAP</code></td><td>MetalLB 地址变化要改代码</td><td>从 .env 读</td></tr>
        <tr><td>扫描工具没有超时</td><td><code>autotf/services.py _run_tool()</code></td><td>工具卡住则请求永久挂起，占用线程</td><td><code>communicate(timeout=...)</code></td></tr>
        <tr><td>扫描、Apply 同步执行</td><td>autotf views</td><td>一分钟级的 HTTP 请求，经 Cloudflare 可能超时（约 100 秒）</td><td>改为后台任务 + 轮询（依赖里已有 celery，未使用）</td></tr>
        <tr><td>Terraform 不保留 state</td><td><code>ApplyService</code> 临时目录</td><td>重复 Apply 重复建资源，无法 destroy</td><td>按配置持久化工作目录或配置远程 backend</td></tr>
        <tr><td>rotate_partitions 只回扫 7 天</td><td><code>vigil/management/commands/rotate_partitions.py</code></td><td>漏跑超过 7 天的旧分区永远不会删</td><td>查询 <code>pg_inherits</code> 删除所有早于截止日的分区</td></tr>
        <tr><td>kafka-controller 是裸 Pod + emptyDir</td><td><code>/srv/netsentinel/lab/manifests/kafka-5nodes.yaml</code></td><td>被删或节点故障 → Kafka 只能重建</td><td>改 StatefulSet + PVC</td></tr>
        <tr><td>VM 不自启、iptables 不持久</td><td>libvirt、02 脚本</td><td>宿主机重启后需手工恢复</td><td><code>virsh autostart</code>、<code>iptables-persistent</code></td></tr>
        <tr><td>每个节点的 Vector 都从 relay 拉全集群事件</td><td><code>vector-5nodes.yaml</code></td><td>Kafka 里同一事件可能有多份</td><td>改为单副本 Deployment，或每个节点只读本地 Hubble</td></tr>
      </table></div>
    </section>

    <section id="bugs">
      <h2>9.3 功能缺陷</h2>
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
  </div>
</template>

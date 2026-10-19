<template>
  <div v-pre>
        <h1>数据库与模型字段</h1>
    <div class="meta">表结构依据 <code>models.py</code> 与迁移文件，数量依据 2026-10-16 实际查询。</div>

    <section id="dbs">
      <h2>1. 两个数据库与路由</h2>
      <div class="table-wrap"><table>
        <tr><th>别名</th><th>引擎</th><th>位置</th><th>存放</th><th>连接方式</th></tr>
        <tr><td><code>default</code></td><td>SQLite</td><td><code>backend/db.sqlite3</code>（线上 <code class="vp">/srv/netsentinel/prod/backend/</code>，开发 <code class="vn">/home/NEWUSER/github/NetSentinel/backend/</code>，互不相通）</td><td>kcore、autotf、Django 内置（auth、admin、session、contenttypes、migrations）</td><td><code>sqlite3 backend/db.sqlite3</code></td></tr>
        <tr><td><code>vigil</code></td><td>PostgreSQL</td><td>Docker 容器 <code>pg</code>，127.0.0.1:5432，线上库 <code>vigil</code>、开发库 <code>vigil_dev</code>（线上的副本，开发随便用），用户 <code>vigil</code> / 密码 <code>vigil123</code>；用哪个库由 .env 的 <code>VIGIL_DB_NAME</code> 决定</td><td>只有 <code>vigil_detectionrecord</code>（分区表）</td><td><code>docker exec -it pg psql -U vigil vigil</code></td></tr>
      </table></div>
      <p>路由规则（<code>backend/backend/db_router.py AppRouter</code>）：</p>
      <ul>
        <li>读写：<code>kcore → default</code>，<code>vigil → vigil</code>，其他 app（autotf、auth…）返回 None，即落到 <code>default</code>。</li>
        <li>迁移：vigil 的迁移只在 <code>vigil</code> 库执行，其余只在 <code>default</code> 执行。所以要分别执行 <code>migrate</code> 和 <code>migrate --database=vigil</code>。</li>
        <li><code>allow_relation</code> 恒为 True，但两库之间没有外键关系，DetectionRecord 不关联用户。</li>
      </ul>
      <p>当前数据量：<code>kcore_user</code> 4 行、<code>kcore_kubecluster</code> 1 行、<code>autotf_terraformtool</code> 5 行、<code>vigil_detectionrecord</code> 175,015 行、92 个分区。</p>
    </section>

    <section id="er">
      <h2>2. 关系图</h2>
      <pre><code>                 default（SQLite）                                         vigil（PostgreSQL）
┌──────────────────────┐ 1   N ┌──────────────────────────┐          ┌──────────────────────────────────┐
│ kcore_user           │──────▶│ kcore_kubecluster        │          │ vigil_detectionrecord            │
│ (AbstractUser)       │       │ owner_id → user (CASCADE)│          │ PARTITION BY RANGE (created_at)  │
└──────────┬───────────┘       └──────────────────────────┘          │  ├ vigil_detectionrecord_2026_.. │
           │ 1                                                          │  ├ …（每天一个）                 │
           │ N                                                          │  └ vigil_detectionrecord_明天   │
┌──────────▼────────────────┐ 1   1 ┌──────────────────────┐ N   M ┌──────────────────────┐   └─ 与其他表无外键
│ autotf_terraformconfig    │──────▶│ autotf_scanreport    │──────▶│ autotf_terraformtool │
│ owner_id → user (CASCADE) │       │ config_id (CASCADE)  │ (经    │ 全局，管理员维护     │
└───────────────────────────┘       └──────────────────────┘ autotf_scanreport_tools)</code></pre>
      <p>删除用户会级联删除其集群、Terraform 配置及对应报告；删除工具会从报告的多对多关系中移除。</p>
    </section>

    <section id="kcore">
      <h2>3. kcore 表</h2>
      <h3>kcore_user（<code>kcore.models.User</code>，<code>AUTH_USER_MODEL</code>）</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>类型</th><th>约束</th><th>说明</th></tr>
        <tr><td><code>id</code></td><td>AutoField</td><td>PK</td><td>用户 ID，URL 中的 <code>&lt;pk&gt;</code></td></tr>
        <tr><td><code>username</code></td><td>varchar(150)</td><td>唯一</td><td>登录名</td></tr>
        <tr><td><code>email</code></td><td>EmailField</td><td>唯一</td><td>注册时必填且唯一；<code>generate_bridge_token</code> 创建的服务账号 email 为空串</td></tr>
        <tr><td><code>password</code></td><td>varchar(128)</td><td></td><td>Django PBKDF2 哈希；服务账号为不可用密码</td></tr>
        <tr><td><code>is_staff</code></td><td>bool</td><td></td><td>管理员：可进前端 <code>/admin</code>，<code>check_owner</code> 直接放行</td></tr>
        <tr><td><code>is_superuser</code></td><td>bool</td><td></td><td>可进 Django Admin <code>/admin/</code></td></tr>
        <tr><td><code>is_active</code></td><td>bool</td><td></td><td>False 时无法登录</td></tr>
        <tr><td><code>first_name</code> · <code>last_name</code> · <code>last_login</code> · <code>date_joined</code></td><td></td><td></td><td>继承自 AbstractUser，未使用</td></tr>
        <tr><td><code>created_at</code></td><td>datetime</td><td>auto_now_add</td><td>创建时间</td></tr>
      </table></div>
      <p>默认数据（<code>manage.py users_init</code>）：<code>admin / admin123</code>（staff + superuser）、<code>alice / alice123</code>、<code>bob / bob123</code>；另有服务账号 <code>vigil-bridge</code>。<code>users_clear</code> 删除全部用户。</p>
      <p>关联表 <code>kcore_user_groups</code>、<code>kcore_user_user_permissions</code> 为 Django 权限系统所用，项目未使用。</p>

      <h3>kcore_kubecluster（<code>KubeCluster</code>）</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>类型</th><th>约束</th><th>说明</th></tr>
        <tr><td><code>id</code></td><td>AutoField</td><td>PK</td><td>URL 中的 <code>cluster_id</code></td></tr>
        <tr><td><code>owner_id</code></td><td>FK → kcore_user</td><td>CASCADE</td><td>所属用户</td></tr>
        <tr><td><code>name</code></td><td>varchar(255)</td><td>(owner, name) 唯一</td><td>集群名</td></tr>
        <tr><td><code>kubeconfig</code></td><td>text</td><td></td><td>完整 kubeconfig 明文（含证书私钥），API 会原样返回</td></tr>
        <tr><td><code>is_active</code></td><td>bool</td><td>默认 True</td><td>未被代码使用</td></tr>
        <tr><td><code>last_synced_at</code></td><td>datetime</td><td>可空</td><td>未被代码更新</td></tr>
        <tr><td><code>created_at</code></td><td>datetime</td><td>auto_now_add</td><td></td></tr>
      </table></div>
    </section>

    <section id="autotf">
      <h2>4. autotf 表</h2>
      <h3>autotf_terraformconfig（<code>TerraformConfig</code>）</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>类型</th><th>说明</th></tr>
        <tr><td><code>id</code></td><td>AutoField PK</td><td>URL 中的 <code>config_pk</code></td></tr>
        <tr><td><code>owner_id</code></td><td>FK → kcore_user，CASCADE</td><td>(owner, name) 唯一</td></tr>
        <tr><td><code>name</code></td><td>varchar(255)</td><td>配置名</td></tr>
        <tr><td><code>file</code></td><td>FileField(upload_to='terraform/')</td><td>相对路径，实际文件在 <code>backend/terraform/</code>（<code>MEDIA_ROOT</code> 未设置，相对于服务的 WorkingDirectory）</td></tr>
        <tr><td><code>is_scanned</code></td><td>bool</td><td>最近一次扫描成功后为 True；扫描开始时置 False</td></tr>
        <tr><td><code>created_at</code> · <code>updated_at</code></td><td>datetime</td><td></td></tr>
        <tr><td><code>last_apply_at</code></td><td>datetime 可空</td><td>最近一次 apply 时间</td></tr>
        <tr><td><code>last_apply_status</code></td><td><code>success</code> | <code>failed</code> | null</td><td></td></tr>
        <tr><td><code>last_apply_output</code></td><td>text</td><td>terraform init + apply 的 stdout/stderr</td></tr>
      </table></div>

      <h3>autotf_terraformtool（<code>TerraformTool</code>）</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>类型</th><th>说明</th></tr>
        <tr><td><code>name</code></td><td>varchar(255) 唯一</td><td>结果 JSON 中以此为 key</td></tr>
        <tr><td><code>version</code></td><td>varchar(50)</td><td><code>autotf_init</code> 时执行 <code>--version</code> 获得</td></tr>
        <tr><td><code>is_enabled</code></td><td>bool</td><td>全量扫描只用启用的工具</td></tr>
        <tr><td><code>cmd</code></td><td>varchar(500)</td><td>扫描命令，支持 <code>{target_dir}</code>、<code>{target_file}</code>；按空格切分执行（不经 shell）</td></tr>
        <tr><td><code>init_cmd</code></td><td>varchar(500)</td><td>扫描前执行的命令，可空</td></tr>
        <tr><td><code>output_format</code></td><td><code>json</code> | <code>sarif</code></td><td>决定使用哪个解析器</td></tr>
        <tr><td><code>items_path</code></td><td>varchar</td><td>JSON 中问题列表的路径（点号分隔）</td></tr>
        <tr><td><code>severity_field</code> · <code>severity_map</code></td><td>varchar · JSON</td><td>严重度字段及映射到 HIGH / MEDIUM / LOW</td></tr>
        <tr><td><code>rule_id_field</code> · <code>description_field</code></td><td>varchar</td><td>规则 ID、描述字段路径</td></tr>
        <tr><td><code>location_file_field</code> · <code>location_line_field</code></td><td>varchar</td><td>位置字段路径</td></tr>
      </table></div>
      <p>当前 5 个工具（<code>autotf_init</code> 注册）：</p>
      <div class="table-wrap"><table>
        <tr><th>name</th><th>cmd</th><th>格式</th><th>依赖的二进制</th></tr>
        <tr><td>terraform_validate</td><td><code>terraform validate -json</code>（init：<code>terraform init -backend=false -input=false</code>）</td><td>json</td><td><code>/usr/bin/terraform</code></td></tr>
        <tr><td>tflint</td><td><code>tflint --format json {target_dir}</code></td><td>json</td><td><code>tflint</code>（PATH）</td></tr>
        <tr><td>checkov</td><td><code>/srv/netsentinel/tools/checkov/bin/checkov -d {target_dir} -o sarif --quiet</code>（结果读 cwd 下的 <code>results.sarif</code>）</td><td>sarif</td><td>checkov（独立 venv，路径由 <code>settings.AUTOTF_TOOLS_BIN</code> 配置）</td></tr>
        <tr><td>tfsec</td><td><code>tfsec {target_dir} --format sarif --no-color</code></td><td>sarif</td><td><code>tfsec</code></td></tr>
        <tr><td>trivy</td><td><code>trivy config {target_dir} --format sarif</code></td><td>sarif</td><td><code>trivy</code></td></tr>
      </table></div>

      <h3>autotf_scanreport（<code>ScanReport</code>）与 autotf_scanreport_tools</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>类型</th><th>说明</th></tr>
        <tr><td><code>config_id</code></td><td>OneToOne → terraformconfig，CASCADE</td><td>每个配置最多一份报告，重新扫描时覆盖</td></tr>
        <tr><td><code>tools</code></td><td>M2M → terraformtool</td><td>本次扫描用了哪些工具（表 <code>autotf_scanreport_tools</code>）</td></tr>
        <tr><td><code>status</code></td><td><code>pending</code> → <code>running</code> → <code>done</code> | <code>failed</code></td><td>apply 要求 <code>done</code></td></tr>
        <tr><td><code>result</code></td><td>JSON</td><td><code>{"summary":{"high","medium","low"},"tools":{name:{"items":[{rule_id,severity,description,location}],"error"?}}}</code></td></tr>
        <tr><td><code>scanned_at</code></td><td>datetime 可空</td><td>完成时间</td></tr>
      </table></div>
    </section>

    <section id="vigil">
      <h2>5. vigil_detectionrecord（PostgreSQL 分区表）</h2>
      <p>Django 模型 <code>vigil.models.DetectionRecord</code> 设置了 <code>managed = False</code>：Django 只读写，不建表。表结构由 <code>vigil/migrations/0001_initial.py</code> 中的手写 SQL 创建。</p>
      <div class="table-wrap"><table>
        <tr><th>列</th><th>PG 类型</th><th>非空</th><th>来源 / 含义</th></tr>
        <tr><td><code>id</code></td><td>BIGSERIAL</td><td>是</td><td>全局递增；主键为 <code>(id, created_at)</code></td></tr>
        <tr><td><code>src_ip</code> · <code>dst_ip</code></td><td>INET</td><td>是</td><td>五元组</td></tr>
        <tr><td><code>src_port</code> · <code>dst_port</code></td><td>INTEGER</td><td>是</td><td>五元组；ICMP 为 0</td></tr>
        <tr><td><code>protocol</code></td><td>VARCHAR(10)</td><td>是</td><td><code>TCP</code> / <code>UDP</code> / <code>ICMPv4</code> / <code>ICMPv6</code> / <code>OTHER</code></td></tr>
        <tr><td><code>flow_input</code></td><td>JSONB</td><td>是</td><td>送入模型的完整特征（<code>asdict(DetectionInput)</code>）；入口 B 为检测器推送的原始 dict</td></tr>
        <tr><td><code>model_name</code></td><td>VARCHAR(100)</td><td>是</td><td>当前只有 <code>ads_ml_ocsvm</code></td></tr>
        <tr><td><code>is_attack</code></td><td>BOOLEAN</td><td>是</td><td>OCSVM 判定（含余弦复核）</td></tr>
        <tr><td><code>confidence</code></td><td>DOUBLE</td><td>是</td><td>与最近攻击原型的余弦相似度；正常流为 0.0</td></tr>
        <tr><td><code>attack_type</code></td><td>VARCHAR(100)</td><td>否</td><td>9 类原型名之一或 <code>Unknown_Attack</code>；正常为 NULL</td></tr>
        <tr><td><code>explanation</code></td><td>TEXT</td><td>是</td><td>如 <code>OCSVM zsl_seen=Seen_Attack, zsl_sim=0.812</code></td></tr>
        <tr><td><code>raw_output</code></td><td>JSONB</td><td>是</td><td><code>zsl_similarity</code>、<code>zsl_attack</code>、<code>zsl_seen_status</code>、<code>aggregation_ms</code>（入口 A：首包到聚合的毫秒）、<code>inference_ms</code></td></tr>
        <tr><td><code>cilium_action</code></td><td>VARCHAR(50)</td><td>否</td><td><code>ignore</code> / <code>alert</code> / <code>rate_limit</code> / <code>drop</code>（仅建议，见下文）</td></tr>
        <tr><td><code>cilium_reason</code></td><td>TEXT</td><td>是</td><td>explanation 或 attack_type</td></tr>
        <tr><td><code>label</code></td><td>INTEGER</td><td>否</td><td>真实标签：源 IP 末段 20-29 → 1，50-64 → 0，其他 NULL</td></tr>
        <tr><td><code>created_at</code></td><td>TIMESTAMPTZ</td><td>是</td><td>默认 NOW()，<b>分区键</b>（UTC）</td></tr>
      </table></div>
      <p>索引（建在父表，自动继承到每个分区）：<code>vigil_dr_is_attack_idx (is_attack)</code>、<code>vigil_dr_model_name_idx (model_name)</code>、<code>vigil_dr_created_at_idx (created_at DESC)</code>。</p>

      <h3>分区机制</h3>
      <ul>
        <li>按 <code>created_at</code> 每天一个分区，表名 <code>vigil_detectionrecord_YYYY_MM_DD</code>，范围 [当天 00:00, 次日 00:00)。</li>
        <li>初次迁移预建「过去 89 天 + 今天 + 明天」共 91 个分区。</li>
        <li><code>/etc/cron.d/netsentinel</code> 每天 00:00 以 <code>netsentinel</code> 账户 用<b>线上目录</b> <code class="vp">/srv/netsentinel/prod</code> 执行 <code>rotate_partitions</code>（开发目录默认连 vigil_dev，用错目录分区会建到开发库）：创建<b>明天</b>的分区；删除 90 天前那一天及再往前 6 天的分区。日志 <code>/srv/netsentinel/logs/rotate_partitions.log</code>。</li>
        <li><b>若 cron 停了超过 1 天</b>，到达没有分区的日期时插入会报错 <code>no partition of relation "vigil_detectionrecord" found for row</code>，所有检测写库失败。补救：手动执行 <code>rotate_partitions</code>（只建明天），或用下方 SQL 补建当天分区。</li>
        <li>删除只回扫 7 天，因此更早的分区不会被自动清理（当前最早分区为 2026_03_19）。</li>
      </ul>
      <pre><code><span class="c">-- 查看分区数量与范围</span>
SELECT count(*), min(c.relname), max(c.relname) FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid
 WHERE i.inhparent='vigil_detectionrecord'::regclass;
<span class="c">-- 每个分区的行数</span>
SELECT tableoid::regclass AS part, count(*) FROM vigil_detectionrecord GROUP BY 1 ORDER BY 1 DESC LIMIT 10;
<span class="c">-- 手动补建某天分区</span>
CREATE TABLE IF NOT EXISTS vigil_detectionrecord_2026_10_17 PARTITION OF vigil_detectionrecord
  FOR VALUES FROM ('2026-10-17') TO ('2026-10-18');
<span class="c">-- 手动删除旧分区（整天数据立即释放空间）</span>
DROP TABLE IF EXISTS vigil_detectionrecord_2026_03_19;</code></pre>
      <div class="danger"><code>0001_initial</code> 的第一条 SQL 是 <code>DROP TABLE IF EXISTS vigil_detectionrecord CASCADE</code>。执行 <code>migrate vigil zero --database=vigil</code> 或重新应用该迁移会<b>清空全部检测记录</b>。</div>

      <h3>常用查询</h3>
      <pre><code><span class="c">-- 最近 1 小时攻击按类型</span>
SELECT attack_type, count(*) FROM vigil_detectionrecord
 WHERE is_attack AND created_at &gt; now() - interval '1 hour' GROUP BY 1 ORDER BY 2 DESC;
<span class="c">-- 用真实标签评估（混淆矩阵）</span>
SELECT label, is_attack, count(*) FROM vigil_detectionrecord WHERE label IS NOT NULL GROUP BY 1,2;
<span class="c">-- 某个源 IP 的记录</span>
SELECT id, created_at, dst_ip, dst_port, is_attack, attack_type, confidence
  FROM vigil_detectionrecord WHERE src_ip = '192.168.100.21' ORDER BY created_at DESC LIMIT 20;
<span class="c">-- 推理 / 聚合耗时</span>
SELECT avg((raw_output-&gt;&gt;'inference_ms')::float), avg((raw_output-&gt;&gt;'aggregation_ms')::float)
  FROM vigil_detectionrecord WHERE created_at &gt; now() - interval '1 day';</code></pre>
    </section>

    <section id="features">
      <h2>6. 35 个流特征（检测输入）</h2>
      <p>一条“流”= 一个 Kafka 消费批次内同一五元组 <code>(src_ip, dst_ip, src_port, dst_port, protocol)</code> 的全部 Hubble 事件。字段在以下五处必须一致：<code>K dataset/aggregate_flows.py</code>、<code>K kafka/vigil_bridge.py</code>、<code>N vigil/bridge.py compute_flow()</code>、<code>N vigil/serializers.py FlowInputSerializer</code>、<code>N vigil/ml/models/base.py DetectionInput</code>（以及 <code>detector/detector.py</code>）。</p>
      <p>“模型使用”列：OCSVM 流水线实际只用 28 列；标“常量剔除”的列在训练集中恒定，被 <code>constant_cols</code> 去掉。</p>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>字段</th><th>类型</th><th>计算方式（<code>compute_flow</code>）</th><th>模型使用</th></tr>
        <tr><td>1</td><td><code>src_ip</code></td><td>str</td><td>Hubble <code>IP.source</code></td><td>OrdinalEncoder</td></tr>
        <tr><td>2</td><td><code>dst_ip</code></td><td>str</td><td><code>IP.destination</code></td><td>OrdinalEncoder</td></tr>
        <tr><td>3</td><td><code>protocol</code></td><td>str</td><td><code>l4</code> 中出现的 TCP / UDP / ICMPv4 / ICMPv6，否则 OTHER</td><td>OrdinalEncoder</td></tr>
        <tr><td>4</td><td><code>src_port</code></td><td>int</td><td><code>l4.TCP|UDP.source_port</code>，无则 0</td><td>是</td></tr>
        <tr><td>5</td><td><code>dst_port</code></td><td>int</td><td><code>destination_port</code></td><td>是</td></tr>
        <tr><td>6</td><td><code>flow_duration</code></td><td>float 秒</td><td>末包时间 − 首包时间，最小 1e-6</td><td>是（log1p）</td></tr>
        <tr><td>7</td><td><code>total_packets</code></td><td>int</td><td>事件数</td><td>是（log1p）</td></tr>
        <tr><td>8</td><td><code>fwd_packets</code></td><td>int</td><td><code>traffic_direction == INGRESS</code> 的数量</td><td>是（log1p）</td></tr>
        <tr><td>9</td><td><code>bwd_packets</code></td><td>int</td><td>total − fwd</td><td>常量剔除</td></tr>
        <tr><td>10</td><td><code>fwd_ratio</code></td><td>float</td><td>fwd / total（4 位小数）</td><td>是</td></tr>
        <tr><td>11</td><td><code>packets_per_second</code></td><td>float</td><td>total / duration</td><td>是（log1p）</td></tr>
        <tr><td>12-15</td><td><code>iat_mean</code> · <code>iat_std</code> · <code>iat_min</code> · <code>iat_max</code></td><td>float 秒</td><td>相邻事件时间差的均值 / 总体标准差 / 最小 / 最大；单包为 0</td><td>是（log1p）</td></tr>
        <tr><td>16-21</td><td><code>syn_count</code> · <code>ack_count</code> · <code>fin_count</code> · <code>rst_count</code> · <code>psh_count</code> · <code>urg_count</code></td><td>int</td><td><code>l4.TCP.flags</code> 中该标志为真的事件数</td><td>前 5 个是（log1p）；urg 常量剔除</td></tr>
        <tr><td>22-25</td><td><code>syn_ratio</code> · <code>ack_ratio</code> · <code>fin_ratio</code> · <code>rst_ratio</code></td><td>float</td><td>对应 count / total</td><td>是</td></tr>
        <tr><td>26</td><td><code>reply_count</code></td><td>int</td><td><code>is_reply == true</code> 的事件数</td><td>常量剔除</td></tr>
        <tr><td>27</td><td><code>reply_ratio</code></td><td>float</td><td>reply / total</td><td>是</td></tr>
        <tr><td>28</td><td><code>forwarded_count</code></td><td>int</td><td><code>verdict == FORWARDED</code> 数</td><td>是（log1p）</td></tr>
        <tr><td>29</td><td><code>drop_count</code></td><td>int</td><td>total − forwarded</td><td>常量剔除</td></tr>
        <tr><td>30</td><td><code>drop_ratio</code></td><td>float</td><td>drop / total</td><td>常量剔除</td></tr>
        <tr><td>31</td><td><code>is_bidirectional</code></td><td>0/1</td><td>流中出现过不止一种 direction</td><td>常量剔除</td></tr>
        <tr><td>32</td><td><code>is_tcp</code></td><td>0/1</td><td>protocol == TCP</td><td>是</td></tr>
        <tr><td>33</td><td><code>is_udp</code></td><td>0/1</td><td>protocol == UDP</td><td>是</td></tr>
        <tr><td>34</td><td><code>is_icmp</code></td><td>0/1</td><td>ICMPv4 / ICMPv6</td><td>常量剔除</td></tr>
        <tr><td>35</td><td><code>is_well_known_port</code></td><td>0/1</td><td>dst_port &lt; 1024</td><td>是</td></tr>
        <tr><td>—</td><td><code>label</code></td><td>"0"/"1"/""</td><td>流内各包标签的众数</td><td>不送入模型，只写库</td></tr>
        <tr><td>—</td><td><code>aggregation_ms</code></td><td>float</td><td>入口 A 专有：flush 时刻 − 首包时间</td><td>不送入模型，写入 raw_output</td></tr>
      </table></div>
      <p>入口 A 过滤规则（<code>bridge.py</code>）：源和目的<b>都</b>是基础设施地址（<code>10.*</code>、节点 .10-.15、MetalLB .200-.250、宿主机 .1）时丢弃；任一端口为 9092/9093/9094（Kafka 自身流量）时丢弃。</p>
    </section>

    <section id="model">
      <h2>7. 检测模型 ads_ml_ocsvm</h2>
      <h3>文件</h3>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>内容</th></tr>
        <tr><td><code>vigil/ml/ads_ml/config.yaml</code></td><td>模型路径、训练数据路径、报告路径</td></tr>
        <tr><td><code>trained/ebpf_ocsvm_pipeline.joblib</code>（69 KB）</td><td>dict：encoder（OrdinalEncoder）、scaler、PCA(20)、detector=<code>OneClassSVM(nu=0.01)</code>、列定义、clip 范围</td></tr>
        <tr><td><code>trained/multi_attack_semantic_prototypes_kmeans.joblib</code>（43 KB）</td><td>9 类攻击的 KMeans 原型向量，共 190 个</td></tr>
        <tr><td><code>trained/step_10_final_train_data.csv</code>（11 MB）</td><td>PCA 后的训练样本（PC1..PC20），用于余弦复核</td></tr>
        <tr><td><code>main.py</code></td><td><code>_load_resources()</code>、<code>main(35 个特征)</code></td></tr>
        <tr><td><code>utils/data_preprocessing.py</code></td><td>编码 → 去常量列 → log1p → clip → 选 28 列 → 标准化 → PCA</td></tr>
        <tr><td><code>utils/anomaly_detection.py</code></td><td>OCSVM 判定 + 边界样本余弦复核</td></tr>
        <tr><td><code>utils/zero_shot_learning.py</code></td><td>攻击类型匹配</td></tr>
        <tr><td><code>utils/cloud_reporting.py</code></td><td>每次推理追加一行到 <code>results/Anomaly_Detection_Report.csv</code></td></tr>
      </table></div>
      <h3>推理流程</h3>
      <ol>
        <li><b>预处理</b>：35 个字段 → 3 个类别列做 OrdinalEncoder → 剔除 7 个常量列 → 14 个计数 / 时间列做 log1p → 按训练分位数 clip → 保留 28 列 → StandardScaler → PCA 降到 20 维。</li>
        <li><b>OCSVM</b>：<code>predict == -1</code> 判为攻击（1），否则正常（0）。</li>
        <li><b>边界复核</b>：<code>|sigmoid(score) − sigmoid(−score)| &lt; 0.10</code> 的样本，与训练集求余弦相似度，取 Top-5 平均：≥ 0.95 改判正常，≤ 0.90 改判攻击，介于两者之间保持原判。</li>
        <li><b>零样本分类</b>：攻击样本与 190 个原型比较余弦相似度，取最高者；≥ 0.50 为 <code>Seen_Attack</code> + 原型名，否则 <code>Unknown_Attack</code>。最高相似度写入 <code>confidence</code>。</li>
      </ol>
      <h3>9 类攻击原型</h3>
      <div class="table-wrap"><table>
        <tr><th>attack_type</th><th>原型数</th><th>attack_type</th><th>原型数</th></tr>
        <tr><td><code>ddos-TCP SYN flood</code></td><td>50</td><td><code>Slowloris</code></td><td>5</td></tr>
        <tr><td><code>Dos-TCP SYN flood</code></td><td>30</td><td><code>Slow-body</code></td><td>10</td></tr>
        <tr><td><code>TCP sequence prediction</code></td><td>50</td><td><code>Slow-read</code></td><td>5</td></tr>
        <tr><td><code>DoS Get</code></td><td>20</td><td><code>Slow-range</code></td><td>10</td></tr>
        <tr><td><code>Credentials hijacking</code></td><td>10</td><td><code>Unknown_Attack</code></td><td>相似度 &lt; 0.5 时</td></tr>
      </table></div>
      <div class="note"><b>性能注意</b>：<code>main()</code> 每次调用都会重新执行 <code>_load_resources()</code>，即每条流都重新读取两个 joblib 和 11 MB 的 CSV，并向报告 CSV 追加一行。流量大时推理耗时主要花在这里（见 <code>raw_output.inference_ms</code>）。</div>

      <h3>模型注册（<code>ml/models/registry.py</code>）</h3>
      <ul>
        <li>导入时实例化 <code>AdsMLModel</code>；失败只记 warning（<code>AdsMLModel not loaded</code>），注册表为空，检测接口返回空结果。</li>
        <li><code>example_threshold.py</code> 的 <code>ThresholdModel</code>（<code>threshold_v1</code>，规则：syn_ratio ≥ 0.8 / pps ≥ 500 / 回包率 ≤ 0.05）存在但<b>未注册</b>。注册方法：在 registry.py 末尾加 <code>registry.register(ThresholdModel())</code>，重启后端。</li>
        <li>新模型：继承 <code>BaseDetectionModel</code>，实现 <code>name</code> 与 <code>predict(DetectionInput) -&gt; DetectionResult</code>，然后注册。不指定 <code>model</code> 时每条流会跑<b>所有</b>已注册模型，各写一条记录。</li>
      </ul>
    </section>

    <section id="cilium">
      <h2>8. Cilium 动作策略</h2>
      <p><code>vigil/ml/cilium/policy.py</code>：</p>
      <div class="table-wrap"><table>
        <tr><th>条件</th><th>cilium_action</th></tr>
        <tr><td>非攻击，或 confidence &lt; 0.6</td><td><code>ignore</code></td></tr>
        <tr><td>attack_type = <code>syn_flood</code></td><td><code>drop</code></td></tr>
        <tr><td>attack_type = <code>flood</code></td><td><code>rate_limit</code></td></tr>
        <tr><td>attack_type = <code>port_scan</code> / <code>anomaly</code> / 其他任何值</td><td><code>alert</code></td></tr>
      </table></div>
      <div class="note">ads_ml 输出的类型名（如 <code>Dos-TCP SYN flood</code>）与映射表的 key（<code>syn_flood</code>）不匹配，所以当前实际只会出现 <code>ignore</code> 和 <code>alert</code>。<code>apply_action()</code> 是 stub，只打印 <code>[CILIUM STUB]</code> 日志，不会下发 CiliumNetworkPolicy；<code>_build_cnp_yaml()</code> 已写好封禁源 IP 的策略模板供将来接入。</div>
    </section>

    <section id="knet-data">
      <h2>9. knetsentinel 侧数据文件</h2>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>粒度</th><th>列</th><th>生成方式</th></tr>
        <tr><td><code>dataset/dataset.csv</code>、<code>dataset_v1.csv</code></td><td>包级</td><td><code>timestamp, verdict, direction, summary, src_ip, dst_ip, protocol, src_port, dst_port, tcp_flags, is_reply, trace_reason, label</code></td><td><code>dataset_collector.py</code> / <code>kafka_read_csv.py</code></td></tr>
        <tr><td><code>flows*.csv</code></td><td>流级</td><td>上表 35 特征 + label</td><td><code>aggregate_flows.py -i dataset.csv -o flows.csv -t 5</code>（5 秒超时窗口）</td></tr>
        <tr><td><code>simulation/simulate4.csv</code></td><td>流级</td><td>35 特征 + 攻击类型标签</td><td><code>gen_simulate4_csv.py</code> 合并 <code>test set_20000.csv</code> 与 <code>20000_test_attack_label.csv</code></td></tr>
        <tr><td><code>traffic_request/read_result.csv</code></td><td>包级</td><td>同 dataset</td><td><code>start_read.sh</code></td></tr>
        <tr><td><code>traffic_request/record_send_uuid.txt</code></td><td>每行一个 JSON</td><td>每条重放 flow 的发送记录</td><td><code>start_send.sh</code></td></tr>
        <tr><td><code>simulation/monitor/monitor_report_&lt;mode&gt;.txt</code>、<code>monitor_detail_&lt;mode&gt;.csv</code></td><td>—</td><td>混淆矩阵、Accuracy / Precision / Recall / F1</td><td><code>simulation/run.sh</code></td></tr>
      </table></div>
    </section>
  </div>
</template>

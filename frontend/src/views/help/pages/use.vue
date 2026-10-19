<template>
  <div v-pre>
        <h1>网页使用</h1>
    <div class="meta">读完你能：登录、管理用户、登记并操作 K8s 集群、扫描和部署 Terraform、读懂检测结果。每天的网页检查清单在 <a href="/help/health#web">每日健康检查</a>。<br>
      界面是英文的，按钮名按界面原样写出（如 <span class="ui">New User</span>）。每个操作后面注明它调用的后端接口，方便你在第 2、3 章对照代码。</div>

    <section id="login">
      <h2>1.1 登录、退出与登录状态</h2>
      <div class="steps">
        <div class="step"><div class="step-title">打开网页</div>
          <p>访问 <code>https://knettf.com</code>（或 <code>http://&lt;宿主机 IP&gt;:8080</code>）。未登录时任何地址都会被送到 <code>/login</code>，页面标题 <b>NetSentinel</b>。</p></div>
        <div class="step"><div class="step-title">输入账号密码</div>
          <p>填 <span class="ui">Username</span>、<span class="ui">Password</span>，回车或点登录按钮。</p>
          <div class="expect">普通用户进入 <code>/kcore</code>；管理员（<code>is_staff=True</code>）进入 <code>/admin/dashboard</code>。失败提示 <code>Invalid username or password</code>。</div></div>
      </div>
      <h3>背后发生了什么</h3>
      <ol>
        <li>前端 <code>POST /api/auth/token/</code>，body <code>{"username","password"}</code>，后端返回 <code>{"access","refresh"}</code> 两个 JWT。</li>
        <li>前端再 <code>GET /api/kcore/users/me/</code> 拿到 <code>{id, username, email, is_staff}</code>。</li>
        <li>三样东西存进浏览器 <code>localStorage</code>：<code>token</code>、<code>refreshToken</code>、<code>user</code>。</li>
        <li>之后每个请求都带 <code>Authorization: Bearer &lt;access&gt;</code>。access 2 小时过期，过期时前端自动用 refresh 换新的（<a href="/help/frontend">《前端代码》</a> 2.5）；refresh 7 天过期，过期后被送回登录页。</li>
      </ol>
      <h3>常用</h3>
      <ul>
        <li><b>退出</b>：右上角 <span class="ui">Sign Out</span>（管理后台在左下角）。会清空 localStorage 三项。</li>
        <li><b>手机</b>：右上角菜单按钮展开导航（窄屏抽屉）。</li>
        <li><b>进入管理后台</b>：顶部导航<b>没有</b>入口，地址栏输入 <code>/admin</code>。不是管理员会被送回 <code>/kcore</code>。</li>
        <li><b>从管理后台回普通页面</b>：地址栏输入 <code>/kcore</code>、<code>/vigil</code> 等。</li>
        <li><b>怪异的登录问题</b>（反复掉线、显示别人的名字）：浏览器开发者工具 → Application → Local Storage → 删掉三项后重新登录。</li>
      </ul>
    </section>

    <section id="layout">
      <h2>1.2 界面布局</h2>
      <h3>普通页面（顶部导航 <code>NavComponent.vue</code>）</h3>
      <div class="table-wrap"><table>
        <tr><th>导航</th><th>地址</th><th>页面文件</th><th>用途</th></tr>
        <tr><td><span class="ui">Kubernetes</span></td><td><code>/kcore</code></td><td><code>KcoreView.vue</code></td><td>管理<b>你自己</b>登记的集群</td></tr>
        <tr><td><span class="ui">Terraform Scan</span></td><td><code>/autotf</code></td><td><code>AutoTFView.vue</code></td><td>你自己的 Terraform 配置：编写、扫描、部署</td></tr>
        <tr><td><span class="ui">AI Vigil</span></td><td><code>/vigil</code></td><td><code>VigilView.vue</code></td><td>检测看板（所有登录用户看到的是同一份全局数据）</td></tr>
        <tr><td>（看板里的 <span class="ui">View log →</span>）</td><td><code>/vigil/log</code></td><td><code>VigilLogView.vue</code></td><td>检测日志：筛选、分页、详情</td></tr>
        <tr><td><span class="ui">Help</span></td><td><code>/help</code></td><td><code>HelpView.vue</code></td><td>本手册（<code>frontend/src/views/help/pages/</code> 下的 Vue 组件，改完要 <code>scripts/deploy.sh -frontend</code>）</td></tr>
      </table></div>
      <h3>管理后台（<code>AdminLayout.vue</code>，左侧菜单）</h3>
      <div class="table-wrap"><table>
        <tr><th>菜单</th><th>地址</th><th>能看到</th><th>能做</th></tr>
        <tr><td><span class="ui">Dashboard</span></td><td><code>/admin/dashboard</code></td><td>Total Users、Total Clusters、Total TF Configs</td><td>—（后两个数字目前恒为 0，见<a href="/help/issues">《已知问题与练习》</a>）</td></tr>
        <tr><td><span class="ui">Users</span></td><td><code>/admin/users</code></td><td>全部用户：ID、Username、Email、Role</td><td>新建、删除</td></tr>
        <tr><td><span class="ui">Clusters</span></td><td><code>/admin/clusters</code></td><td>所有人的集群：名称、所有者、状态、创建时间</td><td>删除</td></tr>
        <tr><td><span class="ui">TF Configs</span></td><td><code>/admin/tf-configs</code></td><td>所有人的 Terraform 配置</td><td>删除</td></tr>
        <tr><td><span class="ui">TF Tools</span></td><td><code>/admin/tf-tools</code></td><td>扫描工具：名称、版本、格式、命令、状态</td><td>新建、编辑、启用 / 停用、删除</td></tr>
      </table></div>
      <div class="learn"><b>权限模型一句话</b>：每个集群、每个 Terraform 配置都有一个 owner。普通用户只能操作自己的；管理员（<code>is_staff</code>）可以操作所有人的。判断写在后端 <code>common/permissions.py</code> 的 <code>check_owner()</code>。检测数据（vigil）没有 owner，所有登录用户都能看。</div>
    </section>

    <section id="users">
      <h2>1.3 用户管理（管理员）</h2>
      <h3>新建用户</h3>
      <div class="steps">
        <div class="step"><div class="step-title">Users → New User</div><p>弹出 <b>Create User</b>。</p></div>
        <div class="step"><div class="step-title">填写</div>
          <ul>
            <li><span class="ui">Username</span>：登录名，不能重复。</li>
            <li><span class="ui">Email</span>：必填，不能重复（后端 <code>UserCreateSerializer</code> 校验）。</li>
            <li><span class="ui">Password</span>：初始密码。注意：通过这个接口创建时<b>不走</b> Django 密码强度校验，请自觉用强密码。</li>
            <li><span class="ui">Admin</span> 开关：<b>不起作用</b>，见下方提示。</li>
          </ul></div>
        <div class="step"><div class="step-title">Create</div>
          <div class="expect">提示 <code>User created</code>，列表多一行，Role 为 User。失败提示 <code>Failed to create user</code>，多是用户名或邮箱已存在。</div></div>
      </div>
      <p>接口：<code>POST /api/kcore/users/</code>，body <code>{username, email, password, is_staff}</code>。</p>
      <div class="note"><b>Admin 开关为什么不生效</b>：<code>UserCreateSerializer</code> 的 <code>fields</code> 只有 <code>username / email / password</code>，<code>is_staff</code> 被丢弃。要设管理员用命令行（<a href="/help/account">账号与令牌</a>）：<br>
        <code class="vp">cd $P/backend &amp;&amp; ../.venv/bin/python manage.py shell -c "from kcore.models import User;u=User.objects.get(username='alice');u.is_staff=True;u.save()"</code></div>
      <h3>删除用户</h3>
      <p>行尾 <span class="ui">Delete</span> → 确认。接口 <code>DELETE /api/kcore/users/&lt;id&gt;/</code>。</p>
      <div class="danger">删除用户会通过外键 <code>on_delete=CASCADE</code> <b>一并删除</b>他名下的所有集群记录和 Terraform 配置（含报告），不可恢复。不要删除 <code>vigil-bridge</code>（检测服务账号，它的 token 写在 <code>.env</code> 里），也不要删自己。</div>
      <h3>网页上做不了、要用命令行的</h3>
      <div class="table-wrap"><table>
        <tr><th>需求</th><th>命令（在 <code class="vp">$P/backend</code> 下）</th></tr>
        <tr><td>改密码</td><td><code>../.venv/bin/python manage.py changepassword &lt;用户名&gt;</code></td></tr>
        <tr><td>设 / 取消管理员</td><td>见上方提示，<code>is_staff=True/False</code></td></tr>
        <tr><td>停用账号（不删除）</td><td>同上，<code>is_active=False</code></td></tr>
        <tr><td>改用户名 / 邮箱</td><td><code>PUT /api/kcore/users/&lt;id&gt;/</code>（本人或管理员），或 shell 中修改</td></tr>
        <tr><td>Django 自带后台</td><td><code>/admin/</code>（注意结尾斜杠，是 Django admin，不是前端的 <code>/admin</code>）。需要 <code>is_staff</code>，用 session 登录；模型未注册，用处有限</td></tr>
      </table></div>
      <div class="note"><b>自助注册</b>：<code>POST /api/kcore/users/</code> 是 <code>AllowAny</code>，任何人都能用 curl 注册普通账号（登录页没有入口）。巡检时留意陌生账号。</div>
    </section>

    <section id="clusters">
      <h2>1.4 登记集群</h2>
      <p>“集群”记录 = 名称 + kubeconfig 文本，存在 SQLite 的 <code>kcore_kubecluster</code> 表。后端每次操作集群时都用这段 kubeconfig 现场建一个 Kubernetes 客户端（<code>common/kclient.py</code>）。</p>
      <div class="steps">
        <div class="step"><div class="step-title">拿到 kubeconfig</div>
          <p>实验集群的在宿主机 <code>~/.kube/config</code>，用 <code>cat ~/.kube/config</code> 复制全部内容。<b>它等同集群最高权限</b>，只走安全渠道。</p></div>
        <div class="step"><div class="step-title">Kubernetes → My Clusters 旁的 Add</div>
          <p>弹出 <b>Add Cluster</b>，填名称（同一用户下不能重名，如 <code>lab</code>）和 <span class="ui">KubeConfig</span>，点 <span class="ui">Add Cluster</span>。</p>
          <p>接口 <code>POST /api/kcore/users/&lt;自己的 id&gt;/clusters/</code>，body <code>{name, kubeconfig}</code>。</p></div>
        <div class="step"><div class="step-title">验证</div>
          <p>点左侧新集群 → <span class="ui">Namespaces</span> 标签。</p>
          <div class="expect">列出 <code>default</code>、<code>kube-system</code>、<code>metallb-system</code>、<code>targets</code> 等为成功。报错：kubeconfig 错误或集群未开机。</div></div>
      </div>
      <h3>集群重建后</h3>
      <p>重建会换 CA 和证书，旧 kubeconfig 失效，页面所有操作报错。网页上没有编辑入口：删除旧记录（只删网页记录，不影响真实集群）→ 用同样名称重新添加。也可以直接调 <code>PUT /api/kcore/clusters/&lt;id&gt;/</code>，body <code>{"kubeconfig": "..."}</code>。</p>
      <p>管理后台 <span class="ui">Clusters</span> 能看到所有人的集群但只能删除；要操作某集群需由所有者在 Kubernetes 页面进行（或管理员用 API 直接调，<code>check_owner</code> 对管理员放行）。</p>
    </section>

    <section id="k8s">
      <h2>1.5 Kubernetes 页面逐项</h2>
      <p>选中左侧集群后，右侧有六个标签：<span class="ui">Namespaces</span>、<span class="ui">Pods</span>、<span class="ui">Deployments</span>、<span class="ui">Services</span>、<span class="ui">ConfigMaps</span>、<span class="ui">DaemonSets</span>。除 Namespaces 外都要先在 <span class="ui">Select Namespace</span> 下拉中选命名空间（默认 <code>default</code>）。</p>
      <div class="table-wrap"><table>
        <tr><th>操作</th><th>在哪</th><th>接口</th><th>说明</th></tr>
        <tr><td>列出资源</td><td>切换标签 / 刷新按钮</td><td><code>GET /api/kcore/clusters/&lt;id&gt;/resources/&lt;type&gt;/?namespace=&lt;ns&gt;</code></td><td>type ∈ namespaces、pods、deployments、services、configmaps、daemonsets</td></tr>
        <tr><td>看 YAML</td><td>行内 <span class="ui">YAML</span></td><td><code>GET .../resources/&lt;type&gt;/&lt;name&gt;/?namespace=</code></td><td>后端用 dynamic client 读出对象再转 YAML</td></tr>
        <tr><td>编辑</td><td>行内 <span class="ui">Edit</span> → 改 → <span class="ui">Apply</span></td><td><code>POST .../apply/</code> body <code>{yaml}</code></td><td>Server-Side Apply，field manager <code>netsentinel</code>，<code>force_conflicts=True</code>（会覆盖别人管理的字段）</td></tr>
        <tr><td>新建</td><td>右上 <span class="ui">Apply YAML</span></td><td>同上</td><td>可贴多份文档（<code>---</code> 分隔），结果提示 “Applied: N resource(s), M error(s)”</td></tr>
        <tr><td>看 Pod 日志</td><td>Pods 行内 <span class="ui">Logs</span></td><td>WebSocket <code>/ws/clusters/&lt;id&gt;/pods/&lt;ns&gt;/&lt;pod&gt;/logs/</code></td><td>窗口显示 <b>● Connected</b> 后实时滚动；关闭窗口即断开</td></tr>
        <tr><td>重启</td><td>Deployments / DaemonSets 行内重启</td><td><code>POST .../resources/&lt;type&gt;/&lt;name&gt;/</code> body <code>{namespace, force}</code></td><td><b>Normal (Rolling)</b>：给 Pod 模板打 <code>kubectl.kubernetes.io/restartedAt</code> 注解，滚动替换，不中断（优先）。<b>Force (Delete Pods)</b>：按 selector 把 Pod 全部以 <code>grace_period_seconds=0</code> 删除，会中断</td></tr>
        <tr><td>删除</td><td>行内 <span class="ui">Delete</span> → <b>Confirm Delete</b></td><td><code>DELETE .../resources/&lt;type&gt;/&lt;name&gt;/</code> body <code>{namespace}</code></td><td>Pod 删后通常会被控制器重建；Deployment、Service、Namespace 删除是永久的</td></tr>
      </table></div>
      <h3>实验集群里各命名空间有什么</h3>
      <div class="table-wrap"><table>
        <tr><th>Namespace</th><th>对象</th><th>能否在网页上动</th></tr>
        <tr><td><code>default</code></td><td><code>kafka-controller</code>（裸 Pod）、<code>kafka-broker-0..3</code>（StatefulSet）、<code>my-nginx</code>（Deployment + LoadBalancer .204）</td><td>my-nginx 可以；Kafka <b>不要</b></td></tr>
        <tr><td><code>kube-system</code></td><td>cilium（DS）、cilium-operator、hubble-relay、hubble-ui、vector（DS）、coredns、etcd、apiserver 等</td><td><b>不要</b>删除或 Force 重启</td></tr>
        <tr><td><code>metallb-system</code></td><td>metallb-controller、metallb-speaker</td><td><b>不要</b></td></tr>
        <tr><td><code>local-path-storage</code></td><td>local-path-provisioner</td><td><b>不要</b></td></tr>
        <tr><td><code>targets</code></td><td>靶机 .210-.214（<code>$K/cluster-setup/targets.yaml</code>）</td><td>可以重启</td></tr>
        <tr><td><code>netsentinel</code></td><td>检测器（入口 B，目前未部署）</td><td>可以</td></tr>
      </table></div>
      <div class="danger"><b>绝对不要</b>在网页上删除 <code>kafka-controller</code>：它是裸 Pod + emptyDir，删了不会重建，KRaft 元数据丢失，只能 <a href="/help/power#rebuild-kafka">重建 Kafka</a>。也不要删除任何 Namespace。</div>
    </section>

    <section id="tf">
      <h2>1.6 Terraform 扫描与部署</h2>
      <h3>创建配置</h3>
      <p><span class="ui">Terraform Scan</span> → My Configs 旁 <span class="ui">New</span> → <b>New Terraform Config</b>，两个标签二选一：</p>
      <ul>
        <li><span class="ui">Upload File</span>：填 Name，选本地 <code>.tf</code>。接口 <code>POST /api/autotf/users/&lt;id&gt;/tf-configs/</code>（multipart，字段 <code>name</code>、<code>file</code>）。</li>
        <li><span class="ui">Write Online</span>：填 Name 和 Content。接口 <code>POST /api/autotf/users/&lt;id&gt;/tf-configs/text/</code>，body <code>{name, content}</code>，后端存成 <code>&lt;name&gt;.tf</code>。</li>
      </ul>
      <p>文件存到 <code class="vp">$P/backend/terraform/</code>（Django FileField，<code>upload_to='terraform/'</code>，相对于服务的工作目录 <code>backend/</code>）。同一用户下名称不能重复。</p>
      <h3>编辑</h3>
      <p>选中配置 → <b>Config Content</b> 卡片 <span class="ui">Edit</span> → 改 → <span class="ui">Save</span>（<code>PUT /api/autotf/tf-configs/&lt;id&gt;/</code>，body <code>{content}</code>）。<b>改内容会把 <code>is_scanned</code> 置为 False</b>，必须重新扫描才能 Apply。只改名不会。</p>
      <h3>扫描</h3>
      <ul>
        <li><span class="ui">Full Scan</span>：所有 Enabled 的工具。<code>POST .../tf-configs/&lt;id&gt;/scan/</code>。</li>
        <li><span class="ui">Manual Scan</span>：弹出 <b>Manual Scan — Select Tools</b> 勾选。<code>POST .../scan/manual/</code>，body <code>{tool_ids: [...]}</code>。</li>
      </ul>
      <p>扫描是<b>同步</b>的：HTTP 请求一直挂着直到 5 个工具都跑完（几秒到一分钟），期间不要刷新。完成后 <b>Scan Report</b> 显示：</p>
      <ul>
        <li>HIGH / MEDIUM / LOW / TOTAL 计数和比例条；全无问题显示 “✓ No security issues found across all tools”。</li>
        <li>每个工具一节：名称、版本、输出格式（JSON / SARIF）、发现数（或 ✓ Clean）、问题表（rule_id、severity、description、location）。</li>
        <li><span class="ui">View Report</span> 新窗口打开 HTML 报告，<span class="ui">Download PDF</span> 下载 PDF（reportlab 生成）。这两个链接用 <code>?token=&lt;access&gt;</code> 鉴权，因为浏览器直接打开新窗口时带不上 Authorization 头。</li>
        <li>删除报告：<span class="ui">Delete Report</span>（<code>DELETE .../report/</code>），同时 <code>is_scanned</code> 置 False。</li>
      </ul>
      <div class="note">某个工具结果显示 <code>tool not found: xxx</code>：服务进程的 PATH 里找不到它。其他工具结果仍有效。处理：装上工具，或在 TF Tools 中停用。</div>
      <h3>部署（Apply）</h3>
      <p><span class="ui">Apply</span> 按钮只在三个条件全满足时可点，灰色时鼠标悬停看原因：</p>
      <div class="table-wrap"><table>
        <tr><th>提示</th><th>前端判断</th><th>后端也会再查一遍</th></tr>
        <tr><td>Run a scan first</td><td><code>is_scanned</code> 为 False</td><td>No scan report found</td></tr>
        <tr><td>Scan must be complete</td><td>报告 status ≠ done</td><td>Scan is not complete.</td></tr>
        <tr><td>Fix all HIGH severity issues first</td><td><code>summary.high &gt; 0</code></td><td>Cannot apply: HIGH severity issues found</td></tr>
      </table></div>
      <p>后端（<code>autotf/services.py ApplyService</code>）在临时目录里写 <code>main.tf</code>，执行 <code>terraform init -input=false</code>（超时 120 秒）和 <code>terraform apply -auto-approve -input=false</code>（超时 300 秒），把输出、状态、时间写回配置。页面显示 Last apply 的成功 / 失败标签和完整输出。</p>
      <div class="danger">Apply 会<b>真实创建</b>资源。临时目录用完即删，<b>不保留 terraform.tfstate</b>：重复 Apply 会再建一次，也无法从网页 destroy。</div>
      <h3>管理扫描工具（管理员，TF Tools）</h3>
      <div class="table-wrap"><table>
        <tr><th>操作</th><th>步骤</th><th>接口</th></tr>
        <tr><td>停用 / 启用</td><td><span class="ui">Edit</span> → 切 <span class="ui">Enabled</span> → Save</td><td><code>PATCH /api/autotf/tf-tools/&lt;id&gt;/</code></td></tr>
        <tr><td>删除</td><td><span class="ui">Delete</span>。建议用停用代替；删了可以用 <code>manage.py autotf_init</code> 重新生成</td><td><code>DELETE</code> 同上</td></tr>
        <tr><td>新增</td><td><span class="ui">New Tool</span>，字段含义见<a href="/help/backend">《后端代码》</a> 3.7</td><td><code>POST /api/autotf/tf-tools/</code></td></tr>
      </table></div>
      <p>默认 5 个工具：<code>terraform_validate</code>、<code>tflint</code>、<code>checkov</code>、<code>tfsec</code>、<code>trivy</code>。普通用户的工具列表只返回 Enabled 的。</p>
    </section>

    <section id="vigil">
      <h2>1.7 AI Vigil 看板与检测日志</h2>
      <h3>看板 <code>/vigil</code></h3>
      <div class="table-wrap"><table>
        <tr><th>区域</th><th>数据来源</th><th>含义</th></tr>
        <tr><td>左侧 <b>Detection model</b></td><td><code>GET /api/vigil/models/</code></td><td>已注册的模型，正常为 <code>ads_ml_ocsvm</code>。显示 No models registered = 模型加载失败</td></tr>
        <tr><td>左侧 <span class="ui">Attacks only</span> 开关</td><td>records 的 <code>only_attacks</code> 参数</td><td>下方日志只显示攻击</td></tr>
        <tr><td>LIVE、时钟、Last updated、Refresh now</td><td>—</td><td>每 <b>30 秒</b>自动刷新一次 stats 和 records；按钮立即刷新</td></tr>
        <tr><td>Total Inspected / Attacks Detected / Normal Flows / Attack Rate</td><td><code>GET /api/vigil/stats/</code></td><td>全表累计：流数、判为攻击数、正常数、攻击比例</td></tr>
        <tr><td>Attack Type Breakdown</td><td>stats.<code>by_attack_type</code></td><td>各攻击类型数量（条形图）</td></tr>
        <tr><td>Model Coverage</td><td>stats.<code>by_model</code></td><td>每个模型检测的数量</td></tr>
        <tr><td>Recent Attack Events</td><td>records 中 <code>is_attack</code> 的前 30 条</td><td>最近攻击；<span class="ui">View log →</span> 进日志页</td></tr>
        <tr><td>Detection Log</td><td><code>GET /api/vigil/records/?limit=100</code></td><td>最近记录，新记录按 id 去重后插到前面，最多保留 200 条</td></tr>
      </table></div>
      <div class="note">stats 每次都对整张分区表做 <code>COUNT</code> 和 <code>GROUP BY</code>，数据量大时会慢，这是看板加载慢的主要原因。</div>
      <h3>日志 <code>/vigil/log</code></h3>
      <ul>
        <li>筛选：Verdict（All / Attack / Normal → <code>only_attacks</code> / <code>only_normal</code>）、攻击类型（9 个固定选项 → <code>attack_type</code>）、时间范围（转成 ISO 发给 <code>time_from</code> / <code>time_to</code>，<span class="ui">Clear time</span> 清除）。</li>
        <li>每页 50 / 100 / 200 / 500（后端上限 500），<span class="ui">← Prev</span> / <span class="ui">Next →</span>；每 <b>15 秒</b>自动刷新当前页。</li>
        <li>点一行 → 详情抽屉（<code>GET /api/vigil/records/&lt;id&gt;/</code>）：<b>Flow</b>、<b>Ground Truth</b>、<b>Detection Result</b>、<b>ZSL Similarity Ranking</b>、<b>Cilium Response</b>、<b>Flow Features</b>。</li>
      </ul>
      <h3>每个字段怎么读</h3>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>来自</th><th>说明</th></tr>
        <tr><td>Verdict / is_attack</td><td>OCSVM（+ 余弦复核）</td><td>攻击或正常</td></tr>
        <tr><td>Confidence</td><td>ZSL 最高余弦相似度</td><td>0～1，越高越像该攻击类型；<b>正常流量恒为 0</b>（它不是“正常的置信度”）</td></tr>
        <tr><td>Attack Type</td><td>ZSL 原型匹配</td><td>训练时的攻击类别名（如 <code>Dos-TCP SYN flood</code>、<code>Slowloris</code>、<code>DoS Get</code>）；相似度 &lt; 0.5 时为 <code>Unknown_Attack</code></td></tr>
        <tr><td>Explanation</td><td>模型</td><td>如 <code>OCSVM zsl_seen=Seen_Attack, zsl_sim=0.873</code></td></tr>
        <tr><td>raw_output</td><td>模型 + 服务</td><td><code>zsl_similarity</code>、<code>zsl_attack</code>、<code>zsl_seen_status</code>、<code>aggregation_ms</code>（从流第一个包到聚合完成的毫秒数）、<code>inference_ms</code>（推理耗时）</td></tr>
        <tr><td>Cilium action / reason</td><td><code>ml/cilium/policy.py</code></td><td><code>ignore</code>（正常或置信度 &lt; 0.6）/ <code>alert</code> / <code>drop</code> / <code>rate_limit</code>。<b>只是建议，不会真的封禁</b></td></tr>
        <tr><td>Label / Ground Truth</td><td>bridge 按源 IP 打的标签</td><td>源 IP 末段 20-29 → 1（攻击）；50-64 → 0（正常）；其他 → 空</td></tr>
        <tr><td>Flow Features</td><td><code>flow_input</code> JSON</td><td>送进模型的特征（<a href="/help/detect">《检测链路与模型》</a> 4.3 有逐个解释）</td></tr>
      </table></div>
      <p>来源 <code>192.168.100.20-29</code>、<code>.170-.184</code> 一般是实验脚本发出的模拟攻击，属预期内。</p>
    </section>
  </div>
</template>

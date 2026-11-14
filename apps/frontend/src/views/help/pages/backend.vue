<template>
  <div v-pre>
        <h1>3 后端代码</h1>
    <div class="meta">读完你能：说出一个 HTTP 请求在后端经过的每一步，读懂三个应用的每个文件，会跑管理命令、加接口、改数据库结构。<br>
      代码根目录 <code class="vn">/home/NEWUSER/github/knettf/apps/backend/</code>（开发），线上运行的是 <code class="vp">/srv/netsentinel/prod/apps/backend/</code>（见 <a href="/help/index#envs">开发与生产</a>）。<code>manage.py</code> 命令在对应目录里用 <code>../../.venv/bin/python manage.py ...</code> 执行：调试、生成迁移在 <code class="vn">/home/NEWUSER/github/knettf</code>；操作线上数据（改密码、补分区）在 <code class="vp">/srv/netsentinel/prod</code>。逐个接口的参数与响应示例见 <a href="/help/api">API 逐接口</a>，表字段见 <a href="/help/db">数据库与模型字段</a>。</div>

    <section id="django">
      <h2>3.1 Django 五分钟入门（只讲本项目用到的）</h2>
      <dl class="terms">
        <dt>project</dt><dd><code>apps/backend/backend/</code>：全局配置（settings、总路由、ASGI 入口）。</dd>
        <dt>app</dt><dd>一个功能模块，本项目有 <code>kcore</code>、<code>autotf</code>、<code>vigil</code>，外加共享代码 <code>common</code>（不是 app，只是包）。</dd>
        <dt>models.py</dt><dd>数据表定义。一个类 = 一张表，表名默认 <code>&lt;app&gt;_&lt;类名小写&gt;</code>，如 <code>kcore_kubecluster</code>。</dd>
        <dt>migrations/</dt><dd>表结构变更脚本。改了 models 后 <code>makemigrations</code> 生成，<code>migrate</code> 执行。</dd>
        <dt>serializers.py</dt><dd>DRF 的“序列化器”：校验请求 JSON（输入）、把模型对象转成 JSON（输出）。</dd>
        <dt>views.py</dt><dd>处理请求的类。本项目都继承 <code>APIView</code>，方法名就是 HTTP 方法：<code>get()</code>、<code>post()</code>、<code>put()</code>、<code>patch()</code>、<code>delete()</code>。</dd>
        <dt>services.py</dt><dd>本项目自己的约定：业务逻辑放这里，view 只负责“取参数 → 查权限 → 调 service → 返回”。</dd>
        <dt>urls.py</dt><dd>URL → view 的映射。</dd>
        <dt>consumers.py / routing.py</dt><dd>Channels 的 WebSocket 处理类和它的 URL 映射。</dd>
        <dt>management/commands/</dt><dd>自定义命令，文件名就是命令名：<code>users_init.py</code> → <code>manage.py users_init</code>。</dd>
        <dt>apps.py</dt><dd>app 配置；<code>ready()</code> 在 Django 启动完成时调用一次（vigil 在这里启动后台线程）。</dd>
      </dl>
    </section>

    <section id="start">
      <h2>3.2 进程是怎么起来的</h2>
<ol>
        <li><b>systemd 启动</b>：<code>/etc/systemd/system/netsentinel.service</code> 以 <code>netsentinel</code> 账户、工作目录 <code class="vp">/srv/netsentinel/prod</code><code>/backend</code> 运行 <code class="vp">/srv/netsentinel/prod</code><code>/.venv/bin/uvicorn backend.asgi:application --host 0.0.0.0 --port 8080</code>。<code>Restart=always</code>，<code>MemoryMax=3G</code>，<code>TasksMax=500</code>。</li>
        <li><b>uvicorn 导入 <code>apps/backend/asgi.py</code></b>：设置 <code>DJANGO_SETTINGS_MODULE=backend.settings</code>，调用 <code>django.setup()</code>。</li>
        <li><b>读配置</b>：<code>settings.py</code> 读取 <code class="vp">/srv/netsentinel/prod</code><code>/backend/backend/.env</code>（<code>DEBUG=False</code>、<code>SECRET_KEY</code>、<code>VIGIL_DB_NAME=vigil</code>、<code>VIGIL_ADS_ML_CONFIG</code> …）。</li>
        <li><b>启动 bridge</b>：加载 INSTALLED_APPS 时调用 <code>vigil/apps.py</code> 的 <code>ready()</code>；<code>_should_start_bridge()</code> 看到进程是 uvicorn，就 <code>bridge.start()</code> 起两个守护线程 vigil-bridge、vigil-drainer（见 <a href="/help/detect">4 检测链路与模型</a>）。</li>
        <li><b>加载模型</b>：导入 <code>vigil/detection/registry.py</code> 时按 <code>VIGIL_MODELS</code> 实例化模型，日志 <code>AdsMLModel loaded from ...</code>。</li>
        <li><b>开始处理请求</b>：<code>ProtocolTypeRouter</code> 把 <code>http</code> 交给 Django，把 <code>websocket</code> 交给 <code>kcore.routing</code> + <code>vigil.routing</code> 的 Channels consumer。</li>
      </ol>
      <p>只有<b>一个</b> uvicorn 进程（没开 <code>--workers</code>），bridge 线程因此只有一份。如果将来加 workers，每个进程都会起一份 bridge，导致重复消费入库。</p>
      <p><code>_should_start_bridge()</code> 规则：<code>migrate</code>、<code>shell</code>、<code>check</code>、<code>test</code> 等命令不启动；<code>runserver</code> 只在自动重载的子进程（<code>RUN_MAIN=true</code>）启动；<code>argv[0]</code> 含 daphne / uvicorn / gunicorn 时启动。所以你在命令行跑 <code>manage.py shell</code> 不会多出一个 Kafka 消费者，但 <b><code>manage.py runserver</code> 会</b>。开发目录的 <code>.env</code> 设了 <code>VIGIL_KAFKA_GROUP_ID=vigil-bridge-dev</code>，开发 bridge 用自己的 consumer group，拿到一份完整的流量写进 <code>vigil_dev</code>，不影响线上。<b>新建开发环境时一定要设这个变量</b>：不设就默认 <code>vigil-bridge</code>，会和线上分走 Kafka 分区，线上漏收流量。</p>
    </section>

    <section id="settings">
      <h2>3.3 settings.py 逐项</h2>
      <div class="table-wrap"><table>
        <tr><th>设置</th><th>当前值</th><th>说明 / 风险</th></tr>
        <tr><td><code>env.read_env(...)</code></td><td><code>apps/backend/backend/.env</code></td><td>真正被读取的 .env，开发和线上各一份，不进 Git。仓库根目录那个 <code>.env</code> 不会被读。下面标“env”的设置都从这里读，没写就用默认值（默认值 = 开发配置）</td></tr>
        <tr><td><code>SECRET_KEY</code></td><td>env；默认是代码里那个 insecure key</td><td>JWT 签名也用它。线上 .env 里是单独生成的随机值；换掉它会让所有已登录用户的 token 失效</td></tr>
        <tr><td><code>DEBUG</code></td><td>env；默认 <code>True</code>，线上 <code>False</code></td><td>开着时出错返回带源码的调试页。关掉后 WhiteNoise 只在启动时扫描 dist，所以前端构建后要重启（<code>deploy.sh</code> 会做）</td></tr>
        <tr><td><code>ALLOWED_HOSTS</code></td><td>env；默认 <code>["*"]</code>，线上 <code>knettf.com,localhost,127.0.0.1,192.168.100.1</code></td><td>用别的域名 / IP 访问线上会返回 400，要加进 .env 并重启</td></tr>
        <tr><td><code>INSTALLED_APPS</code></td><td>channels、Django 内置、rest_framework、corsheaders、simplejwt、kcore、autotf、vigil</td><td><code>channels</code> 放第一位是 Channels 的要求</td></tr>
        <tr><td><code>MIDDLEWARE</code></td><td>Cors → Security → <b>WhiteNoise</b> → Session → Common → <b>DisableCSRFForAPI</b> → Auth → Messages → Clickjacking</td><td>WhiteNoise 提供前端文件；自定义中间件让 <code>/api/</code>、<code>/auth/</code> 免 CSRF</td></tr>
        <tr><td><code>DATABASES</code></td><td><code>default</code>：SQLite <code>apps/backend/db.sqlite3</code>（各目录自己的）；<code>vigil</code>：PostgreSQL，env <code>VIGIL_DB_NAME</code> / <code>_USER</code> / <code>_PASSWORD</code> / <code>_HOST</code> / <code>_PORT</code>，默认 <code>vigil/vigil123@127.0.0.1:5432/vigil_dev</code></td><td>线上 .env 设 <code>VIGIL_DB_NAME=vigil</code>。<b>忘了设就会连到开发库</b></td></tr>
        <tr><td><code>DATABASE_ROUTERS</code></td><td><code>backend.db_router.AppRouter</code></td><td>见 <a href="#db">两个数据库与路由</a></td></tr>
        <tr><td><code>TIME_ZONE</code> / <code>USE_TZ</code></td><td><code>UTC</code> / <code>True</code></td><td>数据库与 API 一律 UTC，前端转本地时间</td></tr>
        <tr><td><code>WHITENOISE_ROOT</code></td><td><code>apps/frontend/dist</code></td><td>该目录下的文件按原路径对外提供</td></tr>
        <tr><td><code>AUTH_USER_MODEL</code></td><td><code>kcore.User</code></td><td>自定义用户表 <code>kcore_user</code></td></tr>
        <tr><td><code>REST_FRAMEWORK</code></td><td>认证 JWT；默认权限 <code>IsAuthenticated</code>；异常处理 <code>common.exceptions.exception_handler</code></td><td>所以没特别声明的接口都要登录</td></tr>
        <tr><td><code>SIMPLE_JWT</code></td><td>access 2 小时，refresh 7 天，头 <code>Bearer</code></td><td></td></tr>
        <tr><td><code>VIGIL_BRIDGE_TOKEN</code></td><td>env</td><td>入口 B 检测器 WebSocket 的共享密钥</td></tr>
        <tr><td><code>VIGIL_KAFKA_GROUP_ID</code></td><td>env；默认 <code>vigil-bridge</code>，开发设 <code>vigil-bridge-dev</code></td><td>bridge 的 Kafka consumer group，见 <a href="#start">进程是怎么起来的</a></td></tr>
        <tr><td><code>CORS_ALLOW_ALL_ORIGINS</code></td><td><code>True</code></td><td></td></tr>
        <tr><td><code>CSRF_TRUSTED_ORIGINS</code></td><td>trycloudflare、localhost:8080，加上 env <code>CSRF_EXTRA_ORIGINS</code>（线上 <code>https://knettf.com</code>）</td><td>只影响 Django admin 这类 session 表单</td></tr>
        <tr><td><code>CHANNEL_LAYERS</code></td><td><code>InMemoryChannelLayer</code></td><td>进程内，不能跨进程广播；目前也没用到 group 广播</td></tr>
        <tr><td><code>TF_BIN</code></td><td><code>ENVIRONMENT=linux_development</code> → <code>/usr/bin/terraform</code>；<code>mac_os</code> → Mac 路径</td><td><code>.env</code> 里<b>必须</b>有 <code>ENVIRONMENT</code>，否则 settings 直接报错，服务起不来</td></tr>
      </table></div>
    </section>

    <section id="lifecycle">
      <h2>3.4 一个请求的完整生命周期</h2>
      <p>以“查看集群 3 的 default 命名空间下的 Pod”为例：<code>GET /api/kcore/clusters/3/resources/pods/?namespace=default</code></p>
      <div class="steps">
        <div class="step"><div class="step-title">中间件链</div><p>CORS 头 → WhiteNoise（不是静态文件，放过）→ <code>DisableCSRFForAPI</code> 标记免 CSRF → ...</p></div>
        <div class="step"><div class="step-title">URL 匹配</div>
          <p><code>apps/backend/urls.py</code>：<code>api/kcore/</code> → <code>include('kcore.urls')</code> → <code>clusters/&lt;int:cluster_id&gt;/resources/&lt;str:resource_type&gt;/</code> → <code>KubeResourceList</code>，参数 <code>cluster_id=3, resource_type='pods'</code>。</p></div>
        <div class="step"><div class="step-title">DRF 认证与权限</div>
          <p><code>JWTAuthentication</code> 解析 <code>Authorization: Bearer ...</code>，取出 <code>user_id</code> 查 <code>kcore_user</code> 得到 <code>request.user</code>。token 无效 / 过期 → 401。然后默认权限 <code>IsAuthenticated</code>。</p></div>
        <div class="step"><div class="step-title">view 方法</div>
<pre><code>cluster = KubeClusterService.get_cluster_by_id(cluster_id)   <span class="c"># 不存在 → NotFound → 404</span>
check_owner(request, cluster.owner.pk)                       <span class="c"># 不是本人也不是 staff → 403</span>
bk_service = KubeResourceService(cluster)                    <span class="c"># 用 kubeconfig 建客户端</span>
resources = bk_service.get_pods(namespace)                   <span class="c"># → kclient.core.list_namespaced_pod()</span>
return self.success_response({'resources': [r.to_dict() for r in resources]})</code></pre></div>
        <div class="step"><div class="step-title">统一响应</div>
<pre><code>HTTP 200
{"status": "success", "code": 0, "message": "Success", "data": {"resources": [...]}}</code></pre></div>
        <div class="step"><div class="step-title">出错时</div>
          <p>view 里抛出的 DRF 异常（<code>NotFound</code>、<code>PermissionDenied</code>、<code>ValidationError</code>、认证失败）被 <code>common/exceptions.py</code> 转成 <code>{"status":"error","code":1,"message":"...","data":null}</code>（5xx 时 code=2）。<b>非 DRF 异常</b>（如 kubernetes 客户端连不上集群抛的异常）不会被转换，DEBUG 模式下直接返回 500 调试页。</p></div>
      </div>
    </section>

    <section id="common">
      <h2>3.5 common/：共享代码</h2>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>内容</th></tr>
        <tr><td><code>response.py</code></td><td><code>ResponseMixin(Response)</code>：所有 view 都 <code>class X(APIView, ResponseMixin)</code>，于是有 <code>self.success_response(data, status)</code>、<code>created_response</code>、<code>bad_request_response</code>、<code>unauthorized_response</code>、<code>forbidden_response</code>、<code>not_found_response</code>、<code>error_response(message, status, data)</code>、<code>server_error_response</code>。约定：code 0 成功 / 1 客户端错误 / 2 服务器错误</td></tr>
        <tr><td><code>exceptions.py</code></td><td>DRF 异常处理器，见上</td></tr>
        <tr><td><code>permissions.py</code></td><td><code>check_owner(request, owner_pk)</code>：<code>is_staff</code> 直接放行；否则 <code>request.user.pk != owner_pk</code> 抛 <code>PermissionDenied</code></td></tr>
        <tr><td><code>middleware.py</code></td><td><code>DisableCSRFForAPI</code>：路径以 <code>/api/</code> 或 <code>/auth/</code> 开头时设 <code>_dont_enforce_csrf_checks</code></td></tr>
        <tr><td><code>kclient.py</code></td><td><code>KubeClient(kubeconfig_str)</code>：<code>yaml.safe_load</code> → <code>config.new_client_from_config_dict</code> → <code>self.core</code>（CoreV1Api）、<code>self.apps</code>（AppsV1Api）。提供各资源 get/list/create/patch/delete、<code>apply_yaml</code>、<code>get_resource_yaml</code>、<code>restart_deployment/daemonset</code></td></tr>
        <tr><td><code>__init__.py</code></td><td>导出 <code>Request</code> 类型，供 view 做类型标注 <code>request: common.Request</code></td></tr>
        <tr><td><code>ctypto.py</code>、<code>pdfgen.py</code></td><td>空文件，预留</td></tr>
      </table></div>
    </section>

    <section id="db">
      <h2>3.6 两个数据库与路由</h2>
<pre><code>class AppRouter:
    ROUTES = {'kcore': 'default', 'vigil': 'vigil'}
    db_for_read / db_for_write → ROUTES.get(app_label)   <span class="c"># autotf、auth 等不在表里 → None → 用 default</span>
    allow_migrate(db, app_label) → app 在表里则只能迁到对应库；其余只能迁到 default</code></pre>
      <div class="table-wrap"><table>
        <tr><th>库</th><th>引擎</th><th>放什么</th><th>迁移命令</th></tr>
        <tr><td><code>default</code></td><td>SQLite <code>db.sqlite3</code></td><td>kcore（User、KubeCluster）、autotf（TerraformConfig、TerraformTool、ScanReport）、Django 内置（auth、session、admin、contenttypes）</td><td><code>manage.py migrate</code></td></tr>
        <tr><td><code>vigil</code></td><td>PostgreSQL（Docker 容器 <code>pg</code>）</td><td><code>vigil_detectionrecord</code> 分区表</td><td><code>manage.py migrate --database=vigil</code></td></tr>
      </table></div>
      <p>为什么拆两个库：检测记录量大、要按天分区和自动删除，适合 PostgreSQL；其余数据很少，SQLite 足够且免维护。代价是跨库没有外键（检测记录不关联用户）。</p>
      <p>常用的看库命令：</p>
<pre class="on-prod"><code>sqlite3 <span class="vp">/srv/netsentinel/prod</span>/apps/backend/db.sqlite3 ".tables"
sqlite3 <span class="vp">/srv/netsentinel/prod</span>/apps/backend/db.sqlite3 "select id,username,is_staff,is_active from kcore_user;"
docker exec -it pg psql -U vigil vigil            <span class="c"># 进入 psql，\d+ vigil_detectionrecord 看结构，\q 退出</span></code></pre>
    </section>

    <section id="kcore">
      <h2>3.7 kcore：用户与集群</h2>
      <h3>models.py</h3>
      <ul>
        <li><code>User(AbstractUser)</code>：在 Django 内置用户上加 <code>email</code> 唯一、<code>created_at</code>；<code>id</code> 是 AutoField。<code>is_staff</code> = 管理员，<code>is_active</code> = 是否可登录。</li>
        <li><code>KubeCluster</code>：<code>owner</code>（FK User，CASCADE）、<code>name</code>、<code>kubeconfig</code>（TextField 明文）、<code>is_active</code>、<code>last_synced_at</code>（目前没人写它）、<code>created_at</code>；<code>unique_together(owner, name)</code>。</li>
      </ul>
      <h3>urls.py → views.py</h3>
      <div class="table-wrap"><table>
        <tr><th>URL（前缀 <code>/api/kcore/</code>）</th><th>View</th><th>方法与权限</th></tr>
        <tr><td><code>users/me/</code></td><td><code>UserMe</code></td><td>GET 登录即可</td></tr>
        <tr><td><code>users/</code></td><td><code>UserList</code></td><td>GET 仅管理员（<code>IsAdminUser</code>）；POST <b>任何人</b>（<code>AllowAny</code>，注册）</td></tr>
        <tr><td><code>users/&lt;pk&gt;/</code></td><td><code>UserDetail</code></td><td>GET / PUT / DELETE，本人或管理员</td></tr>
        <tr><td><code>users/&lt;pk&gt;/clusters/</code></td><td><code>KubeClusterList</code></td><td>GET / POST，本人或管理员</td></tr>
        <tr><td><code>clusters/&lt;pk&gt;/</code></td><td><code>KubeClusterDetail</code></td><td>GET / PUT / DELETE，集群 owner 或管理员</td></tr>
        <tr><td><code>clusters/&lt;id&gt;/resources/&lt;type&gt;/</code></td><td><code>KubeResourceList</code></td><td>GET 列表；POST 创建；PUT 更新；DELETE 删除（name 在 body）</td></tr>
        <tr><td><code>clusters/&lt;id&gt;/resources/&lt;type&gt;/&lt;name&gt;/</code></td><td><code>KubeResourceDetail</code></td><td>GET 返回 <code>{yaml}</code>；POST = 重启（<code>{namespace, force}</code>）；DELETE</td></tr>
        <tr><td><code>clusters/&lt;id&gt;/apply/</code></td><td><code>KubeApply</code></td><td>POST <code>{yaml}</code> → <code>{results: [{kind,name,status,message?}]}</code></td></tr>
      </table></div>
      <h3>kclient.py 的三个要点</h3>
      <ul>
        <li><b>每次请求都新建客户端</b>：<code>KubeResourceService(cluster)</code> 构造时解析 kubeconfig。简单但有开销，集群不可达时每个请求都要等超时。</li>
        <li><b><code>apply_yaml</code></b>：<code>yaml.safe_load_all</code> 逐文档 → <code>DynamicClient.resources.get(api_version, kind)</code> → <code>server_side_apply(field_manager='netsentinel', force_conflicts=True)</code>；旧版客户端没有这个方法时退回 patch，再不行 create。每个文档的成功失败单独记录，一个失败不影响其他。</li>
        <li><b>重启</b>：普通重启 = patch <code>spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] = 当前 UTC</code>（和 <code>kubectl rollout restart</code> 一样）；强制 = 读出 selector 的 <code>match_labels</code>，把匹配的 Pod 以 0 秒宽限期删除。</li>
      </ul>
      <h3>consumers.py：Pod 日志</h3>
      <p><code>PodLogConsumer.connect()</code> 立即 accept，然后在一个<b>线程</b>里调用 <code>read_namespaced_pod_log(follow=True, _preload_content=False)</code> 逐行读取，用 <code>loop.call_soon_threadsafe(queue.put_nowait, line)</code> 交回事件循环，再 <code>send({"log": line})</code>。断开时把 <code>_streaming</code> 置 False 让线程退出。没有任何鉴权。</p>
      <h3>管理命令</h3>
      <ul>
        <li><code>users_init</code>：创建 admin（staff + superuser）/ alice / bob，已存在则跳过。</li>
        <li><code>users_clear</code>：<b>删除全部用户</b>（<code>User.objects.all().delete()</code>），连带所有集群和 Terraform 配置，也包括 <code>vigil-bridge</code> 服务账号——之后必须重新 <code>generate_bridge_token --write-env</code> 并重启。</li>
      </ul>
    </section>

    <section id="autotf">
      <h2>3.8 autotf：Terraform 扫描与部署</h2>
      <h3>三个模型</h3>
      <div class="table-wrap"><table>
        <tr><th>模型</th><th>关键字段</th></tr>
        <tr><td><code>TerraformConfig</code></td><td><code>owner</code>、<code>name</code>（与 owner 联合唯一）、<code>file</code>（FileField，<code>upload_to='terraform/'</code>）、<code>is_scanned</code>、<code>last_apply_at / status / output</code></td></tr>
        <tr><td><code>TerraformTool</code></td><td><code>name</code>（唯一）、<code>version</code>、<code>is_enabled</code>、<code>cmd</code>、<code>init_cmd</code>、<code>output_format</code>（json / sarif）、JSON 映射字段 7 个</td></tr>
        <tr><td><code>ScanReport</code></td><td><code>config</code>（<b>一对一</b>，每个配置只保留最新一份报告）、<code>tools</code>（多对多）、<code>status</code>（pending / running / done / failed）、<code>result</code>（JSON）、<code>scanned_at</code></td></tr>
      </table></div>
      <h3>扫描流程 <code>ScanService._execute()</code></h3>
      <ol>
        <li><code>update_or_create</code> 报告 → status=pending，设置工具 → status=running；<code>config.is_scanned=False</code>。</li>
        <li>建临时目录，把 .tf 内容写成 <code>main.tf</code>。</li>
        <li>对每个工具 <code>_run_tool(tool, tmpdir, tf_path)</code>：
          <ul>
            <li><code>cmd</code> 里的 <code>{target_dir}</code>、<code>{target_file}</code> 被替换，然后 <b><code>.split()</code></b> 成参数列表（所以参数里不能有空格）。</li>
            <li>PATH 前面加上 <code>settings.AUTOTF_TOOLS_BIN</code>（默认 <code>/srv/netsentinel/tools/checkov/bin</code>，checkov 在那里）。</li>
            <li>有 <code>init_cmd</code> 先跑它（terraform_validate 需要先 <code>terraform init -backend=false</code>）。</li>
            <li>运行命令，只取 stdout；找不到可执行文件 → <code>{'items': [], 'error': 'tool not found: xxx'}</code>。<b>没有超时</b>，工具卡住整个请求就卡住。</li>
            <li>按 <code>output_format</code> 调 <code>_parse_sarif</code> 或 <code>_parse_json</code>。</li>
          </ul></li>
        <li>汇总 <code>result = {summary: {high, medium, low}, tools: {名字: {items: [...]}}}</code>，status=done，<code>is_scanned=True</code>。中途异常 → status=failed。</li>
      </ol>
      <h3>两种解析器</h3>
      <p><b>SARIF</b>（checkov / tfsec / trivy）：遍历 <code>runs[].results[]</code>，<code>level</code> 映射 error→HIGH、warning→MEDIUM、note/none→LOW；描述优先取规则的 <code>shortDescription.text</code>；位置取 <code>locations[0].physicalLocation</code> 的 <code>uri:startLine</code>。</p>
      <p><b>JSON</b>（terraform validate / tflint）：靠工具记录里的映射字段，支持点号路径（<code>range.start.line</code>，遇到列表可用数字下标）：</p>
      <div class="table-wrap"><table>
        <tr><th>字段</th><th>terraform_validate</th><th>tflint</th></tr>
        <tr><td><code>items_path</code>（问题数组在哪）</td><td><code>diagnostics</code></td><td><code>issues</code></td></tr>
        <tr><td><code>severity_field</code></td><td><code>severity</code></td><td><code>rule.severity</code></td></tr>
        <tr><td><code>severity_map</code></td><td><code>{"error":"HIGH","warning":"MEDIUM"}</code></td><td><code>{"error":"HIGH","warning":"MEDIUM","notice":"LOW"}</code></td></tr>
        <tr><td><code>rule_id_field</code></td><td><code>address</code></td><td><code>rule.name</code></td></tr>
        <tr><td><code>description_field</code></td><td><code>summary</code></td><td><code>message</code></td></tr>
        <tr><td><code>location_file_field</code> / <code>_line_field</code></td><td><code>range.filename</code> / <code>range.start.line</code></td><td>同左</td></tr>
      </table></div>
      <p>新增一个 JSON 输出的工具时，先手动跑一遍看它的 JSON 结构，再照这张表填映射。</p>
      <h3>部署 <code>ApplyService.apply()</code></h3>
      <p>先检查：有报告、status=done、<code>summary.high == 0</code>，否则抛 <code>ValidationError</code>（400）。然后临时目录里 <code>TF_BIN init -input=false</code>（120 秒）→ <code>TF_BIN apply -auto-approve -input=false</code>（300 秒），stdout+stderr 拼进 <code>last_apply_output</code>。</p>
      <h3>HTML / PDF 报告</h3>
      <p><code>ScanReportHTMLView</code>、<code>ScanReportPDFView</code> 是普通 Django <code>View</code>（不是 DRF），用 <code>_user_from_query_token()</code> 从 <code>?token=</code> 解析 <code>AccessToken</code> 得到用户，再做 owner 检查。HTML 由 <code>_render_report_html()</code> 拼字符串，PDF 由 <code>_render_report_pdf()</code> 用 reportlab 画。</p>
      <h3>管理命令</h3>
      <ul>
        <li><code>autotf_init</code>：建 <code>apps/backend/terraform/</code> 目录；对 5 个工具 <code>update_or_create</code>，版本通过执行 <code>--version</code> 获得（找不到记 unknown）。<b>会覆盖</b>你在网页上改过的工具命令。</li>
        <li><code>autotf_clear</code>：删除全部配置、报告，<b>并删除整个 <code>apps/backend/terraform/</code> 目录</b>。</li>
      </ul>
      <h3>迁移历史</h3>
      <p>0001 初始 → 0002 工具加 cmd 字段 → 0003 配置加 apply 字段 → 0004 改 output_format → 0005 改 owner → 0006 恢复 owner 外键约束。</p>
    </section>

    <section id="vigil">
      <h2>3.9 vigil：文件地图</h2>
      <p>检测的原理和数据流在<a href="/help/detect">《检测链路与模型》</a>细讲，这里只给文件地图：</p>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>作用</th></tr>
        <tr><td><code>apps.py</code></td><td><code>ready()</code> 中按条件启动 bridge</td></tr>
        <tr><td><code>bridge.py</code></td><td>入口 A：Kafka 消费线程 + drainer 线程 + <code>compute_flow()</code> 特征计算</td></tr>
        <tr><td><code>services.py</code></td><td><code>detect_flow()</code>、<code>detect_batch()</code>、<code>get_stats()</code>、<code>list_models()</code></td></tr>
        <tr><td><code>views.py</code> / <code>urls.py</code></td><td><code>detect/</code>、<code>detect/batch/</code>（POST）、<code>records/</code>、<code>records/&lt;pk&gt;/</code>、<code>stats/</code>、<code>models/</code>（GET），全部需要登录</td></tr>
        <tr><td><code>serializers.py</code></td><td><code>FlowInputSerializer</code>（35 特征 + 可选 <code>model</code>、<code>aggregation_ms</code>、<code>label</code>）、<code>BatchFlowInputSerializer</code>（<code>flows</code> + <code>model</code>）、<code>DetectionRecordSerializer</code>（全字段）</td></tr>
        <tr><td><code>models.py</code></td><td><code>DetectionRecord</code>，<code>managed = False</code>（表由手写 SQL 建）</td></tr>
        <tr><td><code>migrations/0001_initial.py</code></td><td>RunSQL：建分区父表 + 3 个索引 + 91 个日分区</td></tr>
        <tr><td><code>consumers.py</code> / <code>routing.py</code></td><td>入口 B：<code>ws/detector/push/</code>，Bearer 共享密钥</td></tr>
        <tr><td><code>detection/</code></td><td><code>base.py</code>（输入输出数据类、抽象基类、<code>flow_from_dict</code>）、<code>registry.py</code>（注册表、<code>run_all</code> / <code>run_one</code>）、<code>ads_ml/</code>（AdsMLModel）、<code>example_threshold.py</code>（示例，未注册）</td></tr>
        <tr><td><code>ingest/</code></td><td><code>bridge.py</code>（Kafka 消费线程）、<code>features.py</code>（五元组聚合、35 个特征）</td></tr>
        <tr><td><code>response/</code></td><td><code>cilium.py</code>（生成 Cilium 封禁策略）</td></tr>
                <tr><td><code>management/commands/</code></td><td><code>generate_bridge_token</code>、<code>rotate_partitions</code></td></tr>
        <tr><td><code>tests.py</code></td><td>单元测试</td></tr>
      </table></div>
    </section>

    <section id="cmds">
      <h2>3.10 manage.py 命令速查</h2>
<pre class="on-both"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>/apps/backend      # 开发；操作线上数据时换成 <span class="vp">/srv/netsentinel/prod</span>/apps/backend</code></pre>
      <div class="table-wrap"><table>
        <tr><th>命令</th><th>做什么</th></tr>
        <tr><td><code>../../.venv/bin/python manage.py check</code></td><td>检查配置和代码能否加载，改完代码先跑它</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py showmigrations</code></td><td>看哪些迁移已执行</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py makemigrations [app]</code></td><td>根据 models 变化生成迁移文件</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py sqlmigrate &lt;app&gt; &lt;编号&gt;</code></td><td>看迁移会执行的 SQL</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py migrate</code> / <code>--database=vigil</code></td><td>执行迁移（两个库要分别执行）</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py shell</code></td><td>Django 交互环境（不会启动 bridge）</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py shell -c "..."</code></td><td>执行一行 Python</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py dbshell --database=vigil</code></td><td>直接进 psql（需本机有 psql 客户端；没有就用 <code>docker exec -it pg psql -U vigil vigil</code>）</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py createsuperuser</code> / <code>changepassword &lt;u&gt;</code></td><td>建超级用户 / 改密码</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py users_init</code> / <code>users_clear</code></td><td>初始化 / 清空用户</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py autotf_init</code> / <code>autotf_clear</code></td><td>初始化 / 清空 Terraform 数据</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py generate_bridge_token [--username vigil-bridge] [--years 10] [--write-env]</code></td><td>生成长期 JWT 并写入 <code>apps/backend/backend/.env</code>（需重启服务生效）</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py rotate_partitions [--database vigil] [--dry-run]</code></td><td>建明天分区、删 90 天前的分区（<code>/etc/cron.d/netsentinel</code> 每天 0 点以 netsentinel 账户跑）</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py test kcore autotf</code></td><td>跑单元测试：145 个用例，约 5 分钟（2026-10-18 全部通过）。测试库为临时 SQLite，不影响线上数据</td></tr>
        <tr><td><code>../../.venv/bin/python manage.py runserver 8090</code></td><td>开发服务器（只在 <code class="vn">/home/NEWUSER/github/knettf</code> 里跑；8000 被别的项目占用）。<b>会启动 bridge</b>，见 <a href="#start">进程是怎么起来的</a></td></tr>
      </table></div>
    </section>

    <section id="practice">
      <h2>3.11 新增一个接口的步骤</h2>
      <p>目标：<code>GET /api/vigil/top-sources/?limit=5</code> 返回攻击次数最多的源 IP。</p>
      <div class="steps">
        <div class="step"><div class="step-title">service：<code>vigil/services.py</code> 末尾加</div>
<pre><code>def top_attack_sources(limit: int = 5) -&gt; list[dict]:
    from django.db.models import Count
    return list(
        DetectionRecord.objects.filter(is_attack=True)
        .values("src_ip").annotate(count=Count("id")).order_by("-count")[:limit]
    )</code></pre></div>
        <div class="step"><div class="step-title">view：<code>vigil/views.py</code> 加</div>
<pre><code>class TopSourcesView(APIView, ResponseMixin):
    def get(self, request: common.Request):
        limit = min(int(request.query_params.get("limit", 5)), 50)
        return self.success_response({"sources": services.top_attack_sources(limit)})</code></pre>
          <p>没写 <code>permission_classes</code> 就沿用默认 <code>IsAuthenticated</code>。</p></div>
        <div class="step"><div class="step-title">url：<code>vigil/urls.py</code> 加</div>
<pre><code>path("top-sources/", views.TopSourcesView.as_view(), name="vigil-top-sources"),</code></pre></div>
        <div class="step"><div class="step-title">检查并重启</div>
<pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>/apps/backend &amp;&amp; ../../.venv/bin/python manage.py check
../../.venv/bin/python manage.py runserver 8090      # runserver 改代码自动重载</code></pre></div>
        <div class="step"><div class="step-title">用 curl 验证</div>
<pre><code>TOKEN=$(curl -s -X POST localhost:8090/api/auth/token/ -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"&lt;密码&gt;"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')
curl -s "localhost:8090/api/vigil/top-sources/?limit=3" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool</code></pre>
          <div class="expect">预期：<code>{"status":"success","code":0,"message":"Success","data":{"sources":[{"src_ip":"192.168.100.23","count":...}]}}</code></div></div>
        <div class="step"><div class="step-title">写测试（可选但推荐）</div><p>参照 <code>vigil/tests.py</code> 的写法加一个用例。</p></div>
        <div class="step"><div class="step-title">提交并上线</div><pre class="on-both"><code>cd /home/NEWUSER/github/knettf &amp;&amp; git add -A &amp;&amp; git commit -m "vigil: top-sources 接口" &amp;&amp; git push
<span class="c"># PR 合并到 main 后</span>
/srv/netsentinel/prod/ops/scripts/deploy.sh -backend</code></pre></div>
      </div>
      <h3>改数据库结构的流程</h3>
      <ul>
        <li><b>kcore / autotf</b>（SQLite）：在 <code class="vn">/home/NEWUSER/github/knettf</code> 改 models.py → <code>makemigrations</code> → <code>sqlmigrate</code> 看 SQL → 在开发库 <code>migrate</code> 试 → 提交 → 备份线上 <code class="vp">/srv/netsentinel/prod/apps/backend/db.sqlite3</code> → PR 合并后 <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend</code>（自动 migrate default）。</li>
        <li><b>vigil</b>（<code>managed=False</code>）：改 models.py 只生成不执行 SQL 的状态迁移。真正改表要在迁移里加 <code>migrations.RunSQL("ALTER TABLE vigil_detectionrecord ADD COLUMN ...", reverse_sql=...)</code>；对父表的 ALTER 自动作用于所有分区。先在开发库（<code>vigil_dev</code>）<code>migrate --database=vigil</code> 试，部署后再在 <code class="vp">/srv/netsentinel/prod</code> 里对线上库执行。</li>
      </ul>
    </section>
  </div>
</template>

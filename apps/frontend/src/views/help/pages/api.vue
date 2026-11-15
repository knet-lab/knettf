<template>
  <div v-pre>
        <h1>7 API 逐接口说明</h1>
    <div class="meta">基址：本机 <code>http://localhost:8080</code>，公网 <code>https://knettf.com</code>（cloudflared）。全部路由定义在 <code>apps/backend/backend/urls.py</code> 及各 app 的 <code>urls.py</code>；WebSocket 路由在 <code>apps/backend/asgi.py</code>。</div>

    <section id="conv">
      <h2>7.1 通用约定</h2>
      <h3>认证</h3>
      <ul>
        <li>默认所有 <code>/api/</code> 接口需要 JWT：Header <code>Authorization: Bearer &lt;access&gt;</code>（<code>settings.REST_FRAMEWORK</code> 默认 <code>IsAuthenticated</code>）。</li>
        <li>access 有效期 <b>2 小时</b>，refresh 有效期 <b>7 天</b>（<code>SIMPLE_JWT</code>）。前端 <code>stores/auth.ts</code> 遇 401 自动用 refresh 换新 access。</li>
        <li>例外：<code>POST /api/auth/token/</code>、<code>POST /api/auth/token/refresh/</code>、<code>POST /api/kcore/users/</code>（注册）无需登录；报告 HTML / PDF 用 URL 参数 <code>?token=</code>。</li>
        <li>CSRF：<code>common/middleware.py</code> 对 <code>/api/</code> 关闭 CSRF 校验。</li>
      </ul>
      <h3>权限</h3>
      <ul>
        <li><b>本人或管理员</b>：<code>common/permissions.py check_owner()</code>：<code>request.user.is_staff</code> 直接放行，否则资源 owner 必须等于当前用户，不符返回 403。</li>
        <li><b>仅管理员</b>：<code>is_staff=True</code>。</li>
        <li><b>登录即可</b>：vigil 全部接口，不区分用户（检测记录是全局共享的）。</li>
      </ul>
      <h3>统一响应格式（<code>common/response.py</code>）</h3>
      <pre><code><span class="c">// 成功（200 / 201）</span>
{ "status": "success", "code": 0, "message": "Success", "data": { ... } }
<span class="c">// 客户端错误（400 / 401 / 403 / 404）</span>
{ "status": "error", "code": 1, "message": "错误说明", "data": null }
<span class="c">// 服务端错误（500）</span>
{ "status": "error", "code": 2, "message": "Internal Server Error", "data": null }</code></pre>
      <p>DRF 抛出的异常（校验失败、403、404）由 <code>common/exceptions.py</code> 统一包装，<code>message</code> 为 <code>str(exc.detail)</code>。<b>例外</b>：登录 / 刷新接口直接返回 simplejwt 的原始 JSON（不包装）；报告 HTML / PDF 返回文件。</p>
      <h3>快速获取 token</h3>
      <pre><code>TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/kcore/users/me/</code></pre>
    </section>

    <section id="index">
      <h2>7.2 端点总表</h2>
      <div class="table-wrap"><table>
        <tr><th>方法</th><th>路径</th><th>作用</th><th>权限</th><th>View</th></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/auth/token/</code></td><td>登录</td><td>公开</td><td>simplejwt <code>TokenObtainPairView</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/auth/token/refresh/</code></td><td>刷新 access</td><td>公开</td><td><code>TokenRefreshView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/kcore/users/me/</code></td><td>当前用户</td><td>登录</td><td><code>kcore.UserMe</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span></td><td><code>/api/kcore/users/</code></td><td>用户列表 / 注册</td><td>GET 管理员；POST 公开</td><td><code>UserList</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-put">PUT</span> <span class="m m-delete">DELETE</span></td><td><code>/api/kcore/users/&lt;pk&gt;/</code></td><td>用户详情 / 修改 / 删除</td><td>本人或管理员</td><td><code>UserDetail</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span></td><td><code>/api/kcore/users/&lt;pk&gt;/clusters/</code></td><td>用户的集群列表 / 添加集群</td><td>本人或管理员</td><td><code>KubeClusterList</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-put">PUT</span> <span class="m m-delete">DELETE</span></td><td><code>/api/kcore/clusters/&lt;pk&gt;/</code></td><td>集群详情 / 修改 / 删除</td><td>本人或管理员</td><td><code>KubeClusterDetail</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span> <span class="m m-put">PUT</span> <span class="m m-delete">DELETE</span></td><td><code>/api/kcore/clusters/&lt;id&gt;/resources/&lt;type&gt;/</code></td><td>K8s 资源列表 / 创建 / 更新 / 删除</td><td>本人或管理员</td><td><code>KubeResourceList</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span> <span class="m m-delete">DELETE</span></td><td><code>/api/kcore/clusters/&lt;id&gt;/resources/&lt;type&gt;/&lt;name&gt;/</code></td><td>取 YAML / 重启 / 删除</td><td>本人或管理员</td><td><code>KubeResourceDetail</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/kcore/clusters/&lt;id&gt;/apply/</code></td><td>apply 原始 YAML</td><td>本人或管理员</td><td><code>KubeApply</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span></td><td><code>/api/autotf/users/&lt;pk&gt;/tf-configs/</code></td><td>配置列表 / 上传文件创建</td><td>本人或管理员</td><td><code>TerraformConfigList</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/autotf/users/&lt;pk&gt;/tf-configs/text/</code></td><td>在线编辑器创建</td><td>本人或管理员</td><td><code>TerraformConfigTextCreate</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-put">PUT</span> <span class="m m-delete">DELETE</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/</code></td><td>配置详情 / 修改 / 删除</td><td>本人或管理员</td><td><code>TerraformConfigDetail</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/content/</code></td><td>读 .tf 文本</td><td>本人或管理员</td><td><code>TerraformConfigContent</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/scan/</code></td><td>用全部启用工具扫描</td><td>本人或管理员</td><td><code>TerraformConfigFullScan</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/scan/manual/</code></td><td>指定工具扫描</td><td>本人或管理员</td><td><code>TerraformConfigManualScan</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/apply/</code></td><td>terraform init + apply</td><td>本人或管理员</td><td><code>TerraformConfigApply</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-delete">DELETE</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/report/</code></td><td>扫描报告 JSON / 删除报告</td><td>本人或管理员</td><td><code>ScanReportDetail</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/report/html/?token=</code></td><td>报告 HTML</td><td>仅 owner（管理员也不行）</td><td><code>ScanReportHTMLView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/autotf/tf-configs/&lt;pk&gt;/report/pdf/?token=</code></td><td>报告 PDF 下载</td><td>仅 owner</td><td><code>ScanReportPDFView</code></td></tr>
        <tr><td><span class="m m-get">GET</span> <span class="m m-post">POST</span></td><td><code>/api/autotf/tf-tools/</code></td><td>工具列表 / 新增工具</td><td>GET 登录；POST 管理员</td><td><code>TerraformToolList</code></td></tr>
        <tr><td><span class="m m-patch">PATCH</span> <span class="m m-delete">DELETE</span></td><td><code>/api/autotf/tf-tools/&lt;id&gt;/</code></td><td>修改 / 删除工具</td><td>管理员</td><td><code>TerraformToolDetail</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/vigil/detect/</code></td><td>单条流检测</td><td>登录</td><td><code>vigil.DetectView</code></td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/vigil/detect/batch/</code></td><td>批量检测</td><td>登录</td><td><code>DetectBatchView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/vigil/records/</code></td><td>检测记录分页查询</td><td>登录</td><td><code>RecordsView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/vigil/records/&lt;pk&gt;/</code></td><td>单条记录</td><td>登录</td><td><code>RecordDetailView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/vigil/stats/</code></td><td>统计汇总</td><td>登录</td><td><code>StatsView</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>/api/vigil/models/</code></td><td>已注册模型</td><td>登录</td><td><code>ModelsView</code></td></tr>
        <tr><td><span class="m m-ws">WS</span></td><td><code>/ws/clusters/&lt;id&gt;/pods/&lt;ns&gt;/&lt;pod&gt;/logs/</code></td><td>Pod 日志实时流</td><td><b>无鉴权</b></td><td><code>kcore.PodLogConsumer</code></td></tr>
        <tr><td><span class="m m-ws">WS</span></td><td><code>/ws/detector/push/</code></td><td>原入口 B 检测器推送结果（已停用，保留未用）</td><td>Bearer = <code>VIGIL_BRIDGE_TOKEN</code></td><td><code>vigil.DetectorPushConsumer</code></td></tr>
        <tr><td>—</td><td><code>/admin/</code></td><td>Django Admin</td><td>superuser</td><td><code>django.contrib.admin</code></td></tr>
        <tr><td>—</td><td>其余非 <code>api/ admin/ static/ ws/</code> 路径</td><td>返回 <code>apps/frontend/dist/index.html</code>（Vue 路由接管）</td><td>公开</td><td><code>urls.spa_view</code></td></tr>
      </table></div>
    </section>

    <section id="auth">
      <h2>7.3 认证 auth</h2>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/auth/token/</code><span class="perm">公开</span></div>
        <p>请求体（JSON 或 form）：<code>username</code>、<code>password</code>。成功返回<b>未包装</b>的 JSON：</p>
        <pre><code>{ "refresh": "eyJ...", "access": "eyJ..." }</code></pre>
        <p>失败：401 <code>{"status":"error","code":1,"message":"No active account found with the given credentials"}</code>。access 的 payload 含 <code>user_id</code>。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/auth/token/refresh/</code><span class="perm">公开</span></div>
        <p>请求：<code>{"refresh": "eyJ..."}</code> → 返回 <code>{"access": "eyJ..."}</code>。refresh 过期（7 天）后只能重新登录。</p>
      </div>
    </section>

    <section id="kcore-user">
      <h2>7.4 kcore · 用户</h2>
      <p>代码：<code>apps/backend/kcore/views.py</code>（UserMe / UserList / UserDetail）→ <code>services.UserService</code> → 模型 <code>User</code>。用户对象输出字段（<code>UserResponseSerializer</code>）：<code>id, username, email, is_staff</code>。</p>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/kcore/users/me/</code><span class="perm">登录</span></div>
        <pre><code>{ "status":"success","code":0,"message":"Success",
  "data": { "id": 1, "username": "admin", "email": "admin@netsentinel.dev", "is_staff": true } }</code></pre>
        <p>前端登录后调用此接口确定 <code>is_staff</code>，决定能否进 <code>/admin</code>。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/kcore/users/</code><span class="perm">管理员</span></div>
        <p>返回全部用户数组。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/kcore/users/</code><span class="perm">公开（注册）</span></div>
        <p>请求：<code>{"username":"carol","email":"carol@x.com","password":"..."}</code>。username、email 唯一，重复返回 400（<code>Username already exists</code> / <code>Email already exists</code>）。密码经 <code>set_password</code> 哈希存储。返回 201 + 用户对象。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-put">PUT</span><span class="m m-delete">DELETE</span><code>/api/kcore/users/&lt;pk&gt;/</code><span class="perm">本人或管理员</span></div>
        <ul>
          <li>PUT 只接受 <code>username</code>、<code>email</code>（都可选），<b>不能改密码</b>；改密码需 Django Admin 或 <code>manage.py changepassword &lt;user&gt;</code>。</li>
          <li>DELETE 会级联删除该用户的集群（<code>KubeCluster</code>）和 Terraform 配置（含扫描报告）。</li>
          <li>不存在返回 404。</li>
        </ul>
      </div>
    </section>

    <section id="kcore-cluster">
      <h2>7.5 kcore · 集群</h2>
      <p>集群对象输出（<code>KubeClusterResponseSerializer</code>）：<code>id, name, owner{...}, kubeconfig, is_active, last_synced_at, created_at</code>。<b>注意：响应包含完整 kubeconfig 明文</b>。</p>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-post">POST</span><code>/api/kcore/users/&lt;pk&gt;/clusters/</code><span class="perm">本人或管理员</span></div>
        <p>POST 请求：<code>{"name":"lab","kubeconfig":"&lt;/home/NEWUSER/.kube/config 全文&gt;"}</code>；同一用户下 name 唯一。创建时不校验 kubeconfig 能否连通，连不上的错误会在调用资源接口时才出现（502）。</p>
        <pre><code>curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  http://localhost:8080/api/kcore/users/1/clusters/ \
  -d "$(python3 -c 'import json,os;print(json.dumps({"name":"lab","kubeconfig":open(os.path.expanduser("~/.kube/config")).read()}))')"</code></pre>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-put">PUT</span><span class="m m-delete">DELETE</span><code>/api/kcore/clusters/&lt;pk&gt;/</code><span class="perm">本人或管理员</span></div>
        <p>PUT 可改 <code>name</code>、<code>kubeconfig</code>（都可选）。<b>集群重建后证书变化，必须用 PUT 更新 kubeconfig</b>，否则所有资源接口报 502。</p>
      </div>
    </section>

    <section id="kcore-res">
      <h2>7.6 kcore · K8s 资源</h2>
      <p>代码：<code>KubeResourceList</code> / <code>KubeResourceDetail</code> / <code>KubeApply</code> → <code>services.KubeResourceService</code> → <code>common/kclient.py KubeClient</code>（kubernetes Python 客户端，用集群记录中的 kubeconfig 建连）。</p>
      <p><code>&lt;type&gt;</code> 取值：<code>namespaces</code>、<code>pods</code>、<code>deployments</code>、<code>services</code>、<code>configmaps</code>、<code>daemonsets</code>。其他值返回 400 <code>Invalid resource type</code>。</p>
      <div class="table-wrap"><table>
        <tr><th>方法</th><th>路径</th><th>参数</th><th>支持的 type</th><th>返回</th></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>.../resources/&lt;type&gt;/</code></td><td>query <code>namespace</code>（namespaces 除外必填）</td><td>全部 6 种</td><td><code>{"resources":[...]}</code>（对象 <code>to_dict()</code>）</td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>.../resources/&lt;type&gt;/</code></td><td>namespaces：<code>{name}</code>；configmaps：<code>{namespace,name,data}</code>；deployments / services / daemonsets：<code>{namespace, ...K8s 对象体}</code></td><td>除 pods 外</td><td>201 <code>{"resource":{...}}</code></td></tr>
        <tr><td><span class="m m-put">PUT</span></td><td><code>.../resources/&lt;type&gt;/</code></td><td><code>{namespace, name, ...}</code>；configmaps 需 <code>data</code></td><td>deployments、services、configmaps、daemonsets</td><td><code>{"resource":{...}}</code></td></tr>
        <tr><td><span class="m m-delete">DELETE</span></td><td><code>.../resources/&lt;type&gt;/</code></td><td>body <code>{namespace, name}</code>；namespaces 只要 <code>{name}</code></td><td>全部</td><td><code>{"message":"Pod deleted"}</code></td></tr>
        <tr><td><span class="m m-get">GET</span></td><td><code>.../resources/&lt;type&gt;/&lt;name&gt;/</code></td><td>query <code>namespace</code></td><td>全部</td><td><code>{"yaml":"..."}</code>（动态客户端读取实时对象）</td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>.../resources/&lt;type&gt;/&lt;name&gt;/</code></td><td><code>{namespace, force?}</code></td><td>deployments、daemonsets</td><td>重启。<code>force=false</code>：打 <code>kubectl.kubernetes.io/restartedAt</code> 注解滚动重启；<code>force=true</code>：按 selector 立即删除全部 Pod（grace=0）</td></tr>
        <tr><td><span class="m m-delete">DELETE</span></td><td><code>.../resources/&lt;type&gt;/&lt;name&gt;/</code></td><td>body <code>{namespace}</code></td><td>全部</td><td>删除</td></tr>
        <tr><td><span class="m m-post">POST</span></td><td><code>/api/kcore/clusters/&lt;id&gt;/apply/</code></td><td><code>{"yaml":"多文档 YAML"}</code></td><td>任意 kind</td><td><code>{"results":[{"kind","name","status":"applied|error","message"?}]}</code>；任一失败整体返回 400 并带 results</td></tr>
      </table></div>
      <p>错误码：参数缺失 400；连接集群或 K8s API 报错 502（message 为异常文本）。</p>
    </section>

    <section id="autotf">
      <h2>7.7 autotf · Terraform</h2>
      <p>代码：<code>apps/backend/autotf/views.py</code> → <code>services.py</code>（TerraformConfigService / TerraformToolService / ScanReportService / ScanService / ApplyService）。</p>
      <h3>配置对象</h3>
      <p>列表（<code>TerraformConfigListSerializer</code>）：<code>id, name, is_scanned, created_at, updated_at, report, last_apply_at, last_apply_status, last_apply_output</code>；详情多一个 <code>file</code>（文件路径）。<code>report</code> 为摘要 <code>{id, status, tools[], scanned_at}</code> 或 <code>null</code>。</p>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/autotf/users/&lt;pk&gt;/tf-configs/</code><span class="perm">本人或管理员</span></div>
        <p><code>multipart/form-data</code>：<code>name</code>、<code>file</code>（.tf）。文件保存到 <code>apps/backend/terraform/</code>。同一用户下 name 唯一。</p>
        <pre><code>curl -X POST -H "Authorization: Bearer $TOKEN" -F name=demo -F file=@main.tf \
  http://localhost:8080/api/autotf/users/1/tf-configs/</code></pre>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/autotf/users/&lt;pk&gt;/tf-configs/text/</code><span class="perm">本人或管理员</span></div>
        <p>JSON：<code>{"name":"demo","content":"resource ... {}"}</code>，后端写成文件。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-put">PUT</span><span class="m m-delete">DELETE</span><code>/api/autotf/tf-configs/&lt;pk&gt;/</code><span class="perm">本人或管理员</span></div>
        <p>PUT 可选字段 <code>name</code>、<code>file</code>、<code>content</code>；<code>file</code> 与 <code>content</code> 二选一，全空返回 400。DELETE 同时删除文件与报告。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/autotf/tf-configs/&lt;pk&gt;/content/</code><span class="perm">本人或管理员</span></div>
        <p>返回 <code>{"content": ".tf 文本"}</code>。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/autotf/tf-configs/&lt;pk&gt;/scan/</code> · <code>/scan/manual/</code><span class="perm">本人或管理员</span></div>
        <ul>
          <li><code>scan/</code>：用所有 <code>is_enabled=True</code> 的工具；一个都没有返回 404 <code>No enabled tools available</code>。</li>
          <li><code>scan/manual/</code>：<code>{"tool_ids":[1,3]}</code>，非启用 ID 返回 400 <code>Tool IDs not available: [...]</code>。</li>
          <li><b>同步执行</b>：请求会阻塞到所有工具跑完（checkov / trivy 可能数十秒）。流程：报告置 <code>running</code> → 把 .tf 拷入临时目录 → 每个工具先跑 <code>init_cmd</code> 再跑 <code>cmd</code>（<code>{target_dir}</code>、<code>{target_file}</code> 占位符替换）→ 按 <code>output_format</code> 解析 JSON / SARIF → 统计 high / medium / low → 报告置 <code>done</code>，配置 <code>is_scanned=true</code>。异常时报告置 <code>failed</code>。</li>
          <li>工具不存在时该工具结果为 <code>{"items":[],"error":"tool not found: xxx"}</code>，不影响其他工具。</li>
          <li>返回完整报告（同 GET report）。</li>
        </ul>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/autotf/tf-configs/&lt;pk&gt;/apply/</code><span class="perm">本人或管理员</span></div>
        <p>前置检查（不满足返回 400）：已有报告；报告状态为 <code>done</code>；<code>summary.high == 0</code>。随后在临时目录执行 <code>TF_BIN init -input=false</code>（超时 120s）和 <code>TF_BIN apply -auto-approve -input=false</code>（超时 300s），结果写入 <code>last_apply_status / last_apply_output / last_apply_at</code>。</p>
        <div class="danger">临时目录用完即删，<b>terraform state 不保留</b>：每次 apply 都视为全新部署，无法 destroy 或增量变更。<code>TF_BIN</code> 由 <code>apps/backend/backend/.env</code> 的 <code>ENVIRONMENT</code> 决定（<code>linux_development</code> → <code>/usr/bin/terraform</code>）。</div>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-delete">DELETE</span><code>/api/autotf/tf-configs/&lt;pk&gt;/report/</code><span class="perm">本人或管理员</span></div>
        <pre><code>{ "id": 3, "status": "done", "scanned_at": "...", "tools": [ {工具对象}, ... ],
  "result": {
    "summary": { "high": 1, "medium": 4, "low": 2 },
    "tools": { "checkov": { "items": [ { "rule_id": "CKV_AWS_20", "severity": "HIGH",
                                         "description": "...", "location": "main.tf:12" } ] } } } }</code></pre>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/autotf/tf-configs/&lt;pk&gt;/report/html/?token=&lt;access&gt;</code> · <code>/report/pdf/?token=</code><span class="perm">仅 owner</span></div>
        <p>普通 Django View，供浏览器直接打开 / 下载；token 从 URL 读取。只认 owner，管理员访问他人报告也返回 403。PDF 文件名 <code>report_&lt;name&gt;.pdf</code>（reportlab 生成）。</p>
      </div>
      <h3>扫描工具</h3>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><span class="m m-post">POST</span><code>/api/autotf/tf-tools/</code><span class="perm">GET 登录（普通用户只看启用的）；POST 管理员</span></div>
        <p>工具字段：<code>name, version, is_enabled, cmd, init_cmd, output_format(json|sarif), items_path, severity_field, severity_map, rule_id_field, description_field, location_file_field, location_line_field</code>（含义见 <a href="/help/db#autotf">数据库页</a>）。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-patch">PATCH</span><span class="m m-delete">DELETE</span><code>/api/autotf/tf-tools/&lt;id&gt;/</code><span class="perm">管理员</span></div>
        <p>PATCH 为部分更新，例如 <code>{"is_enabled": false}</code> 停用某个工具。</p>
      </div>
    </section>

    <section id="vigil">
      <h2>7.8 vigil · 流量检测</h2>
      <p>代码：<code>apps/backend/vigil/views.py</code> → <code>services.py</code> → <code>detection/registry.py</code>（模型推理）→ <code>response/cilium.py</code>（动作建议）→ <code>models.DetectionRecord</code>（写 PostgreSQL）。</p>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/vigil/detect/</code><span class="perm">登录</span></div>
        <p>请求体是一条流的 35 个特征（<code>FlowInputSerializer</code>，必填只有 <code>src_ip</code>、<code>dst_ip</code>、<code>protocol</code>，其余缺省为 0），可选 <code>label</code>（"0"/"1"/""）、<code>model</code>（指定模型名，不填则跑全部已注册模型）。字段列表见 <a href="/help/db#features">特征表</a>。</p>
        <pre><code>curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  http://localhost:8080/api/vigil/detect/ -d '{
  "src_ip":"192.168.100.21","dst_ip":"192.168.100.11","protocol":"TCP",
  "src_port":40000,"dst_port":80,"flow_duration":500000,"total_packets":200,
  "fwd_packets":200,"packets_per_second":400,"syn_count":200,"syn_ratio":1.0,
  "is_tcp":1,"is_well_known_port":1,"label":"1"}'</code></pre>
        <p>响应 <code>data</code>：</p>
        <pre><code>{ "count": 1, "results": [ {
    "model_name": "ads_ml_ocsvm", "is_attack": true, "confidence": 0.8123,
    "attack_type": "DoS", "explanation": "OCSVM zsl_seen=..., zsl_sim=0.812",
    "raw_output": { "zsl_similarity": 0.8123, "zsl_attack": "DoS", "zsl_seen_status": "...",
                    "aggregation_ms": null, "inference_ms": 12.3 },
    "recommended_action": "alert",
    "record_id": 175016, "cilium_action": "alert", "cilium_reason": "OCSVM ...",
    "src_ip": "...", "dst_ip": "...", "src_port": 40000, "dst_port": 80, "protocol": "TCP",
    "created_at": "2026-10-16T09:30:00+00:00", "aggregation_ms": null, "inference_ms": 12.3 } ] }</code></pre>
        <p>错误：字段校验失败 400（message 为 errors 字符串）；指定了未注册模型 400 <code>Model 'x' not registered. Available: [...]</code>。<b>每次调用都会写入一条记录</b>，测试时请带 <code>label</code> 以便区分。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-post">POST</span><code>/api/vigil/detect/batch/</code><span class="perm">登录</span></div>
        <p>请求：<code>{"flows":[{...},{...}], "model": null}</code>。在一个数据库事务内逐条执行 <code>detect_flow</code>，任何一条出错整批回滚。响应同上，<code>results</code> 为所有流的结果拼接。入口 C（<code>K lab/collect/vigil_bridge.py</code>）调用此接口。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/vigil/records/</code><span class="perm">登录</span></div>
        <div class="table-wrap"><table>
          <tr><th>query 参数</th><th>说明</th><th>默认</th></tr>
          <tr><td><code>only_attacks</code></td><td><code>true</code> 只看攻击</td><td>false</td></tr>
          <tr><td><code>only_normal</code></td><td><code>true</code> 只看正常</td><td>false</td></tr>
          <tr><td><code>model_name</code></td><td>按模型过滤，如 <code>ads_ml_ocsvm</code></td><td>—</td></tr>
          <tr><td><code>attack_type</code></td><td>按攻击类型精确匹配</td><td>—</td></tr>
          <tr><td><code>time_from</code> / <code>time_to</code></td><td>ISO 时间，作用于 <code>created_at</code>（UTC）</td><td>—</td></tr>
          <tr><td><code>limit</code></td><td>每页条数，最大 500</td><td>50</td></tr>
          <tr><td><code>offset</code></td><td>偏移</td><td>0</td></tr>
        </table></div>
        <p>返回 <code>{"records":[DetectionRecord 全字段], "total": N, "offset": 0, "limit": 50}</code>，按 <code>created_at</code> 倒序。前端 <code>VigilLogView.vue</code> 每 15 秒轮询一次。</p>
        <pre><code>curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8080/api/vigil/records/?only_attacks=true&amp;limit=5&amp;time_from=2026-10-16T00:00:00Z'</code></pre>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/vigil/records/&lt;pk&gt;/</code><span class="perm">登录</span></div>
        <p>单条记录全部字段，含 <code>flow_input</code>（35 特征）与 <code>raw_output</code>。不存在返回 404。注意 id 在分区表中仍全局唯一（BIGSERIAL）。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/vigil/stats/</code><span class="perm">登录</span></div>
        <pre><code>{ "total": 175015, "attacks": 120000, "normal": 55015, "attack_rate": 0.6857,
  "by_attack_type": [ {"attack_type": "DoS", "count": 80000}, ... ],
  "by_model": [ {"model_name": "ads_ml_ocsvm", "count": 175015} ],
  "recent": [ 最近 10 条记录 ] }</code></pre>
        <p>对全表做 COUNT 和 GROUP BY，记录量很大时较慢。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-get">GET</span><code>/api/vigil/models/</code><span class="perm">登录</span></div>
        <p>返回 <code>{"models": ["ads_ml_ocsvm"]}</code>。若为空数组，说明 ads_ml 模型加载失败（后端日志有 <code>model ... not loaded</code>），此时检测接口返回空结果。</p>
      </div>
    </section>

    <section id="ws">
      <h2>7.9 WebSocket</h2>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-ws">WS</span><code>/ws/clusters/&lt;cluster_id&gt;/pods/&lt;namespace&gt;/&lt;pod&gt;/logs/</code><span class="perm">无鉴权</span></div>
        <p>连接后后端开线程调用 <code>read_namespaced_pod_log(follow=True)</code>，每行推送 <code>{"log": "一行日志\n"}</code>；Pod 结束则流结束。前端 <code>KcoreView.vue</code> 使用。</p>
      </div>
      <div class="endpoint">
        <div class="endpoint-head"><span class="m m-ws">WS</span><code>/ws/detector/push/</code><span class="perm">Header <code>Authorization: Bearer &lt;VIGIL_BRIDGE_TOKEN&gt;</code></span></div>
        <p>原入口 B（集群内检测器，已停用）使用，目前没有使用方。token 与 <code>settings.VIGIL_BRIDGE_TOKEN</code>（来自 <code>apps/backend/backend/.env</code>）字符串不一致或未配置时，以 code <b>4401</b> 关闭连接。</p>
        <p>客户端发送：</p>
        <pre><code>{ "results": [ { "src_ip": "...", "dst_ip": "...", "src_port": 0, "dst_port": 80, "protocol": "TCP",
                 "is_attack": true, "confidence": 0.8, "attack_type": "DoS",
                 "zsl_seen": "...", "zsl_top": {...}, "label": "1", ...其他特征 } ] }</code></pre>
        <p>服务端逐条构造 <code>DetectionResult</code>（model_name 固定为 <code>ads_ml_ocsvm</code>），计算 Cilium 动作后写库；不回发消息。</p>
      </div>
      <div class="note">没有向浏览器或 <code>monitor.py</code> 推送检测结果的 WebSocket，前端靠 REST 轮询。</div>
    </section>

    <section id="frontend">
      <h2>7.10 前端页面 → 接口</h2>
      <div class="table-wrap"><table>
        <tr><th>前端路由</th><th>组件</th><th>调用的接口</th><th>权限守卫</th></tr>
        <tr><td><code>/login</code></td><td><code>LoginView.vue</code></td><td><code>auth/token/</code> → <code>kcore/users/me/</code></td><td>公开</td></tr>
        <tr><td><code>/</code></td><td>重定向</td><td>—</td><td>—</td></tr>
        <tr><td><code>/kcore</code></td><td><code>KcoreView.vue</code> + <code>stores/kcore.ts</code></td><td><code>kcore/users/&lt;me&gt;/clusters/</code>、<code>clusters/&lt;id&gt;/resources/…</code>、<code>apply/</code>、WS Pod 日志</td><td>登录</td></tr>
        <tr><td><code>/autotf</code></td><td><code>AutoTFView.vue</code></td><td><code>autotf/users/&lt;me&gt;/tf-configs/…</code>、<code>tf-configs/&lt;id&gt;/scan|apply|report…</code>、<code>tf-tools/</code></td><td>登录</td></tr>
        <tr><td><code>/vigil</code></td><td><code>VigilView.vue</code></td><td><code>vigil/models/</code>、<code>stats/</code>、<code>records/</code>、<code>records/&lt;id&gt;/</code></td><td>登录</td></tr>
        <tr><td><code>/vigil/log</code></td><td><code>VigilLogView.vue</code></td><td><code>vigil/records/</code>（15 秒轮询）、<code>records/&lt;id&gt;/</code></td><td>登录</td></tr>
        <tr><td><code>/help</code></td><td><code>HelpView.vue</code></td><td>无（手册页面在 <code>src/views/help/pages/</code>，路由 <code>/help/:page</code>）</td><td>登录</td></tr>
        <tr><td><code>/admin/dashboard</code></td><td><code>admin/DashboardView.vue</code></td><td>用户、集群、配置汇总</td><td>管理员（否则跳 <code>/kcore</code>）</td></tr>
        <tr><td><code>/admin/users</code></td><td><code>admin/UsersView.vue</code></td><td><code>kcore/users/</code>、<code>users/&lt;pk&gt;/</code></td><td>管理员</td></tr>
        <tr><td><code>/admin/clusters</code></td><td><code>admin/ClustersView.vue</code></td><td><code>kcore/users/&lt;pk&gt;/clusters/</code>、<code>clusters/&lt;pk&gt;/</code></td><td>管理员</td></tr>
        <tr><td><code>/admin/tf-configs</code></td><td><code>admin/TFConfigsView.vue</code></td><td><code>autotf/users/&lt;pk&gt;/tf-configs/</code>、<code>tf-configs/&lt;pk&gt;/</code></td><td>管理员</td></tr>
        <tr><td><code>/admin/tf-tools</code></td><td><code>admin/TFToolsView.vue</code></td><td><code>autotf/tf-tools/</code>、<code>tf-tools/&lt;id&gt;/</code></td><td>管理员</td></tr>
      </table></div>
      <p>开发模式 <code>pnpm dev</code> 时，Vite 把 <code>/api</code>、<code>/ws</code> 代理到 <code>127.0.0.1:8080</code>（<code>vite.config.ts</code>）。生产由后端直接提供 <code>apps/frontend/dist</code>。</p>
    </section>
  </div>
</template>

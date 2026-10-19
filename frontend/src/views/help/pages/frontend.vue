<template>
  <div v-pre>
        <h1>前端代码</h1>
    <div class="meta">读完你能：在本机跑起前端开发环境，读懂每个页面的代码，知道一个按钮点下去调了哪个接口，会改页面、加页面、构建上线。<br>
      代码根目录 <code class="vn">~/github/NetSentinel/frontend/</code>（开发目录；线上的 <code class="vp">~/netsentinel-prod/frontend/</code> 只由 <code>deploy.sh</code> 构建，见 <a href="/help/index#envs">开发与生产</a>）。前置知识：会一点 HTML / JavaScript；Vue 不熟也没关系，本章按需讲。</div>

    <section id="stack">
      <h2>2.1 技术栈与版本</h2>
      <div class="table-wrap"><table>
        <tr><th>东西</th><th>版本（package.json）</th><th>在本项目里干什么</th></tr>
        <tr><td>Vue</td><td>3.5</td><td>页面框架。全部用 <code>&lt;script setup lang="ts"&gt;</code> 组合式写法</td></tr>
        <tr><td>Vue Router</td><td>5</td><td>前端路由（<code>/kcore</code>、<code>/admin/users</code> ...），HTML5 history 模式</td></tr>
        <tr><td>Pinia</td><td>3</td><td>全局状态：登录信息（<code>auth</code>）、命名空间缓存（<code>kcore</code>）</td></tr>
        <tr><td>Element Plus</td><td>2.13</td><td>UI 组件：<code>el-button</code>、<code>el-table</code>、<code>el-dialog</code>、<code>ElMessage</code> 等；图标全部全局注册</td></tr>
        <tr><td>TypeScript</td><td>5.9</td><td>类型检查，<code>vue-tsc</code> 在 build 时运行</td></tr>
        <tr><td>Vite</td><td>7</td><td>开发服务器 + 打包</td></tr>
        <tr><td>Node / pnpm</td><td>Node ≥ 20.19 或 ≥ 22.12</td><td>包管理用 pnpm（有 <code>pnpm-lock.yaml</code>，不要混用 npm）</td></tr>
        <tr><td>ESLint + oxlint + Prettier</td><td>—</td><td><code>pnpm lint</code>、<code>pnpm format</code></td></tr>
      </table></div>
      <p>没有用 axios：所有请求都是原生 <code>fetch</code>，统一经过 <code>auth.apiFetch()</code> 包装。没有用图表库：看板的条形图、数字滚动都是手写 CSS + 组件。</p>
    </section>

    <section id="tree">
      <h2>2.2 目录逐个说明</h2>
<pre><code>frontend/
├── package.json         脚本与依赖
├── pnpm-lock.yaml       锁定版本
├── vite.config.ts       Vite 配置：插件、@ 别名、开发代理 /api /ws → 127.0.0.1:8090（开发后端；可用环境变量 DEV_BACKEND 覆盖）
├── .env · .env.production   VITE_API_BASE=/api、VITE_WS_BASE=（空）；.env 不在 Git 中
├── index.html           唯一的 HTML 壳，里面只有 &lt;div id="app"&gt;
├── tsconfig*.json       TypeScript 配置（app 与 node 两套）
├── eslint.config.ts · .oxlintrc.json · .prettierrc.json · .editorconfig
├── public/              原样复制进 dist/ 的静态文件（不经过打包）
│   ├── favicon.ico / favicon.png
│   └── (手册在 src/views/help/pages/)
├── src/
│   ├── main.ts          入口：创建 app，装 Pinia、Router、ElementPlus，注册全部图标
│   ├── App.vue          根组件：决定显不显示顶部导航 + &lt;RouterView/&gt;
│   ├── router/index.ts  路由表 + 全局守卫（登录 / 管理员）
│   ├── stores/
│   │   ├── auth.ts      token、用户信息、apiFetch()、login()、logout()、自动刷新 token
│   │   └── kcore.ts     每个集群的 namespace 列表缓存
│   ├── components/
│   │   ├── NavComponent.vue   顶部导航 + 窄屏抽屉 + Sign Out
│   │   └── RollingNumber.vue  看板上会“滚动”的数字
│   ├── views/
│   │   ├── LoginView.vue      登录
│   │   ├── KcoreView.vue      Kubernetes（约 1000 行）
│   │   ├── AutoTFView.vue     Terraform Scan（约 1550 行）
│   │   ├── VigilView.vue      AI Vigil 看板（约 1530 行）
│   │   ├── VigilLogView.vue   检测日志（约 570 行）
│   │   ├── HelpView.vue       三个手册的 iframe 标签页
│   │   └── admin/             AdminLayout + Dashboard / Users / Clusters / TFConfigs / TFTools
│   └── assets/          base.css、main.css（全局样式）
└── dist/                pnpm build 的输出（不进 Git），后端直接提供它</code></pre>
    </section>

    <section id="run">
      <h2>2.3 开发模式 vs 生产模式</h2>
      <p>这是前端最容易搞混的地方：<b>线上没有单独的前端服务器</b>。</p>
      <div class="table-wrap"><table>
        <tr><th></th><th>开发模式</th><th>生产模式（现在线上）</th></tr>
        <tr><td>启动</td><td><code class="vn">cd ~/github/NetSentinel/frontend &amp;&amp; pnpm dev</code></td><td><code>scripts/deploy.sh -frontend</code> 在 <code class="vp">~/netsentinel-prod</code> 里 <code>pnpm build</code> 生成 <code>dist/</code>，然后重启后端</td></tr>
        <tr><td>访问</td><td><code>http://localhost:5173</code></td><td><code>http://localhost:8080</code> / <code>https://knettf.com</code></td></tr>
        <tr><td>页面从哪来</td><td>Vite 实时编译，改代码浏览器自动刷新（HMR）</td><td>Django 的 WhiteNoise 中间件直接返回 <code>dist/</code> 里的文件（<code>settings.WHITENOISE_ROOT</code>）</td></tr>
        <tr><td><code>/api</code> 请求</td><td>Vite 代理到开发后端 <code>http://127.0.0.1:8090</code>（<code>vite.config.ts</code> 的 <code>server.proxy</code>）</td><td>同源，直接到后端</td></tr>
        <tr><td><code>/ws</code> WebSocket</td><td>同样代理（<code>ws: true</code>）</td><td>同源</td></tr>
        <tr><td><code>VITE_API_BASE</code></td><td>来自 <code>frontend/.env</code>（本机有，但被 .gitignore 忽略）</td><td><code>/api</code>（<code>.env.production</code> 覆盖 <code>.env</code>）</td></tr>
      </table></div>
      <div class="note"><b>新机器上的坑</b>：Git 里只有 <code>.env.production</code>；本机的 <code>frontend/.env</code>（<code>VITE_API_BASE=/api</code>、<code>VITE_WS_BASE=</code>）没有提交。在新克隆的仓库里 <code>pnpm dev</code> 时 <code>VITE_API_BASE</code> 是 <code>undefined</code>，URL 会变成 <code>undefined/kcore/...</code>。先创建同样内容的 <code>frontend/.env</code>。（VigilView / VigilLogView 写死了 <code>/api/vigil/...</code>，不受影响。）</div>
      <h3>路径 <code>/kcore</code> 刷新为什么不 404</h3>
      <p>浏览器直接请求 <code>/kcore</code> 时，<code>dist/</code> 里没有这个文件。后端 <code>backend/urls.py</code> 最后一条路由 <code>re_path(r'^(?!api/|admin/|static/|ws/).*$', spa_view)</code> 把所有非 API 路径都返回 <code>dist/index.html</code>，然后 Vue Router 根据地址显示对应页面。<code>favicon.ico</code>、<code>/assets/*</code> 这种真实文件则被 WhiteNoise 先一步返回。</p>
      <h3>常用命令</h3>
<pre class="on-both"><code>cd <span class="vn">~/github/NetSentinel</span>/frontend
pnpm install        <span class="c"># 装依赖（第一次或 package.json 变了）</span>
pnpm dev            <span class="c"># 开发服务器 :5173（需开发后端在 :8090：cd <span class="vn">~/github/NetSentinel</span>/backend &amp;&amp; ../.venv/bin/python manage.py runserver 8090）</span>
pnpm build          <span class="c"># 本地只用来检查能否构建；线上构建交给 deploy.sh。= 并行执行 type-check（vue-tsc --build）和 build-only（vite build）</span>
pnpm build-only     <span class="c"># 跳过类型检查，只打包（类型报错又急着上线时用）</span>
pnpm preview        <span class="c"># 本地预览 dist/</span>
pnpm lint           <span class="c"># oxlint --fix 然后 eslint --fix</span>
pnpm format         <span class="c"># prettier 格式化 src/</span></code></pre>
      <p>上线：提交后 <code class="vn">cd ~/github/NetSentinel &amp;&amp; scripts/deploy.sh -frontend</code>。线上 <code>DEBUG=False</code>，WhiteNoise 只在进程启动时扫描 dist，所以脚本构建完会重启后端，否则新文件 404、页面白屏。浏览器 <span class="kbd">Ctrl</span>+<span class="kbd">F5</span> 强刷。</p>
    </section>

    <section id="boot">
      <h2>2.4 启动流程：main.ts → App.vue → 路由守卫</h2>
      <h3><span class="file">src/main.ts</span></h3>
<pre><code>import './assets/main.css'
const app = createApp(App)
app.use(createPinia())        <span class="c">// 状态管理</span>
app.use(router)               <span class="c">// 路由</span>
app.use(ElementPlus)          <span class="c">// UI 组件全部全局可用</span>
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)   <span class="c">// 所有图标注册成全局组件，如 &lt;Plus/&gt;</span>
}
app.mount('#app')</code></pre>
      <h3><span class="file">src/App.vue</span></h3>
      <p>根组件只做一件事：路径以 <code>/admin</code> 开头或是 <code>/login</code> 时<b>不显示</b>顶部导航（管理后台有自己的左侧菜单），然后放一个 <code>&lt;RouterView /&gt;</code> 显示当前页面。</p>
      <h3><span class="file">src/router/index.ts</span></h3>
      <div class="table-wrap"><table>
        <tr><th>路径</th><th>组件</th><th>meta</th></tr>
        <tr><td><code>/login</code></td><td>LoginView</td><td><code>public: true</code></td></tr>
        <tr><td><code>/</code></td><td>重定向到 <code>/kcore</code></td><td></td></tr>
        <tr><td><code>/kcore</code>、<code>/autotf</code>、<code>/vigil</code>、<code>/vigil/log</code>、<code>/help</code></td><td>对应 View</td><td><code>requiresAuth: true</code></td></tr>
        <tr><td><code>/admin</code>（子路由 dashboard / users / clusters / tf-configs / tf-tools）</td><td>AdminLayout + 子页面</td><td><code>requiresAdmin: true</code>（写在父路由上，子路由继承）</td></tr>
      </table></div>
      <p>所有页面组件都是 <code>() =&gt; import(...)</code> 懒加载，打包后每个页面一个 JS 文件。全局守卫：</p>
<pre><code>router.beforeEach((to) =&gt; {
  const auth = useAuthStore()
  document.title = to.meta.title ?? 'NetSentinel'      <span class="c">// 浏览器标签标题</span>
  if (to.meta.public) return true                       <span class="c">// 登录页放行</span>
  if (!auth.isLoggedIn) return { name: 'login' }        <span class="c">// 没 token → 登录页</span>
  if (to.meta.requiresAdmin &amp;&amp; !auth.isAdmin) return { path: '/kcore' }
  return true
})</code></pre>
      <div class="learn"><b>注意</b>：前端守卫只是“体验”，真正的权限在后端。<code>isAdmin</code> 来自 localStorage 里的 <code>user.is_staff</code>，用户可以自己改成 true 看到管理后台的壳子，但后端接口（如 <code>GET /api/kcore/users/</code> 要求 <code>IsAdminUser</code>）仍会返回 403。</div>
    </section>

    <section id="auth">
      <h2>2.5 登录与 token：<span class="file">stores/auth.ts</span></h2>
      <p>整个前端最核心的文件，所有请求都经过它。</p>
      <h3>状态</h3>
      <div class="table-wrap"><table>
        <tr><th>名字</th><th>来源</th><th>用途</th></tr>
        <tr><td><code>token</code></td><td>localStorage <code>token</code></td><td>JWT access，2 小时</td></tr>
        <tr><td><code>refreshToken</code></td><td>localStorage <code>refreshToken</code></td><td>JWT refresh，7 天</td></tr>
        <tr><td><code>user</code></td><td>localStorage <code>user</code>（JSON）</td><td><code>{id, username, email, is_staff}</code></td></tr>
        <tr><td><code>isLoggedIn</code></td><td>computed</td><td><code>!!token</code></td></tr>
        <tr><td><code>isAdmin</code></td><td>computed</td><td><code>!!user.is_staff</code></td></tr>
      </table></div>
      <h3><code>apiFetch(input, init)</code>：统一请求入口</h3>
<pre><code>async function apiFetch(input, init = {}) {
  const isFormData = init.body instanceof FormData
  const makeHeaders = () =&gt; ({
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),  <span class="c">// 上传文件时让浏览器自己设 multipart 边界</span>
    ...init.headers,
    Authorization: `Bearer ${token.value}`,
  })
  let res = await fetch(input, { ...init, headers: makeHeaders() })
  if (res.status === 401) {                    <span class="c">// access 过期</span>
    const ok = await tryRefresh()              <span class="c">// 用 refresh 换新 access</span>
    if (ok) res = await fetch(input, { ...init, headers: makeHeaders() })   <span class="c">// 重放一次</span>
    else { logout(); window.location.href = '/login' }
  }
  return res
}</code></pre>
      <p><code>tryRefresh()</code> 调 <code>POST /api/auth/token/refresh/</code> body <code>{refresh}</code>，成功后更新 <code>token</code>。它用一个模块级的 <code>refreshPromise</code> 保证<b>同时有 10 个请求 401 也只刷新一次</b>，其余请求等同一个 Promise。</p>
      <h3><code>login(username, password)</code></h3>
      <ol>
        <li><code>POST /api/auth/token/</code> → 存 access、refresh。</li>
        <li><code>GET /api/kcore/users/me/</code> → 存 user。</li>
        <li>返回 <code>null</code> 表示成功，否则返回错误文案。LoginView 据此跳 <code>/admin/dashboard</code> 或 <code>/kcore</code>。</li>
      </ol>
      <div class="note">少数地方没走 <code>apiFetch</code>，而是 <code>fetch(url, { headers: auth.authHeaders() })</code>（例如 KcoreView 的 <code>openYaml</code>）。这些请求在 access 过期时<b>不会</b>自动刷新，会直接报错；再点一次（期间别的请求刷新过 token）就好了。新代码请一律用 <code>apiFetch</code>。</div>
    </section>

    <section id="kcore">
      <h2>2.6 页面：<span class="file">KcoreView.vue</span>（Kubernetes）</h2>
      <p>布局：左侧集群列表（窄屏是抽屉），右侧六个 <code>el-tab-pane</code>。按代码里的注释分块讲：</p>
      <div class="table-wrap"><table>
        <tr><th>代码块</th><th>状态 / 函数</th><th>做什么</th></tr>
        <tr><td>Clusters</td><td><code>clusters</code>、<code>selectedCluster</code>、<code>fetchClusters()</code>、<code>selectCluster()</code></td><td>挂载时拉 <code>GET /kcore/users/&lt;我&gt;/clusters/</code>；选中集群后切到 Namespaces 标签并加载</td></tr>
        <tr><td>Add / Delete Cluster</td><td><code>showAddCluster</code>、<code>newCluster</code>、<code>addCluster()</code>、<code>deleteCluster()</code></td><td>POST / DELETE 集群</td></tr>
        <tr><td>Resources</td><td><code>activeTab</code>、<code>resources</code>、<code>selectedNamespace</code>、<code>loadResources()</code>、<code>onTabChange()</code></td><td>按标签和命名空间拉列表。<b>防竞态</b>：请求前快照 clusterId 和 type，返回时若用户已切走就丢弃结果</td></tr>
        <tr><td>YAML View / Edit</td><td><code>yamlDialog</code>、<code>openYaml(row, type, readonly)</code>、<code>submitYamlEdit()</code></td><td>读：<code>GET .../resources/&lt;type&gt;/&lt;name&gt;/</code> 取 <code>data.yaml</code>；写：<code>POST .../apply/</code></td></tr>
        <tr><td>Apply YAML (blank)</td><td><code>applyDialog</code>、<code>submitApply()</code></td><td>空白对话框贴 YAML，统计 <code>results</code> 中 applied / error 数</td></tr>
        <tr><td>Restart</td><td><code>submitRestart(row, type, force)</code></td><td>下拉 <code>Normal (Rolling)</code> / <code>Force (Delete Pods)</code> → <code>POST .../resources/&lt;type&gt;/&lt;name&gt;/</code> body <code>{namespace, force}</code></td></tr>
        <tr><td>Delete</td><td><code>deleteDialog</code>、<code>openDeleteDialog()</code>、<code>submitDelete()</code></td><td><code>DELETE</code> 带 body <code>{namespace}</code>（Namespace 本身不带）</td></tr>
        <tr><td>Pod Logs</td><td><code>socket</code>、<code>connectWs()</code>、<code>logContent</code>、<code>wsConnected</code></td><td>见下</td></tr>
        <tr><td>Helpers</td><td><code>formatTime</code>、<code>formatPorts</code>、<code>podStatusType</code></td><td>时间本地化、端口 <code>80/TCP</code> 格式、Pod 状态标签颜色</td></tr>
      </table></div>
      <h3>Pod 日志 WebSocket</h3>
<pre><code>const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
socket = new WebSocket(`${WS_BASE}/ws/clusters/${clusterId}/pods/${ns}/${name}/logs/`)
socket.onmessage = (e) =&gt; { logContent.value += JSON.parse(e.data).log; 滚动到底 }
socket.onclose = () =&gt; { wsConnected.value = false }</code></pre>
      <p>后端每读到一行日志就发一条 <code>{"log": "..."}</code>。注意 URL 里<b>没有 token</b>，后端也不校验（<a href="/help/issues">《已知问题与练习》</a>已知问题）。页面卸载（<code>onUnmounted</code>）或关闭窗口时 <code>socket.close()</code>。</p>
      <h3><span class="file">stores/kcore.ts</span></h3>
      <p>只缓存“每个集群有哪些 namespace”，供下拉框用。<code>fetchNamespaces(clusterId)</code> 用一个 <code>Map&lt;clusterId, Promise&gt;</code> 去重并发请求；更新时用 <code>{...old, [id]: names}</code> 生成新对象，保证 Vue 能侦测到变化。</p>
    </section>

    <section id="autotf">
      <h2>2.7 页面：<span class="file">AutoTFView.vue</span>（Terraform Scan）</h2>
      <div class="table-wrap"><table>
        <tr><th>功能</th><th>函数</th><th>接口</th></tr>
        <tr><td>配置列表 / 选中</td><td><code>fetchConfigs()</code>、<code>selectConfig()</code></td><td><code>GET /autotf/users/&lt;我&gt;/tf-configs/</code>；选中后并行 <code>loadContent()</code> 和 <code>loadReport()</code></td></tr>
        <tr><td>看 / 改内容</td><td><code>loadContent()</code>、<code>startEditContent()</code>、<code>saveContent()</code>、<code>cancelEdit()</code></td><td><code>GET .../tf-configs/&lt;id&gt;/content/</code>；<code>PUT .../tf-configs/&lt;id&gt;/</code> body <code>{content}</code></td></tr>
        <tr><td>删除配置</td><td><code>confirmDelete()</code>（<code>ElMessageBox</code> 二次确认）</td><td><code>DELETE .../tf-configs/&lt;id&gt;/</code></td></tr>
        <tr><td>新建</td><td><code>openAddDialog()</code>、<code>onFileChange()</code>、<code>submitAdd()</code>；<code>addMode</code> = file / text</td><td>file：<code>FormData</code>（name、file）→ <code>POST .../tf-configs/</code>；text：JSON → <code>POST .../tf-configs/text/</code></td></tr>
        <tr><td>全量扫描</td><td><code>runFullScan()</code>，<code>scanning</code> 控制转圈</td><td><code>POST .../scan/</code>，响应即报告</td></tr>
        <tr><td>手动扫描</td><td><code>openManualScan()</code> 拉工具 → 勾选 <code>selectedToolIds</code> → <code>runManualScan()</code></td><td><code>GET /autotf/tf-tools/</code>；<code>POST .../scan/manual/</code></td></tr>
        <tr><td>报告</td><td><code>loadReport()</code>、<code>deleteReport()</code>、<code>totalFindings</code>、<code>sevPct()</code></td><td><code>GET / DELETE .../report/</code></td></tr>
        <tr><td>HTML / PDF</td><td><code>viewHtmlReport()</code>、<code>downloadPdf()</code></td><td><code>window.open('.../report/html/?token=' + auth.token)</code>、<code>.../report/pdf/?token=</code></td></tr>
        <tr><td>工具元信息</td><td><code>fetchAllTools()</code>、<code>toolMeta(name)</code>、<code>simplifyCmd()</code></td><td>报告里每个工具旁显示版本和 JSON / SARIF 标签</td></tr>
        <tr><td>Apply</td><td><code>canApply</code>、<code>applyBlockReason</code>（computed）、<code>runApply()</code></td><td><code>POST .../apply/</code>，返回更新后的配置（含 <code>last_apply_*</code>）</td></tr>
      </table></div>
    </section>

    <section id="vigil">
      <h2>2.8 页面：<span class="file">VigilView.vue</span> 与 <span class="file">VigilLogView.vue</span></h2>
      <h3>VigilView（看板）</h3>
      <ul>
        <li>自己包了一层 <code>apiFetch(path, opts, timeoutMs=8000)</code>：用 <code>AbortController</code> 给每个请求加 8 秒超时，并直接返回 <code>json.data</code>。失败时 <code>catch {}</code> 保留旧数据（“keep stale”），所以后端短暂故障时页面不会清空。</li>
        <li><code>onMounted</code>：先 <code>loadModels()</code>，再 <code>loadAll()</code>（并行 <code>loadStats()</code> + <code>loadRecords()</code>），然后 <code>setInterval(loadAll, 30000)</code>；另有 1 秒一次的时钟。</li>
        <li><code>loadRecords(force)</code>：非 force 时只把新出现的 id 插到前面，保留最多 200 条，避免整表闪烁。</li>
        <li>详情：<code>openDetail(id)</code> → <code>detailRecord</code>；<code>sortedZsl</code> 把 raw_output 按值从大到小排；<code>flowFeatures</code> 从 <code>flow_input</code> 去掉 5 元组和 label 后显示。</li>
        <li>时间：<code>created_at</code> 是 UTC ISO 字符串，页面用浏览器本地时区格式化，并显示 <code>tzOffset</code>（如 UTC+9）。</li>
      </ul>
      <h3>VigilLogView（日志）</h3>
      <ul>
        <li>筛选状态 <code>verdict</code>、<code>filterAttackType</code>、<code>timeFrom</code>、<code>timeTo</code>；分页 <code>limit</code>、<code>offset</code>、<code>total</code>。</li>
        <li><code>ATTACK_TYPES</code> 是写死的 9 个类型名，必须与模型原型里的名字一致（<a href="/help/detect">《检测链路与模型》</a> 4.6）。换模型后若类型名变了，这里要同步改。</li>
        <li><code>reload()</code> 回到第一页；<code>prevPage()</code> / <code>nextPage()</code> 改 offset；<code>setInterval(loadRecords, 15000)</code>。</li>
      </ul>
      <h3><span class="file">components/RollingNumber.vue</span></h3>
      <p>接收 <code>value</code>、<code>decimals</code>、<code>suffix</code>，数字变化时做逐位滚动动画。<code>value</code> 为 <code>null</code> 时显示占位。</p>
    </section>

    <section id="admin">
      <h2>2.9 管理后台：<span class="file">views/admin/</span></h2>
      <div class="table-wrap"><table>
        <tr><th>文件</th><th>怎么取数据</th><th>备注</th></tr>
        <tr><td><code>AdminLayout.vue</code></td><td>—</td><td>左侧菜单（<code>el-menu</code> + router）、右侧 <code>&lt;RouterView/&gt;</code>、左下 Sign Out</td></tr>
        <tr><td><code>DashboardView.vue</code></td><td><code>GET /kcore/users/</code> + <code>GET /autotf/tf-configs/all/</code></td><td>后一个接口<b>不存在</b>（404），TF Configs 恒为 0；集群数靠 <code>u.cluster_count</code>，但用户序列化器没有这个字段，也恒为 0</td></tr>
        <tr><td><code>UsersView.vue</code></td><td><code>GET/POST /kcore/users/</code>、<code>DELETE /kcore/users/&lt;id&gt;/</code></td><td>Admin 开关发了 <code>is_staff</code> 但后端忽略</td></tr>
        <tr><td><code>ClustersView.vue</code></td><td>先拉全部用户，再对每个用户 <code>GET /kcore/users/&lt;id&gt;/clusters/</code>（N+1 次请求）</td><td>没有“全部集群”接口，所以这样拼</td></tr>
        <tr><td><code>TFConfigsView.vue</code></td><td>同上，逐用户 <code>GET /autotf/users/&lt;id&gt;/tf-configs/</code></td><td>同上</td></tr>
        <tr><td><code>TFToolsView.vue</code></td><td><code>GET/POST /autotf/tf-tools/</code>、<code>PATCH/DELETE /autotf/tf-tools/&lt;id&gt;/</code></td><td>表单：Output Format 选 JSON 时才显示 Items Path、Severity Field / Map 等映射字段；Severity Map 是 JSON 文本，提交前 <code>parseSeverityMap()</code> 校验</td></tr>
      </table></div>
    </section>

    <section id="conv">
      <h2>2.10 代码约定（照着写就不会错）</h2>
      <ul>
        <li><b>请求</b>：<code>const BASE = import.meta.env.VITE_API_BASE</code>，然后 <code>auth.apiFetch(`${BASE}/xxx/`)</code>。URL 结尾要有 <code>/</code>（Django 的约定，不带会 404 或 301）。</li>
        <li><b>响应</b>：后端统一包成 <code>{status, code, message, data}</code>，所以取数据是 <code>(await res.json()).data</code>，报错文案是 <code>.message</code>。判断成功用 <code>res.ok</code>。</li>
        <li><b>提示</b>：成功 <code>ElMessage.success()</code>，失败 <code>ElMessage.error(json.message ?? '...')</code>；危险操作用 <code>el-popconfirm</code> 或 <code>ElMessageBox.confirm</code>。</li>
        <li><b>加载状态</b>：每个异步操作配一个 <code>xxxLoading</code> / <code>xxxing</code> 的 ref，绑到按钮 <code>:loading</code>。</li>
        <li><b>窄屏</b>：<code>.narrow-only</code> 按钮 + <code>sidebarOpen</code> 控制抽屉。</li>
        <li><b>样式</b>：写在组件的 <code>&lt;style scoped&gt;</code> 里，全局只有 <code>assets/main.css</code>。</li>
      </ul>
    </section>

    <section id="practice">
      <h2>2.11 实战：新增一个“系统状态”页面</h2>
      <p>目标：顶部导航多一个 <b>Status</b>，显示已注册的模型和检测总数。按顺序做：</p>
      <div class="steps">
        <div class="step"><div class="step-title">新建 <code>src/views/StatusView.vue</code></div>
<pre><code>&lt;script setup lang="ts"&gt;
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
const BASE = import.meta.env.VITE_API_BASE
const auth = useAuthStore()
const models = ref&lt;string[]&gt;([])
const total = ref(0)
onMounted(async () =&gt; {
  const [m, s] = await Promise.all([
    auth.apiFetch(`${BASE}/vigil/models/`).then(r =&gt; r.json()),
    auth.apiFetch(`${BASE}/vigil/stats/`).then(r =&gt; r.json()),
  ])
  models.value = m.data?.models ?? []
  total.value = s.data?.total ?? 0
})
&lt;/script&gt;
&lt;template&gt;
  &lt;div style="padding:24px"&gt;
    &lt;h2&gt;System Status&lt;/h2&gt;
    &lt;p&gt;Models: {{ models.join(', ') || 'none' }}&lt;/p&gt;
    &lt;p&gt;Total flows: {{ total }}&lt;/p&gt;
  &lt;/div&gt;
&lt;/template&gt;</code></pre></div>
        <div class="step"><div class="step-title">在 <code>router/index.ts</code> 的用户区加路由</div>
<pre><code>{ path: '/status', name: 'status', component: () =&gt; import('../views/StatusView.vue'),
  meta: { requiresAuth: true, title: 'NetSentinel - Status' } },</code></pre></div>
        <div class="step"><div class="step-title">在 <code>NavComponent.vue</code> 的 <code>links</code> 数组加一项</div>
<pre><code>{ to: '/status', label: 'Status', icon: Monitor },</code></pre></div>
        <div class="step"><div class="step-title">本地验证</div>
          <p>确认有 <code>frontend/.env</code>、开发后端在 8090 运行，<code>pnpm dev</code>，打开 <code>http://localhost:5173/status</code>。</p></div>
        <div class="step"><div class="step-title">上线</div>
          <p>本地 <code>pnpm build</code> 确认类型检查通过 → <code>git commit</code> → <code class="vn">cd ~/github/NetSentinel &amp;&amp; scripts/deploy.sh -frontend</code> → 浏览器强刷 <code>https://knettf.com/status</code>。新路由不用改后端：后端的 SPA 兜底会把 <code>/status</code> 交给前端路由。</p></div>
      </div>
    </section>
  </div>
</template>

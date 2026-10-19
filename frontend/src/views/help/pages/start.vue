<template>
  <div v-pre>
    <h1>先认识这个项目</h1>
    <div class="meta">这一页只讲轮廓：系统是做什么的、由哪几块组成、东西放在哪、日常要做哪些事。不需要执行任何命令，读完大约 10 分钟。</div>

    <section id="what">
      <h2>一句话说清楚</h2>
      <p>NetSentinel 是一个网站（<code>https://knettf.com</code>）。它在实验室自建的 Kubernetes 集群里抓网络流量，用机器学习模型判断哪些流量是攻击，并把结果显示在网页上。网站另外还能管理集群、检查 Terraform 配置文件的安全问题。</p>
      <div class="cards">
        <div class="card"><b>Kubernetes</b><span>登记集群后，在网页上查看和管理集群里的资源。</span></div>
        <div class="card"><b>Terraform Scan</b><span>上传 .tf 配置文件，用 5 个工具扫描安全问题，没有高危问题才允许部署。</span></div>
        <div class="card"><b>AI Vigil</b><span>实时显示检测结果：看了多少流量、发现多少攻击、是哪种攻击。</span></div>
      </div>
    </section>

    <section id="parts">
      <h2>由哪几块组成</h2>
      <p>整个系统都在实验室的一台服务器上（内网地址 <code>192.168.0.247</code>）。可以把它想成三层：</p>
      <div class="table-wrap"><table>
        <tr><th>层</th><th>是什么</th><th>坏了会怎样</th></tr>
        <tr><td><b>1. 网站</b></td><td>一个常驻的后台服务 <code>netsentinel</code>，同时提供网页和接口；再通过 Cloudflare 隧道 <code>cloudflared-knettf</code> 让外网能访问 knettf.com</td><td>网页打不开</td></tr>
        <tr><td><b>2. 数据库</b></td><td>两个：一个 SQLite 文件存用户、集群和 Terraform 配置；一个 PostgreSQL（Docker 容器 <code>pg</code>）存检测记录</td><td>登录失败或检测记录写不进去</td></tr>
        <tr><td><b>3. 实验集群</b></td><td>5 台虚拟机组成的 Kubernetes 集群，负责产生和采集流量，再送给网站的检测模型</td><td>网站正常，但 AI Vigil 没有新数据</td></tr>
      </table></div>
      <div class="learn">记住这三层的顺序，以后排查问题就是从第 1 层往第 3 层一层层确认。</div>
    </section>

    <section id="code">
      <h2>代码在哪里</h2>
      <p>代码分在两个 GitHub 仓库里，都在实验室的 GitHub 组织 <code>knet-lab</code> 下：</p>
      <div class="table-wrap"><table>
        <tr><th>仓库</th><th>内容</th><th>服务器上的目录</th></tr>
        <tr><td><b>NetSentinel</b></td><td>网站本身（前端 + 后端 + 检测模型）</td><td>开发目录 <code>~/github/NetSentinel</code>；线上目录 <code>~/netsentinel-prod</code></td></tr>
        <tr><td><b>knetsentinel</b></td><td>实验集群的搭建脚本和发流量的脚本</td><td><code>~/knetsentinel</code></td></tr>
      </table></div>
      <p>网站有<b>两份</b>：开发目录用来改代码和试验，线上目录是用户实际在用的。改好的代码要用一条部署命令发布到线上，不能直接在线上目录里改。具体做法在项目手册「改动上线」里。</p>
    </section>

    <section id="duty">
      <h2>日常要做的事</h2>
      <div class="table-wrap"><table>
        <tr><th>多久一次</th><th>做什么</th><th>在哪里看</th></tr>
        <tr><td>只做一次</td><td>拿到自己的服务器账户、权限和 GitHub 权限</td><td>本教程第 2 步</td></tr>
        <tr><td>只做一次</td><td>改掉网站默认账号的密码，核对用户</td><td>本教程第 3 步</td></tr>
        <tr><td>每天 5 分钟</td><td>健康检查：确认网站、数据库、集群都正常</td><td>项目手册 · 每日健康检查</td></tr>
        <tr><td>服务器重启后</td><td>手动启动实验集群，再重启网站服务</td><td>项目手册 · 开关机</td></tr>
        <tr><td>出问题时</td><td>按看到的现象查原因</td><td>项目手册 · 排障与日志</td></tr>
      </table></div>
      <div class="note">服务器上还跑着别的项目（my-code、pnu-notice 等），不属于 NetSentinel，不要停也不要删。</div>
    </section>
  </div>
</template>

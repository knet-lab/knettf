<template>
  <div v-pre>
        <h1>接手准备：Linux 账户、权限与 Git</h1>
    <div class="meta">分三个阶段：<b>一 准备工作</b>（申请账户、权限、Git，止于“准备完成验收”）→ <b>二 正式接手</b>（从验收通过开始）→ <b>三 后续</b>（可选）。先看 <a href="#roadmap">全流程一览</a>。<br>
      本页所有命令、路径、IP 都是按这台机器实际情况写的（2026-10 核对）。命令里的 <code>NEWUSER</code> 指接手人<b>自己新建的</b>账户，执行时替换成你的用户名。</div>

    <section id="machine">
      <h2>先了解：这台机器的现状</h2>
      <div class="table-wrap"><table>
        <tr><th>项目</th><th>实际值</th></tr>
        <tr><td>主机名 / 系统</td><td><code>cis-Z10PE-D8-WS</code>，Ubuntu 24.04.2，56 核，125 GB 内存</td></tr>
        <tr><td>访问地址</td><td>实验室内网 <code>192.168.0.247</code>；Tailscale <code>100.117.219.123</code>（tailnet 属于原作者的 Tailscale 账号）</td></tr>
        <tr><td>SSH</td><td>端口 22，<b>禁止密码登录</b>（<code>PasswordAuthentication no</code>），只能用密钥</td></tr>
        <tr><td>人类账户</td><td><code>cis</code>（uid 1000，装机时的第一个账户，实验室共用，<b>不得用于接手</b>）、<code>soar009</code>（原作者）</td></tr>
        <tr><td>集群虚拟机</td><td>libvirt 系统级：<code>k8s-master</code> 192.168.100.10，<code>k8s-node1~4</code> 192.168.100.11~14</td></tr>
      </table></div>

      <h3>属于 NetSentinel 的东西（全部在 soar009 名下）</h3>
      <div class="table-wrap"><table>
        <tr><th>资源</th><th>位置</th><th>说明</th></tr>
        <tr><td>平台代码（开发）</td><td><code>/home/soar009/github/NetSentinel</code></td><td>GitHub <code>Wk-P/NetSentinel</code>（SSH 远程，分支 main）；平时改代码、提交都在这里</td></tr>
        <tr><td>平台代码（线上）</td><td><code>/home/soar009/netsentinel-prod</code></td><td>开发目录的 git clone（origin 指向开发目录），只由 <code>scripts/deploy.sh</code> 更新，不要在里面改代码</td></tr>
        <tr><td>集群/检测代码</td><td><code>/home/soar009/knetsentinel</code></td><td>GitHub <code>Wk-P/knetsentinel</code>（<b>HTTPS</b> 远程，分支 master）——是第二个独立仓库</td></tr>
        <tr><td>Python 环境</td><td>两个目录各有一个 <code>.venv</code>（uv 管理）</td><td>依赖见 <code>pyproject.toml</code> / <code>uv.lock</code></td></tr>
        <tr><td>Terraform 扫描工具</td><td><code>/home/soar009/terraform/.venv/bin/checkov</code></td><td>路径写死在 <code>backend/autotf/services.py:267</code> 和 <code>autotf_init.py:63-64</code></td></tr>
        <tr><td>后端服务</td><td><code>~/.config/systemd/user/netsentinel.service</code></td><td>运行 <code>netsentinel-prod</code>，uvicorn 监听 8080，user 级服务，已开 linger</td></tr>
        <tr><td>隧道</td><td><code>cloudflared-knettf.service</code> + <code>~/.cloudflared/netsentinel.yml</code></td><td>knettf.com → localhost:8080</td></tr>
        <tr><td>定时任务</td><td>soar009 的 crontab</td><td>每天 0 点用 <code>netsentinel-prod</code> 执行 <code>manage.py rotate_partitions --database vigil</code></td></tr>
        <tr><td>数据库</td><td>SQLite：两个目录各自的 <code>backend/db.sqlite3</code>（线上以 <code>netsentinel-prod</code> 为准）；PostgreSQL：Docker 容器 <code>pg</code>（5432，线上库 <code>vigil</code>，开发库 <code>vigil_dev</code>）</td><td>容器数据在 <code>/home/docker-data</code>，与 soar009 家目录无关</td></tr>
        <tr><td>密钥/口令</td><td>两个目录各自的 <code>backend/backend/.env</code>：线上那份有 <code>SECRET_KEY</code>、<code>DEBUG=False</code>、<code>VIGIL_BRIDGE_TOKEN</code>；PostgreSQL 密码目前是 <code>settings.py</code> 里的默认值</td><td>.env 不在 Git 里，权限 600</td></tr>
      </table></div>

      <h3>同一台机器上的其他项目——不要碰</h3>
      <div class="note">这台服务器不只跑 NetSentinel。以下服务也在运行，管理时不要停、不要删：
        <ul>
          <li>soar009 名下：<code>my-code-panel / my-code-queue / my-code-monitor</code> 服务、<code>cloudflared-my-code</code> 隧道（my-code.knettf.com）</li>
          <li>Docker：<code>pnu-notice-*</code>（4 个容器）、<code>emotion-talk-backend-1</code></li>
          <li>端口 3306（MySQL）、8000、8081、8099 都不是 NetSentinel 的</li>
        </ul>
        NetSentinel 只用 8080（线上后端）、5432（容器 <code>pg</code>），开发时另用 8090（开发后端）和 5173（Vite）。</div>
    </section>

    <section id="roadmap">
      <h2>全流程一览</h2>
      <div class="table-wrap"><table>
        <tr><th>阶段</th><th>内容</th><th>做完的标志</th></tr>
        <tr><td><b>一 准备工作</b><br>（只做一次，必做）</td><td>1.1 申请 Linux 账户 → 1.2 加入 GitHub 仓库 → 1.3 配置 Git → 1.4 验收</td><td><a href="#ready">准备完成验收</a> 6 项全部通过</td></tr>
        <tr><td><b>二 正式接手</b><br>（验收通过后开始）</td><td>2.1 学会操作服务 → 2.2 接手第一天 → 之后每天 <a href="/help/health">健康检查</a></td><td>第一天清单做完，之后进入日常</td></tr>
        <tr><td><b>三 后续</b><br>（可选，择机）</td><td>3.1 迁出 soar009 家目录 → 3.2 原作者离开时收尾</td><td>原作者账户可以安全锁定</td></tr>
      </table></div>
      <div class="note">验收没通过之前<b>不要</b>开始阶段二：账户、权限、Git 身份没配好就操作服务，容易出现权限错误或提交记到别人名下。</div>
    </section>

    <div class="phase"><div class="phase-n">阶段一</div><div><b>准备工作</b><br>让你有自己的账户、权限和 Git 身份。这一阶段还不碰线上服务。</div></div>

    <section id="user">
      <h2>1.1 账户与权限</h2>
      <div class="danger"><b>禁止用 <code>cis</code> 账户接手。</b><code>cis</code> 是装机时的共用账户，权限过大（sudo + docker + libvirt），用它操作出了问题查不到是谁做的，也没法单独收回某个人的权限。接手人必须<b>新建自己的 Linux 账户</b>，按下面流程申请权限；不要借用 <code>cis</code> 或 <code>soar009</code> 的密码、密钥。</div>

      <h3>流程</h3>
      <div class="table-wrap"><table>
        <tr><th>步骤</th><th>谁做</th><th>做什么</th><th>结果</th></tr>
        <tr><td>1 申请</td><td>接手人</td><td>向实验室负责人提交：想要的用户名、SSH 公钥（下文 ①）、需要哪些组及理由</td><td>负责人书面（邮件/群消息）批准，留档</td></tr>
        <tr><td>2 建账户</td><td>现有管理员</td><td>按下面命令新建账户、放公钥、只加批准的组</td><td>接手人能用密钥登录</td></tr>
        <tr><td>3 核对</td><td>接手人</td><td>登录后 <code>id</code>，确认组与批准的一致</td><td>多了或少了都反馈管理员</td></tr>
        <tr><td>4 收回</td><td>管理员</td><td>人员离开时 <code>sudo usermod -L NEWUSER</code> 锁账户，删 <code>authorized_keys</code>，移出各组</td><td>不影响服务和其他人</td></tr>
      </table></div>

      <h3>管理员：新建账户</h3>
      <pre><code>sudo adduser NEWUSER                                   # 设置密码（只用于 sudo，SSH 不收密码）
sudo usermod -aG sudo,docker,libvirt NEWUSER           # 只加批准的组
id NEWUSER</code></pre>
      <div class="table-wrap"><table>
        <tr><th>组</th><th>在这台机器上能做什么</th><th>何时批准</th></tr>
        <tr><td><code>sudo</code></td><td>完全管理员；可以 <code>sudo -iu soar009</code> 操作原作者的服务（见 2.1）</td><td>负责运维、要重启服务时</td></tr>
        <tr><td><code>docker</code></td><td>管理 <code>pg</code> 容器；注意也能看到/停掉 pnu-notice、emotion-talk 等别人的容器</td><td>要操作数据库时</td></tr>
        <tr><td><code>libvirt</code></td><td><code>virsh -c qemu:///system list</code> 管理 5 台 k8s 虚拟机</td><td>要开关/重建集群时</td></tr>
      </table></div>
      <div class="note">组变更要<b>重新登录</b>才生效。只看网页、不运维的人不需要 Linux 账户，在网站上建普通账号即可（<a href="/help/account">账号与令牌</a>）。</div>

      <h3>SSH 登录（这台机器只认密钥）</h3>
      <p>因为禁止了密码登录，<code>ssh-copy-id</code> 用不了，要由已能登录的人帮你放公钥：</p>
      <pre><code># ① 接手人在自己电脑上生成密钥，把 .pub 内容发给管理员
ssh-keygen -t ed25519 -C "NEWUSER@cis-Z10PE-D8-WS"
cat ~/.ssh/id_ed25519.pub

# ② 管理员在服务器上（把引号里换成收到的整行公钥）
sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.ssh
echo 'ssh-ed25519 AAAA... NEWUSER@cis-Z10PE-D8-WS' | sudo tee -a /home/NEWUSER/.ssh/authorized_keys
sudo chown NEWUSER:NEWUSER /home/NEWUSER/.ssh/authorized_keys && sudo chmod 600 /home/NEWUSER/.ssh/authorized_keys

# ③ 接手人登录
ssh NEWUSER@192.168.0.247            # 在实验室内网
ssh NEWUSER@100.117.219.123          # 在外面，需要加入 Tailscale（见下）</code></pre>
      <p><b>Tailscale</b>：现在的 tailnet 是原作者个人 Tailscale 账号。接手人要从外网连，需原作者在 Tailscale 后台 <b>Users → Invite users</b> 邀请，或接手人用自己的 tailnet 重新在服务器上 <code>sudo tailscale up</code> 登录（会换 IP，原作者设备就连不上了）。</p>

      <h3>kubectl</h3>
      <pre><code>sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.kube
sudo install -o NEWUSER -g NEWUSER -m 600 /home/soar009/.kube/config /home/NEWUSER/.kube/config
kubectl get nodes        # 接手人执行，应看到 k8s-master + k8s-node1~4 共 5 个 Ready</code></pre>
    </section>

    <section id="github">
      <h2>1.2 GitHub：邀请到两个仓库</h2>
      <p><code>user.email</code> 只决定提交上<b>显示</b>谁，能不能 push 取决于 GitHub <b>账号</b>是不是协作者。两个仓库要分别邀请：</p>
      <div class="table-wrap"><table>
        <tr><th>仓库</th><th>本地目录</th><th>邀请页面</th></tr>
        <tr><td><code>Wk-P/NetSentinel</code></td><td><code>/home/soar009/github/NetSentinel</code></td><td><code>https://github.com/Wk-P/NetSentinel/settings/access</code></td></tr>
        <tr><td><code>Wk-P/knetsentinel</code></td><td><code>/home/soar009/knetsentinel</code></td><td><code>https://github.com/Wk-P/knetsentinel/settings/access</code></td></tr>
      </table></div>
      <ol>
        <li>原作者（Wk-P）打开上面两个页面 → <b>Add people</b> → 输入接手人的 GitHub 用户名 → 发送。协作者自动有 push 权限，邀请 7 天内有效。</li>
        <li>接手人打开 <code>https://github.com/Wk-P/NetSentinel/invitations</code> 和 <code>https://github.com/Wk-P/knetsentinel/invitations</code> 分别接受。</li>
        <li>接手人在 GitHub <b>Settings → Emails</b> 确认要用的提交邮箱已验证。</li>
      </ol>
      <p>长期：两个仓库都是 Wk-P 个人仓库，原作者离开后无法给别人 Admin 权限。建议建一个实验室 Organization，用 <b>Settings → General → Transfer ownership</b> 把两个仓库转过去，然后在服务器上 <code>git remote set-url origin git@github.com:组织名/NetSentinel.git</code>（knetsentinel 同理）。</p>
    </section>

    <section id="git">
      <h2>1.3 本地 Git：用自己的身份提交</h2>

      <h3>第 1 步：在服务器上给你的账户配 GitHub 密钥</h3>
      <p>这是你在<b>服务器上</b>用来连 GitHub 的密钥，和 1.1 里登录服务器的密钥不是一个。</p>
      <pre><code>ssh-keygen -t ed25519 -C "你的GitHub邮箱"
cat ~/.ssh/id_ed25519.pub        # 加到 GitHub → Settings → SSH and GPG keys → New SSH key
ssh -T git@github.com            # 期望 Hi 你的用户名!；若是 Hi Wk-P! 说明在用原作者的密钥</code></pre>

      <h3>第 2 步：把两个仓库里写死的 Wk-P 身份移到 soar009 全局（必须做）</h3>
      <p>现在两个仓库的 <code>.git/config</code> 里都有 <code>user.name=Wk-P</code> / <code>user.email=weekend2000119@gmail.com</code>。仓库级配置优先于个人全局配置，不删的话<b>谁提交都显示 Wk-P</b>。soar009 本身没有全局身份，所以先补上再删：</p>
      <pre><code>sudo -iu soar009
git config --global user.name  Wk-P
git config --global user.email weekend2000119@gmail.com
for r in ~/github/NetSentinel ~/knetsentinel; do
  git -C $r config --local --unset user.name
  git -C $r config --local --unset user.email
done
exit</code></pre>
      <p>（迁移后路径换成 <code>/srv/netsentinel/NetSentinel</code>、<code>/srv/netsentinel/knetsentinel</code>。）</p>

      <h3>第 3 步：你的全局身份</h3>
      <pre><code>git config --global user.name  "你的名字"
git config --global user.email "你在GitHub已验证的邮箱"   # 或 GitHub 提供的 数字+用户名@users.noreply.github.com
git config --global --list</code></pre>

      <h3>第 4 步：在哪里改代码</h3>
      <p><b>已迁移到 /srv（3.1 做过）</b>：直接在线上目录工作，改完重启服务即可。</p>
      <pre><code>cd /srv/netsentinel/NetSentinel && git status
cd /srv/netsentinel/knetsentinel
git remote set-url origin git@github.com:Wk-P/knetsentinel.git   # 原来是 HTTPS，改成 SSH 才能用密钥 push</code></pre>
      <p><b>还没迁移</b>：你的账户对 soar009 的目录只有读权限，只能克隆到自己家目录开发：</p>
      <pre class="on-prod"><code>mkdir -p ~/github && cd ~/github
git clone git@github.com:Wk-P/NetSentinel.git
git clone git@github.com:Wk-P/knetsentinel.git ~/knetsentinel
# 改完 push 到 GitHub 后，部署到线上：
sudo -iu soar009 bash -c 'cd ~/github/NetSentinel && git pull --ff-only && scripts/deploy.sh -all'   # 这里的 ~ 是 soar009 的</code></pre>
      <p>链路是 你的 clone → GitHub → soar009 的开发目录 <code>~/github/NetSentinel</code> → <code>deploy.sh</code> 拉到线上目录 <code>~/netsentinel-prod</code> 并构建、重启。不要直接在 <code>netsentinel-prod</code> 里 pull GitHub，它的 origin 是开发目录。</p>

      <h3>第 5 步：试一次提交</h3>
      <pre><code>cd ~/github/NetSentinel          # 或 /srv/netsentinel/NetSentinel
git switch -c test/handover
echo "" >> README.md && git commit -am "test: handover commit"
git log -1 --format='%an <%ae>'     # 应是你自己
git push -u origin test/handover
git switch main && git push origin --delete test/handover && git branch -D test/handover</code></pre>

      <h3>常见错误</h3>
      <div class="table-wrap"><table>
        <tr><th>现象</th><th>原因</th><th>处理</th></tr>
        <tr><td><code>Permission denied (publickey)</code></td><td>服务器上你账户的公钥没加到 GitHub</td><td>第 1 步</td></tr>
        <tr><td><code>Permission to Wk-P/NetSentinel.git denied to 你的用户名</code></td><td>没接受邀请（两个仓库各要接受一次）</td><td>1.2</td></tr>
        <tr><td>knetsentinel push 时要求输入用户名密码</td><td>远程是 HTTPS</td><td>第 4 步的 <code>set-url</code></td></tr>
        <tr><td>提交作者显示 Wk-P</td><td>第 2 步没做，或在 soar009 身份下提交</td><td>第 2 步</td></tr>
        <tr><td><code>detected dubious ownership</code></td><td>仓库属于 soar009</td><td><code>git config --global --add safe.directory 仓库路径</code></td></tr>
        <tr><td><code>insufficient permission for adding an object</code></td><td>/srv 下有文件不是组可写</td><td><code>sudo chmod -R g+rwX /srv/netsentinel/NetSentinel/.git</code>，确认 umask 002</td></tr>
      </table></div>
    </section>

    <section id="ready">
      <h2>1.4 准备完成验收（阶段一到此结束）</h2>
      <p>用<b>你自己的账户</b>登录服务器，逐条执行。6 条都符合，准备工作才算结束；任何一条不符合，回到对应小节。</p>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>检查</th><th>应该看到</th><th>不符合回到</th></tr>
        <tr><td>1</td><td><code>ssh NEWUSER@192.168.0.247</code></td><td>用密钥直接登录，不问密码</td><td>1.1 SSH 登录</td></tr>
        <tr><td>2</td><td><code>id</code></td><td>组和批准的一致（如 sudo、docker、libvirt）</td><td>1.1 流程第 3 步</td></tr>
        <tr><td>3</td><td><code>sudo -iu soar009 systemctl --user is-active netsentinel</code></td><td><code>active</code></td><td>1.1（缺 sudo 组）</td></tr>
        <tr><td>4</td><td><code>kubectl get nodes</code></td><td>5 个节点 <code>Ready</code></td><td>1.1 kubectl</td></tr>
        <tr><td>5</td><td><code>ssh -T git@github.com</code></td><td><code>Hi 你的GitHub用户名!</code></td><td>1.3 第 1 步</td></tr>
        <tr><td>6</td><td>在两个仓库各试一次提交并 push</td><td>GitHub 上作者是你，不是 Wk-P</td><td>1.2、1.3 第 2–5 步</td></tr>
      </table></div>
    </section>

    <div class="phase"><div class="phase-n">阶段二</div><div><b>正式接手</b><br>验收通过后从这里开始。你开始负责线上服务。</div></div>

    <section id="transition">
      <h2>2.1 日常怎么操作服务（迁移前）</h2>
      <p>迁移（3.1）之前，后端、隧道、crontab 都是 soar009 的，你直接执行 <code>systemctl --user</code> 看到的是自己的（空的）。用 sudo 切过去：</p>
      <pre class="on-prod"><code>sudo -iu soar009                         # 输入的是你自己的密码
systemctl --user status netsentinel cloudflared-knettf
systemctl --user restart netsentinel
journalctl --user -u netsentinel -f
crontab -l                               # 看定时任务
exit</code></pre>
      <div class="note">在 <code>sudo -iu soar009</code> 下<b>不要 git commit</b>：两个仓库的 <code>.git/config</code> 都写死了 <code>user.name=Wk-P</code>，提交会记到原作者名下（见 1.3 第 2 步）。<code>git pull</code> 可以。</div>
    </section>

    <section id="day1">
      <h2>2.2 接手第一天</h2>
      <p>按顺序做一次，之后转入每天的 <a href="/help/health">健康检查</a>。</p>
      <ol>
        <li>完整做一遍 <a href="/help/health">每日健康检查</a>，记下各项的正常值，作为以后对比的基线。</li>
        <li>改掉网站默认账号 admin / alice / bob 的密码（<a href="/help/account">账号与令牌</a>）——它们写在代码里，等于公开。</li>
        <li>在网站管理后台 Users 里核对账号，删掉或停用陌生账号。</li>
        <li>读一遍 <a href="/help/trouble#dont">不要做的事</a> 和 <a href="/help/power">开关机与恢复</a>，知道宿主机重启后要做什么。</li>
        <li>确认已经从原作者那里当面拿到：网页管理员账号、线上 <code>.env</code> 里的 token、PostgreSQL 密码（见 3.2 第 5 条）。</li>
        <li>读 <a href="/help/index#envs">开发与生产</a>：知道哪个目录是线上、怎么用 <code>deploy.sh</code> 上线。</li>
      </ol>
      <div class="learn">做到这里，你已经正式接手。阶段三不着急，等系统稳定、有停机窗口时再做。</div>
    </section>

    <div class="phase"><div class="phase-n">阶段三</div><div><b>后续（可选）</b><br>不影响日常运维，择机进行。</div></div>

    <section id="migrate">
      <h2>3.1 迁出 soar009 家目录（可选，需停机）</h2>
      <div class="note">下面的步骤写于开发 / 线上分离之前，只搬了一个 NetSentinel 目录。现在要搬<b>两个</b>：<code>~/github/NetSentinel</code>（开发）和 <code>~/netsentinel-prod</code>（线上）。额外要做：线上目录 <code>git remote set-url origin &lt;新的开发目录&gt;</code>；systemd 服务和 cron 指向<b>线上目录</b>；两个目录的 <code>.venv</code> 都重建；<code>scripts/deploy.sh</code> 里的 <code>ROOT</code>（或环境变量 <code>NETSENTINEL_PROD</code>）指向新的线上目录，<code>systemctl --user</code> 改成 <code>sudo systemctl</code>。</div>
      <p>目标：代码放 <code>/srv/netsentinel</code>（现在 <code>/srv</code> 是空的），用 <code>netsentinel</code> 组授权；服务、定时任务改成系统级。<b>只动 NetSentinel</b>，my-code 的服务和隧道保持原样。预计停机 15–30 分钟，knettf.com 期间不可用。</p>

      <h3>第 1 步：建组、建目录</h3>
      <pre><code>sudo groupadd netsentinel
sudo usermod -aG netsentinel soar009
sudo usermod -aG netsentinel NEWUSER
sudo mkdir -p /srv/netsentinel</code></pre>

      <h3>第 2 步：停服务、搬代码（三个目录）</h3>
      <pre class="on-prod"><code>sudo -iu soar009 systemctl --user stop cloudflared-knettf netsentinel
sudo mv /home/soar009/github/NetSentinel /srv/netsentinel/NetSentinel
sudo mv /home/soar009/knetsentinel        /srv/netsentinel/knetsentinel
sudo mv /home/soar009/terraform           /srv/netsentinel/terraform     # autotf 用的 checkov
sudo chown -R soar009:netsentinel /srv/netsentinel
sudo chmod -R g+rwX /srv/netsentinel
sudo find /srv/netsentinel -type d -exec chmod g+s {} +
echo 'umask 002' | sudo tee -a /home/NEWUSER/.bashrc /home/soar009/.bashrc</code></pre>
      <p>SQLite 文件（<code>backend/*.sqlite3</code>）也随之变成组可写，NEWUSER 才能跑 <code>manage.py</code>。</p>

      <h3>第 3 步：改写死的路径、重建虚拟环境</h3>
      <pre><code>cd /srv/netsentinel/NetSentinel
# 已知的两处：
sed -i 's#/home/soar009/terraform#/srv/netsentinel/terraform#g' \
  backend/autotf/services.py backend/autotf/management/commands/autotf_init.py
# 再确认一遍没有遗漏（手册页里的路径是说明文字，可以不管）
grep -rIn --exclude-dir={.git,node_modules,.venv,dist} /home/soar009 . ../knetsentinel ../terraform

# 两个 venv 都写死了旧路径，必须重建
rm -rf .venv && uv sync --frozen
cd ../terraform && rm -rf .venv && python3.12 -m venv .venv && .venv/bin/pip install checkov

sudo git config --system --add safe.directory /srv/netsentinel/NetSentinel
sudo git config --system --add safe.directory /srv/netsentinel/knetsentinel</code></pre>

      <h3>第 4 步：隧道配置移到 /etc/cloudflared</h3>
      <pre><code>sudo mkdir -p /etc/cloudflared
sudo cp /home/soar009/.cloudflared/netsentinel.yml /etc/cloudflared/
sudo cp /home/soar009/.cloudflared/491d938b-3187-4d93-84da-66df739753e6.json /etc/cloudflared/
sudo chmod 600 /etc/cloudflared/*
sudo sed -i 's#/home/soar009/.cloudflared/#/etc/cloudflared/#' /etc/cloudflared/netsentinel.yml
# my-code.yml 和它的凭证留在原处，不要动</code></pre>

      <h3>第 5 步：系统级服务</h3>
      <p><code>/etc/systemd/system/netsentinel.service</code>（由现有 user 服务改写，只改了 User/Group、路径和 WantedBy）：</p>
      <pre><code>[Unit]
Description=NetSentinel Django Backend
After=network.target docker.service

[Service]
User=soar009
Group=netsentinel
WorkingDirectory=/srv/netsentinel/NetSentinel/backend
Environment=DJANGO_SETTINGS_MODULE=backend.settings
ExecStart=/srv/netsentinel/NetSentinel/.venv/bin/uvicorn backend.asgi:application --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3
TimeoutStartSec=30
TimeoutStopSec=8
KillMode=mixed
KillSignal=SIGTERM
TasksMax=500
MemoryMax=3G
MemorySwapMax=0

[Install]
WantedBy=multi-user.target</code></pre>
      <p><code>User=soar009</code> 先保持不变，最稳；以后可以换成专用账户（例如 <code>sudo useradd -r -g netsentinel netsentinel</code>）。</p>
      <p><code>/etc/systemd/system/cloudflared-knettf.service</code>：</p>
      <pre><code>[Unit]
Description=Cloudflare Tunnel (knettf.com)
After=network-online.target netsentinel.service
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/cloudflared --no-autoupdate tunnel --config /etc/cloudflared/netsentinel.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target</code></pre>

      <h3>第 6 步：定时任务移到系统 cron</h3>
      <pre><code>sudo -iu soar009 crontab -e      # 删掉 rotate_partitions 那一行
sudo tee /etc/cron.d/netsentinel &lt;&lt;'EOF'
0 0 * * * soar009 /srv/netsentinel/NetSentinel/.venv/bin/python /srv/netsentinel/NetSentinel/backend/manage.py rotate_partitions --database vigil >> /var/log/netsentinel-rotate.log 2>&1
EOF
sudo touch /var/log/netsentinel-rotate.log && sudo chown soar009:netsentinel /var/log/netsentinel-rotate.log</code></pre>

      <h3>第 7 步：切换并验证</h3>
      <pre class="on-prod"><code>sudo -iu soar009 systemctl --user disable netsentinel cloudflared-knettf
sudo systemctl daemon-reload
sudo systemctl enable --now netsentinel cloudflared-knettf
sudo systemctl status netsentinel cloudflared-knettf
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/      # 期望 200
curl -s -o /dev/null -w '%{http_code}\n' https://knettf.com/         # 期望 200
sudo -iu soar009 systemctl --user is-active cloudflared-my-code        # 确认 my-code 没受影响</code></pre>
      <div class="note">回退：<code>sudo systemctl disable --now netsentinel cloudflared-knettf</code>，把三个目录 mv 回原处，<code>sudo -iu soar009 systemctl --user enable --now netsentinel cloudflared-knettf</code>。<br>
        迁移后，手册其他章节里的 <code>systemctl --user</code> → <code>sudo systemctl</code>，<code>journalctl --user -u</code> → <code>journalctl -u</code>，<code>/home/soar009/github/NetSentinel</code> → <code>/srv/netsentinel/NetSentinel</code>，<code>/home/soar009/knetsentinel</code> → <code>/srv/netsentinel/knetsentinel</code>。</div>
    </section>

    <section id="offboard">
      <h2>3.2 原作者离开时的收尾</h2>
      <ol>
        <li><a href="#ready">准备完成验收</a> 全部通过。</li>
        <li>GitHub：两个仓库转到组织，或至少确认接手人已是协作者。</li>
        <li>Cloudflare：knettf.com 和两条隧道都在原作者的 Cloudflare 账号里，要把接手人加为成员（Manage Account → Members）。</li>
        <li>Tailscale：tailnet 是原作者的，要么邀请接手人，要么接手人用自己的账号重新登录（1.1）。</li>
        <li>当面交接：网页管理员账号、<code>~/netsentinel-prod/backend/backend/.env</code>（SECRET_KEY、VIGIL_BRIDGE_TOKEN）、PostgreSQL 密码（vigil 用户，当前是 <code>settings.py</code> 里的默认值）。</li>
        <li><b>不能直接锁 soar009</b>：即使 NetSentinel 已迁移，my-code 的三个服务和 my-code 隧道仍是 soar009 的 user 服务，锁账户（或关 linger）会把它们一起停掉。先和 my-code 的负责人确认怎么处理，再执行：
          <pre><code>sudo usermod -L soar009              # 只锁密码；密钥登录要另外删 authorized_keys
sudo gpasswd -d soar009 sudo</code></pre></li>
      </ol>
    </section>
  </div>
</template>

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

      <h3>属于 NetSentinel 的东西</h3>
      <p>结构分两半：<b>线上</b>全部放在 <code>/srv/netsentinel</code>，由没有登录权限的系统账户 <code>netsentinel</code> 运行；<b>开发</b>在每个人自己的 <code>/home/NEWUSER/github</code> 里。这样线上不依赖任何个人账户，谁离开、谁的账户被锁都不影响 knettf.com；每人改代码互不干扰，只有经过 PR 和 <code>release.sh</code> 的提交才会进入线上。</p>
      <div class="table-wrap"><table>
        <tr><th>资源</th><th>位置</th><th>说明</th></tr>
        <tr><td>平台代码（开发）</td><td>每人自己的 <code>/home/NEWUSER/github/NetSentinel</code></td><td>GitHub <code>knet-lab/NetSentinel</code>（SSH 远程，个人分支名 = 你的 Linux 用户名）；平时改代码、提交都在这里</td></tr>
        <tr><td>平台代码（线上）</td><td><code>/srv/netsentinel/prod</code></td><td>归 <code>netsentinel</code> 账户和组；GitHub <code>knet-lab/NetSentinel</code> 的 clone，停在 <code>prod</code> 分支，只由 <code>/srv/netsentinel/release.sh</code>（内部调用 <code>scripts/deploy.sh</code>）从 GitHub <code>prod</code> 更新，不要在里面改代码</td></tr>
        <tr><td>集群/检测代码（开发）</td><td>每人自己的 <code>/home/NEWUSER/github/knetsentinel</code></td><td>GitHub <code>knet-lab/knetsentinel</code>（第二个独立仓库，SSH 远程，个人分支名 = 你的 Linux 用户名）；平时改代码、提交都在这里</td></tr>
        <tr><td>集群/检测代码（运行）</td><td><code>/srv/netsentinel/knetsentinel</code></td><td>同一仓库的 clone，停在 <code>master</code> 分支，只从 merge-dev 快进；集群脚本在这里运行，数据也放在这里，不要在里面改代码</td></tr>
        <tr><td>Python 环境</td><td>两个目录各有一个 <code>.venv</code>（uv 管理）</td><td>依赖见 <code>pyproject.toml</code> / <code>uv.lock</code></td></tr>
        <tr><td>Terraform 扫描工具</td><td><code>/srv/netsentinel/tools/checkov/bin/checkov</code></td><td>归 <code>netsentinel</code> 账户的独立 venv，依赖见 <code>deploy/checkov-requirements.txt</code>；路径由 settings 的 <code>AUTOTF_TOOLS_BIN</code> 决定</td></tr>
        <tr><td>后端服务</td><td><code>/etc/systemd/system/netsentinel.service</code></td><td>系统服务，以 <code>netsentinel</code> 账户运行 <code>/srv/netsentinel/prod</code>，uvicorn 监听 8080</td></tr>
        <tr><td>隧道</td><td><code>/etc/systemd/system/cloudflared-knettf.service</code> + <code>/etc/cloudflared/knettf/config.yml</code></td><td>knettf.com → localhost:8080，以 <code>netsentinel</code> 账户运行</td></tr>
        <tr><td>定时任务</td><td><code>/etc/cron.d/netsentinel</code></td><td>每天 0 点以 <code>netsentinel</code> 账户用 <code>/srv/netsentinel/prod</code> 执行 <code>manage.py rotate_partitions --database vigil</code></td></tr>
        <tr><td>数据库</td><td>SQLite：两个目录各自的 <code>backend/db.sqlite3</code>（线上以 <code>/srv/netsentinel/prod</code> 为准）；PostgreSQL：Docker 容器 <code>pg</code>（5432，线上库 <code>vigil</code>，开发库 <code>vigil_dev</code>）</td><td>容器数据在 <code>/home/docker-data</code>，不属于任何个人家目录</td></tr>
        <tr><td>密钥/口令</td><td>两个目录各自的 <code>backend/backend/.env</code>：线上那份有 <code>SECRET_KEY</code>、<code>DEBUG=False</code>、<code>VIGIL_BRIDGE_TOKEN</code>；PostgreSQL 密码目前是 <code>settings.py</code> 里的默认值</td><td>.env 不在 Git 里，权限 600</td></tr>
        <tr><td>运行工具</td><td><code>/usr/local/bin/uv</code>、<code>/opt/node-v22.21.1</code>；日志 <code>/srv/netsentinel/logs</code>，备份 <code>/srv/netsentinel/backups</code></td><td>装在系统路径，<code>netsentinel</code> 账户和每个人都能用，不依赖某人的家目录</td></tr>
      </table></div>
      <p>服务、隧道、定时任务、sudo 规则的配置文件都在仓库的 <code>deploy/</code> 目录里，改了要提交，重装时照下表复制，机器上的配置因此始终能从 Git 恢复：</p>
      <div class="table-wrap"><table>
        <tr><th>仓库文件</th><th>装到</th></tr>
        <tr><td><code>deploy/systemd/netsentinel.service</code></td><td><code>/etc/systemd/system/netsentinel.service</code></td></tr>
        <tr><td><code>deploy/systemd/cloudflared-knettf.service</code></td><td><code>/etc/systemd/system/cloudflared-knettf.service</code></td></tr>
        <tr><td><code>deploy/cloudflared-knettf.yml</code></td><td><code>/etc/cloudflared/knettf/config.yml</code>（隧道凭证 JSON 在同一目录，不进 Git）</td></tr>
        <tr><td><code>deploy/cron.netsentinel</code></td><td><code>/etc/cron.d/netsentinel</code></td></tr>
        <tr><td><code>deploy/sudoers.netsentinel</code></td><td><code>/etc/sudoers.d/netsentinel</code></td></tr>
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
        <tr><td><b>一 准备工作</b><br>（只做一次，必做）</td><td>1.1 申请 Linux 账户 → 1.2 加入 GitHub 仓库 → 1.3 配置 Git → 1.4 验收</td><td><a href="#ready">准备完成验收</a> 7 项全部通过</td></tr>
        <tr><td><b>二 正式接手</b><br>（验收通过后开始）</td><td>2.1 学会操作服务 → 2.2 接手第一天 → 之后每天 <a href="/help/health">健康检查</a></td><td>第一天清单做完，之后进入日常</td></tr>
        <tr><td><b>三 交接</b><br>（有人离开时）</td><td>3.1 外部账号与口令移交 → 锁定离开者的账户</td><td>离开者的账户锁定后线上照常</td></tr>
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
cat /home/NEWUSER/.ssh/id_ed25519.pub

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
      <h2>1.2 GitHub：加入 knet-lab 组织</h2>
      <p>两个仓库都在实验室组织 <code>knet-lab</code> 下。<code>user.email</code> 只决定提交上<b>显示</b>谁，能不能 push 取决于你的 GitHub <b>账号</b>在不在组织里：</p>
      <div class="table-wrap"><table>
        <tr><th>仓库</th><th>本地目录</th><th>远程地址</th></tr>
        <tr><td><code>knet-lab/NetSentinel</code></td><td><code>/home/NEWUSER/github/NetSentinel</code></td><td><code>git@github.com:knet-lab/NetSentinel.git</code>（个人分支 → <code>merge-dev</code> → <code>prod</code>）</td></tr>
        <tr><td><code>knet-lab/knetsentinel</code></td><td><code>/home/NEWUSER/github/knetsentinel</code>（开发）、<code>/srv/netsentinel/knetsentinel</code>（运行）</td><td><code>git@github.com:knet-lab/knetsentinel.git</code>（个人分支 → <code>merge-dev</code> → <code>master</code>）</td></tr>
      </table></div>
      <ol>
        <li>组织的任意一位 Owner 打开 <code>https://github.com/orgs/knet-lab/people</code> → <b>Invite member</b> → 输入接手人的 GitHub 用户名。要能管理仓库和成员就给 <b>Owner</b>，只写代码给 <b>Member</b> 即可。</li>
        <li>接手人打开 <code>https://github.com/orgs/knet-lab/invitation</code> 接受，一次邀请两个仓库都能用。</li>
        <li>接手人在 GitHub <b>Settings → Emails</b> 确认要用的提交邮箱已验证。</li>
      </ol>
      <p>组织里始终保持至少两个 Owner，这样任何一个人离开都不会导致没人能管理仓库。</p>
    </section>

    <section id="git">
      <h2>1.3 本地 Git：用自己的身份提交</h2>

      <h3>先看整体流程</h3>
      <p>服务器上的每个 Linux 账户对应一个 GitHub 账号，用它自己的密钥连 GitHub、用它自己的名字提交。Linux 用户名同时当作个人分支名：</p>
      <div class="table-wrap"><table>
        <tr><th>谁</th><th>Linux 账户（= 个人分支名）</th><th>GitHub 账号</th><th>连 GitHub 的密钥</th></tr>
        <tr><td>原作者</td><td><code>soar009</code></td><td><code>Wk-P</code></td><td>—</td></tr>
        <tr><td>接手人</td><td><code>NEWUSER</code>（你自己的）</td><td>你自己的</td><td>你在第 1 步生成的</td></tr>
      </table></div>
      <p>一次代码修改从开发到上线经过下面几步，<b>审查只发生在 PR 这一处</b>，之后的分支只做快进、不再改动：</p>
      <pre><code>/home/NEWUSER/github/NetSentinel        你的开发目录，在个人分支 NEWUSER 上改代码、commit、push
        │
        ▼  在 GitHub 开 PR：NEWUSER → merge-dev
merge-dev                               另一人审查（Files changed → Review changes → Approve）后合并
        │
        ▼  /srv/netsentinel/release.sh -frontend | -backend | -all
prod                                    只从 merge-dev 快进，从不直接提交
        │
        ▼  release.sh 接着运行 deploy.sh
/srv/netsentinel/prod                   用运行者自己的 GitHub 密钥 git pull，构建，重启服务</code></pre>
      <p>knetsentinel 前半段相同（开发目录 <code>/home/NEWUSER/github/knetsentinel</code> → PR → <code>merge-dev</code>），合并后把 <code>master</code> 快进到 <code>merge-dev</code>，再在运行目录 <code>/srv/netsentinel/knetsentinel</code> 里 <code>git pull --ff-only</code>。两边的具体命令见 <a href="/help/deploy">部署修改</a>。</p>
      <p>所以下面按顺序做：用你自己的 Linux 账户配 GitHub 密钥（push 和发布时 pull 都用它）→ 从 GitHub 克隆到你的开发目录、建个人分支 → 设置提交身份 → 试一次提交。没 push、没合并到 merge-dev 的提交都不会上线。</p>

      <h3>第 1 步：在服务器上给你的账户配 GitHub 密钥</h3>
      <p>服务器上一共有两种密钥，不要混：</p>
      <div class="table-wrap"><table>
        <tr><th>密钥</th><th>私钥在哪</th><th>公钥加到哪</th><th>用途</th></tr>
        <tr><td>登录密钥（1.1）</td><td>你自己的电脑</td><td>服务器 <code>/home/NEWUSER/.ssh/authorized_keys</code></td><td>你从自己电脑 ssh 登录服务器</td></tr>
        <tr><td>GitHub 密钥（本步）</td><td>服务器 <code>/home/NEWUSER/.ssh/github_ssh_key</code></td><td>你自己的 GitHub 账号 Settings → SSH and GPG keys</td><td>服务器上以你的身份 clone / push / pull，发布时 <code>deploy.sh</code> 的 <code>git pull</code> 也用它</td></tr>
      </table></div>
      <p>以 NEWUSER 登录服务器后执行。密钥单独命名为 <code>github_ssh_key</code>，不占用默认的 <code>id_ed25519</code>，只在连 github.com 时使用，不会被拿去连别的主机：</p>
      <pre><code>ssh-keygen -t ed25519 -N "" -C "你的GitHub邮箱" -f /home/NEWUSER/.ssh/github_ssh_key
printf 'Host github.com\n    HostName github.com\n    User git\n    IdentityFile /home/NEWUSER/.ssh/github_ssh_key\n    IdentitiesOnly yes\n' &gt;&gt; /home/NEWUSER/.ssh/config
chmod 600 /home/NEWUSER/.ssh/config
cat /home/NEWUSER/.ssh/github_ssh_key.pub     # 整行复制 → GitHub 右上头像 → Settings → SSH and GPG keys → New SSH key，Key type 选 Authentication Key
ssh -T git@github.com                          # 第一次问 Are you sure you want to continue connecting 输入 yes</code></pre>
      <p>期望输出 <code>Hi 你的GitHub用户名! You've successfully authenticated</code>。<code>-N ""</code> 表示不设口令，否则每次 push、发布都要输口令；<code>IdentitiesOnly yes</code> 让 ssh 连 GitHub 时只用这一把，不去试其他密钥。</p>
      <div class="note">只用你自己的密钥。<code>ssh -T</code> 若输出的不是你的 GitHub 用户名，说明你不在自己的账户下。</div>

      <h3>第 2 步：从 GitHub 克隆到你的开发目录，建个人分支</h3>
      <p>代码只在自己家目录的开发目录里改，<b>不要</b>在 <code>/srv/netsentinel/prod</code> 或 <code>/srv/netsentinel/knetsentinel</code> 里改。先把自己加进 <code>netsentinel</code> 组（加完重新登录，<code>id</code> 里能看到才算生效），发布时才能写 <code>/srv</code> 下的目录：</p>
      <pre class="on-prod"><code>sudo usermod -aG netsentinel NEWUSER
mkdir -p /home/NEWUSER/github
git clone git@github.com:knet-lab/NetSentinel.git /home/NEWUSER/github/NetSentinel
git clone git@github.com:knet-lab/knetsentinel.git /home/NEWUSER/github/knetsentinel
git -C /home/NEWUSER/github/NetSentinel switch -c NEWUSER origin/merge-dev
git -C /home/NEWUSER/github/NetSentinel push -u origin NEWUSER
git -C /home/NEWUSER/github/knetsentinel switch -c NEWUSER origin/merge-dev
git -C /home/NEWUSER/github/knetsentinel push -u origin NEWUSER</code></pre>

      <h3>第 3 步：本地仓库的提交设置</h3>
      <p>提交身份写在<b>你自己的两个开发仓库</b>里（仓库内的 <code>.git/config</code>），只对这两个仓库生效，不影响你账户下的其他项目：</p>
      <pre><code>git -C /home/NEWUSER/github/NetSentinel  config user.name  "你的GitHub用户名"
git -C /home/NEWUSER/github/NetSentinel  config user.email "你在GitHub已验证的邮箱"   # 或 GitHub 提供的 数字+用户名@users.noreply.github.com
git -C /home/NEWUSER/github/knetsentinel config user.name  "你的GitHub用户名"
git -C /home/NEWUSER/github/knetsentinel config user.email "你在GitHub已验证的邮箱"
git -C /home/NEWUSER/github/NetSentinel  config --local --get-regexp user     # 应显示你的名字和邮箱
git -C /home/NEWUSER/github/knetsentinel config --local --get-regexp user     # 同上</code></pre>
      <p>为什么只写在开发仓库：这两个目录只有你自己用，写在这里最精确。邮箱必须是 GitHub 上已验证的，GitHub 才会把提交关联到你的账号。线上目录 <code>/srv/netsentinel/prod</code> 和 <code>/srv/netsentinel/knetsentinel</code> 是大家共用的、只 pull 不提交，<b>不要</b>在里面设身份，否则谁在那里提交都会显示成同一个人。</p>

      <h3>第 4 步：试一次提交</h3>
      <p>用一个临时分支试，不弄脏个人分支。knetsentinel 把路径换成 <code>/home/NEWUSER/github/knetsentinel</code> 再做一遍：</p>
      <pre><code>cd /home/NEWUSER/github/NetSentinel
git switch -c test/handover
git commit --allow-empty -m "test: handover commit"
git log -1 --format='%an &lt;%ae&gt;'     # 应是你自己
git push -u origin test/handover     # GitHub 上作者应是你
git switch NEWUSER
git push origin --delete test/handover
git branch -D test/handover</code></pre>

      <h3>第 5 步：确认你能发布（线上目录的 pull）</h3>
      <p>发布时 <code>release.sh</code> → <code>deploy.sh</code> 会在 <code>/srv/netsentinel/prod</code> 里执行 <code>git pull</code>。这个目录归 <code>netsentinel</code>，但 <code>git pull</code> 由<b>运行 release.sh 的那个账户</b>执行，用的是<b>那个账户</b>的 GitHub 密钥：也就是你在第 1 步加的 <code>/home/NEWUSER/.ssh/github_ssh_key</code>。先确认它能从这里 fetch：</p>
      <pre><code>git -C /srv/netsentinel/prod fetch origin     # 以 NEWUSER 执行，不报错即可</code></pre>
      <p>报 <code>Permission denied (publickey)</code> → 回到第 1 步；报 <code>insufficient permission</code> 或 <code>dubious ownership</code> → 还没加进 <code>netsentinel</code> 组或没重新登录（第 2 步）。</p>

      <h3>常见错误</h3>
      <div class="table-wrap"><table>
        <tr><th>现象</th><th>原因</th><th>处理</th></tr>
        <tr><td><code>Permission denied (publickey)</code></td><td>服务器上你账户的公钥没加到 GitHub</td><td>第 1 步</td></tr>
        <tr><td><code>Permission to knet-lab/NetSentinel.git denied to 你的用户名</code></td><td>还没接受 knet-lab 组织的邀请</td><td>1.2</td></tr>
        <tr><td>提交作者显示 Wk-P</td><td>在 soar009 账户下提交了，或你的开发仓库里没设身份</td><td>第 3 步</td></tr>
        <tr><td><code>detected dubious ownership</code></td><td>仓库属于别的账户</td><td><code>git config --global --add safe.directory 仓库路径</code>（线上目录已在系统级配置里加过）</td></tr>
        <tr><td><code>insufficient permission for adding an object</code></td><td>/srv 下有文件不是组可写</td><td><code>sudo chmod -R g+rwX /srv/netsentinel/prod/.git</code>，确认 umask 002</td></tr>
      </table></div>
    </section>

    <section id="ready">
      <h2>1.4 准备完成验收（阶段一到此结束）</h2>
      <p>用<b>你自己的账户</b>登录服务器，逐条执行。7 条都符合，准备工作才算结束；任何一条不符合，回到对应小节。</p>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>检查</th><th>应该看到</th><th>不符合回到</th></tr>
        <tr><td>1</td><td><code>ssh NEWUSER@192.168.0.247</code></td><td>用密钥直接登录，不问密码</td><td>1.1 SSH 登录</td></tr>
        <tr><td>2</td><td><code>id</code></td><td>组和批准的一致（如 sudo、docker、libvirt）</td><td>1.1 流程第 3 步</td></tr>
        <tr><td>3</td><td><code>sudo systemctl is-active netsentinel cloudflared-knettf</code>；<code>id</code> 里有 <code>netsentinel</code> 组</td><td><code>active</code></td><td>1.1（缺 sudo 组）</td></tr>
        <tr><td>4</td><td><code>kubectl get nodes</code></td><td>5 个节点 <code>Ready</code></td><td>1.1 kubectl</td></tr>
        <tr><td>5</td><td><code>ssh -T git@github.com</code></td><td><code>Hi 你的GitHub用户名!</code></td><td>1.3 第 1 步</td></tr>
        <tr><td>6</td><td>在两个仓库各试一次提交并 push</td><td>GitHub 上作者是你，不是 Wk-P</td><td>1.2、1.3 第 2–4 步</td></tr>
        <tr><td>7</td><td><code>git -C /srv/netsentinel/prod fetch origin</code>，以自己的账户执行</td><td>不报错</td><td>1.3 第 1、5 步</td></tr>
      </table></div>
    </section>

    <div class="phase"><div class="phase-n">阶段二</div><div><b>正式接手</b><br>验收通过后从这里开始。你开始负责线上服务。</div></div>

    <section id="transition">
      <h2>2.1 日常怎么操作服务</h2>
      <p>后端和隧道是系统服务，以 <code>netsentinel</code> 账户运行，用你自己的账户加 sudo 操作，不用切到 soar009：</p>
      <pre class="on-prod"><code>sudo systemctl status netsentinel cloudflared-knettf
sudo systemctl restart netsentinel
sudo journalctl -u netsentinel -f
cat /etc/cron.d/netsentinel              # 看定时任务
tail /srv/netsentinel/logs/rotate_partitions.log</code></pre>
      <div class="note">不要在 <code>sudo -iu soar009</code> 下 <b>git commit</b>，提交会记到原作者 Wk-P 名下。my-code 的服务是 soar009 的 user 服务（<code>sudo -iu soar009 systemctl --user ...</code>），不归你管。</div>
    </section>

    <section id="day1">
      <h2>2.2 接手第一天</h2>
      <p>按顺序做一次，之后转入每天的 <a href="/help/health">健康检查</a>。</p>
      <ol>
        <li>完整做一遍 <a href="/help/health">每日健康检查</a>，记下各项的正常值，作为以后对比的基线。</li>
        <li>改掉网站默认账号 admin / alice / bob 的密码（<a href="/help/account">账号与令牌</a>）——它们写在代码里，等于公开。</li>
        <li>在网站管理后台 Users 里核对账号，删掉或停用陌生账号。</li>
        <li>读一遍 <a href="/help/trouble#dont">不要做的事</a> 和 <a href="/help/power">开关机与恢复</a>，知道宿主机重启后要做什么。</li>
        <li>确认已经从原作者那里当面拿到：网页管理员账号、线上 <code>.env</code> 里的 token、PostgreSQL 密码（见 3.1 第 5 条）。</li>
        <li>读 <a href="/help/index#envs">开发与生产</a>：知道哪个目录是线上、怎么用 <code>release.sh</code> 上线。</li>
      </ol>
      <div class="learn">做到这里，你已经正式接手。阶段三在以后有人离开时再做。</div>
    </section>

    <div class="phase"><div class="phase-n">阶段三</div><div><b>交接</b><br>任何一个 owner 离开时做，保证剩下的人仍能管住所有外部账号。</div></div>

    <section id="offboard">
      <h2>3.1 有人离开时的交接</h2>
      <ol>
        <li><a href="#ready">准备完成验收</a> 全部通过。</li>
        <li>GitHub：knet-lab 组织里保持至少两个 Owner，离开者移出前确认其余 Owner 已在（1.2）。</li>
        <li>Cloudflare：knettf.com 和隧道在原作者的 Cloudflare 账号里，要把留下的人加为成员（Manage Account → Members）。</li>
        <li>Tailscale：tailnet 属于原作者，要么邀请留下的人，要么改用留下的人自己的 tailnet（1.1）。</li>
        <li>当面移交：网页管理员账号、<code>/srv/netsentinel/prod/backend/backend/.env</code>（SECRET_KEY、VIGIL_BRIDGE_TOKEN）、PostgreSQL 密码（vigil 用户，当前是 <code>settings.py</code> 里的默认值）。</li>
        <li>锁定离开者的账户。NetSentinel 线上不在任何个人账户下，锁谁都不影响它；但 soar009 下还跑着 my-code 的服务和隧道，锁 soar009（或关 linger）会把它们一起停掉，要先和 my-code 的负责人确认：
          <pre><code>sudo usermod -L 用户名              # 只锁密码；密钥登录要另外删 /home/用户名/.ssh/authorized_keys
sudo gpasswd -d 用户名 sudo</code></pre></li>
      </ol>
    </section>
  </div>
</template>

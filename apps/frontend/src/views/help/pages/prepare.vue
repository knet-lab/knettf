<template>
  <div v-pre>
        <h1>账户、权限与 GitHub</h1>
    <div class="meta">申请你自己的 Linux 账户和权限、加入 GitHub 组织、配好密钥和提交身份，最后用 2.4 验收。这一步还不碰线上服务。<br>
      本页所有命令、路径、IP 都是按这台机器实际情况写的。命令里的 <code>NEWUSER</code> 指接手人<b>自己新建的</b>账户，执行时替换成你的用户名。</div>

    <section id="before">
      <h2>开始之前</h2>
      <p>先读完 <a href="/help/start">第 1 步</a>，知道系统由哪几块组成。机器本身的情况（主机、地址、其他项目、配置文件位置）见 <a href="/help/index#machine">系统总览 · 这台机器</a>。这一步做完，你在服务器和 GitHub 上都有自己的身份，但还不碰线上服务。</p>
    </section>

    <section id="user">
      <h2>2.1 账户与权限</h2>
      <p>项目只有两个人：<b>原作者</b>（Linux 账户 <code>soar009</code>）和<b>接手人</b>。接手人用自己新建的 Linux 账户工作，不用 <code>cis</code>（装机时的共用账户，谁做的操作都查不到），也不借用 <code>soar009</code> 的密码或密钥。</p>
      <div class="table-wrap"><table>
        <tr><th>步骤</th><th>谁做</th><th>做什么</th></tr>
        <tr><td>1</td><td>接手人</td><td>在自己电脑上生成登录密钥，把想用的 Linux 用户名和公钥发给原作者</td></tr>
        <tr><td>2</td><td>原作者</td><td>在服务器上建账户、放公钥、加组</td></tr>
        <tr><td>3</td><td>接手人</td><td>登录，确认组都在</td></tr>
        <tr><td>4</td><td>原作者</td><td>给接手人复制一份集群凭证，需要外网访问时邀请进 Tailscale</td></tr>
        <tr><td>5</td><td>接手人</td><td>确认能操作集群</td></tr>
      </table></div>

      <h3>第 1 步 · 接手人：生成登录密钥</h3>
      <p>在<b>你自己的电脑</b>上执行，把生成的 <code>id_ed25519.pub</code> 整行内容和你想用的用户名发给原作者。这台服务器只认密钥，不接受密码登录。</p>
      <pre><code>ssh-keygen -t ed25519 -C "NEWUSER@cis-Z10PE-D8-WS"</code></pre>

      <h3>第 2 步 · 原作者：建账户、放公钥、加组</h3>
      <pre class="on-prod"><code>sudo adduser NEWUSER                                         # 设一个密码，只用于 sudo
sudo usermod -aG sudo,docker,libvirt,netsentinel NEWUSER
sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.ssh
echo '收到的整行公钥' | sudo tee -a /home/NEWUSER/.ssh/authorized_keys
sudo chown NEWUSER:NEWUSER /home/NEWUSER/.ssh/authorized_keys
sudo chmod 600 /home/NEWUSER/.ssh/authorized_keys</code></pre>
      <div class="table-wrap"><table>
        <tr><th>组</th><th>为什么需要</th></tr>
        <tr><td><code>sudo</code></td><td>管理服务（<code>sudo systemctl restart netsentinel</code>）、看日志、改线上 <code>.env</code></td></tr>
        <tr><td><code>docker</code></td><td>操作数据库容器 <code>pg</code>（备份、查数据）。也能看到别的项目的容器，不要动它们</td></tr>
        <tr><td><code>libvirt</code></td><td>开关和重建 5 台集群虚拟机（<code>virsh -c qemu:///system</code>）</td></tr>
        <tr><td><code>netsentinel</code></td><td>写 <code>/srv/netsentinel</code> 下的目录，发布（<code>release.sh</code>）和替换模型都需要</td></tr>
      </table></div>

      <h3>第 3 步 · 接手人：登录并确认</h3>
      <pre><code>ssh NEWUSER@192.168.0.247        # 实验室内网
id                               # 应看到 sudo、docker、libvirt、netsentinel</code></pre>
      <p>在外网要通过 Tailscale 地址 <code>100.117.219.123</code> 登录，见第 4 步。</p>

      <h3>第 4 步 · 原作者：集群凭证和 Tailscale</h3>
      <pre class="on-prod"><code>sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.kube
sudo install -o NEWUSER -g NEWUSER -m 600 /home/soar009/.kube/config /home/NEWUSER/.kube/config</code></pre>
      <p>Tailscale 网络在原作者的账号下：接手人需要从外网登录时，原作者在 Tailscale 后台 <b>Users → Invite users</b> 邀请接手人。</p>

      <h3>第 5 步 · 接手人：确认能操作集群</h3>
      <pre><code>kubectl get nodes                # 应看到 k8s-master、k8s-node1~4 共 5 个 Ready</code></pre>
    </section>

    <section id="github">
      <h2>2.2 GitHub：加入 knet-lab 组织</h2>
      <p>仓库 <code>knet-lab/knettf</code> 在实验室组织 <code>knet-lab</code> 下，平台（<code>apps/</code>、<code>detector/</code>、<code>ops/</code>）和实验环境（<code>lab/</code>，原 knetsentinel）都在里面。<code>user.email</code> 只决定提交上<b>显示</b>谁，能不能 push 取决于你的 GitHub <b>账号</b>在不在组织里：</p>
      <div class="table-wrap"><table>
        <tr><th>仓库</th><th>本地目录</th><th>远程地址</th></tr>
        <tr><td><code>knet-lab/knettf</code></td><td><code>/home/NEWUSER/github/knettf</code>（开发）；运行目录 <code>/srv/netsentinel/prod</code>（平台）、<code>/srv/netsentinel/lab</code>（实验环境，由 <code>lab/sync-to-srv.sh</code> 同步）</td><td><code>git@github.com:knet-lab/knettf.git</code>（个人分支 → <code>merge-dev</code> → <code>prod</code>）</td></tr>
      </table></div>
      <ol>
        <li>组织的任意一位 Owner 打开 <code>https://github.com/orgs/knet-lab/people</code> → <b>Invite member</b> → 输入接手人的 GitHub 用户名。要能管理仓库和成员就给 <b>Owner</b>，只写代码给 <b>Member</b> 即可。</li>
        <li>接手人打开 <code>https://github.com/orgs/knet-lab/invitation</code> 接受，即可访问仓库。</li>
        <li>接手人在 GitHub <b>Settings → Emails</b> 确认要用的提交邮箱已验证。</li>
      </ol>
      <p>组织里始终保持至少两个 Owner，这样任何一个人离开都不会导致没人能管理仓库。</p>
    </section>

    <section id="git">
      <h2>2.3 本地 Git：用自己的身份提交</h2>

      <h3>先看整体流程</h3>
      <p>服务器上的每个 Linux 账户对应一个 GitHub 账号，用它自己的密钥连 GitHub、用它自己的名字提交。Linux 用户名同时当作个人分支名：</p>
      <div class="table-wrap"><table>
        <tr><th>谁</th><th>Linux 账户（= 个人分支名）</th><th>GitHub 账号</th><th>连 GitHub 的密钥</th></tr>
        <tr><td>原作者</td><td><code>soar009</code></td><td><code>Wk-P</code></td><td>—</td></tr>
        <tr><td>接手人</td><td><code>NEWUSER</code>（你自己的）</td><td>你自己的</td><td>你在第 1 步生成的</td></tr>
      </table></div>
      <p>一次代码修改从开发到上线经过下面几步，<b>审查只发生在 PR 这一处</b>，之后的分支只做快进、不再改动：</p>
      <pre class="uml">flowchart LR
  A["开发目录<br>个人分支 NEWUSER"] -->|"① PR + 审查"| B["merge-dev"]
  B -->|"② release.sh"| C["prod"]
  C -->|"③ deploy.sh"| D["线上目录"]
  classDef dev fill:#f0fff4,stroke:#38a169,color:#1a202c
  classDef gh fill:#f8fafc,stroke:#1a202c,color:#1a202c
  classDef prod fill:#fff5f5,stroke:#e53e3e,color:#1a202c
  class A dev
  class B,C gh
  class D prod</pre>
      <ol>
        <li><b>PR + 审查</b>：在 <code>/home/NEWUSER/github/knettf</code> 的个人分支 <code>NEWUSER</code> 上 commit、push，开 PR 到 <code>merge-dev</code>，另一人审查（Files changed → Review changes → Approve）后合并。</li>
        <li><b>release.sh</b>：运行 <code>/srv/netsentinel/release.sh -frontend | -backend | -all</code>，把 <code>prod</code> 快进到 <code>merge-dev</code>，从不直接在 prod 上提交。</li>
        <li><b>deploy.sh</b>：在 <code>/srv/netsentinel/prod</code> 里用运行者自己的 GitHub 密钥 <code>git pull</code>，构建，重启服务。</li>
      </ol>
      <p>实验环境 <code>lab/</code> 也走同一个 PR 流程；合并到 <code>merge-dev</code> 后，在自己的开发目录里运行 <code>bash lab/sync-to-srv.sh</code> 把代码同步到运行目录 <code>/srv/netsentinel/lab</code>。具体命令见 <a href="/help/deploy">部署修改</a>。</p>
      <p>所以下面按顺序做：用你自己的 Linux 账户配 GitHub 密钥（push 和发布时 pull 都用它）→ 从 GitHub 克隆到你的开发目录、建个人分支 → 设置提交身份 → 试一次提交。没 push、没合并到 merge-dev 的提交都不会上线。</p>

      <h3>第 1 步：在服务器上给你的账户配 GitHub 密钥</h3>
      <p>服务器上一共有两种密钥，不要混：</p>
      <div class="table-wrap"><table>
        <tr><th>密钥</th><th>私钥在哪</th><th>公钥加到哪</th><th>用途</th></tr>
        <tr><td>登录密钥（2.1）</td><td>你自己的电脑</td><td>服务器 <code>/home/NEWUSER/.ssh/authorized_keys</code></td><td>你从自己电脑 ssh 登录服务器</td></tr>
        <tr><td>GitHub 密钥（本步）</td><td>服务器 <code>/home/NEWUSER/.ssh/github_ssh_key</code></td><td>你自己的 GitHub 账号 Settings → SSH and GPG keys</td><td>服务器上以你的身份 clone / push / pull，发布时 <code>release.sh</code> 的 push 和 <code>deploy.sh</code> 的 <code>git pull</code> 也用它</td></tr>
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
      <p>代码只在自己家目录的开发目录里改，<b>不要</b>在 <code>/srv/netsentinel/prod</code> 或 <code>/srv/netsentinel/lab</code> 里改。发布要写 <code>/srv</code> 下的目录，所以 2.1 已经把你加进了 <code>netsentinel</code> 组：</p>
      <pre><code>mkdir -p /home/NEWUSER/github
git clone git@github.com:knet-lab/knettf.git /home/NEWUSER/github/knettf
git -C /home/NEWUSER/github/knettf switch -c NEWUSER origin/merge-dev
git -C /home/NEWUSER/github/knettf push -u origin NEWUSER</code></pre>

      <h3>第 3 步：本地仓库的提交设置</h3>
      <p>提交身份写在<b>你自己的开发仓库</b>里（仓库内的 <code>.git/config</code>），只对这个仓库生效，不影响你账户下的其他项目：</p>
      <pre><code>git -C /home/NEWUSER/github/knettf  config user.name  "你的GitHub用户名"
git -C /home/NEWUSER/github/knettf  config user.email "你在GitHub已验证的邮箱"   # 或 GitHub 提供的 数字+用户名@users.noreply.github.com
git -C /home/NEWUSER/github/knettf  config --local --get-regexp user     # 应显示你的名字和邮箱
      <p>为什么只写在开发仓库：这个目录只有你自己用，写在这里最精确。邮箱必须是 GitHub 上已验证的，GitHub 才会把提交关联到你的账号。线上目录 <code>/srv/netsentinel/prod</code> 和 <code>/srv/netsentinel/lab</code> 是大家共用的运行目录，不提交，<b>不要</b>在里面设身份，否则谁在那里提交都会显示成同一个人。</p>

      <h3>第 4 步：试一次提交</h3>
      <p>用一个临时分支试，不弄脏个人分支：</p>
      <pre><code>cd /home/NEWUSER/github/knettf
git switch -c test/handover
git commit --allow-empty -m "test: handover commit"
git log -1 --format='%an &lt;%ae&gt;'     # 应是你自己
git push -u origin test/handover     # GitHub 上作者应是你
git switch NEWUSER
git push origin --delete test/handover
git branch -D test/handover</code></pre>

      <h3>第 5 步：确认你能发布（push prod、pull 线上目录）</h3>
      <p>发布时两个脚本都在 <code>/srv/netsentinel/prod</code> 里操作 GitHub：<code>release.sh</code> 执行 <code>git push origin origin/merge-dev:prod</code>（往 GitHub 推），<code>deploy.sh</code> 执行 <code>git pull</code>（从 GitHub 拉）。这个目录归 <code>netsentinel</code>，但 Git 命令由<b>运行 release.sh 的那个账户</b>执行，用的是<b>那个账户</b>的 GitHub 密钥，也就是你在第 1 步加的 <code>/home/NEWUSER/.ssh/github_ssh_key</code>。所以要确认它在这里既能拉也能推：</p>
      <pre><code>git -C /srv/netsentinel/prod fetch origin                                   # 能拉：不报错即可
git -C /srv/netsentinel/prod push --dry-run origin origin/prod:prod         # 能推：只演练不推送，输出 Everything up-to-date 即可</code></pre>
      <p>报 <code>Permission denied (publickey)</code> → 回到第 1 步；push 报 <code>Permission to knet-lab/knettf.git denied</code> → 你的 GitHub 账号在组织里没有写权限（2.2）；报 <code>insufficient permission</code> 或 <code>dubious ownership</code> → 还没加进 <code>netsentinel</code> 组（2.1 第 2 步），或加组后没重新登录。</p>

      <h3>常见错误</h3>
      <div class="table-wrap"><table>
        <tr><th>现象</th><th>原因</th><th>处理</th></tr>
        <tr><td><code>Permission denied (publickey)</code></td><td>服务器上你账户的公钥没加到 GitHub</td><td>第 1 步</td></tr>
        <tr><td><code>Permission to knet-lab/knettf.git denied to 你的用户名</code></td><td>还没接受 knet-lab 组织的邀请</td><td>2.2</td></tr>
        <tr><td>提交作者显示 Wk-P</td><td>在 soar009 账户下提交了，或你的开发仓库里没设身份</td><td>第 3 步</td></tr>
        <tr><td><code>detected dubious ownership</code></td><td>仓库属于别的账户</td><td><code>git config --global --add safe.directory 仓库路径</code>（线上目录已在系统级配置里加过）</td></tr>
        <tr><td><code>insufficient permission for adding an object</code></td><td>/srv 下有文件不是组可写</td><td><code>sudo chmod -R g+rwX /srv/netsentinel/prod/.git</code>，确认 umask 002</td></tr>
      </table></div>
    </section>

    <section id="ready">
      <h2>2.4 准备完成验收</h2>
      <p>用<b>你自己的账户</b>登录服务器，逐条执行。7 条都符合，准备工作才算结束；任何一条不符合，回到对应小节。</p>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>检查</th><th>应该看到</th><th>不符合回到</th></tr>
        <tr><td>1</td><td><code>ssh NEWUSER@192.168.0.247</code></td><td>用密钥直接登录，不问密码</td><td>2.1 第 1–3 步</td></tr>
        <tr><td>2</td><td><code>id</code></td><td>有 sudo、docker、libvirt、netsentinel</td><td>2.1 第 2 步</td></tr>
        <tr><td>3</td><td><code>sudo systemctl is-active netsentinel cloudflared-knettf</code></td><td><code>active</code></td><td>2.1 第 2 步（缺 sudo 组）</td></tr>
        <tr><td>4</td><td><code>kubectl get nodes</code></td><td>5 个节点 <code>Ready</code></td><td>2.1 第 4–5 步</td></tr>
        <tr><td>5</td><td><code>ssh -T git@github.com</code></td><td><code>Hi 你的GitHub用户名!</code></td><td>2.3 第 1 步</td></tr>
        <tr><td>6</td><td>试一次提交并 push</td><td>GitHub 上作者是你，不是 Wk-P</td><td>2.2、2.3 第 2–4 步</td></tr>
        <tr><td>7</td><td><code>git -C /srv/netsentinel/prod fetch origin</code>，以自己的账户执行</td><td>不报错</td><td>2.3 第 1、5 步</td></tr>
      </table></div>
    </section>

  </div>
</template>

<template>
  <div v-pre>
        <h1>改动上线</h1>
    <div class="meta">改了代码或配置之后，怎么让它在线上生效、会影响谁、怎么确认成功。<br>
      流程固定为：在开发目录 <code class="vn">/home/NEWUSER/github/NetSentinel</code> 的<b>个人分支</b>上改、<code>git commit</code>、<code>git push</code> → 在 GitHub 开 PR 合并到 <code>merge-dev</code> → 对方审核后合并 → 运行 <code>/srv/netsentinel/release.sh</code>，把 <code>merge-dev</code> 原样快进到 <code>prod</code> 并调用 <code>scripts/deploy.sh</code>，部署脚本把 GitHub 上的 <code>prod</code> 拉到线上目录 <code class="vp">/srv/netsentinel/prod</code> 再构建、重启。两个目录的分工见 <a href="/help/index#envs">开发与生产</a>。其他改动按后面几节逐项做。</div>

    <section id="branches">
      <h2>分支与协作规则</h2>
      <pre class="uml">sequenceDiagram
  autonumber
  actor Dev as 开发者 NEWUSER
  participant Local as 开发目录<br>/home/NEWUSER/github/NetSentinel
  participant GH as GitHub<br>knet-lab/NetSentinel
  actor Rev as 审查人（另一位 owner）
  participant Rel as /srv/netsentinel/release.sh
  participant Prod as /srv/netsentinel/prod
  Dev->>Local: git switch NEWUSER，git pull origin merge-dev（先跟上已合并的改动）
  Dev->>Local: 改代码、本地测试、git commit
  Local->>GH: git push origin NEWUSER
  Dev->>GH: 开 PR：base = merge-dev，compare = NEWUSER，Reviewers 选对方
  GH->>Rev: Files changed 逐行审查 → Review changes
  alt Request changes
    Rev-->>Dev: 要改：在原分支继续 commit、push，PR 自动更新，回到第 2 步
  else Approve
    Rev-->>Dev: 同意
    Dev->>GH: Merge pull request，提交进入 merge-dev
  end
  Dev->>Rel: release.sh -frontend（或 -backend、-all）
  Rel->>GH: 列出 origin/prod..origin/merge-dev，输入 y，把 prod 快进到 merge-dev（不产生新提交）
  Rel->>Prod: 调用 scripts/deploy.sh
  Prod->>GH: git pull --ff-only（用运行者自己的 GitHub 密钥）
  Prod->>Prod: 构建 / 迁移 → 重启 netsentinel → HTTP 200 → https://knettf.com</pre>
      <p>⑤ 下次开始干活时回到 ①：<code>git pull origin merge-dev</code> 会带回 PR 的合并提交和对方的改动。</p>
      <div class="table-wrap"><table>
        <tr><th>分支</th><th>谁改、怎么改</th><th>作用</th></tr>
        <tr><td>个人分支（<code>NEWUSER</code> 等）</td><td>本人随便 commit / push</td><td>自己的工作区，别人不往里推。每人一个，名字和 Linux 用户名一致</td></tr>
        <tr><td><code>merge-dev</code></td><td>只能通过 PR 合并，<b>不直接 push</b></td><td>两人改动的汇合点，也是 GitHub 默认分支；上面的每个提交都经过对方审核</td></tr>
        <tr><td><code>prod</code></td><td>只用 <code>git push origin origin/merge-dev:prod</code> 快进，<b>不 commit、不开 PR、不 force push</b></td><td>线上运行的版本，永远是 merge-dev 上某个已审核的提交</td></tr>
      </table></div>
      <div class="note">仓库是免费组织的私有仓库，GitHub 的分支保护（Rulesets）<b>不生效</b>，以上规则靠两人遵守。唯一由 Git 自动把关的是：不加 <code>-f</code> 时，非快进的 push 会被拒绝，所以 prod 不会被意外改写。<b>任何时候都不要用 <code>git push -f</code></b>。</div>
      <div class="task"><h4><span class="n">1</span>审核：在 PR 上进行</h4>
        <div class="do"><div>开 PR 时在右侧 <b>Reviewers</b> 点齿轮选对方。对方打开 PR → <b>Files changed</b> 逐行看，可以在行上留评论 → 右上 <b>Review changes</b> 选 <b>Approve</b>（同意）或 <b>Request changes</b>（要改）。要改时作者在自己的分支上继续 commit、push，PR 自动更新，再审一次。Approve 后由作者点 <b>Merge pull request</b>。</div></div>
        <div class="why"><div>审核只做一次，就在进 merge-dev 之前。prod 和 merge-dev 内容完全相同，发布时不需要再审；发布前看一眼 <code>git log origin/prod..origin/merge-dev</code> 即可。</div></div>
        <div class="res"><div>PR 页面显示 <code>merged ... into merge-dev from NEWUSER</code>。看清楚是 <b>into merge-dev</b>。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>常见情况</h4>
        <div class="do"><div><div class="table-wrap"><table>
          <tr><th>情况</th><th>做法</th></tr>
          <tr><td>对方的 PR 已合并，我要跟上</td><td><code>git switch NEWUSER && git pull origin merge-dev</code>，有冲突就在自己分支上解决后 commit、push</td></tr>
          <tr><td>PR 冲突（GitHub 显示 This branch has conflicts）</td><td>同上：在自己分支上 <code>git pull origin merge-dev</code>，解决冲突后 push，PR 自动变为可合并</td></tr>
          <tr><td>PR 的 base 选错了</td><td>合并前：PR 标题旁 Edit，把 base 改成 <code>merge-dev</code>。已经合进别的分支：不用撤，重新开一个 base 为 <code>merge-dev</code> 的 PR</td></tr>
          <tr><td>GitHub 首页提示 “prod had recent pushes · Compare &amp; pull request”</td><td>忽略，<b>不要点</b>。prod 不走 PR</td></tr>
          <tr><td>发布时 <code>rejected (non-fast-forward)</code></td><td>说明 prod 上有 merge-dev 没有的提交（有人直接改了 prod）。用 <code>git log origin/merge-dev..origin/prod</code> 查是什么，两人商量，把需要的改动走 PR 进 merge-dev 后再发布</td></tr>
          <tr><td>上线后出问题要回退</td><td>在个人分支上 <code>git revert &lt;提交&gt;</code> → PR → 快进 prod → 部署。不要在线上目录里改代码，也不要把 prod 往回 reset</td></tr>
          <tr><td>新成员加入</td><td>owner 在 GitHub Settings → Collaborators 邀请（Write 权限）；Linux 账户见 <a href="/help/prepare">接手准备</a>；个人分支从 merge-dev 建：<code>git switch -c NEWUSER origin/merge-dev && git push -u origin NEWUSER</code></td></tr>
        </table></div></div></div>
        <div class="why"><div>所有改动都只从个人分支进入，经过 merge-dev 再到 prod，任何时候都能用 <code>git log</code> 查到某个线上版本是谁、在哪个 PR 里改的。</div></div>
        <div class="res"><div><code>git branch -a</code> 只有 <code>merge-dev</code>、<code>prod</code> 和各人的个人分支，没有 main。</div></div>
      </div>
    </section>

    <section id="before">
      <h2>上线前</h2>
      <div class="note">分支：每人一个个人分支（如 <code>NEWUSER</code>），只在自己的分支上 commit；<code>merge-dev</code> 只通过 PR 合并；<code>prod</code> 只从 <code>merge-dev</code> 快进，不在上面做任何修改。没有 main 分支。</div>
      <div class="task"><h4><span class="n">1</span>在个人分支上验证并提交</h4>
        <div class="do"><div><pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/NetSentinel</span> && git switch <span class="vn">NEWUSER</span>
git pull origin merge-dev                 # 先合进别人已合并的改动
git status && git diff
git add -A && git commit -m "模块：说明"
git push origin <span class="vn">NEWUSER</span></code></pre>提交前先在开发环境（<code>runserver 8090</code> + <code>pnpm dev</code>）跑一遍。</div></div>
        <div class="why"><div>先合进 <code>merge-dev</code>，冲突在自己的分支上解决，不会带进 PR。</div></div>
        <div class="res"><div>只有你这次的改动。<code>dist/</code>、<code>.venv/</code>、<code>node_modules/</code>、<code>db.sqlite3</code>、<code>.env</code> 不提交。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>开 PR 合并到 merge-dev</h4>
        <div class="do"><div>GitHub 上 knet-lab/NetSentinel → Pull requests → New：base 选 <code>merge-dev</code>，compare 选你的分支。对方看过后合并。</div></div>
        <div class="why"><div><code>merge-dev</code> 是两个人改动的汇合点，只通过 PR 进入，每次合并都有记录、有人看过。</div></div>
        <div class="res"><div>PR 显示 Merged，<code>merge-dev</code> 上出现这次的提交。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>把 merge-dev 发布到 prod</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/release.sh -frontend    # 或 -backend / -all；不带参数只快进 prod、不部署</code></pre><code>release.sh</code> 是服务器上的工具，<b>不在 Git 里</b>（<code>.gitignore</code> 已排除，不要复制进仓库提交）。它依次：<code>git fetch</code> → 检查 prod 能否快进到 merge-dev → 列出这次要发布的提交，输入 <code>y</code> 确认 → <code>git push origin origin/merge-dev:prod</code> → 调用 <code class="vp">/srv/netsentinel/prod</code><code>/scripts/deploy.sh</code>（参数原样传入，即下一节的部署）。等价的手动做法：<pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/NetSentinel</span> && git fetch origin
git log --oneline origin/prod..origin/merge-dev   # 这次要发布的提交
git push origin origin/merge-dev:prod             # 只能快进，不能快进时会被拒绝</code></pre></div></div>
        <div class="why"><div><code>prod</code> 和 <code>merge-dev</code> 是同一串提交，发布时不产生新提交、不改代码，上线的就是 merge-dev 上确认过的那个版本。部署脚本只认 GitHub 上的 <code>prod</code>：线上目录 <code class="vp">/srv/netsentinel/prod</code> 停在 <code>prod</code> 分支，从 GitHub 执行 <code>git pull --ff-only</code>（用运行者自己的 GitHub 密钥）。运行者必须在 <code>netsentinel</code> 组里；线上目录有本地改动或不在 <code>prod</code> 分支时脚本拒绝部署。出了问题用 <code>git log</code> 查是哪次改动，在个人分支上 <code>git revert</code> 后照常走 1–3 步。</div></div>
        <div class="res"><div>输出 <code>... -&gt; prod</code>。<span class="bad">rejected (non-fast-forward)</span>：有人直接改了 prod，先查清楚，不要 force push。</div></div>
      </div>
      <div class="note"><span class="tag tag-k">K</span> knetsentinel 走同样的流程：在开发目录 <code>/home/NEWUSER/github/knetsentinel</code> 的个人分支上改 → PR 合并到 <code>merge-dev</code> → 把 <code>master</code> 快进到 merge-dev，并更新运行目录：<pre><code>git -C /srv/netsentinel/knetsentinel push origin origin/merge-dev:master
git -C /srv/netsentinel/knetsentinel pull --ff-only origin master</code></pre>不要直接在 <code>/srv/netsentinel/knetsentinel</code> 里改代码。数据（<code>dataset/</code>、<code>logs/</code>、<code>*.csv</code>）和 minikube 旧脚本不在 Git 里，只在运行目录。</div>
    </section>

    <section id="script">
      <h2>前端 / 后端代码：用发布脚本</h2>
      <p>下面每一步都在 PR 合并到 <code>merge-dev</code> 之后运行。<code>release.sh</code> 先把 prod 快进到 merge-dev，再把参数原样交给 <code class="vp">/srv/netsentinel/prod</code><code>/scripts/deploy.sh</code>。只想按当前 prod 重新构建（不发布新提交）时直接运行 <code>/srv/netsentinel/prod/scripts/deploy.sh -frontend</code> 等。</p>

      <div class="task"><h4><span class="n">1</span>改了前端代码（含 <code>src/views/help/pages/</code> 下的手册）</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/release.sh -frontend      # PR 合并到 merge-dev 之后</code></pre>脚本在 <code class="vp">/srv/netsentinel/prod</code> 里 <code>git pull</code> → <code>pnpm install --frozen-lockfile</code> → <code>pnpm build</code> → 重启 <code>netsentinel</code>。</div></div>
        <div class="why"><div>浏览器拿到的是 <code>frontend/dist/</code> 里构建好的文件，不是 <code>src/</code> 源码，不构建改动就不会出现。<code>--frozen-lockfile</code> 保证依赖版本和 <code>pnpm-lock.yaml</code> 一致。线上 <code>DEBUG=False</code>，WhiteNoise 只在进程启动时扫描一次 dist，新构建的文件（文件名带新哈希）要<b>重启后</b>才能被访问，所以脚本最后会重启服务，副作用同下面后端那一步。</div></div>
        <div class="res"><div>最后输出 <code>✓ netsentinel active，HTTP 200</code>。浏览器按 <span class="kbd">Ctrl</span>+<span class="kbd">F5</span> 强制刷新即可看到。<br><span class="bad">构建失败</span>：多半是 TypeScript 类型错误，按报错的文件和行号修改。线上不受影响，旧的 dist 还在。</div></div>
      </div>

      <div class="task"><h4><span class="n">2</span>改了后端 Python 代码</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/release.sh -backend      # PR 合并到 merge-dev 之后</code></pre>脚本依次：<code>git pull</code> → <code>uv sync --frozen</code> → <code>manage.py check</code> → <code>collectstatic</code> → <code>migrate</code>（default 库）→ 重启 <code>netsentinel</code> → 最多等 20 秒，确认 8080 返回 200。</div></div>
        <div class="why"><div>Python 代码在进程启动时加载，不重启就还是旧代码。先 <code>check</code> 是为了在重启<b>之前</b>发现语法和配置错误，免得把服务重启成起不来的状态。vigil 库（PostgreSQL）<b>不会</b>自动 migrate：大表 ALTER 可能锁表很久，脚本只提示，由你确认后手动执行。</div></div>
        <div class="res"><div>最后输出 <code>✓ netsentinel active，HTTP 200</code>。<br>副作用：所有 WebSocket 断开（页面和入口 B 检测器会自动重连）；<code>flow_queue</code> 里还没处理的批次丢失；bridge 从 Kafka 已提交的 offset 继续，不重复也不漏。<br><span class="bad">20 秒内没有 200</span>：脚本会打印最后 30 行日志并以失败退出，按其中的 Traceback 修好再跑一次。<br><span class="bad">提示 vigil 有未应用的迁移</span>：看下面“数据库结构”一节。</div></div>
      </div>

      <div class="task"><h4><span class="n">3</span>前后端都改了</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/release.sh -all      # PR 合并到 merge-dev 之后</code></pre></div></div>
        <div class="why"><div>先后端再前端，最后只重启一次。</div></div>
        <div class="res"><div>依次看到上面两步的 ✓，最后是 <code>==&gt; 完成</code>。</div></div>
      </div>
    </section>

    <section id="models">
      <h2>数据库结构（models.py）</h2>
      <div class="task"><h4><span class="n">1</span>先备份</h4>
        <div class="do"><div><pre class="on-prod"><code>sqlite3 <span class="vp">/srv/netsentinel/prod</span>/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
docker exec pg pg_dump -U vigil -Fc vigil &gt; /srv/netsentinel/backups/vigil_$(date +%F).dump     # 改 vigil 表时</code></pre></div></div>
        <div class="why"><div>迁移中途失败可能让表处于改了一半的状态，有备份才能退回去。</div></div>
        <div class="res"><div>生成备份文件，大小不为 0。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>在开发目录生成迁移并检查 SQL</h4>
        <div class="do"><div><pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/NetSentinel</span>/backend
../.venv/bin/python manage.py makemigrations
../.venv/bin/python manage.py sqlmigrate &lt;app&gt; &lt;编号&gt;</code></pre></div></div>
        <div class="why"><div>执行之前先看清楚会跑什么 SQL，尤其是删列、改类型这类不可逆的操作。vigil 的 <code>DetectionRecord</code> 是 <code>managed=False</code>，改字段只会生成<b>不执行 SQL</b> 的状态迁移（<code>sqlmigrate</code> 显示 <code>(no-op)</code>），真正改表要在同一个迁移里手写 <code>RunSQL</code>（<code>ALTER TABLE vigil_detectionrecord ...</code> 会自动作用于所有分区）。</div></div>
        <div class="res"><div>新的迁移文件出现在 <code>&lt;app&gt;/migrations/</code>，SQL 符合预期。先在开发库执行（<code>migrate</code>、<code>migrate --database=vigil</code>，开发的 vigil 库是 <code>vigil_dev</code>）确认没问题，再提交迁移文件。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>执行并重启</h4>
        <div class="do"><div><pre class="on-both"><code>/srv/netsentinel/release.sh -backend      # PR 合并后；default 库会自动 migrate
cd <span class="vp">/srv/netsentinel/prod</span>/backend && ../.venv/bin/python manage.py migrate --database=vigil   # 只在改了 vigil 时
sudo systemctl restart netsentinel</code></pre></div></div>
        <div class="why"><div>vigil 是大表，ALTER 期间会锁表、阻塞写入，所以单独执行，并挑没有实验的时候做。</div></div>
        <div class="res"><div><code>showmigrations</code> 全部是 <code>[X]</code>，服务返回 200。</div></div>
      </div>
    </section>

    <section id="deps">
      <h2>依赖</h2>
      <div class="task"><h4><span class="n">1</span>Python 依赖</h4>
        <div class="do"><div>在开发目录 <code>uv add 包名</code> 并提交，然后：<pre class="on-prod"><code>/srv/netsentinel/release.sh -backend      # PR 合并到 merge-dev 之后</code></pre>整个 <code>.venv</code> 要重建时先停服务：<pre class="on-prod"><code>sudo systemctl stop netsentinel
cd <span class="vp">/srv/netsentinel/prod</span> && rm -rf .venv && uv sync --frozen
sudo systemctl start netsentinel</code></pre></div></div>
        <div class="why"><div>服务配置了 <code>Restart=always</code>：<code>.venv</code> 不完整时它每 3 秒重启失败一次，日志会被刷满，所以重建前要先停。</div></div>
        <div class="res"><div>服务 active，返回 200。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>前端依赖</h4>
        <div class="do"><div><pre class="on-both"><code>cd <span class="vn">/home/NEWUSER/github/NetSentinel</span>/frontend && pnpm add &lt;包&gt;     # 提交、push、PR 合并后：
/srv/netsentinel/release.sh -frontend</code></pre></div></div>
        <div class="why"><div><code>pnpm add</code> 会同时修改 <code>package.json</code> 和 <code>pnpm-lock.yaml</code>，两个文件都要提交，否则下一个人用 frozen-lockfile 安装时会报错。</div></div>
        <div class="res"><div>构建成功，<code>git status</code> 里能看到两个文件都有改动。</div></div>
      </div>
    </section>

    <section id="model">
      <h2>检测模型文件（ads_ml）</h2>
      <p>模型文件不在 Git 里，也不随 <code>release.sh</code> 发布：线上按版本放在 <code class="vp">/srv/netsentinel/models/ads_ml/current</code> 指向的目录，由 <code>.env</code> 的 <code>VIGIL_ADS_ML_CONFIG</code> 指定。换版本 = 新建版本目录 → <code>manage.py check_model --config …</code> → 改 <code>current</code> 软链接 → 重启；回滚把软链接指回旧版本再重启。完整步骤和流程图见 <a href="/help/detect#newmodel">4.11 替换模型与新增模型</a>。</p>
      <p>新增一个模型类（代码）照常走 PR 和 <code>release.sh -backend</code>，上线后在 <code>.env</code> 的 <code>VIGIL_MODELS</code> 里启用。</p>
    </section>

    <section id="other">
      <h2>其他改动对照表</h2>
      <div class="table-wrap"><table>
        <tr><th>改了什么</th><th>怎么做</th><th>为什么 / 结果</th></tr>
        <tr><td>线上 <code class="vp">/srv/netsentinel/prod/backend/backend/.env</code></td><td>直接编辑（不进 Git）→ <code>sudo systemctl restart netsentinel</code></td><td>环境变量只在进程启动时读一次；重启后用 <a href="/help/health">健康检查</a> 第 1 步确认</td></tr>
        <tr><td>systemd unit 文件</td><td><code>sudo systemctl daemon-reload</code> → restart</td><td>不 reload 的话 systemd 还在用旧定义；<code>systemctl cat netsentinel</code> 可确认</td></tr>
        <tr><td>cloudflared 配置</td><td><code>sudo systemctl restart cloudflared-knettf</code></td><td>公网会中断几秒</td></tr>
        <tr><td>Kafka 地址变了</td><td>改 <code>vigil/bridge.py</code> 的 <code>KAFKA_BOOTSTRAP</code>（入口 B 改 ConfigMap）→ PR → <code>release.sh -backend</code></td><td>地址是写死在代码里的；成功后日志有 <code>bridge starting</code> 且没有 <code>bridge error</code></td></tr>
        <tr><td>Vector 配置</td><td><code>kubectl apply -f /srv/netsentinel/knetsentinel/cilium-vector/vector-5nodes.yaml</code> → <code>kubectl -n kube-system rollout restart ds/vector</code></td><td>重启期间的 Hubble 事件丢失，不会补发</td></tr>
        <tr><td>单个 Kafka broker</td><td><code>kubectl delete pod kafka-broker-N</code>，等它 Running 了再处理下一个</td><td>min.insync.replicas=2，同时停两个以上会导致写入失败；数据在 PVC 上，不会丢</td></tr>
        <tr><td>Kafka controller</td><td><b>不要删</b></td><td>它是裸 Pod + emptyDir，删了不会重建，元数据丢失，只能 <a href="/help/power#rebuild-kafka">重建 Kafka</a></td></tr>
        <tr><td>hubble-relay / Cilium</td><td><code>kubectl -n kube-system rollout restart deploy/hubble-relay</code>（或 <code>ds/cilium</code>）</td><td>Vector 5 秒后自动重连；重启 Cilium 网络会短暂抖动</td></tr>
        <tr><td>单台 VM</td><td><code>kubectl drain k8s-nodeN --ignore-daemonsets --delete-emptydir-data</code> → <code>virsh reboot</code> → <code>kubectl uncordon k8s-nodeN</code></td><td>先 drain 让 Pod 正常迁走；该节点上的 broker 会等节点回来（PVC 绑定在节点上）</td></tr>
        <tr><td>PostgreSQL</td><td><code>docker restart pg</code></td><td>重启期间写库失败，那一批记录丢弃，之后自动恢复</td></tr>
      </table></div>
    </section>
  </div>
</template>

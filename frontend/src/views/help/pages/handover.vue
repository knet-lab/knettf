<template>
  <div v-pre>
    <h1>人员交接</h1>
    <div class="meta">任何一个 owner 离开时做。NetSentinel 线上由系统账户 <code>netsentinel</code> 运行，不依赖任何个人账户，所以交接的重点不是服务器，而是<b>外部账号和口令</b>：GitHub 组织、Cloudflare、Tailscale、网站管理员和线上 <code>.env</code>。保证剩下的人能管住它们，再锁离开者的账户。</div>

    <section id="offboard">
      <h2>交接清单</h2>
      <ol>
        <li>接手人已通过 <a href="/help/prepare#ready">入门第 2 步的验收</a>。</li>
        <li>GitHub：knet-lab 组织里保持至少两个 Owner，离开者移出前确认其余 Owner 已在（<a href="/help/prepare#github">入门 2.2</a>）。</li>
        <li>Cloudflare：knettf.com 和隧道在原作者的 Cloudflare 账号里，要把留下的人加为成员（Manage Account → Members）。</li>
        <li>Tailscale：tailnet 属于原作者，要么邀请留下的人，要么改用留下的人自己的 tailnet（<a href="/help/prepare#user">入门 2.1</a>）。</li>
        <li>当面移交：网页管理员账号、<code>/srv/netsentinel/prod/backend/backend/.env</code>（SECRET_KEY、VIGIL_BRIDGE_TOKEN）、PostgreSQL 密码（vigil 用户，当前是 <code>settings.py</code> 里的默认值）。</li>
        <li>锁定离开者的账户。NetSentinel 线上不在任何个人账户下，锁谁都不影响它；但 soar009 下还跑着 my-code 的服务和隧道，锁 soar009（或关 linger）会把它们一起停掉，要先和 my-code 的负责人确认：
          <pre><code>sudo usermod -L 用户名              # 只锁密码；密钥登录要另外删 /home/用户名/.ssh/authorized_keys
sudo gpasswd -d 用户名 sudo</code></pre></li>
      </ol>
    </section>
  </div>
</template>

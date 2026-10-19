<template>
  <div v-pre>
    <h1>接手第一天</h1>
    <div class="meta">前两步拿到了账户和权限，这一页列出第一天要做完的事。每一项都链接到项目手册里的详细说明。全部做完，教程就结束了，以后遇到具体任务直接查项目手册。</div>

    <section id="todo">
      <h2>第一天清单</h2>
      <div class="steps">
        <div class="step"><div class="step-title">完整做一遍每日健康检查</div>
          <p>照着 <a href="/help/health">每日健康检查</a> 逐项做，把每一项的正常结果记下来。以后每天对照这份记录，就知道哪里变了。</p></div>
        <div class="step"><div class="step-title">改掉网站默认账号的密码</div>
          <p><code>admin</code>、<code>alice</code>、<code>bob</code> 的初始密码写在代码里，等于公开。做法见上一步 <a href="/help/account">网站账号与令牌</a>。</p></div>
        <div class="step"><div class="step-title">核对网站用户</div>
          <p>登录网站 → 管理后台 Users。网站允许任何人注册，不认识的账号先删掉，再告诉实验室负责人。</p></div>
        <div class="step"><div class="step-title">知道服务器重启后要做什么</div>
          <p>读一遍 <a href="/help/power#startup">开机恢复</a>。服务器重启后实验集群不会自己起来，最容易忘的是最后一步「重启后端」。</p></div>
        <div class="step"><div class="step-title">读一遍「不要做的事」</div>
          <p>在 <a href="/help/trouble">排障与日志</a> 页面最后，列了会造成数据丢失或服务中断的操作。</p></div>
        <div class="step"><div class="step-title">从原作者那里当面拿到密码</div>
          <p>网站管理员账号、线上配置文件 <code>.env</code> 里的令牌、PostgreSQL 密码。不要通过聊天软件或截图传。</p></div>
      </div>
      <div class="ok">做到这里，你已经正式接手。以后的日常就是：每天健康检查，有任务时查项目手册。</div>
    </section>
  </div>
</template>

// NetSentinel 手册：共用侧栏（分组章节 + 当前页目录），滚动时高亮，页底上一页 / 下一页
(function () {
  const GROUPS = [
    { name: '使用网站', pages: [
      { href: 'use.html', title: '网页使用' },
      { href: '../manual_en.html', title: 'User Manual (English)' },
    ] },
    { name: '运维', pages: [
      { href: 'prepare.html', title: '接手准备：账户与 Git' },
      { href: 'health.html', title: '每日健康检查' },
      { href: 'deploy.html', title: '改动上线' },
      { href: 'power.html', title: '开关机 · 重建 · 备份' },
      { href: 'account.html', title: '账号与令牌' },
      { href: 'trouble.html', title: '排障与日志' },
    ] },
    { name: '开发参考', pages: [
      { href: 'index.html', title: '系统总览' },
      { href: 'frontend.html', title: '前端代码' },
      { href: 'backend.html', title: '后端代码' },
      { href: 'detect.html', title: '检测链路与模型' },
      { href: 'infra.html', title: '集群与 Shell 脚本' },
      { href: 'lab.html', title: '实验脚本' },
      { href: 'api.html', title: 'API 逐接口' },
      { href: 'db.html', title: '数据库与字段' },
      { href: 'issues.html', title: '已知问题与练习' },
    ] },
  ];
  const here = location.pathname.split('/').pop() || 'index.html';
  const aside = document.querySelector('.sidebar');
  if (!aside) return;

  let html = '<div class="sidebar-logo">NetSentinel 手册<span>使用 · 运维 · 开发</span></div>';
  GROUPS.forEach((g) => {
    html += `<div class="nav-section">${g.name}</div>`;
    g.pages.forEach((p) => {
      const cur = p.href === here;
      html += `<a class="nav-page${cur ? ' current' : ''}" href="${p.href}">${p.title}</a>`;
      if (cur) {
        document.querySelectorAll('section[id] > h2').forEach((h) => {
          html += `<a class="nav-item" href="#${h.parentElement.id}">${h.textContent}</a>`;
        });
      }
    });
  });
  aside.innerHTML = html;

  // 页底：同组内的上一页 / 下一页
  const group = GROUPS.find((g) => g.pages.some((p) => p.href === here));
  const main = document.querySelector('.main');
  if (group && main) {
    const list = group.pages.filter((p) => !p.href.startsWith('..'));
    const idx = list.findIndex((p) => p.href === here);
    const prev = list[idx - 1], next = list[idx + 1];
    const nav = document.createElement('div');
    nav.className = 'pager';
    nav.innerHTML =
      (prev ? `<a href="${prev.href}">← ${prev.title}</a>` : '<span></span>') +
      (next ? `<a href="${next.href}">${next.title} →</a>` : '<span></span>');
    main.appendChild(nav);
  }

  const links = [...aside.querySelectorAll('.nav-item')];
  const secs = links.map((a) => document.querySelector(a.getAttribute('href')));
  const onScroll = () => {
    let i = 0;
    secs.forEach((s, k) => { if (s && s.getBoundingClientRect().top < 120) i = k; });
    links.forEach((a, k) => a.classList.toggle('active', k === i));
  };
  document.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();

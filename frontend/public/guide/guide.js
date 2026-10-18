// 使用管理手册：共用侧栏（章节列表 + 当前页目录），滚动时高亮
(function () {
  const PAGES = [
    { href: 'prepare.html', title: '准备工作：账户与 Git' },
    { href: 'index.html', title: '0. 开始之前' },
    { href: 'use.html', title: '1. 网页使用全流程' },
    { href: 'frontend.html', title: '2. 前端代码' },
    { href: 'backend.html', title: '3. 后端代码' },
    { href: 'detect.html', title: '4. 检测链路与模型' },
    { href: 'infra.html', title: '5. 集群与 Shell 脚本' },
    { href: 'lab.html', title: '6. 实验脚本' },
    { href: 'manage.html', title: '7. 日常管理与变更' },
    { href: 'issues.html', title: '8. 已知问题与练习' },
  ];
  const here = location.pathname.split('/').pop() || 'index.html';
  const aside = document.querySelector('.sidebar');
  if (!aside) return;

  let html = '<div class="sidebar-logo">使用管理手册<span>NetSentinel · knetsentinel 全项目</span></div>';
  html += '<div class="nav-section">章节</div>';
  PAGES.forEach((p) => {
    const cur = p.href === here;
    html += `<a class="nav-page${cur ? ' current' : ''}" href="${p.href}">${p.title}</a>`;
    if (cur) {
      document.querySelectorAll('section[id] > h2').forEach((h) => {
        html += `<a class="nav-item" href="#${h.parentElement.id}">${h.textContent}</a>`;
      });
    }
  });
  html += '<div class="nav-section">相关</div>';
  html += '<a class="nav-page" href="../ops/index.html">运维对照手册 →</a>';
  aside.innerHTML = html;

  // 页底：上一章 / 下一章
  const idx = PAGES.findIndex((p) => p.href === here);
  const main = document.querySelector('.main');
  if (main && idx >= 0) {
    const prev = PAGES[idx - 1], next = PAGES[idx + 1];
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

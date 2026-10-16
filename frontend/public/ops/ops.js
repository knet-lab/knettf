// 共用侧栏：页面列表 + 当前页各 section 的目录，滚动时高亮
(function () {
  const PAGES = [
    { href: 'index.html', title: '总览与代码组织' },
    { href: 'api.html', title: 'API 逐接口说明' },
    { href: 'db.html', title: '数据库与模型字段' },
    { href: 'runbook.html', title: '运维操作逐步骤' },
  ];
  const here = location.pathname.split('/').pop() || 'index.html';
  const aside = document.querySelector('.sidebar');
  if (!aside) return;

  let html = '<div class="sidebar-logo">运维对照手册<span>NetSentinel · knetsentinel</span></div>';
  html += '<div class="nav-section">页面</div>';
  for (const p of PAGES) {
    const cur = p.href === here;
    html += `<a class="nav-page${cur ? ' current' : ''}" href="${p.href}">${p.title}</a>`;
    if (cur) {
      document.querySelectorAll('section[id] > h2').forEach((h) => {
        html += `<a class="nav-item" href="#${h.parentElement.id}">${h.textContent}</a>`;
      });
    }
  }
  aside.innerHTML = html;

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

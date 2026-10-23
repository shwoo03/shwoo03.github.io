(() => {
  const root = document.documentElement;
  try {
    root.dataset.bsTheme = localStorage.getItem('blog-theme') === 'dark' ? 'dark' : 'light';
  } catch {
    root.dataset.bsTheme = 'light';
  }
  document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('theme-toggle');
    if (!button) return;
    function updateButton() {
      const next = root.dataset.bsTheme === 'dark' ? '라이트' : '다크';
      button.setAttribute('aria-label', `${next} 모드로 전환`);
      button.title = `${next} 모드로 전환`;
      button.querySelector('.theme-label').textContent = `${next} 모드`;
    }
    button.hidden = false;
    updateButton();
    button.addEventListener('click', () => {
      root.dataset.bsTheme = root.dataset.bsTheme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('blog-theme', root.dataset.bsTheme); } catch { /* Mode still works when storage is unavailable. */ }
      updateButton();
    });
  });
})();

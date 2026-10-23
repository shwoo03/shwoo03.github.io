(() => {
  const button = document.querySelector('#sidebar-toggle');
  const body = document.querySelector('#sidebar-body');
  const mobile = matchMedia('(max-width:760px)');
  const read = key => { try { return sessionStorage.getItem(key); } catch { return null; } };
  const save = (key, value) => { try { sessionStorage.setItem(key, value); } catch { /* Navigation still works without storage. */ } };
  function collapse(value) {
    document.body.classList.toggle('sidebar-collapsed', value);
    body.hidden = value;
    button.setAttribute('aria-expanded', String(!value));
    button.setAttribute('aria-label', `사이드바 ${value ? '펼치기' : '접기'}`);
    if (mobile.matches) document.querySelector('.site-shell').inert = !value;
    else document.querySelector('.site-shell').inert = false;
  }
  collapse(mobile.matches || read('blog-sidebar') === 'closed');
  button.addEventListener('click', () => {
    const closed = button.getAttribute('aria-expanded') === 'true';
    collapse(closed);
    save('blog-sidebar', closed ? 'closed' : 'open');
  });
  mobile.addEventListener('change', () => collapse(mobile.matches || read('blog-sidebar') === 'closed'));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      collapse(true); button.focus();
    }
  });
  document.querySelectorAll('[data-folder]').forEach(folder => {
    const key = `blog-folder:${folder.dataset.folder}`;
    folder.open = read(key) !== 'closed';
    if (folder.querySelector('[aria-current="page"]')) folder.open = true;
    folder.addEventListener('toggle', () => save(key, folder.open ? 'open' : 'closed'));
  });
  const toc = document.querySelector('#article-toc');
  if (toc) {
    if (mobile.matches) toc.querySelector('details').open = false;
    document.querySelectorAll('.article-content h2, .article-content h3, .article-content h4').forEach((heading, index) => {
      if (!heading.id) heading.id = `section-${index + 1}`;
      const link = document.createElement('a');
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent;
      link.dataset.level = heading.tagName.slice(1);
      toc.querySelector('nav').append(link);
    });
    toc.hidden = !toc.querySelector('a');
  }
  const input = document.querySelector('#search');
  if (!input) return;
  const results = document.querySelector('#results');
  const original = [...results.children];
  const count = document.querySelector('#result-count');
  const total = count.textContent;
  let posts;
  function search() {
    const query = input.value.trim().toLocaleLowerCase();
    const pagination = document.querySelector('#pagination');
    if (pagination) pagination.hidden = !!query;
    if (!query) {
      results.replaceChildren(...original);
      count.textContent = total;
    } else if (posts) {
      const matches = posts.filter(post => `${post.title} ${post.categories} ${post.content}`.toLocaleLowerCase().includes(query));
      results.replaceChildren(...matches.map(post => {
        const row = document.createElement('a'); row.className = 'post-row'; row.href = post.url;
        const group = document.createElement('div');
        const path = document.createElement('p'); path.className = 'post-path';
        path.textContent = post.categories.split(', ').filter(name => name !== post.title.trim()).join(' / ');
        const title = document.createElement('h2'); title.textContent = post.title.trim();
        const time = document.createElement('time'); time.dateTime = post.date.slice(0, 10); time.textContent = time.dateTime.replaceAll('-', '.');
        group.append(path, title); row.append(group, time); return row;
      }));
      count.textContent = matches.length;
    } else {
      const matches = original.filter(row => row.dataset.search.toLocaleLowerCase().includes(query));
      results.replaceChildren(...matches); count.textContent = matches.length;
    }
    document.querySelector('#search-empty').hidden = results.children.length !== 0;
  }
  input.addEventListener('input', search);
  fetch(input.dataset.index).then(response => {
    if (!response.ok) throw new Error(`Search: ${response.status}`);
    return response.json();
  }).then(data => { posts = data; search(); }).catch(() => {
    input.title = '검색 데이터를 불러오지 못해 현재 페이지의 제목과 카테고리에서 검색합니다.';
  });
})();

const categoryMeta = [
  { id: 'operator', name: '算子', en: 'KERNELS & OPERATORS', icon: '01' },
  { id: 'compiler', name: '编译器', en: 'COMPILERS & RUNTIMES', icon: '02' },
  { id: 'communication', name: '通信', en: 'DISTRIBUTED COMMUNICATION', icon: '03' },
  { id: 'framework', name: '框架', en: 'TRAINING & INFERENCE', icon: '04' },
];
const state = { category: 'all', query: '', items: [] };
const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = s => document.querySelector(s);
function render() {
  const query = state.query.trim().toLowerCase();
  const items = state.items.filter(item => (state.category === 'all' || item.category === state.category) && (!query || `${item.title} ${(item.tags || []).join(' ')}`.toLowerCase().includes(query)));
  $('#categories').innerHTML = `<button class="category-card ${state.category === 'all' ? 'active' : ''}" data-category="all"><span class="num">◎</span><span class="count">${state.items.length}</span><strong>全部方向</strong><small>ALL TOPICS</small></button>` + categoryMeta.map(cat => `<button class="category-card ${state.category === cat.id ? 'active' : ''}" data-category="${cat.id}"><span class="num">${cat.icon}</span><span class="count">${state.items.filter(x => x.category === cat.id).length}</span><strong>${cat.name}</strong><small>${cat.en}</small></button>`).join('');
  $('#categories').querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => { state.category = button.dataset.category; render(); }));
  $('#list-title').innerHTML = `${state.category === 'all' ? '全部题目' : `${categoryMeta.find(x => x.id === state.category)?.name || ''}题目`} <small>${items.length}</small>`;
  if (!items.length) {
    $('#questions').innerHTML = `<div class="empty"><strong>${state.items.length ? '没有匹配的题目' : '题库正在等待首次采集'}</strong><p>${state.items.length ? '换一个关键词试试。' : '数据只会在本机完成授权后采集并同步；目前没有伪造或预置题目。'}</p>${!state.items.length ? '<p class="notice">管理员：按仓库 README 完成本机二维码登录和定时任务配置。</p>' : ''}</div>`;
    return;
  }
  $('#questions').innerHTML = items.map((item, index) => {
    const category = categoryMeta.find(c => c.id === item.category);
    return `<article class="question-card"><div class="q-icon">${String(index + 1).padStart(2, '0')}</div><div class="q-content"><h3>${esc(item.title)}</h3><div class="tags"><span class="tag category">${esc(category?.name || '待分类')}</span>${(item.tags || []).slice(0, 4).map(tag => `<span class="tag">${esc(tag)}</span>`).join('')}</div></div><a class="source" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">查看来源 ↗</a><time class="q-date">${esc(item.first_seen || '')}</time></article>`;
  }).join('');
}
$('#search').addEventListener('input', event => { state.query = event.target.value; render(); });
fetch('./data/questions.json', { cache: 'no-store' }).then(response => { if (!response.ok) throw new Error('data'); return response.json(); }).then(data => {
  state.items = Array.isArray(data.questions) ? data.questions : [];
  if (data.updated_at) $('#updated').textContent = `更新于 ${data.updated_at}`;
  render();
}).catch(() => { $('#questions').innerHTML = '<div class="empty"><strong>暂时无法读取题库</strong><p>请稍后刷新页面。</p></div>'; });

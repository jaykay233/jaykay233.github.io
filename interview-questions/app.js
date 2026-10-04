const categoryMeta = [
  { id: 'operator', name: '算子', en: 'KERNELS & OPERATORS', icon: '01' },
  { id: 'compiler', name: '编译器', en: 'COMPILERS & RUNTIMES', icon: '02' },
  { id: 'communication', name: '通信', en: 'DISTRIBUTED COMMUNICATION', icon: '03' },
  { id: 'framework', name: '框架', en: 'TRAINING & INFERENCE', icon: '04' },
];
const params = new URLSearchParams(location.search);
const state = { category: 'all', query: params.get('q') || '', items: [] };
$('#search').value = state.query;
const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = s => document.querySelector(s);
function render() {
  const query = state.query.trim().toLowerCase();
  const items = state.items.filter(item => (state.category === 'all' || item.category === state.category) && (!query || `${item.question || item.title} ${item.source_title || ''} ${(item.knowledge_points || item.tags || []).join(' ')}`.toLowerCase().includes(query)));
  $('#categories').innerHTML = `<button class="category-card ${state.category === 'all' ? 'active' : ''}" data-category="all"><span class="num">◎</span><span class="count">${state.items.length}</span><strong>全部方向</strong><small>ALL TOPICS</small></button>` + categoryMeta.map(cat => `<button class="category-card ${state.category === cat.id ? 'active' : ''}" data-category="${cat.id}"><span class="num">${cat.icon}</span><span class="count">${state.items.filter(x => x.category === cat.id).length}</span><strong>${cat.name}</strong><small>${cat.en}</small></button>`).join('');
  $('#categories').querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => { state.category = button.dataset.category; render(); }));
  $('#list-title').innerHTML = `${state.category === 'all' ? '全部题目' : `${categoryMeta.find(x => x.id === state.category)?.name || ''}题目`} <small>${items.length}</small>`;
  if (!items.length) {
    $('#questions').innerHTML = `<div class="empty"><strong>${state.items.length ? '没有匹配的题目' : '题库暂时没有题目'}</strong><p>${state.items.length ? '换一个关键词试试。' : '题库内容会持续整理和更新，请稍后再来查看。'}</p></div>`;
    return;
  }
  $('#questions').innerHTML = items.map((item, index) => {
    const category = categoryMeta.find(c => c.id === item.category);
    const knowledgePoints = item.knowledge_points || item.tags || [];
    return `<article class="question-card"><div class="q-icon">${String(index + 1).padStart(2, '0')}</div><div class="q-content"><h3>${esc(item.question || item.title)}</h3>${item.source_title ? `<div class="source-title">整理来源：${esc(item.source_title)}</div>` : ''}<div class="tags"><span class="tag category">${esc(category?.name || '待分类')}</span></div>${knowledgePoints.length ? `<div class="knowledge-points"><span class="knowledge-label">知识点</span>${knowledgePoints.map(point => `<button class="knowledge-chip" type="button" data-knowledge-point="${esc(point)}">${esc(point)}</button>`).join('')}</div>` : ''}${Array.isArray(item.answer_points) && item.answer_points.length ? `<details class="answer-points"><summary>回答要点</summary><ul>${item.answer_points.map(point => `<li>${esc(point)}</li>`).join('')}</ul></details>` : ''}</div>${item.source_url ? `<a class="source" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">查看来源 ↗</a>` : ''}<time class="q-date">${esc(item.first_seen || '')}</time></article>`;
  }).join('');
  $('#questions').querySelectorAll('[data-knowledge-point]').forEach(button => button.addEventListener('click', () => {
    state.query = button.dataset.knowledgePoint;
    $('#search').value = state.query;
    render();
  }));
}
$('#search').addEventListener('input', event => { state.query = event.target.value; const url = new URL(location.href); state.query ? url.searchParams.set('q', state.query) : url.searchParams.delete('q'); history.replaceState(null, '', url); render(); });
fetch('./data/questions.json', { cache: 'no-store' }).then(response => { if (!response.ok) throw new Error('data'); return response.json(); }).then(data => {
  state.items = Array.isArray(data.questions) ? data.questions : [];
  const deepepCount = state.items.filter(item => (item.knowledge_points || []).includes('DeepEP')).length;
  $('#deepep-link').textContent = `DeepEP 专题（${deepepCount}）`;
  if (data.updated_at) $('#updated').textContent = `更新于 ${data.updated_at}`;
  render();
}).catch(() => { $('#questions').innerHTML = '<div class="empty"><strong>暂时无法读取题库</strong><p>请稍后刷新页面。</p></div>'; });

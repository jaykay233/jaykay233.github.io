const app = document.getElementById('app-view');
const isPagesSite = /\/archatlas\/?$/.test(location.pathname);
const state = { view: 'models', models: [], modules: [], stats: {}, selectedId: '', filter: 'all', sort: 'popular', query: '', moduleQuery: '', selectedModule: 'mhc', relatedModelQuery: '' };
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (value = '') => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const shortName = name => name.split(/[ -]/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase();
function cleanEvidenceLine(value) {
  return String(value || '')
    .replace(/^\s{0,3}(?:[-+*]|\d+[.)])\s+/, '')
    .replace(/^\s{0,3}#{1,6}\s+/, '')
    .replace(/^\s*\|+\s*/, '')
    .replace(/\|+\s*$/, '')
    .replace(/\\([*_`])/g, '$1')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!?\[([^\]]+)\]\((?:https?:\/\/)?[^)]+\)/g, '$1')
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}
function isUsefulEvidenceLine(value) {
  return value && !/^(?:library_name|pipeline_tag|tags|license|language|datasets|base_model|model-index|---)\s*:/i.test(value);
}
const moduleLabels = {
  'decoder-only':'Decoder-only', gqa:'GQA', mla:'MLA', 'deepseek-moe':'MoE', 'mixtral-moe':'MoE',
  'dense-ffn':'Dense FFN', mhc:'mHC', ihc:'iHC', rope:'RoPE', rmsnorm:'RMSNorm', swiglu:'SwiGLU',
  'moe-ffn':'MoE FFN', geglu:'GeGLU', residual:'Residual', 'sliding-window':'Sliding Window',
  'local-global-attention':'Local/Global Attn', csa:'CSA', hca:'HCA', 'hybrid-attention':'Hybrid Layout',
  'gated-deltanet':'Gated DeltaNet', 'gated-attention':'Gated Attention', kda:'KDA',
  'full-attention':'Full Attention', mamba2:'Mamba-2', 'gated-conv':'Gated Conv',
  'longcat-sparse-attention':'LSA', 'deepseek-sparse-attention':'DSA', mtp:'MTP'
};

async function api(path) {
  const target = isPagesSite ? `api/${path.replace(/^\/api\//, '')}.json` : path;
  const res = await fetch(target);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
async function init() {
  try {
    const [models, modules, stats] = await Promise.all([api('/api/models'), api('/api/modules'), api('/api/stats')]);
    state.models = models.items;
    state.modules = modules.items;
    state.stats = stats;
    $('#api-status-text').textContent = isPagesSite ? '静态快照已加载' : 'API 已连接';
    $('#nav-model-count').textContent = stats.models;
    render();
  } catch (err) {
    $('#api-status-text').textContent = 'API 未连接';
    $('.api-status').classList.add('offline');
    app.innerHTML = isPagesSite
      ? `<div class="empty-state">无法加载网站数据快照，请稍后刷新。</div>`
      : `<div class="empty-state">无法连接本地 API。<br>请在项目目录运行 <code>python3 backend/server.py</code>。</div>`;
  }
}

function setView(view) {
  state.view = view;
  const labels = {models:'模型架构', modules:'模块字典', 'module-detail': state.modules.find(m => m.id === state.selectedModule)?.name || '模块详情', sources:'数据来源'};
  $('#breadcrumb-current').textContent = labels[view];
  $$('.nav-item').forEach(btn => btn.classList.toggle('active', btn.dataset.view === (view === 'module-detail' ? 'modules' : view)));
  render();
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function render() {
  if (state.view === 'models') renderModels();
  else if (state.view === 'modules') renderModules();
  else if (state.view === 'module-detail') renderModuleDetail();
  else renderSources();
}

function getFilteredModels() {
  let list = [...state.models];
  const q = state.query.trim().toLocaleLowerCase();
  if (q) list = list.filter(m => [m.name,m.organization,m.family,m.architecture_type,m.summary,...m.modules,...(m.candidate_modules || []),JSON.stringify(m.config_summary || {})].join(' ').toLocaleLowerCase().includes(q));
  if (state.filter === 'pending') list = list.filter(m => m.architecture_status === 'pending');
  if (state.filter === 'dense') list = list.filter(m => m.modules.includes('dense-ffn'));
  if (state.filter === 'moe') list = list.filter(m => m.modules.some(id => id.includes('moe')));
  if (['gqa','mla','mhc','ihc'].includes(state.filter)) list = list.filter(m => m.modules.includes(state.filter));
  const date = model => model.hub_created || model.release || '';
  return list.sort((a, b) => state.sort === 'recent'
    ? date(b).localeCompare(date(a))
    : (b.popularity_score || 0) - (a.popularity_score || 0)
      || (b.popularity_signals || 0) - (a.popularity_signals || 0)
      || (b.downloads_snapshot || 0) - (a.downloads_snapshot || 0)
      || (b.likes_snapshot || 0) - (a.likes_snapshot || 0)
      || date(b).localeCompare(date(a)));
}

function renderModels() {
  const filtered = getFilteredModels();
  const selected = filtered.find(m => m.id === state.selectedId) || filtered[0] || state.models[0];
  if (selected) state.selectedId = selected.id;
  app.innerHTML = `
    <div class="page-heading">
      <div><div class="eyebrow">ARCHITECTURE / CATALOG</div><h1>开源模型架构图谱</h1><p>从模型名称深入到模块组成，比较架构设计，而不只是参数规模。</p></div>
      <div class="heading-right"><span class="updated-pill">Hugging Face 仓库快照 <b>${esc(state.stats.snapshot_date || '—')} · 静态</b></span><button class="button-quiet" id="snapshot-info">收录范围</button></div>
    </div>
    <section class="stats-row">
      <div class="stat-card"><div class="stat-icon">◫</div><div class="stat-info"><span>模型记录</span><strong>${state.stats.models ?? '—'}</strong></div><div class="stat-foot">CATALOG</div></div>
      <div class="stat-card"><div class="stat-icon">⌘</div><div class="stat-info"><span>待拆解候选</span><strong>${state.stats.pending_models ?? '—'}</strong></div><div class="stat-foot">PENDING</div></div>
      <div class="stat-card"><div class="stat-icon">⌬</div><div class="stat-info"><span>已映射模块</span><strong>${state.stats.modules ?? '—'}</strong></div><div class="stat-foot">MODULES</div></div>
      <div class="stat-card"><div class="stat-icon">◎</div><div class="stat-info"><span>配置已读取</span><strong>${state.stats.config_review?.config_status?.ok ?? '—'}</strong></div><div class="stat-foot">CONFIGS</div></div>
    </section>
    <section class="content-grid">
      <div class="panel catalog-panel">
        <div class="panel-heading"><h2>模型目录</h2><div class="catalog-heading-tools"><small>${filtered.length} MODELS · ${state.stats.curated_models ?? 0} 已整理 / ${state.stats.pending_models ?? 0} 待人工确认 · ${state.stats.config_review?.with_structural_findings ?? 0} 有结构线索 · ${state.stats.model_card_review?.selected_representatives ?? 0} 卡片样本</small><label class="sort-control" title="热度为该仓库出现在 Hugging Face 五类榜单中的归一化平均名次，不是跨平台绝对热度"><span>排序</span><select id="model-sort"><option value="popular" ${state.sort==='popular'?'selected':''}>热门优先</option><option value="recent" ${state.sort==='recent'?'selected':''}>最新优先</option></select></label></div></div>
        <label class="search-wrap"><span class="search-icon">⌕</span><input id="model-search" class="search-input" placeholder="搜索模型、模块或组织…" value="${esc(state.query)}"><span class="search-shortcut">⌘ K</span></label>
        <div class="filter-row">
          ${[['all','全部'],['pending','待拆解'],['dense','Dense'],['moe','MoE'],['gqa','GQA'],['mla','MLA'],['mhc','mHC'],['ihc','iHC']].map(([id,label])=>`<button class="filter-chip ${state.filter===id?'active':''}" data-filter="${id}">${label}</button>`).join('')}
        </div>
        <div class="model-list">${filtered.length ? filtered.map(modelRow).join('') : '<div class="empty-state">没有匹配的模型。<br>当前示例数据集可能尚未收录该结构。</div>'}</div>
      </div>
      ${selected ? renderModelDetail(selected) : '<div class="panel detail-panel"><div class="empty-state">还没有可展示的模型</div></div>'}
    </section>`;
  bindModelView();
}

function modelRow(model) {
  const active = model.id === state.selectedId;
  const preferred = (model.architecture_status === 'pending' ? (model.candidate_modules || []) : model.modules).filter(id => moduleLabels[id]);
  const tags = [...new Set(preferred.map(id => moduleLabels[id]))].slice(0,2).map(label => {
    const cls = label === 'MoE' ? 'moe' : ['GQA','MLA','Gated DeltaNet','Gated Attn','KDA','LSA','DSA','SWA','CSA'].includes(label) ? 'attn' : '';
    return `<span class="tiny-tag ${cls}">${esc(label)}</span>`;
  }).join('');
  const pending = model.architecture_status === 'pending';
  const added = pending ? '<span class="tiny-tag pending-tag">待拆解</span>' : (model.added_in_snapshot ? '<span class="tiny-tag fresh">NEW</span>' : '');
  const releaseTag = model.hub_created || model.release || '日期未知';
  return `<button class="model-row ${active?'selected':''}" data-model-id="${esc(model.id)}"><span class="model-mark">${esc(shortName(model.organization))}</span><span class="model-copy"><span class="model-name-line"><span class="model-name">${esc(model.name)}</span>${added}</span><span class="model-org">${esc(model.organization)} · ${esc(model.parameters)}</span><span class="model-subline">${pending ? `<span class="tiny-tag hotness-tag">热度 ${Number(model.popularity_score || 0).toFixed(1)}</span>${tags}<span class="tiny-tag">${model.config_review?.status === 'reviewed' ? '配置初筛' : '架构未核验'}</span>` : tags}<span class="tiny-tag">${esc(releaseTag)}</span></span></span><span class="model-chevron">›</span></button>`;
}
function graphNode(title, kind, variant='', note='') {
  const cls = kind === 'attention' ? 'attention' : kind === 'ffn' ? 'ffn' : kind === 'connection' ? 'connection' : kind === 'mixer' ? 'mixer' : '';
  const label = {norm:'NORM',attention:'ATTENTION',connection:'CONNECTION',ffn:'FFN'}[kind] || kind.toUpperCase();
  return `<div class="graph-node ${cls}"><span class="node-kind">${label}</span><strong>${esc(variant || title)}</strong><small>${esc(note || (variant ? title : ''))}</small></div>`;
}
function renderGraph(model) {
  const arch = model.architecture;
  const sequence = arch.block_modules.filter(mod => mod.kind !== 'connection');
  const connections = arch.block_modules.filter(mod => mod.kind === 'connection');
  const internals = sequence.map((mod,i) => `${i ? '<span class="graph-arrow">›</span>':''}${graphNode(mod.name,mod.kind,mod.variant,mod.note)}`).join('');
  const connectionMarkup = connections.length ? `<div class="connection-strip"><span class="connection-label">CONNECTIONS</span>${connections.map(mod=>`<span class="connection-chip"><b>${esc(mod.variant||mod.name)}</b><small>${esc(mod.note||'跨模块连接')}</small></span>`).join('')}</div>` : '';
  return `<div class="architecture-canvas"><div class="diagram-track">
    <div class="graph-node input"><span class="node-kind">INPUT</span><strong>${esc(arch.input)}</strong><small>词元序列</small></div><span class="graph-arrow">→</span>
    <div class="block-group"><div class="block-group-head"><span>▦</span><strong>${esc(arch.block_label)}</strong><span class="repeat-badge">${arch.block_count ? `× ${esc(arch.block_count)} 层` : '层数未公开'}</span></div><div class="block-inner">${internals}</div>${connectionMarkup}</div>
    <span class="graph-arrow">→</span><div class="graph-node output"><span class="node-kind">OUTPUT</span><strong>${esc(arch.output)}</strong><small>next-token logits</small></div>
  </div>${arch.pattern ? `<div class="architecture-pattern"><b>层间布局</b><span>${esc(arch.pattern)}</span></div>` : ''}<div class="graph-caption"><i></i> 单个 Block 的模块级概览 <span>·</span> 子模块顺序与连接关系分开表达</div></div>`;
}
function renderPendingDetail(model) {
  const config = model.config_summary || {};
  const architectures = Array.isArray(config.architectures) ? config.architectures.join(', ') : '未提供';
  const findings = model.config_review?.findings || [];
  const configReviewed = model.config_review?.status === 'reviewed';
  const meta = [
    ['HF 创建日期', model.hub_created || '未提供'],
    ['下载量快照', Number(model.downloads_snapshot || 0).toLocaleString()],
    ['点赞快照', Number(model.likes_snapshot || 0).toLocaleString()],
    ['模型类型', config.model_type || '未提供'],
    ['层数', config.num_hidden_layers ?? '未公开'],
    ['上下文长度', config.context_length ?? '未公开'],
    ['Q / KV 头数', config.num_attention_heads ? `${config.num_attention_heads} / ${config.num_key_value_heads ?? '未公开'}` : '未公开'],
    ['专家 / Top-K', config.num_experts ? `${config.num_experts} / ${config.top_k_experts ?? '未公开'}` : '未公开'],
    ['激活函数', config.hidden_act || '未公开'],
  ];
  return `<div class="panel detail-panel pending-detail">
    <div class="detail-title-row"><div class="detail-title"><div class="detail-logo">${esc(shortName(model.organization))}</div><div><h2>${esc(model.name)}</h2><p>${esc(model.organization)} <span>·</span> ${esc(model.hub_id || model.family)}</p></div></div><div class="detail-actions"><button class="icon-action" id="copy-model" title="复制模型 ID">⧉</button><a class="button-primary" href="${esc(model.sources?.[0]?.url || '#')}" target="_blank" rel="noreferrer">查看模型 ↗</a></div></div>
    <div class="model-pills"><span class="pill pending-pill">${configReviewed ? '配置已初筛 · 待人工核验' : '待拆解 / 未核验'}</span><span class="pill">${esc(model.license || '未声明')}</span></div>
    <p class="detail-summary">${esc(model.summary)}</p>
    <div class="pending-banner"><strong>${configReviewed ? '以下是 config.json 支持的结构线索，不等于完整架构拆解' : '这是“发现记录”，不是架构结论'}</strong><span>${configReviewed ? '只记录配置显式声明或模型类可支持的线索；未声明的模块、模块顺序和自定义实现必须再查模型卡、论文或代码。线索不会混入已核验模块统计。' : '目前只从 Hugging Face 获取到仓库与部分 config 元数据。此条目不会计入模块统计，也不会绘制推测出来的架构图。'}</span></div>
    <div class="section-title"><h3>可用元数据</h3><span>HUGGING FACE SNAPSHOT</span></div>
    <div class="model-meta pending-meta">${meta.map(([label,value])=>`<div class="meta-cell"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}</div>
    <div class="pending-config"><span>配置声明的模型类</span><code>${esc(architectures)}</code></div>
    ${model.model_card_evidence?.status === 'ok' ? `<div class="section-title"><h3>模型卡证据摘录</h3><span>代表模型卡 · 原文关键词上下文</span></div><div class="card-excerpts">${(model.model_card_evidence.excerpts || []).map(cleanEvidenceLine).filter(isUsefulEvidenceLine).map(line=>`<blockquote>${esc(line)}</blockquote>`).join('')}<div class="evidence-line">原始模型卡：<a href="${esc(model.model_card_evidence.source)}" target="_blank" rel="noreferrer">${esc(model.model_card_evidence.source)}</a>。摘录由关键词自动提取，仅作复核材料，不自动生成架构结论。</div></div>` : ''}
    ${model.model_card_interpretation ? `<div class="section-title"><h3>模型卡模块解读</h3><span>${model.model_card_interpretation.claims.length} 条来源支持的结构陈述 · 尚未代码核验</span></div><div class="card-excerpts">${model.model_card_interpretation.claims.map(item=>`<article class="config-finding"><div><b>${esc(moduleLabels[item.module_id] || item.module_id)}</b><span class="tiny-tag">${esc(item.confidence === 'model-card-explicit' ? '模型卡明确陈述' : '结合上下文映射')}</span></div><p>${esc(item.claim)}</p><blockquote>${esc(cleanEvidenceLine(item.evidence))}</blockquote></article>`).join('')}<div class="evidence-line">解读来源：<a href="${esc(model.model_card_interpretation.source)}" target="_blank" rel="noreferrer">官方模型卡</a>。${(model.model_card_interpretation.limitations || []).map(esc).join('；')}。候选仍标为待核验，以上内容不会计入已确认模块统计。</div></div>` : ''}
    ${configReviewed ? `<div class="section-title"><h3>配置证据初筛</h3><span>${findings.length} 条线索 · 未计为人工核验</span></div>${findings.length ? `<div class="config-findings">${findings.map(item=>`<article class="config-finding"><div><b>${esc(moduleLabels[item.module_id] || item.module_id)}</b><span class="tiny-tag">${item.confidence === 'direct-config' ? '配置直接证据' : '模型类型推断'}</span></div><p>${esc(item.statement)}</p><code>${esc(item.basis)}</code></article>`).join('')}</div>` : '<div class="empty-state compact">配置未明确声明当前模块字典中的可识别结构线索。</div>'}` : ''}
    <div class="bottom-grid"><div class="mini-panel"><h3>榜单发现信息</h3><div class="pending-ranking">${Object.keys(model.rankings || {}).length ? Object.entries(model.rankings).map(([key,value])=>`<span>${esc(key)} <b>${esc(value)}</b></span>`).join('') : '<span>来源于多榜单采样；该仓库未出现在当前保存的具体榜单名次中。</span>'}</div><div class="evidence-line">${esc(model.evidence || '')}</div></div><div class="mini-panel"><h3>来源</h3><div class="source-list">${(model.sources || []).map(source=>`<a class="source-link" href="${esc(source.url)}" target="_blank" rel="noreferrer">↗ ${esc(source.label)}</a>`).join('')}</div><div class="evidence-line">${configReviewed ? `配置证据：${esc(model.config_review.source)}。模型卡、技术报告与实现代码仍待逐条核对。` : '架构模块需进一步依据模型卡、配置、技术报告与实现代码逐条确认。'}</div></div></div>
  </div>`;
}

function renderModelDetail(model) {
  if (model.architecture_status === 'pending') return renderPendingDetail(model);
  const modules = model.modules.map(id => state.modules.find(m => m.id === id)).filter(Boolean);
  const typePill = model.modules.some(id=>id.includes('moe')) ? '<span class="pill dark">Sparse MoE</span>' : '<span class="pill dark">Dense</span>';
  return `<div class="panel detail-panel">
    <div class="detail-title-row"><div class="detail-title"><div class="detail-logo">${esc(shortName(model.organization))}</div><div><h2>${esc(model.name)}</h2><p>${esc(model.organization)} <span>·</span> ${esc(model.family)}</p></div></div><div class="detail-actions"><button class="icon-action" id="copy-model" title="复制模型 ID">⧉</button><a class="button-primary" href="${esc(model.sources[0]?.url || '#')}" target="_blank" rel="noreferrer">查看模型 ↗</a></div></div>
    <div class="model-pills">${typePill}<span class="pill">${esc(model.architecture_type)}</span><span class="pill">${esc(model.license)}</span></div>
    <p class="detail-summary">${esc(model.summary)}</p>
    <div class="model-meta"><div class="meta-cell"><span>参数规模</span><strong>${esc(model.parameters)}</strong></div><div class="meta-cell"><span>架构层数</span><strong>${model.architecture.block_count ? `${esc(model.architecture.block_count)} Blocks` : '未公开'}</strong></div><div class="meta-cell"><span>发布月份</span><strong>${esc(model.release)}</strong></div><div class="meta-cell"><span>证据状态</span><strong>${model.confidence==='paper-and-code'?'模型卡 + 项目/报告':model.confidence==='model-card-and-config'?'模型卡 + 配置核验':'公开元数据'}</strong></div></div>
    <div class="section-title"><h3>模块结构流</h3><span>ARCHITECTURE FLOW</span></div>
    ${renderGraph(model)}
    <div class="bottom-grid"><div class="mini-panel"><h3>架构模块 <span style="color:#a2aba5;font-weight:400">· ${modules.length}</span></h3><div class="module-chips">${modules.map(m=>`<button class="module-chip" data-open-module="${m.id}">${esc(m.name)}</button>`).join('')}</div><div class="evidence-line">标签代表架构语义模块；不展开到底层算子或 kernel。</div></div><div class="mini-panel"><h3>来源与证据 <span class="confidence">● ${model.confidence==='paper-and-code'?'模型卡 + 项目/报告':model.confidence==='model-card-and-config'?'模型卡 + 配置核验':'公开元数据'}</span></h3><div class="source-list">${model.sources.map(s=>`<a class="source-link" href="${esc(s.url)}" target="_blank" rel="noreferrer">↗ ${esc(s.label)}</a>`).join('')}</div><div class="evidence-line">${esc(model.evidence)}</div></div></div>
  </div>`;
}

let searchTimer;
function bindModelView() {
  $('#model-sort')?.addEventListener('change', e => { state.sort = e.target.value; state.selectedId = getFilteredModels()[0]?.id || ''; render(); });
  $('#model-search')?.addEventListener('input', e => { state.query = e.target.value; const caret = e.target.selectionStart; clearTimeout(searchTimer); searchTimer = setTimeout(() => { renderModels(); const input = $('#model-search'); input?.focus(); input?.setSelectionRange(caret, caret); }, 160); });
  $$('.filter-chip').forEach(b => b.addEventListener('click', () => { state.filter = b.dataset.filter; render(); }));
  $$('.model-row').forEach(b => b.addEventListener('click', () => { state.selectedId = b.dataset.modelId; render(); }));
  $$('[data-open-module]').forEach(b => b.addEventListener('click', () => { state.selectedModule = b.dataset.openModule; state.relatedModelQuery = ''; setView('module-detail'); }));
  $('#snapshot-info')?.addEventListener('click', () => toast(state.stats.scope || '近期代表性官方模型静态快照，不是全量榜单。'));
  $('#copy-model')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText(state.selectedId); toast('模型 ID 已复制'); } catch { toast(`模型 ID：${state.selectedId}`); } });
}

function getModuleAssociations(moduleId) {
  const verified = state.models.filter(model => model.modules.includes(moduleId));
  const pending = state.models.filter(model => {
    if (model.architecture_status !== 'pending') return false;
    return (model.candidate_modules || []).includes(moduleId)
      || (model.model_card_interpretation?.claims || []).some(claim => claim.module_id === moduleId);
  }).map(model => {
    const cardClaim = (model.model_card_interpretation?.claims || []).some(claim => claim.module_id === moduleId);
    const configClaim = (model.candidate_modules || []).includes(moduleId);
    return { ...model, associationEvidence: cardClaim && configClaim ? '模型卡解读 + 配置线索' : cardClaim ? '模型卡解读' : '配置线索' };
  });
  return { verified, pending };
}

function renderModules() {
  const filtered = state.modules.filter(m => !state.moduleQuery || `${m.name} ${m.category} ${m.description}`.toLocaleLowerCase().includes(state.moduleQuery.toLocaleLowerCase()));
  app.innerHTML = `<div class="page-heading"><div><div class="eyebrow">ONTOLOGY / MODULES</div><h1>模块字典</h1><p>将架构特征拆成可复用、可检索的模块类别；每项都保留定义与证据状态。</p></div><div class="heading-right"><span class="updated-pill">${state.modules.length} 个分类项</span></div></div>
    <p class="module-intro">架构模块既包括 Attention、FFN、Norm 等计算子结构，也包括残差 / Hyper-Connections 这类模块连接机制。关联模型分为已核验与候选证据两类；候选关联只是检索线索，不代表已经确认。</p>
    <div class="module-toolbar"><label class="search-wrap module-search"><span class="search-icon">⌕</span><input id="module-search" class="search-input" placeholder="搜索模块名称或说明…" value="${esc(state.moduleQuery)}"></label><span class="updated-pill">${filtered.length} 项</span></div>
    <div class="module-grid">${filtered.map(m=>{const counts=getModuleAssociations(m.id);return `<button class="module-card" data-module-id="${esc(m.id)}"><div class="module-card-top"><span class="module-symbol">${m.category==='Attention'?'◉':m.category.includes('FFN')?'⌘':m.category==='连接结构'?'⤴':'◇'}</span><span class="module-category">${esc(m.category)}</span></div><h3>${esc(m.name)}</h3><p>${esc(m.description)}</p><div class="module-card-foot"><span><b>${counts.verified.length}</b> 已核验 · <b>${counts.pending.length}</b> 候选</span><span class="status-tag ${counts.verified.length?'':'pending'}">查看模型 →</span></div></button>`;}).join('')}</div>`;
  $('#module-search')?.addEventListener('input', e => { state.moduleQuery=e.target.value; const caret=e.target.selectionStart; clearTimeout(searchTimer); searchTimer=setTimeout(()=>{renderModules();const input=$('#module-search');input?.focus();input?.setSelectionRange(caret,caret);},130); });
  $$('[data-module-id]').forEach(b => b.addEventListener('click', () => {state.selectedModule=b.dataset.moduleId;state.relatedModelQuery='';setView('module-detail');}));
}

function renderModuleDetail() {
  const selected = state.modules.find(m => m.id === state.selectedModule);
  if (!selected) { setView('modules'); return; }
  const associations = getModuleAssociations(selected.id);
  const relatedQuery = state.relatedModelQuery.trim().toLocaleLowerCase();
  const visibleModels = models => models.filter(m => !relatedQuery || `${m.name} ${m.organization} ${m.hub_id || ''}`.toLocaleLowerCase().includes(relatedQuery));
  const modelLinks = (models, evidenceLabel = '') => models.length
    ? `<div class="related-models">${models.map(m=>{const label=evidenceLabel||m.associationEvidence||'';return `<button data-related-model="${esc(m.id)}" title="${esc(m.hub_id || m.name)}"><span>${esc(m.name)} ↗</span>${label ? `<small>${esc(label)}</small>` : ''}</button>`;}).join('')}</div>`
    : `<div class="module-empty-related">${relatedQuery ? '没有匹配的模型。' : '当前没有此类关联模型。'}</div>`;
  app.innerHTML = `<div class="module-detail-page">
    <div class="page-heading"><div><div class="eyebrow">MODULE / MODEL EXPLORER</div><h1>${esc(selected.name)}</h1><p>${esc(selected.category)} · 查看与该模块关联的模型</p></div><div class="heading-right"><button class="button-quiet" data-view="modules">← 返回模块字典</button></div></div>
    <section class="module-detail-summary"><span class="module-symbol">${selected.category==='连接结构'?'⤴':selected.category==='Attention'?'◉':'⌘'}</span><div><span class="module-category">${esc(selected.category)}</span><p>${esc(selected.description)}</p></div><div class="module-detail-counts"><span><b>${associations.verified.length}</b> 已核验</span><span><b>${associations.pending.length}</b> 候选证据</span></div></section>
    <div class="module-model-toolbar"><label class="search-wrap module-model-search"><span class="search-icon">⌕</span><input id="module-model-search" class="search-input" placeholder="搜索关联模型名称或组织…" value="${esc(state.relatedModelQuery)}"></label><span class="module-category">候选项仅代表有可追溯线索，不计入已核验统计</span></div>
    <div class="module-associated-groups module-detail-groups"><section><div class="module-group-heading"><h2>已核验关联模型</h2><span>${visibleModels(associations.verified).length} / ${associations.verified.length}</span></div><p class="module-related-caption">已纳入该模块的确认结果。</p>${modelLinks(visibleModels(associations.verified))}</section><section><div class="module-group-heading"><h2>候选关联模型</h2><span>${visibleModels(associations.pending).length} / ${associations.pending.length}</span></div><p class="module-related-caption">来自配置线索或模型卡解读，尚待代码、论文或其他来源核验。</p>${modelLinks(visibleModels(associations.pending).map(model=>({...model,associationEvidence:model.associationEvidence})))}</section></div>
  </div>`;
  $('#module-model-search')?.addEventListener('input', e => { state.relatedModelQuery=e.target.value; const caret=e.target.selectionStart; clearTimeout(searchTimer); searchTimer=setTimeout(()=>{renderModuleDetail();const input=$('#module-model-search');input?.focus();input?.setSelectionRange(caret,caret);},130); });
  $$('[data-related-model]').forEach(b => b.addEventListener('click', () => {state.selectedId=b.dataset.relatedModel;state.query='';state.filter='all';setView('models');}));
}

function renderSources() {
  app.innerHTML = `<div class="page-heading"><div><div class="eyebrow">INGESTION / SOURCES</div><h1>数据来源与接入计划</h1><p>按配置的发布者命名空间发现候选；模型卡、配置、论文和实现代码负责证明结构。</p></div><div class="heading-right"><span class="updated-pill">当前状态 <b>静态快照</b></span></div></div>
    <div class="source-layout"><section class="source-panel"><h2>模型发现入口</h2><p>当前候选通过 Hugging Face Hub API 分页发现；config.json 已自动初筛可直接支持的架构线索，热度榜单只用于排序，模型卡、论文和代码负责最终确认。</p>
      <div class="source-row"><div class="source-logo">HF</div><div class="source-row-copy"><strong>Hugging Face Models</strong><span>已采集候选仓库，并批量读取可访问的 config.json；不下载完整权重。</span></div><span class="source-state">已采集快照</span></div>
      <div class="source-row"><div class="source-logo">↗</div><div class="source-row-copy"><strong>Hugging Face Trending / Leaderboards</strong><span>五类 top-1,000 榜单只为候选提供相对热度信号；榜单外候选仍保留，不直接作为架构结论证据。</span></div><span class="source-state">多榜单采样</span></div>
      <div class="source-row"><div class="source-logo">ar</div><div class="source-row-copy"><strong>论文与技术报告</strong><span>用于确认模块设计动机、变体定义与模型家族级结构。</span></div><span class="source-state">人工核验</span></div>
      <div class="source-row"><div class="source-logo">GH</div><div class="source-row-copy"><strong>公开实现代码</strong><span>用来验证模型卡中的结构描述是否落实到具体发布版本。</span></div><span class="source-state">人工核验</span></div>
    </section><section class="source-panel"><h2>当前采集进度与后续流程</h2><p>先建立可追溯的整理流程，再逐步增加自动化。</p><div class="roadmap">
      <div class="roadmap-step"><span class="step-no">01</span><div><strong>已完成：发现与去重</strong><p>按 68 个配置命名空间完整分页，按 Hub 仓库 ID 去重并排除与已整理记录重复的条目。</p></div></div>
      <div class="roadmap-step"><span class="step-no">02</span><div><strong>已完成基础元数据采集</strong><p>记录 Hub 创建时间、热度快照和可获得的 config 摘要；字段缺失时保持未公开。</p></div></div>
      <div class="roadmap-step"><span class="step-no">03</span><div><strong>已完成第一轮：配置证据初筛</strong><p>${state.stats.config_review?.config_status?.ok ?? 0} 份 config.json 已读取；其中 ${state.stats.config_review?.with_structural_findings ?? 0} 条候选形成模块线索。模型卡自动抓取 ${state.stats.model_card_review?.status?.ok ?? 0} 份成功，已有 ${state.stats.model_card_interpretation?.reviewed_models ?? 0} 个代表样本完成逐条解读；其余候选及代码/论文交叉核验仍待推进。</p></div></div>
      <div class="roadmap-step"><span class="step-no">04</span><div><strong>人工复核与图谱查询</strong><p>对 mHC / iHC 等细分结构优先复核，确认模型版本后才进入“已核验”结果。</p></div></div>
    </div><div class="notice">截至 ${esc(state.stats.snapshot_date || '—')}，候选模型来自 Hugging Face Hub API 对配置的 68 个官方发布者/研究机构命名空间分页抓取，并筛选 2025-01-01 以来的公开 text-generation 仓库；这不是全 Hub 所有组织的全量清单。已读取 ${state.stats.config_review?.config_status?.ok ?? 0} 份 config.json，${state.stats.config_review?.with_structural_findings ?? 0} 条有结构线索。按仓库名称排除量化、转换及常见衍生项；候选中仍可能有实验/checkpoint/模型变体。自动线索只作初筛，不会冒充人工核验架构；${state.stats.model_card_review?.status?.ok ?? 0} 个代表架构类型另附模型卡关键词摘录供核查。</div></section></div>`;
}

function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(()=>el.classList.remove('show'),2600);
}

document.addEventListener('click', e => {
  const button = e.target.closest('[data-view]');
  if (button) setView(button.dataset.view);
});
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('#model-search')?.focus(); }
  if (e.key === 'Escape' && document.activeElement?.matches('input')) document.activeElement.blur();
});
init();

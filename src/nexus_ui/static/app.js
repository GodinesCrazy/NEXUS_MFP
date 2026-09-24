const ui = {
  connection: document.querySelector('[data-testid="connection-status"]'),
  connectionLabel: document.getElementById('connectionLabel'),
  tickerStrip: document.getElementById('tickerStrip'),
  refreshMarket: document.getElementById('refreshMarket'),
  runModel: document.getElementById('runModel'),
  runMode: document.getElementById('runMode'),
  toast: document.getElementById('toast'),
};

const state = { dashboard: null, market: null, run: null, toastTimer: null, selectedAsset: 'QQQ' };

const money = (value, currency = 'CLP') => new Intl.NumberFormat('es-CL', {
  style: 'currency', currency, maximumFractionDigits: currency === 'USD' ? 2 : 0,
}).format(Number(value || 0));
const pct = value => `${(Number(value || 0) * 100).toFixed(2).replace('.', ',')}%`;
const compact = value => new Intl.NumberFormat('es-CL', { notation: 'compact', maximumFractionDigits: 2 }).format(Number(value || 0));
const dateTime = value => value ? new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

function toast(message) {
  ui.toast.textContent = message;
  ui.toast.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => ui.toast.classList.remove('show'), 3200);
}

async function api(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  return payload;
}

function setConnection(online) {
  ui.connection.classList.toggle('online', online);
  ui.connectionLabel.textContent = online ? 'LOCAL ONLINE' : 'SIN CONEXIÓN';
}

function renderDashboard(data) {
  state.dashboard = data;
  document.getElementById('artifactTime').textContent = dateTime(data.artifact_updated_at_utc);
  document.getElementById('artifactRoot').textContent = data.artifact_root;
  document.getElementById('portfolioValue').textContent = data.portfolio.value_clp ? money(data.portfolio.value_clp) : 'SIN LEDGER';
  const portfolioReturn = document.getElementById('portfolioReturn');
  portfolioReturn.textContent = `Retorno desde inicio ${pct(data.portfolio.return_since_start)}`;
  portfolioReturn.className = data.portfolio.return_since_start >= 0 ? 'positive' : 'negative';
  document.getElementById('championName').textContent = data.model.champion;
  const allowed = data.causal_gate.promotion_allowed;
  document.getElementById('causalGate').textContent = allowed ? 'ELEGIBLE' : 'BLOQUEADO';
  document.getElementById('causalGate').className = allowed ? 'positive' : 'negative';
  document.getElementById('causalWeight').textContent = `Peso causal ${pct(data.causal_gate.causal_weight)}`;
  const healthy = data.sources.total - data.sources.failed_count;
  document.getElementById('sourceHealth').textContent = data.sources.total ? `${healthy}/${data.sources.total}` : 'SIN LEDGER';
  document.getElementById('sourceDetail').textContent = data.sources.failed_count ? `${data.sources.failed_count} fuentes bloquean promoción` : 'Sin fallos reportados';
  document.getElementById('signalDate').textContent = `SEÑAL ${data.portfolio.signal_date || '—'}`;
  document.getElementById('disclaimer').textContent = data.disclaimer;
  renderSignals(data.signals);
  renderAssetDetail(data.asset_details || []);
  renderMetrics(data.metrics);
  drawEquity(data.equity);
  const blockers = data.causal_gate.blockers || [];
  document.getElementById('blockerList').innerHTML = blockers.length
    ? blockers.map(item => `<span class="blocker">${escapeHtml(item)}</span>`).join('')
    : '<span class="blocker">Sin blockers activos</span>';
  document.getElementById('promotionStatus').textContent = allowed ? 'ELEGIBLE' : `PESO ${pct(data.causal_gate.causal_weight)}`;
  const vintage = data.vintages || {};
  document.getElementById('vintageStatus').textContent = vintage.promotion_ready
    ? `${vintage.series_complete}/${vintage.series_total} LISTO`
    : `${String(vintage.status || 'not_run').toUpperCase()} · ${vintage.snapshots || 0} snapshots`;
}

function renderSignals(signals) {
  const body = document.getElementById('signalsTable');
  if (!signals.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">No hay señales locales disponibles.</td></tr>';
    return;
  }
  body.innerHTML = signals.map(signal => `<tr data-asset-row="${escapeHtml(signal.asset)}">
    <td><button class="asset-link" data-asset="${escapeHtml(signal.asset)}">${escapeHtml(signal.asset)}</button></td>
    <td><span class="action ${escapeHtml(signal.action)}">${escapeHtml(signal.action)}</span></td>
    <td>${signal.current_weight == null ? '—' : pct(signal.current_weight)}</td>
    <td>${pct(signal.target_weight)}</td>
    <td title="${escapeHtml(signal.ensemble)}">${escapeHtml(signal.model_action || 'paper')}</td>
  </tr>`).join('');
  body.querySelectorAll('[data-asset]').forEach(button => button.addEventListener('click', () => {
    state.selectedAsset = button.dataset.asset;
    renderAssetDetail(state.dashboard?.asset_details || []);
    document.getElementById('assetDetailPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }));
}

function renderAssetDetail(details) {
  const tabs = document.getElementById('assetTabs');
  if (!details.length) {
    tabs.innerHTML = '';
    document.getElementById('causalDrivers').innerHTML = '<span class="empty-inline">Sin señales disponibles.</span>';
    return;
  }
  if (!details.some(item => item.asset === state.selectedAsset)) state.selectedAsset = details[0].asset;
  const detail = details.find(item => item.asset === state.selectedAsset);
  tabs.innerHTML = details.map(item => `<button class="asset-tab ${item.asset === detail.asset ? 'active' : ''}" data-detail-asset="${escapeHtml(item.asset)}">${escapeHtml(item.asset)}</button>`).join('');
  tabs.querySelectorAll('[data-detail-asset]').forEach(button => button.addEventListener('click', () => {
    state.selectedAsset = button.dataset.detailAsset;
    renderAssetDetail(details);
  }));
  document.getElementById('detailAsset').textContent = detail.asset;
  const action = document.getElementById('detailAction');
  action.textContent = detail.action; action.className = `action ${detail.action}`;
  document.getElementById('detailCurrent').textContent = detail.current_weight == null ? '—' : pct(detail.current_weight);
  document.getElementById('detailTarget').textContent = pct(detail.target_weight);
  document.getElementById('detailDelta').textContent = detail.weight_delta == null ? '—' : `${detail.weight_delta >= 0 ? '+' : ''}${pct(detail.weight_delta)}`;
  document.getElementById('allocationFill').style.width = `${Number(detail.allocation_strength || 0) * 100}%`;
  document.getElementById('ensembleDrivers').innerHTML = detail.ensemble_components.length
    ? detail.ensemble_components.map(item => `<div class="driver-row"><span>${escapeHtml(item.name)}</span><strong>${pct(item.weight)}</strong></div>`).join('')
    : '<span class="empty-inline">Sin desglose del ensemble.</span>';
  document.getElementById('causalDrivers').innerHTML = detail.causal_drivers.length
    ? detail.causal_drivers.map(item => `<div class="driver-row"><span>${escapeHtml(item.driver)}</span><strong>${escapeHtml(item.status)}</strong></div>`).join('')
    : '<div class="evidence-empty"><strong>0% PESO CAUSAL</strong><span>No existen drivers promovibles para esta señal.</span></div>';
  document.getElementById('detailExplanation').textContent = detail.explanation;
}

function renderMetrics(metrics) {
  const model = metrics.find(row => row.name.includes('META')) || metrics[0];
  const box = document.getElementById('metricsRow');
  if (!model) { box.innerHTML = '<div class="metric"><span>SIN MÉTRICAS</span><strong>—</strong></div>'; return; }
  box.innerHTML = [
    ['RETORNO TOTAL', pct(model.total_return)],
    ['SHARPE', Number(model.sharpe).toFixed(3)],
    ['MAX DRAWDOWN', pct(model.max_drawdown)],
  ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

function setupCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(320, canvas.clientWidth);
  const height = Number(canvas.getAttribute('height')) || 240;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
  return { ctx, width, height };
}

function drawSeries(ctx, values, bounds, color, width, height) {
  if (values.length < 2 || bounds.max === bounds.min) return;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = 8 + index / (values.length - 1) * (width - 16);
    const y = 8 + (bounds.max - value) / (bounds.max - bounds.min) * (height - 24);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.strokeStyle = color; ctx.lineWidth = 1.7; ctx.stroke();
}

function drawEquity(equity) {
  const canvas = document.getElementById('equityChart');
  const { ctx, width, height } = setupCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = '#20332e'; ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) { const y = i * height / 5; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke(); }
  const model = equity.map(point => point.model).filter(Boolean);
  const benchmark = equity.map(point => point.benchmark).filter(Boolean);
  const all = model.concat(benchmark);
  if (!all.length) return;
  const bounds = { min: Math.min(...all), max: Math.max(...all) };
  drawSeries(ctx, benchmark, bounds, '#63d5e6', width, height);
  drawSeries(ctx, model, bounds, '#54f2a6', width, height);
  ctx.fillStyle = '#80958d'; ctx.font = '10px Consolas';
  ctx.fillText(compact(bounds.max), 8, 12); ctx.fillText(compact(bounds.min), 8, height - 4);
}

function sparkSvg(points, positive) {
  if (!points || points.length < 2) return '';
  const values = points.map(point => point.value), min = Math.min(...values), max = Math.max(...values), spread = max - min || 1;
  const coords = values.map((value, i) => `${(i / (values.length - 1) * 90).toFixed(1)},${(34 - (value - min) / spread * 30).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 92 36" aria-hidden="true"><polyline fill="none" stroke="${positive ? '#54f2a6' : '#ff6b6b'}" stroke-width="1.5" points="${coords}"/></svg>`;
}

function renderMarket(market) {
  state.market = market;
  document.getElementById('marketProvider').textContent = market.provider || '—';
  ui.refreshMarket.disabled = market.status === 'loading';
  if (market.status === 'loading' && !market.quotes.length) {
    ui.tickerStrip.innerHTML = '<div class="ticker-skeleton">Consultando cotizaciones online…</div>'; return;
  }
  if (!market.quotes.length) {
    const fallback = state.dashboard?.signals || [];
    ui.tickerStrip.innerHTML = fallback.map(signal => `<div class="ticker"><strong class="ticker-symbol">${signal.asset}</strong><span class="ticker-value">${money(signal.price_usd, 'USD')}</span><span class="neutral-text">LOCAL</span></div>`).join('') || '<div class="ticker-skeleton">Mercado no disponible.</div>';
    return;
  }
  ui.tickerStrip.innerHTML = market.quotes.map(quote => {
    const positive = quote.change_window >= 0;
    return `<div class="ticker"><strong class="ticker-symbol">${escapeHtml(quote.asset)}</strong><div><div class="ticker-value">${money(quote.price_usd, 'USD')}</div><div class="ticker-change ${positive ? 'positive' : 'negative'}">${positive ? '+' : ''}${pct(quote.change_window)}</div></div>${sparkSvg(quote.points, positive)}</div>`;
  }).join('');
}

function renderRun(run) {
  state.run = run;
  document.getElementById('runPhase').textContent = run.phase;
  document.getElementById('runObjective').textContent = run.objective;
  document.getElementById('runPercent').textContent = `${run.progress}%`;
  document.getElementById('progressFill').style.width = `${run.progress}%`;
  document.getElementById('progressTrack').setAttribute('aria-valuenow', run.progress);
  const stateBadge = document.getElementById('runState');
  stateBadge.textContent = run.status.toUpperCase(); stateBadge.className = `run-state ${run.status}`;
  const elapsed = `${String(Math.floor((run.elapsed_seconds || 0) / 60)).padStart(2, '0')}:${String((run.elapsed_seconds || 0) % 60).padStart(2, '0')}`;
  document.getElementById('runMeta').textContent = run.pid ? `PID ${run.pid} · ${run.mode} · ${elapsed}` : (run.finished_at ? `Finalizó ${dateTime(run.finished_at)} · ${elapsed} · código ${run.exit_code}` : 'Sin proceso activo');
  const logs = document.getElementById('runLogs');
  logs.textContent = run.logs.length ? run.logs.join('\n') : '$ NEXUS listo. Ninguna operación real está habilitada.';
  if (run.status === 'running') logs.scrollTop = logs.scrollHeight;
  ui.runModel.disabled = run.status === 'running';
  ui.runMode.disabled = run.status === 'running';
}

async function loadDashboard() {
  try { renderDashboard(await api('/api/dashboard')); setConnection(true); }
  catch (error) { setConnection(false); toast(`Dashboard: ${error.message}`); }
}
async function loadMarket() {
  try { renderMarket(await api('/api/market')); }
  catch (error) { toast(`Mercado: ${error.message}`); }
}
async function loadRun() {
  try { renderRun(await api('/api/run')); }
  catch (error) { toast(`Proceso: ${error.message}`); }
}

ui.refreshMarket.addEventListener('click', async () => {
  try { renderMarket(await api('/api/market/refresh', { method: 'POST' })); toast('Actualización de mercado iniciada.'); }
  catch (error) { toast(error.message); }
});
ui.runModel.addEventListener('click', async () => {
  try {
    const payload = await api('/api/run', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ mode: ui.runMode.value }) });
    renderRun(payload); toast('Cadena NEXUS iniciada en segundo plano.');
  } catch (error) { toast(error.message); }
});

setInterval(() => { document.getElementById('clock').textContent = new Intl.DateTimeFormat('es-CL', { dateStyle:'medium', timeStyle:'medium' }).format(new Date()); }, 1000);
setInterval(loadRun, 2000);
setInterval(loadMarket, 10000);
setInterval(loadDashboard, 60000);
window.addEventListener('resize', () => state.dashboard && drawEquity(state.dashboard.equity));
Promise.all([loadDashboard(), loadMarket(), loadRun()]);

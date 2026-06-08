/* Moss Studio — browser workbench for the Moss language */
(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const editor = $('#editor');
  const output = $('#output');
  const diagnosticsEl = $('#diagnostics');
  const astEl = $('#ast');
  const tokensEl = $('#tokens');
  const symbolsEl = $('#symbols');
  const healthEl = $('#health');
  const summaryEl = $('#summary');
  const fileName = $('#fileName');
  const cursorStatus = $('#cursorStatus');
  const lineNumbers = $('#lineNumbers');
  const diagCount = $('#diagnosticCount');
  const exampleSelect = $('#exampleSelect');
  const pathInput = $('#pathInput');
  const fileInput = $('#fileInput');
  const releaseTag = $('#releaseTag');

  let currentPath = '';
  let lastResponse = null;

  // ── API ──
  async function api(path, body) {
    const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const resp = await fetch(path, init);
    if (!resp.ok) {
      try { return await resp.json(); } catch (_) { return { ok: false, diagnostics: [{ level: 'error', message: `HTTP ${resp.status}` }] }; }
    }
    return resp.json();
  }

  async function upload(source) {
    const resp = await fetch('/api/file/read', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source }) });
    return resp.json();
  }

  // ── Tab switching ──
  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      $$('.panel').forEach(p => p.classList.remove('active'));
      $(`#${tab.dataset.tab}Panel`).classList.add('active');
    });
  });

  // ── Diagnostics click → cursor jump ──
  diagnosticsEl.addEventListener('click', (e) => {
    const row = e.target.closest('[data-line]');
    if (!row) return;
    const line = parseInt(row.dataset.line);
    if (!line) return;
    const lines = editor.value.split('\n');
    let pos = 0;
    for (let i = 0; i < Math.min(line - 1, lines.length); i++) pos += lines[i].length + 1;
    editor.focus();
    editor.setSelectionRange(pos, pos);
  });

  // ── Line numbers sync ──
  function updateLineNumbers() {
    const count = editor.value.split('\n').length;
    const current = lineNumbers.textContent.split('\n').length;
    if (count === current) return;
    let txt = '';
    for (let i = 1; i <= count; i++) txt += i + '\n';
    lineNumbers.textContent = txt;
  }

  editor.addEventListener('input', updateLineNumbers);
  editor.addEventListener('scroll', () => { lineNumbers.scrollTop = editor.scrollTop; });

  editor.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); doRun(); }
    if (e.ctrlKey && e.key === 's') { e.preventDefault(); doSave(); }
  });

  editor.addEventListener('click', updateCursor);
  editor.addEventListener('keyup', updateCursor);
  function updateCursor() {
    const val = editor.value.substring(0, editor.selectionStart);
    const line = val.split('\n').length;
    const col = editor.selectionStart - val.lastIndexOf('\n');
    cursorStatus.textContent = `Ln ${line}, Col ${col}`;
  }

  // ── Health ──
  function setHealth(ok) {
    healthEl.textContent = ok ? 'OK' : 'Errors';
    healthEl.className = ok ? 'pass' : 'fail';
  }

  // ── Actions ──
  async function doCheck() {
    healthEl.textContent = 'Checking…';
    healthEl.className = '';
    const r = await api('/api/check', { source: editor.value, path: currentPath });
    lastResponse = r;
    render(r, false);
    setHealth(r.ok);
  }

  async function doRun() {
    healthEl.textContent = 'Running…';
    healthEl.className = '';
    const r = await api('/api/run', { source: editor.value, path: currentPath });
    lastResponse = r;
    render(r, true);
    setHealth(r.ok);
  }

  async function doTest() {
    healthEl.textContent = 'Testing…';
    healthEl.className = '';
    const r = await api('/api/test', { source: editor.value, path: currentPath });
    lastResponse = r;
    render(r, true);
    setHealth(r.ok);
  }

  async function doTrace() {
    healthEl.textContent = 'Tracing…';
    healthEl.className = '';
    const r = await api('/api/trace', { source: editor.value, path: currentPath });
    lastResponse = r;
    render(r, true);
    setHealth(r.ok);
  }

  async function doProject() {
    const p = currentPath || pathInput.value || 'examples';
    const r = await api('/api/project/info', { path: p });
    output.textContent = JSON.stringify(r, null, 2);
    $('#outputPanel').classList.add('active');
    setHealth(r.ok);
  }

  async function doCompare() {
    output.textContent = 'Running self-host comparison…';
    try {
      const r = await fetch('/api/selfhost/compare', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const d = await r.json();
      output.textContent = (d.output || ['Done']).join('\n');
      setHealth(d.ok);
    } catch (e) {
      output.textContent = 'Compare failed: ' + e;
      setHealth(false);
    }
  }

  // ── Render ──
  function render(r, showOutput) {
    // Output
    if (showOutput) {
      output.textContent = (r.output || []).join('\n');
      $('#outputPanel').classList.add('active');
      $$('.tab').forEach(t => t.classList.remove('active'));
      $('[data-tab="output"]').classList.add('active');
      $$('.panel').forEach(p => p.classList.remove('active'));
      $('#outputPanel').classList.add('active');
    }

    // Diagnostics
    diagCount.textContent = (r.diagnostics || []).length;
    let diagHtml = '';
    for (const d of (r.diagnostics || [])) {
      const loc = d.line ? `<div class="diag-loc">Ln ${d.line}${d.column ? ', Col ' + d.column : ''}</div>` : '';
      diagHtml += `<div class="diagnostic ${d.level}" data-line="${d.line || ''}">${loc}<div class="diag-msg">${esc(d.message)}</div></div>`;
    }
    diagnosticsEl.innerHTML = diagHtml || '';

    // AST
    astEl.textContent = (r.ast || '');

    // Tokens
    let tokHtml = '';
    for (const t of (r.tokens || [])) {
      tokHtml += `<div class="token-row"><span class="token-kind">${esc(t.kind)}</span><span class="token-value">${esc(String(t.value))}</span><span class="token-loc">${t.line}:${t.column}</span></div>`;
    }
    tokensEl.innerHTML = tokHtml;

    // Symbols
    let symHtml = '';
    for (const s of (r.symbols || [])) {
      symHtml += `<div class="symbol-row"><span class="symbol-kind">${esc(s.kind)}</span><span class="symbol-name">${esc(s.name)}</span></div>`;
    }
    symbolsEl.innerHTML = symHtml;

    // Summary
    const s = r.summary || {};
    summaryEl.textContent = `${s.effects || 0} effects | ${s.imports || 0} imports | ${s.types || 0} types | ${s.callables || 0} callables | ${s.tests || 0} tests`;
  }

  // ── File operations ──
  async function doSave() {
    const p = currentPath || pathInput.value;
    if (!p) { healthEl.textContent = 'Enter a path to save'; return; }
    try {
      const r = await fetch('/api/file/write', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: p, source: editor.value })
      });
      const d = await r.json();
      if (d.ok) { currentPath = d.path; pathInput.value = d.path; fileName.textContent = d.path; healthEl.textContent = 'Saved'; }
      else { healthEl.textContent = d.message || 'Save failed'; }
    } catch (e) { healthEl.textContent = 'Save error: ' + e; }
  }

  async function doOpen() {
    const p = pathInput.value;
    if (!p) return;
    try {
      const r = await fetch('/api/file/read', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: p })
      });
      const d = await r.json();
      if (d.ok) { editor.value = d.source; currentPath = d.path; fileName.textContent = d.path; updateLineNumbers(); doCheck(); }
      else { healthEl.textContent = d.message || 'Open failed'; }
    } catch (e) { healthEl.textContent = 'Open error: ' + e; }
  }

  function doNew() {
    editor.value = '';
    currentPath = '';
    pathInput.value = '';
    fileName.textContent = 'scratch.moss';
    output.textContent = '';
    diagnosticsEl.innerHTML = '';
    astEl.textContent = '';
    tokensEl.innerHTML = '';
    symbolsEl.innerHTML = '';
    diagCount.textContent = '0';
    summaryEl.textContent = '0 effects | 0 imports | 0 types | 0 callables | 0 tests';
    healthEl.textContent = 'Ready';
    healthEl.className = '';
    updateLineNumbers();
  }

  // ── Import local file ──
  function doImport() { fileInput.click(); }
  fileInput.addEventListener('change', () => {
    const f = fileInput.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      editor.value = e.target.result;
      currentPath = f.name;
      fileName.textContent = f.name;
      updateLineNumbers();
      doCheck();
    };
    reader.readAsText(f);
  });

  // ── Examples ──
  async function loadExamples() {
    try {
      const r = await fetch('/api/examples');
      const data = await r.json();
      exampleSelect.innerHTML = '<option value="">— Load example —</option>';
      for (const ex of (data.examples || [])) {
        const opt = document.createElement('option');
        opt.value = ex.filename;
        opt.textContent = ex.label;
        exampleSelect.appendChild(opt);
      }
    } catch (_) {}
  }
  exampleSelect.addEventListener('change', async () => {
    const filename = exampleSelect.value;
    if (!filename) return;
    try {
      const r = await fetch('/api/examples');
      const data = await r.json();
      const ex = (data.examples || []).find(e => e.filename === filename);
      if (ex) {
        editor.value = ex.source;
        currentPath = 'examples/' + filename;
        fileName.textContent = filename;
        pathInput.value = 'examples/' + filename;
        updateLineNumbers();
        doCheck();
      }
    } catch (_) {}
  });

  // ── Buttons ──
  $('#runButton').addEventListener('click', doRun);
  $('#checkButton').addEventListener('click', doCheck);
  $('#trustButton').addEventListener('click', doTrust);
  $('#testButton').addEventListener('click', doTest);
  $('#traceButton').addEventListener('click', doTrace);
  $('#projectButton').addEventListener('click', doProject);
  $('#compareButton').addEventListener('click', doCompare);
  $('#newButton').addEventListener('click', doNew);
  $('#importButton').addEventListener('click', doImport);
  $('#loadPathButton').addEventListener('click', doOpen);
  $('#saveButton').addEventListener('click', doSave);

  // ── Trust ──
  async function doTrust() {
    healthEl.textContent = 'Trusting…';
    healthEl.className = '';
    const r = await api('/api/trust', { source: editor.value, path: currentPath });
    renderTrust(r);
    // Switch to Trust tab
    $$('.tab').forEach(t => t.classList.remove('active'));
    $('[data-tab="trust"]').classList.add('active');
    $$('.panel').forEach(p => p.classList.remove('active'));
    $('#trustPanel').classList.add('active');
    setHealth(r.trust);
    // Also render diagnostics from check
    diagCount.textContent = (r.check?.diagnostics || []).length;
    let diagHtml = '';
    for (const d of (r.check?.diagnostics || [])) {
      const loc = d.line ? `<div class="diag-loc">Ln ${d.line}${d.column ? ', Col ' + d.column : ''}</div>` : '';
      diagHtml += `<div class="diagnostic ${d.level}" data-line="${d.line || ''}">${loc}<div class="diag-msg">${esc(d.message)}</div></div>`;
    }
    diagnosticsEl.innerHTML = diagHtml || '';
    const s = r.check?.summary || {};
    summaryEl.textContent = `${s.effects || 0} effects | ${s.imports || 0} imports | ${s.types || 0} types | ${s.callables || 0} callables | ${s.tests || 0} tests`;
  }

  function renderTrust(b) {
    const tc = $('#trustContent');
    const trusted = b.trust;
    const icon = trusted ? '&#x2705;' : '&#x274C;';
    const msg = trusted ? 'Trust Verified' : 'Trust Failed';
    const sub = trusted ? 'All gates passed. This program is provably correct.' : 'One or more gates failed.';

    let html = `<div class="trust-bar ${trusted ? 'trusted' : 'untrusted'}">
      <div class="trust-icon">${icon}</div>
      <div>
        <div class="trust-text ${trusted ? 'trusted' : 'untrusted'}">${msg}</div>
        <div class="trust-sub">${sub}</div>
        <div class="trust-sub" style="margin-top:4px">sha256 <code>${(b.source_sha256||'').substring(0,16)}...</code></div>
      </div>
    </div><div class="gates">`;

    html += _gate('static-check', 'Static Check', b.check?.ok, `${_summaryText(b.check?.summary)}`, b.check?.diagnostics);
    if (b.lock && b.lock.ok !== null) {
      html += _gate('lock', 'Lock', b.lock.ok, b.lock.ok ? `${b.lock.modules||0} modules locked` : (b.lock.error||''));
    }
    html += _gate('trace', 'Rule Trace', b.trace?.ok, `${(b.trace?.events||[]).length} rule(s)`);
    html += _gate('golden', 'Golden', b.golden?.ok === true, b.golden?.note || (b.golden?.ok ? 'matches' : 'mismatch'));
    html += _gate('selfhost', 'Selfhost', b.selfhost?.ok, b.selfhost?.ok ? 'all 5 dimensions match' : 'discrepancy', null, b.selfhost?.expression_error);

    // Trace events
    if (b.trace?.events?.length) {
      html += `<details class="detail-block" style="margin:0 0 8px 0"><summary>${b.trace.events.length} rule evaluation(s)</summary><pre style="max-height:180px">`;
      for (const e of b.trace.events) {
        const args = Object.entries(e.arguments||{}).map(([k,v])=>`${k}=${v}`).join(', ');
        html += `${e.rule}(${args}) → ${e.result}  [${e.file}:${e.line}]\n`;
      }
      html += `</pre></details>`;
    }
    html += '</div>';
    tc.innerHTML = html;
    tc.style.display = 'block';
  }

  function _gate(id, name, ok, detail, diagnostics, extra) {
    const cls = ok === true ? 'pass' : (ok === false ? 'fail' : 'unknown');
    const icon = ok === true ? '✓' : (ok === false ? '✗' : '—');
    const badge = ok === true ? 'PASS' : (ok === false ? 'FAIL' : 'SKIP');
    const badgeCls = ok === true ? 'pass' : (ok === false ? 'fail' : 'warn');
    let h = `<div class="trust-gate ${cls}"><div class="g-icon">${icon}</div><div class="g-name">${name}</div><div class="g-badge ${badgeCls}">${badge}</div>`;
    if (detail) h += `<div class="g-detail">${detail}</div>`;
    if (diagnostics && diagnostics.length) {
      h += `<div style="grid-column:2;font-size:0.72rem;color:var(--fail);margin-top:2px">`;
      for (const d of diagnostics) h += `${d.level}: ${esc(d.message)} `;
      h += `</div>`;
    }
    if (extra) h += `<div style="grid-column:2;font-size:0.7rem;color:var(--muted);margin-top:2px">${esc(extra)}</div>`;
    h += `</div>`;
    return h;
  }

  function _summaryText(s) {
    if (!s) return '';
    return `${s.effects||0} effects, ${s.types||0} types, ${s.callables||0} callables, ${s.tests||0} tests`;
  }

  // ── Init ──
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  loadExamples();
  updateLineNumbers();
  updateCursor();

  // Default scratch content
  if (!editor.value.trim()) {
    editor.value = `fn greet(name) = \`Hello {name}!\`
print(greet("Moss"))`;
    updateLineNumbers();
  }

  // Update release tag from version in response
  fetch('/api/examples').then(r => r.json()).then(() => {
    releaseTag.textContent = '0.6';
  }).catch(() => {});
})();

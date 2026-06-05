const editor = document.querySelector("#editor");
const lineNumbers = document.querySelector("#lineNumbers");
const output = document.querySelector("#output");
const diagnostics = document.querySelector("#diagnostics");
const ast = document.querySelector("#ast");
const tokens = document.querySelector("#tokens");
const health = document.querySelector("#health");
const summary = document.querySelector("#summary");
const cursorStatus = document.querySelector("#cursorStatus");
const fileName = document.querySelector("#fileName");
const pathInput = document.querySelector("#pathInput");
const fileInput = document.querySelector("#fileInput");
const exampleSelect = document.querySelector("#exampleSelect");
const diagnosticCount = document.querySelector("#diagnosticCount");
const symbols = document.querySelector("#symbols");

let currentName = "scratch.moss";
let debounceId = 0;
let lastResult = null;

const fallbackSource = `effect Database

type Order =
  id: Text
  status: Pending | Paid | Shipped | Cancelled
  total: Money

type ShipError = NotReady | Missing

rule canShip(order: Order) -> Bool =
  order.status == Paid and order.total > 0.usd

rule statusLabel(status) =
  match status {
    Pending -> "waiting"
    Paid -> "ready"
    Shipped -> "sent"
    _ -> "closed"
  }

fn ship(order: Order) -> Result<Order, ShipError> uses Database {
  require canShip(order)
    else ShipError.NotReady(order.status)

  updated = order with status = Shipped
  dbPut(order.id, updated)
  return Ok(updated)
}

let order = { id: "A-100", status: Paid, total: 42.usd }
let shipped = ship(order)?
print("status:", shipped.status)
print("label:", statusLabel(shipped.status))
print("stored:", dbGet("A-100").status)

test "ships paid orders" {
  result = ship(order)?
  assert(result.status == Shipped, "paid order should ship")
}
`;

function init() {
  const saved = localStorage.getItem("moss.source");
  editor.value = saved || fallbackSource;
  currentName = localStorage.getItem("moss.fileName") || currentName;
  fileName.textContent = currentName;
  pathInput.value = currentName;
  bindEvents();
  loadExamples();
  updateEditorChrome();
  scheduleCheck();
}

function bindEvents() {
  editor.addEventListener("input", () => {
    localStorage.setItem("moss.source", editor.value);
    updateEditorChrome();
    scheduleCheck();
  });
  editor.addEventListener("scroll", () => {
    lineNumbers.scrollTop = editor.scrollTop;
  });
  editor.addEventListener("keyup", updateCursor);
  editor.addEventListener("click", updateCursor);
  editor.addEventListener("keydown", event => {
    if (event.key === "Tab") {
      event.preventDefault();
      insertText("  ");
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      runSource();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveWorkspacePath();
    }
  });

  document.querySelector("#runButton").addEventListener("click", runSource);
  document.querySelector("#testButton").addEventListener("click", testSource);
  document.querySelector("#checkButton").addEventListener("click", checkSource);
  document.querySelector("#traceButton").addEventListener("click", traceSource);
  document.querySelector("#projectButton").addEventListener("click", inspectProject);
  document.querySelector("#compareButton").addEventListener("click", compareSelfhost);
  document.querySelector("#newButton").addEventListener("click", newFile);
  document.querySelector("#loadPathButton").addEventListener("click", loadWorkspacePath);
  document.querySelector("#savePathButton").addEventListener("click", saveWorkspacePath);
  document.querySelector("#openButton").addEventListener("click", () => fileInput.click());
  document.querySelector("#saveButton").addEventListener("click", downloadSource);
  pathInput.addEventListener("change", () => {
    currentName = pathInput.value.trim() || "scratch.moss";
    persistFile();
  });
  fileInput.addEventListener("change", openFile);
  exampleSelect.addEventListener("change", loadSelectedExample);

  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
}

async function loadExamples() {
  try {
    const data = await fetchJson("/api/examples");
    exampleSelect.innerHTML = "";
    const scratch = document.createElement("option");
    scratch.value = "";
    scratch.textContent = "Examples";
    exampleSelect.appendChild(scratch);
    data.examples.forEach(example => {
      const option = document.createElement("option");
      option.value = example.filename;
      option.textContent = example.label;
      option.dataset.source = example.source;
      exampleSelect.appendChild(option);
    });
  } catch {
    exampleSelect.innerHTML = "<option>Examples</option>";
  }
}

function loadSelectedExample() {
  const option = exampleSelect.selectedOptions[0];
  if (!option || !option.dataset.source) {
    return;
  }
  editor.value = option.dataset.source;
  currentName = option.value;
  persistFile();
  updateEditorChrome();
  checkSource();
}

function newFile() {
  editor.value = "";
  currentName = "scratch.moss";
  persistFile();
  updateEditorChrome();
  renderResult({
    ok: true,
    output: [],
    diagnostics: [],
    ast: "",
    tokens: [],
    summary: { effects: 0, imports: 0, types: 0, callables: 0, tests: 0 },
  });
}

function openFile() {
  const file = fileInput.files[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    editor.value = String(reader.result || "");
    currentName = file.name;
    persistFile();
    updateEditorChrome();
    checkSource();
  };
  reader.readAsText(file);
  fileInput.value = "";
}

function downloadSource() {
  const blob = new Blob([editor.value], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = currentName.endsWith(".moss") ? currentName : `${currentName}.moss`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function persistFile() {
  fileName.textContent = currentName;
  pathInput.value = currentName;
  localStorage.setItem("moss.fileName", currentName);
  localStorage.setItem("moss.source", editor.value);
}

function insertText(text) {
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  editor.value = editor.value.slice(0, start) + text + editor.value.slice(end);
  editor.selectionStart = editor.selectionEnd = start + text.length;
  editor.dispatchEvent(new Event("input"));
}

function updateEditorChrome() {
  updateLineNumbers();
  updateCursor();
}

function updateLineNumbers() {
  const count = Math.max(1, editor.value.split("\n").length);
  lineNumbers.textContent = Array.from({ length: count }, (_, index) => index + 1).join("\n");
}

function updateCursor() {
  const before = editor.value.slice(0, editor.selectionStart);
  const lines = before.split("\n");
  cursorStatus.textContent = `Ln ${lines.length}, Col ${lines[lines.length - 1].length + 1}`;
}

function scheduleCheck() {
  clearTimeout(debounceId);
  debounceId = setTimeout(checkSource, 450);
}

async function checkSource() {
  setBusy("Checking");
  try {
    renderResult(await fetchJson("/api/check", { source: editor.value, path: currentName }));
  } catch (error) {
    renderFailure(error);
  }
}

async function runSource() {
  setBusy("Running");
  activateTab("output");
  try {
    renderResult(await fetchJson("/api/run", { source: editor.value, path: currentName }));
  } catch (error) {
    renderFailure(error);
  }
}

async function testSource() {
  setBusy("Testing");
  activateTab("output");
  try {
    renderResult(await fetchJson("/api/test", { source: editor.value, path: currentName }));
  } catch (error) {
    renderFailure(error);
  }
}

async function traceSource() {
  setBusy("Tracing");
  activateTab("output");
  try {
    renderResult(await fetchJson("/api/trace", { source: editor.value, path: currentName }));
  } catch (error) {
    renderFailure(error);
  }
}

async function inspectProject() {
  setBusy("Inspecting");
  activateTab("output");
  try {
    const result = await fetchJson("/api/project/info", { path: currentName });
    output.textContent = `${result.package.name} ${result.package.version}\n` + result.modules.map(item => `${item.path} -> ${item.imports.join(", ") || "-"}`).join("\n");
    health.textContent = "Project OK";
    health.className = "okText";
  } catch (error) {
    renderFailure(error);
  }
}

async function compareSelfhost() {
  setBusy("Comparing");
  activateTab("output");
  try {
    const result = await fetchJson("/api/selfhost/compare", {});
    output.textContent = result.output.join("\n");
    health.textContent = result.ok ? "Self-host OK" : "Mismatch";
    health.className = result.ok ? "okText" : "errorText";
  } catch (error) {
    renderFailure(error);
  }
}

async function loadWorkspacePath() {
  const path = pathInput.value.trim();
  if (!path) {
    return;
  }
  setBusy("Opening");
  try {
    const result = await fetchJson("/api/file/read", { path });
    editor.value = result.source || "";
    currentName = result.path || path;
    persistFile();
    updateEditorChrome();
    checkSource();
  } catch (error) {
    renderFailure(error);
  }
}

async function saveWorkspacePath() {
  const path = pathInput.value.trim() || currentName;
  setBusy("Saving");
  try {
    const result = await fetchJson("/api/file/write", { path, source: editor.value });
    currentName = result.path || path;
    persistFile();
    health.textContent = "Saved";
    health.className = "okText";
  } catch (error) {
    renderFailure(error);
  }
}

async function fetchJson(url, payload) {
  const options = payload
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    : {};
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function renderResult(result) {
  lastResult = result;
  const hasErrors = result.diagnostics.some(item => item.level === "error");
  health.textContent = result.ok && !hasErrors ? "OK" : "Issue";
  health.className = result.ok && !hasErrors ? "okText" : "errorText";
  summary.textContent = `${result.summary.effects} effects | ${result.summary.imports || 0} imports | ${result.summary.types} types | ${result.summary.callables} callables | ${result.summary.tests || 0} tests`;
  output.textContent = result.output.length ? result.output.join("\n") : "";
  ast.textContent = result.ast || "";
  renderDiagnostics(result.diagnostics, result.ok);
  renderTokens(result.tokens);
  renderSymbols(result.symbols || []);
}

function renderFailure(error) {
  health.textContent = "Offline";
  health.className = "errorText";
  output.textContent = String(error);
  renderDiagnostics([{ level: "error", message: String(error) }], false);
}

function renderDiagnostics(items, ok) {
  diagnostics.innerHTML = "";
  diagnosticCount.textContent = String(items.length);
  diagnosticCount.classList.toggle("hasIssues", items.length > 0);
  const list = items.length ? items : [{ level: ok ? "ok" : "warning", message: ok ? "No diagnostics" : "No result" }];
  list.forEach(item => {
    const node = document.createElement("div");
    node.className = `diag ${item.level}`;
    const level = document.createElement("span");
    level.className = "diagLevel";
    level.textContent = item.level;
    const message = document.createElement("span");
    const location = item.line ? `${item.line}:${item.column || 1}: ` : "";
    message.textContent = location + item.message;
    if (item.line) {
      node.classList.add("located");
      node.title = "Go to source location";
      node.addEventListener("click", () => focusLocation(item.line, item.column || 1));
    }
    node.append(level, message);
    diagnostics.appendChild(node);
  });
}

function focusLocation(line, column) {
  const lines = editor.value.split("\n");
  const safeLine = Math.max(1, Math.min(line, lines.length));
  const safeColumn = Math.max(1, Math.min(column, lines[safeLine - 1].length + 1));
  const offset = lines.slice(0, safeLine - 1).reduce((total, value) => total + value.length + 1, 0) + safeColumn - 1;
  editor.focus();
  editor.setSelectionRange(offset, offset);
  updateCursor();
}

function renderTokens(items) {
  tokens.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "tokenGrid";
  ["Kind", "Value", "Loc"].forEach(label => {
    const cell = document.createElement("span");
    cell.className = "tokenHead";
    cell.textContent = label;
    grid.appendChild(cell);
  });
  items.forEach(token => {
    const kind = document.createElement("span");
    kind.textContent = token.kind;
    const value = document.createElement("span");
    value.textContent = token.value === "\n" ? "\\n" : token.value;
    const loc = document.createElement("span");
    loc.textContent = `${token.line}:${token.column}`;
    grid.append(kind, value, loc);
  });
  tokens.appendChild(grid);
}

function renderSymbols(items) {
  symbols.innerHTML = "";
  items.forEach(item => {
    const node = document.createElement("button");
    node.className = "symbol";
    node.textContent = item.name;
    node.title = "Go to declaration";
    node.addEventListener("click", () => focusLocation(item.range.start.line + 1, item.range.start.character + 1));
    symbols.appendChild(node);
  });
}

function setBusy(label) {
  health.textContent = label;
  health.className = "";
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.remove("active"));
  document.querySelector(`#${name}Panel`).classList.add("active");
}

init();

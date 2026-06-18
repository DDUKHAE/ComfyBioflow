import { app } from "../../scripts/app.js";
import { el, makeDraggable, makeResizable } from "./dom_utils.js";
import {
    getProvider, setProvider, getModel, setModel, getModels, setModels,
    getInputPath, setInputPath, getOutputDir, setOutputDir,
    setActiveTab, getBrowserTarget, setBrowserTarget,
    getBrowserPath, setBrowserPath, getBrowserPathByTarget,
    getQuickPaths, getGenerating, setGenerating,
    getPromptLines, setPromptLines,
    getCachedStatus, setCachedStatus, invalidateCachedStatus,
} from "./state.js";
import {
    fetchStatus, fetchModels, postLogin, postInstall,
    browsePath, fetchDefaultPaths, postGenerate,
} from "./api_client.js";
import {
    renderLLMLog, renderInstallProgress, renderInstallError,
    renderPromptLog, renderBrowserEntries, renderTestConnectionProgress,
    renderTerminalLog,
} from "./ui_controller.js";

// ── xterm.js CDN ───────────────────────────────────────────────────────────────
const _XTERM_JS  = "https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js";
const _XTERM_CSS = "https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css";
const _XTERM_FIT = "https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js";

let _xtermInst  = null;   // xterm Terminal instance
let _xtermWs    = null;   // WebSocket to PTY backend
let _xtermPoll  = null;   // status-poll interval during login
let _fitAddon   = null;

async function _loadXtermJs() {
    if (window.Terminal) return;
    if (!document.querySelector("[data-xterm-css]")) {
        const link = document.createElement("link");
        link.rel = "stylesheet"; link.href = _XTERM_CSS;
        link.dataset.xtermCss = "1";
        document.head.appendChild(link);
    }
    await new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = _XTERM_JS; s.onload = res; s.onerror = rej;
        document.head.appendChild(s);
    });
    // FitAddon (optional)
    if (!window.FitAddon) {
        await new Promise(res => {
            const s = document.createElement("script");
            s.src = _XTERM_FIT; s.onload = res; s.onerror = res;
            document.head.appendChild(s);
        });
    }
}

function _destroyXterm() {
    if (_xtermPoll) { clearInterval(_xtermPoll); _xtermPoll = null; }
    if (_xtermWs)   { _xtermWs.close();  _xtermWs   = null; }
    if (_xtermInst) { _xtermInst.dispose(); _xtermInst = null; }
    _fitAddon = null;
    const wrap = _el("cb-xterm-wrap");
    if (wrap) { wrap.classList.remove("cb-xterm-open"); wrap.innerHTML = ""; }
    const log = _el("cb-llm-log");
    if (log) log.style.display = "";
}

async function _openXtermLogin(provider) {
    try { await _loadXtermJs(); } catch (e) { return false; }

    const wrap = _el("cb-xterm-wrap");
    const log  = _el("cb-llm-log");
    if (!wrap) return false;

    // Hide status card, show terminal
    if (log) log.style.display = "none";
    wrap.innerHTML = "";
    wrap.classList.add("cb-xterm-open");

    // Measure available size
    const rect = wrap.getBoundingClientRect();
    const cols  = Math.max(20, Math.floor((rect.width  - 8) / 7.2)) || 44;
    const rows  = Math.max(4,  Math.floor((rect.height - 8) / 14))  || 18;

    _xtermInst = new window.Terminal({
        cols, rows,
        theme: {
            background: "#0B1A10", foreground: "#FFFFFF",
            cursor: "#1DB954", cursorAccent: "#000000",
            selectionBackground: "rgba(29,185,84,0.25)",
            green: "#1DB954", brightGreen: "#1ED760",
        },
        fontSize: 11,
        fontFamily: '"SF Mono","Consolas","Courier New",monospace',
        cursorBlink: true,
        cursorStyle: "block",
        allowProposedApi: true,
        convertEol: true,
    });
    _xtermInst.open(wrap);

    if (window.FitAddon) {
        _fitAddon = new window.FitAddon.FitAddon();
        _xtermInst.loadAddon(_fitAddon);
        _fitAddon.fit();
    }

    // WebSocket to PTY backend
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url   = `${proto}//${location.host}/comfybio/terminal?provider=${encodeURIComponent(provider)}&cols=${cols}&rows=${rows}`;
    _xtermWs = new WebSocket(url);
    _xtermWs.binaryType = "arraybuffer";

    _xtermWs.onopen  = () => _xtermInst?.write("\x1b[32m[ComfyBIO]\x1b[0m 터미널 세션 연결됨\r\n\r\n");
    _xtermWs.onmessage = (e) => {
        const data = e.data instanceof ArrayBuffer ? new Uint8Array(e.data) : e.data;
        _xtermInst?.write(data);
    };
    _xtermWs.onerror = () => _xtermInst?.write("\r\n\x1b[31m[오류] 서버 연결 실패\x1b[0m\r\n");
    _xtermWs.onclose = () => _xtermInst?.write("\r\n\x1b[33m[세션 종료]\x1b[0m\r\n");

    _xtermInst.onData((d) => {
        if (_xtermWs?.readyState === WebSocket.OPEN) _xtermWs.send(d);
    });

    return true;
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function _el(id) { return document.getElementById(id); }

function _isComfyUILightMode() {
    // 1. Try checking the ComfyUI setting Comfy.ColorPalette
    try {
        const palette = app.extensionManager.setting.get("Comfy.ColorPalette");
        if (palette) {
            const p = palette.toLowerCase();
            if (p.includes("light") || p.includes("white") || p === "arc") {
                return true;
            }
            if (p === "dark" || p.includes("dark") || p === "solarized" || p === "nord") {
                return false;
            }
        }
    } catch (e) {
        try {
            const palette = app.ui.settings.getSetting("Comfy.ColorPalette");
            if (palette) {
                const p = palette.toLowerCase();
                if (p.includes("light") || p.includes("white") || p === "arc") {
                    return true;
                }
                if (p === "dark" || p.includes("dark") || p === "solarized" || p === "nord") {
                    return false;
                }
            }
        } catch (e2) {}
    }

    // 2. Try checking prefers-color-scheme
    try {
        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
            return true;
        }
    } catch (e) {}

    // 3. Fallback: check background color of the body
    try {
        const bodyBg = window.getComputedStyle(document.body).backgroundColor;
        if (bodyBg) {
            const match = bodyBg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (match) {
                const r = parseInt(match[1]);
                const g = parseInt(match[2]);
                const b = parseInt(match[3]);
                const brightness = (r * 299 + g * 587 + b * 114) / 1000;
                return brightness > 128;
            }
        }
    } catch (e) {}

    return false;
}

function _applyTheme() {
    const panel = _el("cb-panel");
    const toggler = _el("cb-toggler");
    const isLight = _isComfyUILightMode();
    if (isLight) {
        panel?.classList.add("cb-theme-light");
        toggler?.classList.add("cb-theme-light");
    } else {
        panel?.classList.remove("cb-theme-light");
        toggler?.classList.remove("cb-theme-light");
    }
}
function _now() {
    return new Date().toLocaleTimeString("en", { hour12: false });
}
function _capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
function _modelsData() {
    return { models: getModels(), default: getModel() };
}

// ── Tab switching ──────────────────────────────────────────────────────────────
function _fitPanelToViewport() {
    const panel = _el("cb-panel");
    if (!panel || panel.classList.contains("cb-hidden")) return;

    panel.style.zoom = "1";
    const panelRect = panel.getBoundingClientRect();
    const left = parseFloat(panel.style.left || `${panelRect.left}`) || panelRect.left;
    const top = parseFloat(panel.style.top || `${panelRect.top}`) || panelRect.top;
    const maxWidth = Math.max(220, window.innerWidth - left - 8);
    const maxHeight = Math.max(100, window.innerHeight - top - 8);

    panel.style.maxWidth = `${maxWidth}px`;
    panel.style.maxHeight = `${maxHeight}px`;
}

function switchTab(tabId) {
    setActiveTab(tabId);
    document.querySelectorAll(".cb-tab-btn").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.tab === tabId));
    document.querySelectorAll(".cb-tab-pane").forEach(pane =>
        pane.style.display = pane.dataset.pane === tabId ? "flex" : "none");
    requestAnimationFrame(_fitPanelToViewport);
}

// ── Provider / Model UI ────────────────────────────────────────────────────────

function _applyStatus(statusData) {
    const badge = _el("cb-provider-badge");
    if (!statusData.installed) {
        badge.textContent = "Not installed"; badge.className = "cb-badge cb-badge-error";
    } else if (!statusData.ready) {
        badge.textContent = "Not logged in"; badge.className = "cb-badge cb-badge-warning";
    } else {
        badge.textContent = "Ready"; badge.className = "cb-badge cb-badge-ok";
    }
}

async function _triggerLogin() {
    const provider = getProvider();

    // Open embedded xterm terminal for the login session
    const opened = await _openXtermLogin(provider);

    if (!opened) {
        // Fallback: open browser URL (old behaviour)
        try {
            const data = await postLogin(provider);
            if (data.login_url) window.open(data.login_url, "_blank");
        } catch { /* ignore */ }
    }

    // Poll status until authenticated (or timeout after 3 min)
    let tries = 0;
    const pollProvider = provider;
    _xtermPoll = setInterval(async () => {
        tries++;
        invalidateCachedStatus(pollProvider);
        const s = await fetchStatus(pollProvider).catch(() => null);
        if (!s) return;
        setCachedStatus(pollProvider, s);

        if (s.ready || tries > 60) {
            _destroyXterm();
            if (getProvider() === pollProvider) {
                _applyStatus(s);
                renderLLMLog(s, _modelsData(), pollProvider, {
                    onInstall: _triggerInstall,
                    onLogin: _triggerLogin,
                    onTestConnection: _triggerTestConnection,
                });
            }
        }
    }, 3000);
}

async function _triggerInstall() {
    const box = _el("cb-llm-log");
    const label = _capitalize(getProvider());

    renderInstallProgress(box, label);

    try {
        const data = await postInstall(getProvider());

        if (data.status === "success") {
            invalidateCachedStatus(getProvider());
            await refreshProvider(getProvider());
        } else {
            renderInstallError(box, label, data.message || "Unknown error", _triggerInstall);
        }
    } catch (err) {
        renderInstallError(box, label, err.message, _triggerInstall);
    }
}

async function _triggerTestConnection() {
    const box = _el("cb-llm-log");
    const label = _capitalize(getProvider());
    renderTestConnectionProgress(box, label);

    try {
        invalidateCachedStatus(getProvider());
        // Add a small UX simulation delay so the connection test feels reactive and real
        await new Promise(resolve => setTimeout(resolve, 600));

        const statusData = await fetchStatus(getProvider());
        setCachedStatus(getProvider(), statusData);

        const modelsData = _modelsData();
        _applyStatus(statusData);
        renderLLMLog(statusData, modelsData, getProvider(), {
            onInstall: _triggerInstall,
            onLogin: _triggerLogin,
            onTestConnection: _triggerTestConnection
        });
    } catch (err) {
        const cached = getCachedStatus(getProvider()) || { installed: true, ready: true };
        renderLLMLog(cached, _modelsData(), getProvider(), {
            onInstall: _triggerInstall,
            onLogin: _triggerLogin,
            onTestConnection: _triggerTestConnection
        });
    }
}

function _populateModelDropdown(models, defaultModel) {
    const modelSel = _el("cb-model");
    modelSel.replaceChildren();
    if (models.length === 0) {
        const opt = document.createElement("option");
        opt.value = ""; opt.textContent = "(no models found)";
        modelSel.appendChild(opt);
        return;
    }
    for (const m of models) {
        const opt = document.createElement("option");
        opt.value = m; opt.textContent = m;
        if (m === defaultModel) opt.selected = true;
        modelSel.appendChild(opt);
    }
}

async function refreshProvider(provider) {
    const badge = _el("cb-provider-badge");
    badge.textContent = "…";
    badge.className = "cb-badge cb-badge-loading";

    const modelsData = await fetchModels(provider);
    setModels(modelsData.models ?? []);
    setModel(modelsData.default ?? (getModels()[0] ?? ""));
    _populateModelDropdown(getModels(), getModel());

    (async () => {
        let statusData = getCachedStatus(provider);
        if (!statusData) {
            statusData = await fetchStatus(provider);
            setCachedStatus(provider, statusData);
        }
        _applyStatus(statusData);
        renderLLMLog(statusData, modelsData, provider, {
            onInstall: _triggerInstall,
            onLogin: _triggerLogin,
            onTestConnection: _triggerTestConnection
        });
    })();
}

// ── File browser ───────────────────────────────────────────────────────────────
function _setBrowserTarget(target) {
    const prevTarget = getBrowserTarget();
    if (prevTarget) {
        getBrowserPathByTarget()[prevTarget] = getBrowserPath() || getBrowserPathByTarget()[prevTarget] || "";
    }

    setBrowserTarget(target);
    document.querySelectorAll(".cb-io-target").forEach(btn =>
        btn.classList.toggle("active", btn.dataset.target === target));

    const inputEl = _el("cb-input-path");
    const outputEl = _el("cb-output-path");
    const inputErr = _el("cb-input-error");
    const outputErr = _el("cb-output-error");
    const label = _el("cb-io-selected-label");
    const pathInput = _el("cb-io-current-path-display");

    inputErr.style.display = target === "input" ? "" : "none";
    outputErr.style.display = target === "output" ? "" : "none";
    label.textContent = target === "input" ? "Selected Input Path" : "Selected Output Directory";

    const currentValue = target === "input" ? inputEl.value.trim() : outputEl.value.trim();
    const rememberedPath = getBrowserPathByTarget()[target] || "";
    const startPath = target === "output"
        ? (rememberedPath || currentValue || getQuickPaths()[target] || getBrowserPath() || "")
        : (currentValue || rememberedPath || getQuickPaths()[target] || getBrowserPath() || "");

    _el("cb-selected-path-val").textContent = currentValue || "Not selected";
    if (pathInput) pathInput.value = startPath;

    _loadBrowser(startPath, target);
}

async function _loadBrowser(path, targetOverride = getBrowserTarget()) {
    const list = _el("cb-browser-list");
    if (list) list.replaceChildren(el("div", { class: "cb-ib-loading" }, ["Loading..."]));
    try {
        const data = await browsePath(path);
        if (data.status !== "success") {
            if (getBrowserTarget() === targetOverride) {
                _updateCurrentPathDisplay(path || "");
            }
            if (list) list.replaceChildren(el("div", { class: "cb-ib-empty" }, [data.error || "Unable to browse path"]));
            return;
        }
        getBrowserPathByTarget()[targetOverride] = data.path;
        if (getBrowserTarget() === targetOverride) {
            setBrowserPath(data.path);
            _updateCurrentPathDisplay(data.path);
            const currentTargetVal = getBrowserTarget() === "input"
                ? _el("cb-input-path")?.value
                : _el("cb-output-path")?.value;
            renderBrowserEntries(data, getBrowserTarget(), currentTargetVal, _handleBrowserRow);
        }
    } catch (err) {
        if (list) list.replaceChildren(el("div", { class: "cb-ib-empty" }, [`Browse failed: ${err.message}`]));
    }
}

function _updateCurrentPathDisplay(path) {
    const display = _el("cb-io-current-path-display");
    if (display) {
        display.value = path || "";
        display.title = path || "";
    }
}

function _handleBrowserRow(row) {
    const action = row.dataset.action;
    const path = row.dataset.path;
    if (action === "open") { _loadBrowser(path); return; }
    if (action === "select-file" && getBrowserTarget() === "input") {
        _selectBrowserPath(path);
        document.querySelectorAll(".cb-browser-row").forEach(r => r.classList.remove("active"));
        row.classList.add("active");
    }
}

function _selectBrowserPath(path) {
    if (getBrowserTarget() === "input") {
        _el("cb-input-path").value = path;
        _el("cb-input-error").textContent = "";
    } else {
        _el("cb-output-path").value = path;
        _el("cb-output-error").textContent = "";
    }
    _el("cb-selected-path-val").textContent = path;
}

// ── Effective path helpers ─────────────────────────────────────────────────────
function getEffectiveInputPath() {
    return _el("cb-input-path")?.value.trim() ?? "";
}

function getEffectiveOutputDir() {
    return _el("cb-output-path")?.value.trim() || "./output";
}

// ── PROMPT tab log ─────────────────────────────────────────────────────────────
function _appendPromptLine(level, msg) {
    getPromptLines().push({ ts: _now(), level, msg });
    renderPromptLog(getPromptLines());
}

function showPromptLog() {
    const box = _el("cb-prompt-log");
    if (box) box.hidden = false;
}

function clearPromptLog() {
    setPromptLines([]);
    renderPromptLog(getPromptLines());
}

// ── Generate ───────────────────────────────────────────────────────────────────
async function triggerGeneration() {
    showPromptLog();
    clearPromptLog();

    const query = _el("cb-query")?.value.trim() ?? "";
    if (!query) {
        _appendPromptLine("ERROR", "Please enter a goal.");
        return;
    }

    const inputPath = getEffectiveInputPath();
    const outputDir = getEffectiveOutputDir();
    const provider  = getProvider();
    const model     = _el("cb-model")?.value ?? getModel();

    setGenerating(true);
    _el("cb-generate-btn").disabled = true;

    _appendPromptLine("INFO", `Provider: ${provider}  |  Model: ${model || "default"}`);
    _appendPromptLine("INFO", `Goal: ${query.slice(0, 100)}${query.length > 100 ? "…" : ""}`);

    try {
        const resp = await postGenerate({ query, input_path: inputPath, output_dir: outputDir, provider, model });

        if (!resp.ok) {
            throw new Error(`Server error: HTTP ${resp.status}`);
        }

        const reader  = resp.body.getReader();
        const decoder = new TextDecoder();
        let   buffer  = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                let event;
                try { event = JSON.parse(line.slice(6)); } catch { continue; }

                if (event.type === "log") {
                    const level = event.level === "ERROR" ? "ERROR"
                                : event.level === "WARN"  ? "WARN"
                                : "INFO";
                    _appendPromptLine(level, event.msg);
                } else if (event.type === "status") {
                    _appendPromptLine("INFO", event.msg);
                } else if (event.type === "error") {
                    _appendPromptLine("ERROR", `❌ ${event.msg}`);
                    setGenerating(false);
                    _el("cb-generate-btn").disabled = false;
                    return;
                } else if (event.type === "done") {
                    _appendPromptLine("INFO", `✅ ${event.msg}`);
                    try {
                        await app.loadGraphData(event.workflow);
                        const n = event.node_count ?? "?";
                        _appendPromptLine("INFO", `캔버스에 ${n}개 노드 로드 완료`);
                    } catch (loadErr) {
                        _appendPromptLine("ERROR", `캔버스 로드 실패: ${loadErr.message}`);
                    }
                    setGenerating(false);
                    _el("cb-generate-btn").disabled = false;
                    return;
                }
            }
        }

    } catch (err) {
        _appendPromptLine("ERROR", `생성 실패: ${err.message}`);
        setGenerating(false);
        _el("cb-generate-btn").disabled = false;
    }
}

// ── HTML ───────────────────────────────────────────────────────────────────────
const PANEL_HTML = `
<div class="cb-header">
  <button class="cb-dna-btn" id="cb-dna-btn" title="Minimize">🧬</button>
  <span class="cb-header-title">ComfyBIO</span>
</div>
<div class="cb-body">

  <div class="cb-tabs">
    <button class="cb-tab-btn active" data-tab="llm"    title="LLM Provider">LLM</button>
    <button class="cb-tab-btn"        data-tab="io"     title="Input / Output">I/O</button>
    <button class="cb-tab-btn"        data-tab="prompt" title="Prompt">RUN</button>
  </div>

  <div class="cb-right">
    <div class="cb-content">

      <!-- ── LLM tab ── -->
      <div class="cb-tab-pane" data-pane="llm" style="display:flex">
        <div>
          <label>Provider</label>
          <div class="cb-row">
            <select id="cb-provider" style="flex:1">
              <option value="claude">Claude</option>
              <option value="codex">Codex</option>
              <option value="gemini">Gemini</option>
              <option value="deterministic">Deterministic (Test)</option>
            </select>
            <span id="cb-provider-badge" class="cb-badge cb-badge-loading">…</span>
          </div>
        </div>

        <div>
          <label>Model</label>
          <select id="cb-model"><option value="">Loading…</option></select>
        </div>

        <div id="cb-llm-log"></div>
        <div id="cb-xterm-wrap"></div>
      </div>

      <!-- ── I/O tab ── -->
      <div class="cb-tab-pane" data-pane="io" style="display:none">

        <div class="cb-io-target-selector">
          <button class="cb-target-btn active cb-io-target" id="cb-io-target-input" data-target="input">Input</button>
          <button class="cb-target-btn cb-io-target" id="cb-io-target-output" data-target="output">Output</button>
        </div>

        <div class="cb-io-path-row">
          <input type="text" id="cb-io-current-path-display" style="flex:1;font-family:monospace;font-size:10px" placeholder="Path — Enter to navigate">
          <button class="cb-btn cb-btn-secondary" id="cb-browser-up">↑ Up</button>
        </div>

        <div id="cb-browser-list" class="cb-browser-list">
          <div class="cb-ib-loading">Loading…</div>
        </div>

        <div class="cb-io-selected-summary">
          <label id="cb-io-selected-label">Selected Input</label>
          <div id="cb-selected-path-val" class="cb-selected-path-val">Not selected</div>
          <input type="text" id="cb-input-path" style="display:none">
          <input type="text" id="cb-output-path" style="display:none">
          <div class="cb-io-error" id="cb-input-error"></div>
          <div class="cb-io-error" id="cb-output-error" style="display:none"></div>
        </div>

        <button class="cb-btn cb-btn-primary" id="cb-browser-select-current" style="width:100%">Apply Directory</button>
      </div>

      <!-- ── PROMPT tab ── -->
      <div class="cb-tab-pane" data-pane="prompt" style="display:none">
        <textarea id="cb-query"
          placeholder="e.g. Parse a FASTA file and calculate GC content&#10;&#10;Ctrl+Enter to run"></textarea>
        <button class="cb-btn cb-btn-generate" id="cb-generate-btn">▶ Generate Workflow</button>
        <div id="cb-prompt-log" hidden></div>
      </div>

    </div>
  </div>

</div>
`;

// ── Extension ──────────────────────────────────────────────────────────────────
app.registerExtension({
    name: "ComfyBIO.Panel",

    async setup() {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = new URL("./comfybio.css?v=" + Date.now(), import.meta.url).href;
        document.head.appendChild(link);

        const panel = document.createElement("div");
        panel.id = "cb-panel";
        panel.className = "cb-hidden";
        panel.innerHTML = PANEL_HTML;
        document.body.appendChild(panel);

        const toggler = document.createElement("button");
        toggler.id = "cb-toggler";
        toggler.textContent = "🧬";
        toggler.title = "Open ComfyBIO panel";
        document.body.appendChild(toggler);

        _applyTheme();
        setInterval(_applyTheme, 300);

        // Force overflow:hidden on all non-scrolling containers via inline style
        // so that any external CSS (ComfyUI) cannot override with overflow:auto
        [".cb-body", ".cb-tabs", ".cb-right", ".cb-content", ".cb-tab-pane", "#cb-llm-log"]
            .flatMap(sel => [...panel.querySelectorAll(sel)])
            .forEach(el => el.style.setProperty("overflow", "hidden", "important"));

        // ── Drag & Resize setup ───────────────────────────────────────────────
        makeDraggable(panel, panel.querySelector(".cb-header"), ".cb-dna-btn");
        makeResizable(panel);
        makeDraggable(toggler, toggler);

        // ── Panel toggle ──────────────────────────────────────────────────────
        toggler.addEventListener("click", () => {
            if (toggler._dragging) return;
            const tr  = toggler.getBoundingClientRect();
            const tcx = tr.left + tr.width  / 2;
            const tcy = tr.top  + tr.height / 2;
            const panelW = panel.offsetWidth || 380;

            panel.style.visibility = "hidden";
            panel.style.left = "0px";
            panel.style.top  = "0px";
            panel.style.right = "auto";
            panel.classList.remove("cb-hidden");

            const dr  = _el("cb-dna-btn").getBoundingClientRect();
            const pr  = panel.getBoundingClientRect();
            const dnaRelX = dr.left - pr.left + dr.width  / 2;
            const dnaRelY = dr.top  - pr.top  + dr.height / 2;

            panel.classList.add("cb-hidden");
            panel.style.visibility = "";

            let left = tcx - dnaRelX;
            let top  = tcy - dnaRelY;
            left = Math.max(8, Math.min(window.innerWidth  - panelW - 8, left));
            top  = Math.max(8, Math.min(window.innerHeight - 460 - 8, top));

            panel.style.left = left + "px";
            panel.style.top  = top  + "px";
            panel.classList.remove("cb-hidden");
            requestAnimationFrame(_fitPanelToViewport);
            toggler.style.display = "none";
        });

        function _collapsePanel(cx, cy) {
            const tw  = toggler.offsetWidth  || 42;
            const th  = toggler.offsetHeight || 42;
            let tLeft = Math.round(cx - tw / 2);
            let tTop  = Math.round(cy - th / 2);
            tLeft = Math.max(0, Math.min(window.innerWidth  - tw, tLeft));
            tTop  = Math.max(0, Math.min(window.innerHeight - th, tTop));
            toggler.style.left   = tLeft + "px";
            toggler.style.top    = tTop  + "px";
            toggler.style.right  = "auto";
            toggler.style.bottom = "auto";
            panel.classList.add("cb-hidden");
            toggler.style.display = "";
        }

        _el("cb-dna-btn").addEventListener("click", (e) => _collapsePanel(e.clientX, e.clientY));

        panel.querySelector(".cb-header").addEventListener("click", (e) => {
            if (panel._dragging) return;
            if (e.target.closest(".cb-dna-btn")) return;
            _collapsePanel(e.clientX, e.clientY);
        });

        // ── Tab buttons ───────────────────────────────────────────────────────
        document.querySelectorAll(".cb-tab-btn").forEach(btn =>
            btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

        // ── Provider / model ──────────────────────────────────────────────────
        _el("cb-provider").addEventListener("change", e => {
            setProvider(e.target.value);
            refreshProvider(getProvider());
        });
        _el("cb-model").addEventListener("change", e => {
            setModel(e.target.value);
            const cachedStatus = getCachedStatus(getProvider());
            if (cachedStatus) renderLLMLog(cachedStatus, _modelsData(), getProvider(), {
                onInstall: _triggerInstall,
                onLogin: _triggerLogin,
                onTestConnection: _triggerTestConnection
            });
        });

        // ── I/O Browser controls ──────────────────────────────────────────────
        document.querySelectorAll(".cb-io-target").forEach(btn =>
            btn.addEventListener("click", () => _setBrowserTarget(btn.dataset.target)));

        _el("cb-browser-up").addEventListener("click", async () => {
            const pathInput = _el("cb-io-current-path-display");
            const typedPath = pathInput?.value.trim() || "";
            if (typedPath && typedPath !== getBrowserPath()) {
                _loadBrowser(typedPath);
                return;
            }
            const data = await browsePath(getBrowserPath());
            if (data.parent) _loadBrowser(data.parent);
        });

        _el("cb-browser-select-current").addEventListener("click", () =>
            _selectBrowserPath(getBrowserPath()));

        // ── Path input navigation ─────────────────────────────────────────────
        const pathInput = _el("cb-io-current-path-display");
        if (pathInput) {
            pathInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    const typedPath = pathInput.value.trim();
                    if (typedPath) _loadBrowser(typedPath);
                }
            });
        }

        // ── Generate ──────────────────────────────────────────────────────────
        _el("cb-generate-btn").addEventListener("click", triggerGeneration);
        _el("cb-query").addEventListener("keydown", e => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                triggerGeneration();
            }
        });

        window.addEventListener("resize", () => requestAnimationFrame(_fitPanelToViewport));

        if (window.ResizeObserver) {
            const fitObserver = new ResizeObserver(() => requestAnimationFrame(_fitPanelToViewport));
            fitObserver.observe(panel);
            const content = panel.querySelector(".cb-content");
            if (content) fitObserver.observe(content);
        }

        // ── Init ──────────────────────────────────────────────────────────────
        fetchDefaultPaths().then(data => {
            setInputPath(data.input_dir || "");
            setOutputDir(data.output_dir || "./output");
            getQuickPaths().input = getInputPath();
            getQuickPaths().output = getOutputDir();
            getQuickPaths().home = data.home_dir || getInputPath() || "/";
            getBrowserPathByTarget().input = getInputPath() || "";
            getBrowserPathByTarget().output = getOutputDir() || "";

            const elOutput = _el("cb-output-path");
            if (elOutput) elOutput.value = getOutputDir();
            setBrowserPath(getInputPath());
            _loadBrowser(getInputPath());
        }).catch(() => {
            _loadBrowser("");
        });

        refreshProvider(getProvider());
        requestAnimationFrame(_fitPanelToViewport);
        setTimeout(_fitPanelToViewport, 0);
    },
});

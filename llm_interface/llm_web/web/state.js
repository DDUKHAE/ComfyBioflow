// ── Centralized state module ───────────────────────────────────────────────────
// Single source of truth for all UI state. No pub/sub — just plain getters/setters.

const _data = {
    provider: "claude",
    model: "",
    models: [],
    inputPath: "",
    outputDir: "",
    activeTab: "llm",
    browserTarget: "input",
    browserPath: "",
    browserPathByTarget: { input: "", output: "" },
    quickPaths: { home: "", root: "/", input: "", output: "" },
    generating: false,
    promptLines: [],
    // Status cache: provider → { data, ts }
    statusCache: {},
};

export const STATUS_TTL_MS = 30_000;

// ── provider ──────────────────────────────────────────────────────────────────
export function getProvider() { return _data.provider; }
export function setProvider(v) { _data.provider = v; }

// ── model ─────────────────────────────────────────────────────────────────────
export function getModel() { return _data.model; }
export function setModel(v) { _data.model = v; }

// ── models ────────────────────────────────────────────────────────────────────
export function getModels() { return _data.models; }
export function setModels(v) { _data.models = v; }

// ── inputPath ─────────────────────────────────────────────────────────────────
export function getInputPath() { return _data.inputPath; }
export function setInputPath(v) { _data.inputPath = v; }

// ── outputDir ─────────────────────────────────────────────────────────────────
export function getOutputDir() { return _data.outputDir; }
export function setOutputDir(v) { _data.outputDir = v; }

// ── activeTab ─────────────────────────────────────────────────────────────────
export function getActiveTab() { return _data.activeTab; }
export function setActiveTab(v) { _data.activeTab = v; }

// ── browserTarget ─────────────────────────────────────────────────────────────
export function getBrowserTarget() { return _data.browserTarget; }
export function setBrowserTarget(v) { _data.browserTarget = v; }

// ── browserPath ───────────────────────────────────────────────────────────────
export function getBrowserPath() { return _data.browserPath; }
export function setBrowserPath(v) { _data.browserPath = v; }

// ── browserPathByTarget ───────────────────────────────────────────────────────
export function getBrowserPathByTarget() { return _data.browserPathByTarget; }
export function setBrowserPathByTarget(v) { _data.browserPathByTarget = v; }

// ── quickPaths ────────────────────────────────────────────────────────────────
export function getQuickPaths() { return _data.quickPaths; }
export function setQuickPaths(v) { _data.quickPaths = v; }

// ── generating ────────────────────────────────────────────────────────────────
export function getGenerating() { return _data.generating; }
export function setGenerating(v) { _data.generating = v; }

// ── promptLines ───────────────────────────────────────────────────────────────
export function getPromptLines() { return _data.promptLines; }
export function setPromptLines(v) { _data.promptLines = v; }

// ── Status cache API ──────────────────────────────────────────────────────────
export function getCachedStatus(provider) {
    const hit = _data.statusCache[provider];
    if (hit && Date.now() - hit.ts < STATUS_TTL_MS) return hit.data;
    return null;
}

export function setCachedStatus(provider, data) {
    _data.statusCache[provider] = { data, ts: Date.now() };
}

export function invalidateCachedStatus(provider) {
    delete _data.statusCache[provider];
}

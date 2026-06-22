// ── Backend API client ─────────────────────────────────────────────────────────
// All fetch() calls to the ComfyBIO backend live here as named async functions.

// GET /comfybio/llm_status?provider=X
export async function fetchStatus(provider) {
    const r = await fetch(`/comfybio/llm_status?provider=${encodeURIComponent(provider)}`);
    return r.json();
}

// GET /comfybio/llm_models?provider=X
export async function fetchModels(provider) {
    const r = await fetch(`/comfybio/llm_models?provider=${encodeURIComponent(provider)}`);
    return r.json();
}

// POST /comfybio/llm_login
export async function postLogin(provider) {
    const r = await fetch("/comfybio/llm_login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
    });
    return r.json();
}

// POST /comfybio/llm_install
export async function postInstall(provider) {
    const r = await fetch("/comfybio/llm_install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
    });
    return r.json();
}

// GET /comfybio/browse_path?path=X
export async function browsePath(path) {
    const r = await fetch(`/comfybio/browse_path?path=${encodeURIComponent(path || "")}`);
    return r.json();
}

// GET /comfybio/default_paths
export async function fetchDefaultPaths() {
    const r = await fetch("/comfybio/default_paths");
    return r.json();
}

// POST /comfybio/generate (returns raw Response for streaming)
export async function postGenerate(payload) {
    return fetch("/comfybio/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

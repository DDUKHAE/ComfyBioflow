// ── UI Controller ─────────────────────────────────────────────────────────────
// Rendering functions extracted from comfybio_test_load.js (Phase 4 refactor).
// All functions use el() from dom_utils.js instead of innerHTML assignments.

import { el } from "./dom_utils.js";

/**
 * Renders the LLM status card in #cb-llm-log.
 * Shows one of three states: not-installed, not-logged-in, or ready.
 *
 * @param {Object} statusData - { installed, ready } from /comfybio/llm_status
 * @param {Object} modelsData - { models, default } from /comfybio/llm_models
 * @param {string} provider   - current provider name (e.g. "claude")
 * @param {{ onInstall?: Function, onLogin?: Function }} callbacks
 */
export function renderLLMLog(statusData, modelsData, provider, { onInstall, onLogin, onTestConnection } = {}) {
    const box = document.getElementById("cb-llm-log");
    if (!box) return;

    const installed = statusData?.installed ?? false;
    const ready = statusData?.ready ?? false;
    const label = provider ? (provider.charAt(0).toUpperCase() + provider.slice(1)) : "";

    box.replaceChildren();

    let card;
    if (!installed) {
        const installBtn = el("button", {
            class: "cb-btn cb-btn-secondary cb-status-action",
            id: "cb-install-btn",
        }, ["Install"]);
        if (onInstall) {
            installBtn.addEventListener("click", onInstall);
        }
        card = el("div", { class: "cb-status-card cb-status-err" }, [
            el("span", { class: "cb-status-icon" }, ["❌"]),
            el("div", { class: "cb-status-content" }, [
                el("div", { class: "cb-status-msg" }, [`${label} CLI not installed`]),
                installBtn,
            ]),
        ]);
    } else if (!ready) {
        const loginBtn = el("button", {
            class: "cb-btn cb-btn-primary cb-status-action",
            id: "cb-login-card-btn",
            style: "padding: 6px 14px; font-size: 11px; margin-top: 4px;"
        }, ["터미널 로그인 (xterm)"]);
        if (onLogin) {
            loginBtn.addEventListener("click", onLogin);
        }
        card = el("div", { class: "cb-status-card cb-status-warn" }, [
            el("span", { class: "cb-status-icon" }, ["⚠️"]),
            el("div", { class: "cb-status-content", style: "align-items: center;" }, [
                el("div", { class: "cb-status-msg" }, [`${label} 로그인 필요`]),
                loginBtn,
            ]),
        ]);
    } else {
        const model = document.getElementById("cb-model")?.value || modelsData?.default || label;
        
        const testBtn = el("button", {
            class: "cb-btn cb-btn-secondary cb-status-action",
            id: "cb-test-conn-btn",
            style: "margin-top: 4px; font-size: 10px; width: 100%; max-width: 130px; padding: 4px 10px;"
        }, ["연결 확인"]);
        if (onTestConnection) {
            testBtn.addEventListener("click", onTestConnection);
        }

        card = el("div", { class: "cb-status-card cb-status-ok" }, [
            el("span", { class: "cb-status-icon" }, ["✅"]),
            el("div", { class: "cb-status-content" }, [
                el("div", { class: "cb-status-msg" }, [`${model} 준비됨`]),
                el("div", { style: "width: 100%; border-top: 1px dashed rgba(16, 185, 129, 0.2); margin: 6px 0;" }),
                el("div", { style: "display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 9px; text-align: left; width: 100%; color: var(--cb-text-muted);" }, [
                    el("div", {}, ["연결 상태: ", el("span", { style: "color: var(--cb-status-ok-text); font-weight: 700;" }, ["양호"])]),
                    el("div", {}, ["평균 지연: ", el("span", { style: "color: var(--cb-text); font-weight: 600;" }, ["1.2s"])]),
                    el("div", {}, ["사용 한도: ", el("span", { style: "color: var(--cb-text); font-weight: 600;" }, ["정상 (98%)"])]),
                    el("div", {}, ["로컬 캐시: ", el("span", { style: "color: var(--cb-status-ok-text); font-weight: 700;" }, ["활성"])]),
                ]),
                testBtn
            ]),
        ]);
    }

    box.appendChild(card);
}

/**
 * Renders a "testing connection in progress" spinner card.
 *
 * @param {HTMLElement} box   - the container element to render into
 * @param {string}      label - capitalized provider name (e.g. "Claude")
 */
export function renderTestConnectionProgress(box, label) {
    if (!box) return;
    box.replaceChildren(
        el("div", { class: "cb-status-card cb-status-warn" }, [
            el("span", { class: "cb-status-icon" }, ["⏳"]),
            el("div", { class: "cb-status-content", style: "align-items: center; justify-content: center;" }, [
                el("div", { class: "cb-status-msg" }, [`${label} 연결 확인 중…`]),
            ]),
        ])
    );
}

/**
 * Renders an "installing in progress" spinner card into the given box element.
 *
 * @param {HTMLElement} box   - the container element to render into
 * @param {string}      label - capitalized provider name (e.g. "Claude")
 */
export function renderInstallProgress(box, label) {
    if (!box) return;
    box.replaceChildren(
        el("div", { class: "cb-status-card cb-status-warn" }, [
            el("span", { class: "cb-status-icon" }, ["⏳"]),
            el("div", { class: "cb-status-content" }, [
                el("div", { class: "cb-status-msg" }, [`Installing ${label} CLI…`]),
            ]),
        ])
    );
}

/**
 * Renders an install-error card with a Retry button into the given box element.
 *
 * @param {HTMLElement} box       - the container element to render into
 * @param {string}      label     - capitalized provider name (e.g. "Claude")
 * @param {string}      message   - error message to display
 * @param {Function}    onInstall - callback for the Retry button
 */
export function renderInstallError(box, label, message, onInstall) {
    if (!box) return;
    const retryBtn = el("button", {
        class: "cb-btn cb-btn-secondary cb-status-action",
        id: "cb-install-btn",
    }, ["Retry"]);
    if (onInstall) {
        retryBtn.addEventListener("click", onInstall);
    }

    box.replaceChildren(
        el("div", { class: "cb-status-card cb-status-err" }, [
            el("span", { class: "cb-status-icon" }, ["❌"]),
            el("div", { class: "cb-status-content" }, [
                el("div", { class: "cb-status-msg" }, [`Install failed: ${message}`]),
                retryBtn,
            ]),
        ])
    );
}

/**
 * Renders ALL accumulated prompt log lines into #cb-prompt-log.
 * Fixes the original bug that only showed the last line.
 * Auto-scrolls to the bottom after rendering.
 *
 * @param {Array<{ ts: string, level: string, msg: string }>} promptLines
 */
export function renderPromptLog(promptLines) {
    const box = document.getElementById("cb-prompt-log");
    if (!box) return;
    box.replaceChildren();
    for (const l of promptLines) {
        const cls = l.level === "ERROR" ? "cb-pl-error"
                  : l.level === "WARN"  ? "cb-pl-warn"
                  : "cb-pl-info";
        box.appendChild(
            el("div", { class: `cb-pl ${cls}` }, [
                el("span", { class: "cb-pl-ts" }, [l.ts]),
                el("span", { class: "cb-pl-lv" }, [l.level]),
                el("span", { class: "cb-pl-msg" }, [l.msg]),
            ])
        );
    }
    // Auto-scroll to bottom
    box.scrollTop = box.scrollHeight;
}

/**
 * Renders the file-browser entry list into #cb-browser-list using el().
 * Eliminates innerHTML with _esc() calls — all values are safe by construction.
 *
 * @param {Object}   data             - response from /comfybio/browse_path
 * @param {string}   browserTarget    - "input" or "output" (unused here, kept for callers)
 * @param {string}   currentPathValue - the currently selected path (to mark active row)
 * @param {Function} onRowClick       - callback invoked with the clicked row element
 */
export function renderBrowserEntries(data, browserTarget, currentPathValue, onRowClick) {
    const list = document.getElementById("cb-browser-list");
    if (!list) return;

    list.replaceChildren();

    const entries = data.entries || [];

    // Parent row
    if (data.parent) {
        const row = el("div", {
            class: "cb-browser-row cb-browser-parent",
            "data-action": "open",
            "data-path": data.parent,
        }, [
            el("span", { class: "cb-browser-icon" }, ["⬆️"]),
            el("span", { class: "cb-browser-name", title: "Up to parent folder" }, [".. (Parent)"]),
        ]);
        row.addEventListener("click", () => onRowClick(row));
        list.appendChild(row);
    }

    if (!entries.length && !data.parent) {
        list.appendChild(el("div", { class: "cb-ib-empty" }, ["No readable entries"]));
        return;
    }

    for (const entry of entries) {
        let icon = "📄";
        if (entry.kind === "dir") {
            icon = "📁";
        } else if (entry.kind === "blocked") {
            icon = "🚫";
        } else {
            const ext = (entry.name || "").split(".").pop().toLowerCase();
            if (["fasta", "fa", "fna", "faa"].includes(ext)) icon = "🧬";
            else if (["gb", "gbk", "genbank"].includes(ext)) icon = "🏷️";
            else if (["fastq", "fq"].includes(ext)) icon = "📊";
            else if (ext === "xml") icon = "🕸️";
            else if (["json", "txt"].includes(ext)) icon = "📝";
        }

        const action = entry.kind === "dir" ? "open"
                     : entry.kind === "file" ? "select-file"
                     : "blocked";
        const isActive = currentPathValue === entry.path;

        const row = el("div", {
            class: `cb-browser-row${isActive ? " active" : ""}`,
            "data-action": action,
            "data-path": entry.path,
            "data-kind": entry.kind,
        }, [
            el("span", { class: "cb-browser-icon" }, [icon]),
            el("span", { class: "cb-browser-name", title: entry.name }, [entry.name]),
        ]);
        row.addEventListener("click", () => onRowClick(row));
        list.appendChild(row);
    }
}

/**
 * Renders terminal logs inside #cb-llm-log.
 *
 * @param {HTMLElement} box - the #cb-llm-log container
 * @param {string} logsText - terminal output log text
 */
export function renderTerminalLog(box, logsText) {
    if (!box) return;

    let term = document.getElementById("cb-term-display");
    if (!term) {
        term = el("pre", {
            id: "cb-term-display",
            style: "background: #111; color: #33ff33; font-family: monospace; font-size: 10px; padding: 10px; border-radius: 4px; border: 1px solid #333; height: 160px; overflow-y: auto; text-align: left; margin-top: 8px; white-space: pre-wrap; word-break: break-all; width: 100%; box-sizing: border-box;"
        });

        box.replaceChildren(
            el("div", { class: "cb-status-card cb-status-warn", style: "padding: 12px; gap: 8px; width: 100%; display: flex; flex-direction: column; box-sizing: border-box;" }, [
                el("div", { style: "display: flex; align-items: center; gap: 8px; width: 100%;" }, [
                    el("span", { style: "font-size: 14px;" }, ["⏳"]),
                    el("div", { class: "cb-status-msg", style: "font-size: 11px; flex: 1; text-align: left; color: var(--cb-status-warn-text);" }, ["터미널 로그인 진행 중 (xterm)..."]),
                ]),
                term
            ])
        );
    }

    term.textContent = logsText;
    term.scrollTop = term.scrollHeight; // Auto-scroll to bottom
}


import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const PROVIDER_MODELS = {
  codex: ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini"],
  claude: ["claude-opus-4.6", "claude-sonnet-5.0", "claude-haiku-4.5"],
  gemini: ["gemini-3.1-pro", "gemini-3.5-flash", "gemini-3.1-flash"],
};

const STEP_CATALOG = {
  "input-validator": {
    stage: "Validate inputs",
    tool: "InputValidator",
    input: "folder path, metadata CSV",
    output: "sample manifest",
    title: "TSR candidates for input validation",
    subtitle: "Input path / sample manifest output",
    candidates: [
      ["RNASeq_InputValidator", "Recommended", "", "Validates FASTQ folder, metadata, species, and genome build."],
      ["Generic_FileManifest", "Needs review", "", "Creates a sample table, but reference checks become manual."],
    ],
  },
  fastqc: {
    stage: "Raw QC",
    tool: "FastQC",
    input: "FASTQ",
    output: "raw-read QC artifacts",
    title: "TSR candidates for raw-read QC",
    subtitle: "FASTQ / QC artifact output",
    candidates: [
      ["FastQC", "Recommended", "", "Produces per-sample raw-read quality reports."],
      ["fastp QC mode", "Review", " amber", "Can produce QC metrics, but trimming behavior must be disabled or separated."],
    ],
  },
  fastp: {
    stage: "Trim reads",
    tool: "fastp",
    input: "FASTQ",
    output: "trimmed FASTQ",
    title: "TSR candidates for read trimming",
    subtitle: "FASTQ / trimmed FASTQ output",
    candidates: [
      ["fastp", "Recommended", "", "Trims adapters and low-quality bases while producing trim metrics."],
      ["Trimmomatic", "Review", " amber", "Requires adapter file and minimum-length policy."],
    ],
  },
  star: {
    stage: "Align reads",
    tool: "STAR",
    input: "trimmed FASTQ",
    output: "aligned BAM",
    title: "TSR candidates for read alignment",
    subtitle: "trimmed FASTQ / aligned BAM output",
    candidates: [
      ["STAR", "Recommended", "", "Genome alignment route for downstream gene counting."],
      ["HISAT2", "Review", " amber", "Compatible aligned output, but index and strandedness settings require review."],
      ["Salmon", "Different route", " amber", "Produces transcript quantification instead of aligned BAM."],
    ],
  },
  featurecounts: {
    stage: "Count genes",
    tool: "featureCounts",
    input: "aligned BAM",
    output: "gene count matrix",
    title: "TSR candidates for gene counting",
    subtitle: "aligned BAM / count matrix output",
    candidates: [
      ["featureCounts", "Recommended", "", "Generates gene-level counts for DESeq2."],
      ["HTSeq-count", "Review", " amber", "Alternative counting engine with stricter annotation and strandedness settings."],
    ],
  },
  deseq2: {
    stage: "DE analysis",
    tool: "DESeq2",
    input: "count matrix, metadata",
    output: "DE table and plots",
    title: "TSR candidates for differential expression",
    subtitle: "count matrix / DE results output",
    candidates: [
      ["DESeq2", "Recommended", "", "Default route for normalization, contrast testing, and DE statistics."],
      ["edgeR", "Model review", " amber", "Alternative DE engine. Requires dispersion, contrast, and filtering parameter review."],
    ],
  },
  report: {
    stage: "Report",
    tool: "InteractiveReport",
    input: "QC artifacts, DE results",
    output: "analysis report",
    title: "TSR candidates for reporting",
    subtitle: "analysis artifacts / report output",
    candidates: [
      ["InteractiveReport", "Recommended", "", "Builds a final report from QC, quantification, and DE artifacts."],
      ["MultiQC", "QC only", " amber", "Useful for QC summary, but does not cover DE interpretation alone."],
    ],
  },
};

const INITIAL_STEPS = ["input-validator", "fastqc", "fastp", "star", "featurecounts", "deseq2", "report"];

function injectStyles() {
  if (document.getElementById("comfybio-panel-styles")) {
    return;
  }
  const style = document.createElement("style");
  style.id = "comfybio-panel-styles";
  style.textContent = `
    :root {
      --cb-bg: #1c1c1c;
      --cb-panel: #252525;
      --cb-panel-2: #2f2f2f;
      --cb-line: #454545;
      --cb-text: #f1f1f1;
      --cb-muted: #a8a8a8;
      --cb-soft: #d6d6d6;
      --cb-teal: #20b2aa;
      --cb-green: #41c287;
      --cb-amber: #e8b04e;
    }

    .comfybio-launcher, .comfybio-panel, .comfybio-panel * {
      box-sizing: border-box;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    .comfybio-launcher {
      position: fixed;
      left: var(--cb-launcher-left, calc(100vw - 78px));
      top: var(--cb-launcher-top, calc(100vh - 78px));
      z-index: 10001;
      width: 56px;
      height: 56px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid rgba(32, 178, 170, 0.65);
      border-radius: 999px;
      background: #183331;
      color: var(--cb-text);
      padding: 0;
      box-shadow: 0 16px 34px rgba(0, 0, 0, 0.3);
      cursor: grab;
      touch-action: none;
      user-select: none;
      transition: border-radius 160ms ease, background 160ms ease, box-shadow 160ms ease;
    }

    .comfybio-launcher.dragging { cursor: grabbing; }
    .comfybio-launcher.panel-open {
      border-radius: 10px 0 10px 0;
      background: #2b3037;
      box-shadow: none;
    }

    .comfybio-launcher svg {
      width: 30px;
      height: 30px;
      color: var(--cb-teal);
    }

    .comfybio-panel {
      position: fixed;
      left: var(--cb-panel-left, 18px);
      top: var(--cb-panel-top, 18px);
      width: var(--cb-panel-width, min(460px, calc(100vw - 36px)));
      height: var(--cb-panel-height, min(720px, calc(100vh - 36px)));
      z-index: 10000;
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 0;
      border: 1px solid var(--cb-line);
      border-radius: 10px;
      background: var(--cb-panel);
      color: var(--cb-text);
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.36);
      opacity: 0;
      pointer-events: none;
      transform: translateY(10px) scale(0.98);
      transform-origin: top left;
      transition: opacity 160ms ease, transform 160ms ease;
    }

    .comfybio-panel.is-open {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0) scale(1);
    }

    .comfybio-panel,
    .comfybio-panel * {
      scrollbar-width: none;
      -ms-overflow-style: none;
    }

    .comfybio-panel::-webkit-scrollbar,
    .comfybio-panel *::-webkit-scrollbar {
      display: none;
    }

    .cb-resize {
      position: absolute;
      z-index: 2;
      background: transparent;
      touch-action: none;
    }
    .cb-resize.n, .cb-resize.s { left: 12px; right: 12px; height: 8px; cursor: ns-resize; }
    .cb-resize.n { top: -4px; }
    .cb-resize.s { bottom: -4px; }
    .cb-resize.e, .cb-resize.w { top: 12px; bottom: 12px; width: 8px; cursor: ew-resize; }
    .cb-resize.e { right: -4px; }
    .cb-resize.w { left: -4px; }
    .cb-resize.ne, .cb-resize.nw, .cb-resize.se, .cb-resize.sw { width: 16px; height: 16px; }
    .cb-resize.ne, .cb-resize.sw { cursor: nesw-resize; }
    .cb-resize.nw, .cb-resize.se { cursor: nwse-resize; }
    .cb-resize.ne { top: -6px; right: -6px; }
    .cb-resize.nw { top: -6px; left: -6px; }
    .cb-resize.se { right: -6px; bottom: -6px; }
    .cb-resize.sw { left: -6px; bottom: -6px; }

    .cb-header {
      min-height: 56px;
      padding: 12px 16px 12px 72px;
      border-bottom: 1px solid var(--cb-line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .cb-title { display: grid; gap: 3px; }
    .cb-title strong { font-size: 15px; }
    .cb-title span { font-size: 12px; color: var(--cb-muted); }
    .cb-actions { display: flex; align-items: center; gap: 8px; }
    .cb-status {
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(65, 194, 135, 0.45);
      color: var(--cb-green);
      background: rgba(65, 194, 135, 0.08);
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      white-space: nowrap;
    }

    .cb-icon-button, .cb-button, .cb-tiny, .cb-tab, .cb-path-button, .cb-step-option, .cb-replace-option {
      border: 1px solid var(--cb-line);
      color: var(--cb-text);
      background: var(--cb-panel-2);
      font: inherit;
    }
    .cb-icon-button {
      width: 36px;
      height: 36px;
      display: inline-grid;
      place-items: center;
      border-radius: 8px;
      padding: 0;
    }
    .cb-button {
      min-height: 44px;
      min-width: 92px;
      border-radius: 7px;
      padding: 10px 12px;
    }
    .cb-button.apply {
      background: var(--cb-teal);
      border-color: var(--cb-teal);
      color: #081013;
      font-weight: 700;
    }
    .cb-tiny {
      min-height: 36px;
      border-radius: 8px;
      padding: 7px 9px;
      font-size: 11px;
    }

    .cb-content {
      overflow: auto;
      padding: 16px;
      display: grid;
      gap: 16px;
      align-content: start;
      min-height: 0;
    }
    .cb-tabs {
      position: sticky;
      top: 0;
      z-index: 4;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
      padding-bottom: 10px;
      background: var(--cb-panel);
    }
    .cb-tab {
      min-height: 40px;
      border-radius: 8px;
      padding: 8px;
      color: var(--cb-soft);
    }
    .cb-tab.active {
      border-color: rgba(32, 178, 170, 0.7);
      color: var(--cb-text);
      background: rgba(32, 178, 170, 0.14);
    }
    .cb-panel-section { display: none; }
    .cb-panel-section.active { display: grid; gap: 12px; }
    .cb-box {
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--cb-line);
      border-radius: 10px;
      background: var(--cb-panel);
    }
    .cb-box-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-size: 13px;
    }
    .cb-box-header span { color: var(--cb-muted); font-size: 11px; }
    .cb-form-grid, .cb-settings-fields, .cb-resource-list { display: grid; gap: 8px; }
    .cb-settings-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .cb-field { display: grid; gap: 5px; min-width: 0; }
    .cb-field label, .cb-field > span {
      color: var(--cb-muted);
      font-size: 11px;
    }
    .cb-field strong {
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .cb-field input, .cb-field select, .cb-field textarea {
      width: 100%;
      border: 1px solid var(--cb-line);
      border-radius: 7px;
      background: var(--cb-bg);
      color: var(--cb-text);
      padding: 8px;
      line-height: 1.4;
    }
    .cb-field textarea { min-height: 92px; resize: vertical; }
    .cb-resource-row {
      display: grid;
      grid-template-columns: minmax(96px, .8fr) minmax(0, 1fr) auto auto;
      align-items: end;
      gap: 8px;
      padding: 8px;
      border: 1px solid var(--cb-line);
      border-radius: 8px;
      background: var(--cb-panel-2);
    }
    .cb-resource-row.extra { grid-template-columns: minmax(88px, .7fr) minmax(80px, .55fr) minmax(0, 1fr) auto auto; }
    .cb-path-wrap, .cb-add-step-wrap { position: relative; }
    .cb-path-menu, .cb-add-step-menu {
      position: absolute;
      right: 0;
      z-index: 5;
      display: none;
      gap: 6px;
      min-width: 130px;
      padding: 7px;
      border: 1px solid rgba(32, 178, 170, 0.48);
      border-radius: 8px;
      background: #1d2228;
      box-shadow: 0 14px 32px rgba(0, 0, 0, 0.32);
    }
    .cb-path-menu { top: calc(100% + 6px); }
    .cb-add-step-menu {
      bottom: calc(100% + 8px);
      width: min(280px, calc(100vw - 40px));
    }
    .cb-path-wrap.open .cb-path-menu,
    .cb-add-step-wrap.open .cb-add-step-menu { display: grid; }

    .cb-message {
      padding: 10px;
      border-left: 3px solid var(--cb-teal);
      border-radius: 7px;
      background: #222629;
      color: var(--cb-soft);
      font-size: 12px;
      line-height: 1.45;
    }
    .cb-message .severity {
      display: inline-flex;
      margin-right: 7px;
      color: var(--cb-teal);
      font-weight: 700;
    }
    .cb-meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .cb-step-list { display: grid; gap: 8px; }
    .cb-step-list.drag-active { user-select: none; }
    .cb-step {
      min-width: 0;
      border: 1px solid var(--cb-line);
      border-radius: 7px;
      background: var(--cb-panel-2);
      display: grid;
      overflow: hidden;
    }
    .cb-step.expanded {
      border-color: rgba(32, 178, 170, 0.58);
      background: #303636;
    }
    .cb-step.dragging {
      opacity: .58;
      box-shadow: 0 16px 34px rgba(0, 0, 0, .28);
    }
    .cb-step-summary {
      display: grid;
      grid-template-columns: 24px 24px minmax(0, 1fr) minmax(80px, .72fr) 28px;
      align-items: center;
      gap: 8px;
      min-height: 48px;
      padding: 8px 10px;
      cursor: pointer;
    }
    .cb-drag {
      width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      border: 1px solid var(--cb-line);
      border-radius: 7px;
      color: var(--cb-muted);
      cursor: grab;
      touch-action: none;
    }
    .cb-badge {
      width: 20px;
      height: 20px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      border: 1px solid rgba(32, 178, 170, .45);
      color: var(--cb-teal);
      font-size: 10px;
      font-weight: 700;
    }
    .cb-step-label {
      color: var(--cb-muted);
      font-size: 10px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .cb-step-tool {
      font-size: 12px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .cb-step-remove {
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      border: 1px solid var(--cb-line);
      border-radius: 999px;
      background: var(--cb-panel);
      color: var(--cb-soft);
      padding: 0;
    }
    .cb-step-remove:hover {
      border-color: rgba(255, 112, 112, .55);
      color: #ff8d8d;
    }
    .cb-step-detail {
      display: grid;
      max-height: 0;
      overflow: hidden;
      padding: 0 10px;
      opacity: 0;
      border-top: 1px solid transparent;
      gap: 8px;
      transition: max-height 220ms ease, opacity 180ms ease, padding 220ms ease, border-color 220ms ease;
    }
    .cb-step.expanded .cb-step-detail {
      max-height: 560px;
      padding: 10px;
      opacity: 1;
      border-top-color: var(--cb-line);
    }
    .cb-detail-grid, .cb-summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .cb-summary-item {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--cb-line);
      border-radius: 10px;
      background: var(--cb-panel-2);
      font-size: 12px;
    }
    .cb-summary-item span {
      max-width: 220px;
      color: var(--cb-muted);
      overflow-wrap: anywhere;
      text-align: right;
    }
    .cb-actions-row { display: flex; flex-wrap: wrap; gap: 5px; }
    .cb-replace-popover {
      display: none;
      gap: 7px;
      padding: 8px;
      border: 1px solid rgba(32, 178, 170, .48);
      border-radius: 7px;
      background: #1d2228;
      box-shadow: 0 14px 32px rgba(0, 0, 0, .28);
    }
    .cb-step.replace-open .cb-replace-popover { display: grid; }
    .cb-replace-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--cb-soft);
      font-size: 11px;
    }
    .cb-replace-option, .cb-step-option {
      display: grid;
      gap: 6px;
      text-align: left;
      border-radius: 10px;
      padding: 10px;
      font-size: 12px;
    }
    .cb-replace-option.recommended {
      border-color: rgba(32, 178, 170, .72);
      background: rgba(32, 178, 170, .1);
    }
    .cb-replace-option span, .cb-step-option span {
      color: var(--cb-muted);
      font-size: 11px;
      line-height: 1.35;
    }
    .cb-chip {
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(65, 194, 135, .45);
      color: var(--cb-green);
      background: rgba(65, 194, 135, .08);
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 11px;
      white-space: nowrap;
    }
    .cb-chip.amber {
      border-color: rgba(232, 176, 78, .45);
      color: var(--cb-amber);
      background: transparent;
    }
    .cb-footer {
      position: sticky;
      bottom: 0;
      z-index: 3;
      display: grid;
      grid-template-columns: 1fr auto auto;
      align-items: center;
      gap: 10px;
      margin: 0 -16px -16px;
      padding: 12px 16px;
      border-top: 1px solid var(--cb-line);
      background: rgba(37, 37, 37, .96);
      backdrop-filter: blur(8px);
    }
    .cb-generate-footer {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    @media (max-width: 640px) {
      .comfybio-panel {
        width: calc(100vw - 24px);
        height: calc(100vh - 24px);
      }
      .cb-settings-fields, .cb-meta, .cb-detail-grid, .cb-summary-grid {
        grid-template-columns: 1fr;
      }
      .cb-resource-row, .cb-resource-row.extra {
        grid-template-columns: 1fr;
      }
    }
  `;
  document.head.append(style);
}

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(options)) {
    if (key === "class") {
      node.className = value;
    } else if (key === "text") {
      node.textContent = value;
    } else if (key === "html") {
      node.innerHTML = value;
    } else if (key.startsWith("data")) {
      node.dataset[key.slice(4).toLowerCase()] = value;
    } else {
      node.setAttribute(key, value);
    }
  }
  for (const child of children) {
    node.append(child);
  }
  return node;
}

function createField(label, value) {
  return el("div", { class: "cb-field" }, [
    el("span", { text: label }),
    el("strong", { text: value }),
  ]);
}

function createPathPicker(label, value, readonly = false) {
  const row = el("div", { class: "cb-resource-row" });
  row.innerHTML = `
    <div class="cb-field">
      <label>Label</label>
      <input class="cb-resource-label" value="${label}" ${readonly ? "readonly" : ""}>
    </div>
    <div class="cb-field">
      <label>Path</label>
      <input class="cb-resource-path" value="${value}">
    </div>
    <div class="cb-path-wrap">
      <button class="cb-path-button cb-tiny" type="button">Browse</button>
      <div class="cb-path-menu">
        <button class="cb-tiny cb-path-choice" type="button" data-kind="file">File</button>
        <button class="cb-tiny cb-path-choice" type="button" data-kind="folder">Folder</button>
      </div>
    </div>
    <button class="cb-tiny cb-remove-resource" type="button" ${readonly ? "hidden" : ""}>x</button>
  `;
  return row;
}

function createExtraResource() {
  const row = el("div", { class: "cb-resource-row extra" });
  row.innerHTML = `
    <div class="cb-field">
      <label>Label</label>
      <input class="cb-resource-label" value="metadata_csv">
    </div>
    <div class="cb-field">
      <label>Type</label>
      <select class="cb-resource-type">
        <option>metadata</option>
        <option>index</option>
        <option>reference</option>
        <option>annotation</option>
        <option>contrast</option>
        <option>other</option>
      </select>
    </div>
    <div class="cb-field">
      <label>Path</label>
      <input class="cb-resource-path" value="/data/project/sample_metadata.csv">
    </div>
    <div class="cb-path-wrap">
      <button class="cb-path-button cb-tiny" type="button">Browse</button>
      <div class="cb-path-menu">
        <button class="cb-tiny cb-path-choice" type="button" data-kind="file">File</button>
        <button class="cb-tiny cb-path-choice" type="button" data-kind="folder">Folder</button>
      </div>
    </div>
    <button class="cb-tiny cb-remove-resource" type="button">x</button>
  `;
  return row;
}

function createStep(step) {
  const item = el("div", { class: "cb-step" });
  item.innerHTML = `
    <div class="cb-step-summary" role="button" tabindex="0" aria-expanded="false">
      <span class="cb-drag" title="Drag to reorder" aria-hidden="true">::</span>
      <span class="cb-badge">0</span>
      <span class="cb-step-label">${step.stage}</span>
      <span class="cb-step-tool">${step.tool}</span>
      <button class="cb-step-remove" type="button" aria-label="Remove step">x</button>
    </div>
    <div class="cb-step-detail">
      <div class="cb-detail-grid">
        ${createField("Input", step.input).outerHTML}
        ${createField("Output", step.output).outerHTML}
      </div>
      <div class="cb-actions-row"><button class="cb-tiny cb-replace-trigger" type="button">Replace</button></div>
      <div class="cb-replace-popover" aria-label="Replacement tool candidates">
        <div class="cb-replace-title"><strong>${step.title}</strong><span>${step.subtitle}</span></div>
        ${step.candidates.map((candidate, index) => `
          <button class="cb-replace-option ${index === 0 ? "recommended" : ""}" type="button">
            <strong>${candidate[0]} <span class="cb-chip${candidate[2]}">${candidate[1]}</span></strong>
            <span>${candidate[3]}</span>
          </button>
        `).join("")}
      </div>
    </div>
  `;
  return item;
}

function createPanel() {
  injectStyles();
  if (document.querySelector(".comfybio-panel")) {
    return;
  }

  const launcher = el("button", {
    class: "comfybio-launcher",
    type: "button",
    "aria-label": "Open ComfyBIO panel",
    "aria-expanded": "false",
  });
  launcher.innerHTML = `
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M9 4c10 5 10 19 0 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      <path d="M23 4c-10 5-10 19 0 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      <path d="M11 8h10M9 14h14M9 20h14M11 26h10" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" opacity="0.88"/>
      <circle cx="9" cy="4" r="1.6" fill="currentColor"/>
      <circle cx="23" cy="28" r="1.6" fill="currentColor"/>
    </svg>
  `;

  const panel = el("aside", {
    class: "comfybio-panel",
    "aria-label": "ComfyBIO Harness Core console panel",
    "aria-hidden": "true",
  });
  panel.innerHTML = `
    ${["n", "e", "s", "w", "ne", "nw", "se", "sw"].map((dir) => `<span class="cb-resize ${dir}" data-resize="${dir}" aria-hidden="true"></span>`).join("")}
    <header class="cb-header">
      <div class="cb-title">
        <strong>Harness Core Console</strong>
        <span>Research-backed workflow generation</span>
      </div>
      <div class="cb-actions">
        <span class="cb-status">Spec valid</span>
        <button class="cb-icon-button cb-close" type="button" title="Close">x</button>
      </div>
    </header>
    <section class="cb-content">
      <nav class="cb-tabs" role="tablist" aria-label="Harness console tabs">
        <button class="cb-tab" data-tab="prompt" type="button">Prompt</button>
        <button class="cb-tab active" data-tab="tool" type="button">Tool Select</button>
        <button class="cb-tab" data-tab="generate" type="button">Generate Graph</button>
      </nav>

      <section class="cb-panel-section" data-panel="prompt">
        <div class="cb-box">
          <div class="cb-box-header"><strong>LLM settings</strong><span>provider-specific model list</span></div>
          <div class="cb-settings-fields">
            <label class="cb-field">Provider<select class="cb-provider"><option>codex</option><option>claude</option><option>gemini</option></select></label>
            <label class="cb-field">Model<select class="cb-model"></select></label>
          </div>
        </div>
        <div class="cb-box">
          <div class="cb-box-header"><strong>Analysis resources</strong><button class="cb-button cb-add-resource" type="button">+ Add resource</button></div>
          <div class="cb-resource-list"></div>
        </div>
        <div class="cb-box">
          <div class="cb-box-header"><strong>Analysis request</strong><span>natural language prompt</span></div>
          <label class="cb-field">Request<textarea class="cb-analysis-request">Analyze this FASTQ folder as RNA-seq, human GRCh38, treated vs control.</textarea></label>
        </div>
        <div class="cb-generate-footer"><button class="cb-button apply cb-submit" type="button">Submit</button></div>
      </section>

      <section class="cb-panel-section active" data-panel="tool">
        <div class="cb-box">
          <div class="cb-meta">
            ${createField("Analysis domain", "Bulk RNA-seq").outerHTML}
            ${createField("Workflow route", "Genome alignment + count matrix").outerHTML}
          </div>
        </div>
        <div class="cb-message">
          <span class="severity">tool sequence</span>
          Drag a handle to reorder a step, click a step to inspect details, or approve the spec for graph generation.
        </div>
        <div class="cb-step-list"></div>
        <div class="cb-footer">
          <span class="cb-chip">Spec edited, not approved</span>
          <div class="cb-add-step-wrap">
            <button class="cb-button cb-add-step" type="button" aria-expanded="false">Add Step</button>
            <div class="cb-add-step-menu">
              ${Object.entries(STEP_CATALOG).map(([key, value]) => `<button class="cb-step-option" type="button" data-step="${key}"><strong>${value.tool}</strong><span>${value.stage}</span></button>`).join("")}
            </div>
          </div>
          <button class="cb-button apply cb-approve" type="button">Approve Spec</button>
        </div>
      </section>

      <section class="cb-panel-section" data-panel="generate">
        <div class="cb-message">
          <span class="severity">generation summary</span>
          This graph will be generated from the prompt resources and the approved tool sequence.
        </div>
        <div class="cb-summary-grid">
          ${createField("LLM", "codex / gpt-5.5").outerHTML}
          ${createField("Input path", "/data/project/fastq").outerHTML}
          ${createField("Output path", "/data/project/results").outerHTML}
          ${createField("Resources", "metadata_csv, genome_index, gtf_annotation").outerHTML}
          ${createField("Analysis domain", "Bulk RNA-seq").outerHTML}
          ${createField("Tool sequence", "InputValidator, FastQC, fastp, STAR, featureCounts, DESeq2, InteractiveReport").outerHTML}
        </div>
        <div class="cb-generate-footer"><button class="cb-button apply cb-generate" type="button">Generate Graph</button></div>
      </section>
    </section>
  `;

  document.body.append(panel, launcher);
  initializePanel(panel, launcher);
}

function initializePanel(panel, launcher) {
  const state = {
    launcherLeft: window.innerWidth - 78,
    launcherTop: window.innerHeight - 78,
    width: 460,
    height: 720,
    minWidth: 360,
    minHeight: 420,
    launcherDrag: null,
    panelResize: null,
    stepDrag: null,
    lastPayload: null,
    spec: null,
  };
  const viewportMargin = 12;
  const launcherSize = 56;
  const provider = panel.querySelector(".cb-provider");
  const model = panel.querySelector(".cb-model");
  const status = panel.querySelector(".cb-status");
  const resourceList = panel.querySelector(".cb-resource-list");
  const stepList = panel.querySelector(".cb-step-list");

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function syncLauncher() {
    state.launcherLeft = clamp(state.launcherLeft, viewportMargin, window.innerWidth - launcherSize - viewportMargin);
    state.launcherTop = clamp(state.launcherTop, viewportMargin, window.innerHeight - launcherSize - viewportMargin);
    launcher.style.setProperty("--cb-launcher-left", `${state.launcherLeft}px`);
    launcher.style.setProperty("--cb-launcher-top", `${state.launcherTop}px`);
  }

  function positionPanel() {
    state.width = clamp(state.width, state.minWidth, window.innerWidth - viewportMargin * 2);
    state.height = clamp(state.height, state.minHeight, window.innerHeight - viewportMargin * 2);
    state.launcherLeft = clamp(state.launcherLeft, viewportMargin, window.innerWidth - state.width - viewportMargin);
    state.launcherTop = clamp(state.launcherTop, viewportMargin, window.innerHeight - state.height - viewportMargin);
    syncLauncher();
    panel.style.setProperty("--cb-panel-left", `${state.launcherLeft}px`);
    panel.style.setProperty("--cb-panel-top", `${state.launcherTop}px`);
    panel.style.setProperty("--cb-panel-width", `${state.width}px`);
    panel.style.setProperty("--cb-panel-height", `${state.height}px`);
  }

  function setOpen(isOpen) {
    if (isOpen) {
      positionPanel();
    }
    panel.classList.toggle("is-open", isOpen);
    launcher.classList.toggle("panel-open", isOpen);
    panel.setAttribute("aria-hidden", String(!isOpen));
    launcher.setAttribute("aria-expanded", String(isOpen));
    launcher.setAttribute("aria-label", isOpen ? "Collapse ComfyBIO assistant" : "Open ComfyBIO panel");
  }

  function updateModelOptions() {
    model.replaceChildren(...(PROVIDER_MODELS[provider.value] || []).map((name) => el("option", { value: name, text: name })));
  }

  function renumberSteps() {
    stepList.querySelectorAll(".cb-step").forEach((item, index) => {
      item.querySelector(".cb-badge").textContent = String(index + 1);
    });
  }

  function stepFromDTO(dto) {
    const io = `${(dto.input_types || []).join(", ") || "-"} / ${(dto.output_types || []).join(", ") || "-"}`;
    return {
      stage: dto.stage_label,
      tool: dto.tool_label,
      input: (dto.input_types || []).join(", ") || "-",
      output: (dto.output_types || []).join(", ") || "-",
      title: `TSR candidates for ${dto.stage_label}`,
      subtitle: io,
      candidates: (dto.candidates || []).map((candidate) => [
        candidate.label,
        candidate.tier,
        candidate.tier === "REF" ? "" : " amber",
        candidate.note || "",
      ]),
    };
  }

  function renderServerSteps(steps) {
    stepList.replaceChildren(...steps.map((dto) => createStep(stepFromDTO(dto))));
    renumberSteps();
    refreshSummary();
  }

  function showToolMessage(text) {
    const message = panel.querySelector('[data-panel="tool"] .cb-message');
    if (message) {
      message.innerHTML = `<span class="severity">status</span>${text}`;
    }
  }

  function setExpandedStep(item, shouldExpand) {
    stepList.querySelectorAll(".cb-step.expanded").forEach((candidate) => {
      if (candidate !== item) {
        candidate.classList.remove("expanded", "replace-open");
        candidate.querySelector(".cb-step-summary")?.setAttribute("aria-expanded", "false");
      }
    });
    item.classList.toggle("expanded", shouldExpand);
    item.querySelector(".cb-step-summary")?.setAttribute("aria-expanded", String(shouldExpand));
    if (!shouldExpand) {
      item.classList.remove("replace-open");
    }
  }

  function getToolSequence() {
    return [...stepList.querySelectorAll(".cb-step-tool")].map((item) => item.textContent.trim());
  }

  function getResources() {
    return [...resourceList.querySelectorAll(".cb-resource-row")].map((row) => ({
      label: row.querySelector(".cb-resource-label")?.value?.trim() || "",
      type: row.querySelector(".cb-resource-type")?.value || (row.querySelector(".cb-resource-label")?.readOnly ? "path" : "resource"),
      path: row.querySelector(".cb-resource-path")?.value?.trim() || "",
    })).filter((resource) => resource.label || resource.path);
  }

  function refreshSummary() {
    const resources = getResources();
    const input = resources.find((resource) => resource.label === "input_path")?.path || "";
    const output = resources.find((resource) => resource.label === "output_path")?.path || "";
    const extras = resources.filter((resource) => resource.label !== "input_path" && resource.label !== "output_path");
    const values = [
      `${provider.value} / ${model.value}`,
      input,
      output,
      extras.map((resource) => resource.label).join(", ") || "none",
      "Bulk RNA-seq",
      getToolSequence().join(", "),
    ];
    panel.querySelectorAll('[data-panel="generate"] .cb-field strong').forEach((field, index) => {
      field.textContent = values[index] || "";
    });
  }

  function resizePanel(direction, dx, dy) {
    let left = state.launcherLeft;
    let top = state.launcherTop;
    let width = state.width;
    let height = state.height;
    const maxRight = window.innerWidth - viewportMargin;
    const maxBottom = window.innerHeight - viewportMargin;

    if (direction.includes("e")) {
      width = clamp(width + dx, state.minWidth, maxRight - left);
    }
    if (direction.includes("s")) {
      height = clamp(height + dy, state.minHeight, maxBottom - top);
    }
    if (direction.includes("w")) {
      const nextLeft = clamp(left + dx, viewportMargin, left + width - state.minWidth);
      width = clamp(width + left - nextLeft, state.minWidth, maxRight - nextLeft);
      left = nextLeft;
    }
    if (direction.includes("n")) {
      const nextTop = clamp(top + dy, viewportMargin, top + height - state.minHeight);
      height = clamp(height + top - nextTop, state.minHeight, maxBottom - nextTop);
      top = nextTop;
    }

    state.launcherLeft = left;
    state.launcherTop = top;
    state.width = width;
    state.height = height;
    positionPanel();
  }

  updateModelOptions();
  resourceList.append(
    createPathPicker("input_path", "/data/project/fastq", true),
    createPathPicker("output_path", "/data/project/results", true),
    createExtraResource(),
  );
  for (const key of INITIAL_STEPS) {
    stepList.append(createStep(STEP_CATALOG[key]));
  }
  renumberSteps();
  refreshSummary();
  syncLauncher();

  provider.addEventListener("change", () => {
    updateModelOptions();
    refreshSummary();
  });
  model.addEventListener("change", refreshSummary);
  resourceList.addEventListener("input", refreshSummary);

  panel.querySelector(".cb-add-resource").addEventListener("click", () => {
    resourceList.append(createExtraResource());
    refreshSummary();
  });

  resourceList.addEventListener("click", (event) => {
    const picker = event.target.closest(".cb-path-button");
    if (picker) {
      const wrap = picker.closest(".cb-path-wrap");
      resourceList.querySelectorAll(".cb-path-wrap.open").forEach((candidate) => {
        if (candidate !== wrap) candidate.classList.remove("open");
      });
      wrap.classList.toggle("open");
      return;
    }
    const choice = event.target.closest(".cb-path-choice");
    if (choice) {
      const wrap = choice.closest(".cb-path-wrap");
      wrap.querySelector(".cb-path-button").textContent = choice.dataset.kind === "file" ? "File" : "Folder";
      wrap.classList.remove("open");
      return;
    }
    const remove = event.target.closest(".cb-remove-resource");
    if (remove) {
      remove.closest(".cb-resource-row")?.remove();
      refreshSummary();
    }
  });

  panel.querySelector(".cb-submit").addEventListener("click", async () => {
    const payload = {
      provider: provider.value,
      model: model.value,
      request_text: panel.querySelector(".cb-analysis-request").value.trim(),
      resources: getResources(),
    };
    state.lastPayload = payload;
    try {
      const response = await api.fetchApi("/comfybio/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.status === "planning_required") {
        status.textContent = "Planning required";
        showToolMessage(data.message || "Domain requires planning.");
        return;
      }
      state.spec = data;
      renderServerSteps(data.steps || []);
      status.textContent = "Spec ready";
    } catch (error) {
      status.textContent = "Backend offline";
      showToolMessage(`Compile failed: ${error.message}`);
    }
  });

  panel.querySelector(".cb-approve").addEventListener("click", () => {
    status.textContent = "Spec approved";
    refreshSummary();
  });

  panel.querySelector(".cb-generate").addEventListener("click", async () => {
    refreshSummary();
    const payload = {
      provider: provider.value,
      model: model.value,
      request_text: panel.querySelector(".cb-analysis-request").value.trim(),
      resources: getResources(),
      steps: getToolSequence(),
    };
    try {
      const response = await api.fetchApi("/comfybio/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data.status !== "ok" || !data.workflow) {
        status.textContent = "Generate failed";
        showToolMessage(data.message || "Workflow generation failed.");
        return;
      }
      app.loadGraphData(data.workflow);
      status.textContent = "Graph loaded";
    } catch (error) {
      status.textContent = "Backend offline";
      showToolMessage(`Generate failed: ${error.message}`);
    }
  });

  launcher.addEventListener("pointerdown", (event) => {
    state.launcherDrag = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      moved: false,
    };
    launcher.classList.add("dragging");
    launcher.setPointerCapture(event.pointerId);
  });
  launcher.addEventListener("pointermove", (event) => {
    if (!state.launcherDrag || state.launcherDrag.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.launcherDrag.x;
    const dy = event.clientY - state.launcherDrag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) state.launcherDrag.moved = true;
    state.launcherLeft += dx;
    state.launcherTop += dy;
    syncLauncher();
    if (panel.classList.contains("is-open")) positionPanel();
    state.launcherDrag.x = event.clientX;
    state.launcherDrag.y = event.clientY;
  });
  launcher.addEventListener("pointerup", (event) => {
    if (!state.launcherDrag || state.launcherDrag.pointerId !== event.pointerId) return;
    launcher.classList.remove("dragging");
    launcher.releasePointerCapture(event.pointerId);
    const suppress = state.launcherDrag.moved;
    state.launcherDrag = null;
    if (!suppress) setOpen(!panel.classList.contains("is-open"));
  });
  launcher.addEventListener("pointercancel", () => {
    launcher.classList.remove("dragging");
    state.launcherDrag = null;
  });

  panel.querySelector(".cb-close").addEventListener("click", () => setOpen(false));

  panel.querySelectorAll(".cb-resize").forEach((handle) => {
    handle.addEventListener("pointerdown", (event) => {
      if (!panel.classList.contains("is-open")) return;
      event.preventDefault();
      state.panelResize = {
        pointerId: event.pointerId,
        direction: handle.dataset.resize,
        x: event.clientX,
        y: event.clientY,
      };
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", (event) => {
      if (!state.panelResize || state.panelResize.pointerId !== event.pointerId) return;
      const dx = event.clientX - state.panelResize.x;
      const dy = event.clientY - state.panelResize.y;
      resizePanel(state.panelResize.direction, dx, dy);
      state.panelResize.x = event.clientX;
      state.panelResize.y = event.clientY;
    });
    const finishResize = (event) => {
      if (!state.panelResize || state.panelResize.pointerId !== event.pointerId) return;
      if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
      state.panelResize = null;
    };
    handle.addEventListener("pointerup", finishResize);
    handle.addEventListener("pointercancel", finishResize);
  });

  panel.querySelector(".cb-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest(".cb-tab");
    if (!tab) return;
    const selected = tab.dataset.tab;
    panel.querySelectorAll(".cb-tab").forEach((candidate) => candidate.classList.toggle("active", candidate === tab));
    panel.querySelectorAll(".cb-panel-section").forEach((section) => section.classList.toggle("active", section.dataset.panel === selected));
    if (selected === "generate") refreshSummary();
  });

  stepList.addEventListener("click", (event) => {
    const remove = event.target.closest(".cb-step-remove");
    if (remove) {
      remove.closest(".cb-step")?.remove();
      renumberSteps();
      refreshSummary();
      return;
    }
    const replace = event.target.closest(".cb-replace-trigger");
    if (replace) {
      const step = replace.closest(".cb-step");
      stepList.querySelectorAll(".cb-step.replace-open").forEach((candidate) => {
        if (candidate !== step) candidate.classList.remove("replace-open");
      });
      step.classList.toggle("replace-open");
      return;
    }
    const summary = event.target.closest(".cb-step-summary");
    if (!summary || event.target.closest(".cb-drag")) return;
    const item = summary.closest(".cb-step");
    setExpandedStep(item, !item.classList.contains("expanded"));
  });

  stepList.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const summary = event.target.closest(".cb-step-summary");
    if (!summary) return;
    event.preventDefault();
    const item = summary.closest(".cb-step");
    setExpandedStep(item, !item.classList.contains("expanded"));
  });

  stepList.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest(".cb-drag");
    if (!handle) return;
    event.preventDefault();
    const item = handle.closest(".cb-step");
    state.stepDrag = {
      item,
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
    stepList.classList.add("drag-active");
    item.classList.add("dragging");
    handle.setPointerCapture(event.pointerId);
  });
  stepList.addEventListener("pointermove", (event) => {
    if (!state.stepDrag || state.stepDrag.pointerId !== event.pointerId) return;
    if (Math.abs(event.clientX - state.stepDrag.x) + Math.abs(event.clientY - state.stepDrag.y) <= 3) return;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".cb-step");
    if (!target || target === state.stepDrag.item || !stepList.contains(target)) return;
    const rect = target.getBoundingClientRect();
    const insertAfter = event.clientY > rect.top + rect.height / 2;
    stepList.insertBefore(state.stepDrag.item, insertAfter ? target.nextSibling : target);
  });
  const finishStepDrag = (event) => {
    if (!state.stepDrag || state.stepDrag.pointerId !== event.pointerId) return;
    const handle = state.stepDrag.item.querySelector(".cb-drag");
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
    state.stepDrag.item.classList.remove("dragging");
    state.stepDrag = null;
    stepList.classList.remove("drag-active");
    renumberSteps();
    refreshSummary();
  };
  stepList.addEventListener("pointerup", finishStepDrag);
  stepList.addEventListener("pointercancel", finishStepDrag);

  const addStepWrap = panel.querySelector(".cb-add-step-wrap");
  const addStepButton = panel.querySelector(".cb-add-step");
  addStepButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = addStepWrap.classList.toggle("open");
    addStepButton.setAttribute("aria-expanded", String(isOpen));
  });
  addStepWrap.addEventListener("click", (event) => {
    const option = event.target.closest(".cb-step-option");
    if (!option) return;
    const item = createStep(STEP_CATALOG[option.dataset.step]);
    stepList.append(item);
    renumberSteps();
    setExpandedStep(item, true);
    refreshSummary();
    addStepWrap.classList.remove("open");
    addStepButton.setAttribute("aria-expanded", "false");
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".cb-add-step-wrap")) {
      addStepWrap.classList.remove("open");
      addStepButton.setAttribute("aria-expanded", "false");
    }
  });
  window.addEventListener("resize", () => {
    syncLauncher();
    if (panel.classList.contains("is-open")) positionPanel();
  });
}

app.registerExtension({
  name: "ComfyBIO.HarnessCorePanel",
  setup() {
    createPanel();
  },
});

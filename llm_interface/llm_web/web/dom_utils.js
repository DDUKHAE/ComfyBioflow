// ── DOM Utilities ──────────────────────────────────────────────────────────────
// Shared helpers extracted from comfybio_test_load.js (Phase 2 refactor).

/**
 * Safe HTML escaper. Escapes &, <, >, and " to prevent XSS when inserting
 * user-controlled strings into innerHTML or HTML attribute values.
 */
export function esc(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Safe DOM element builder. Replaces innerHTML template strings with a
 * structured API that never allows HTML injection.
 *
 * @param {string} tag - HTML tag name (e.g. "div", "span")
 * @param {Object} attrs - key/value pairs set via setAttribute (safe)
 * @param {Array|Node|string} children - child nodes, strings, or arrays of either
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, children = []) {
    const element = document.createElement(tag);

    for (const [key, value] of Object.entries(attrs)) {
        element.setAttribute(key, value);
    }

    const append = (child) => {
        if (Array.isArray(child)) {
            child.forEach(append);
        } else if (child instanceof Node) {
            element.appendChild(child);
        } else if (child != null) {
            element.appendChild(document.createTextNode(String(child)));
        }
    };

    append(children);

    return element;
}

/**
 * Makes an element draggable via a handle element.
 *
 * @param {HTMLElement} element - the element to move
 * @param {HTMLElement} handle - the element that initiates the drag
 * @param {string|null} skipSelector - CSS selector; clicks on matching targets are ignored
 */
export function makeDraggable(element, handle, skipSelector) {
    element._dragging = false;

    handle.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        if (skipSelector && e.target.closest(skipSelector)) return;

        e.preventDefault();
        element._dragging = false;

        const rect = element.getBoundingClientRect();
        const startX = e.clientX;
        const startY = e.clientY;
        const origLeft = rect.left;
        const origTop  = rect.top;

        const onMove = (e) => {
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            if (!element._dragging && Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
            element._dragging = true;
            document.body.style.userSelect = "none";

            const w = element.offsetWidth;
            const h = element.offsetHeight;
            const left = Math.max(0, Math.min(window.innerWidth  - w, origLeft + dx));
            const top  = Math.max(0, Math.min(window.innerHeight - h, origTop  + dy));

            element.style.left   = left + "px";
            element.style.top    = top  + "px";
            element.style.right  = "auto";
            element.style.bottom = "auto";
        };

        const onUp = () => {
            document.body.style.userSelect = "";
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup",   onUp);
            // Reset after click event fires so same-element click suppression still works
            setTimeout(() => { element._dragging = false; }, 0);
        };

        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup",   onUp);
    });
}

/**
 * Adds 8 resize handles (N, NE, E, SE, S, SW, W, NW) to an element,
 * allowing free resizing in all directions.
 *
 * @param {HTMLElement} element - the element to make resizable
 */
export function makeResizable(element) {
    const handles = [
        { cls: "cb-resize-n",  dirs: ["n"]      },
        { cls: "cb-resize-ne", dirs: ["n", "e"] },
        { cls: "cb-resize-e",  dirs: ["e"]      },
        { cls: "cb-resize-se", dirs: ["s", "e"] },
        { cls: "cb-resize-s",  dirs: ["s"]      },
        { cls: "cb-resize-sw", dirs: ["s", "w"] },
        { cls: "cb-resize-w",  dirs: ["w"]      },
        { cls: "cb-resize-nw", dirs: ["n", "w"] },
    ];

    handles.forEach(({ cls, dirs }) => {
        const h = document.createElement("div");
        h.className = "cb-resize-handle " + cls;
        element.appendChild(h);

        h.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return;
            e.preventDefault();
            e.stopPropagation();

            const startX    = e.clientX;
            const startY    = e.clientY;
            const startW    = element.offsetWidth;
            const startH    = element.offsetHeight;
            const rect      = element.getBoundingClientRect();
            const startLeft = rect.left;
            const startTop  = rect.top;

            const onMove = (e) => {
                document.body.style.userSelect = "none";
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;

                if (dirs.includes("e")) {
                    element.style.width = Math.max(280, startW + dx) + "px";
                }
                if (dirs.includes("w")) {
                    const newW = Math.max(280, startW - dx);
                    element.style.width = newW + "px";
                    element.style.left  = (startLeft + startW - newW) + "px";
                    element.style.right = "auto";
                }
                if (dirs.includes("s")) {
                    element.style.maxHeight = "none";
                    element.style.height    = Math.max(200, startH + dy) + "px";
                }
                if (dirs.includes("n")) {
                    const newH = Math.max(200, startH - dy);
                    element.style.maxHeight = "none";
                    element.style.height    = newH + "px";
                    element.style.top       = (startTop + startH - newH) + "px";
                    element.style.bottom    = "auto";
                }
            };

            const onUp = () => {
                document.body.style.userSelect = "";
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup",   onUp);
            };

            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup",   onUp);
        });
    });
}

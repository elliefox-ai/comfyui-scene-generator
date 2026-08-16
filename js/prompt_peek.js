/**
 * PromptPeek v1.0 — live prompt inspection on the node canvas
 *
 * Select, cycle (◀ ▶), or drop an image on the node: the prompt it was
 * generated with is parsed client-side from PNG tEXt chunks and drawn
 * directly on the node — no execution needed.
 *
 * Layout (per Alexander): text on top, image preview at the bottom,
 * scales with node size, scrollbar when text overflows.
 */

import { app } from "../../../scripts/app.js";

console.log("[PromptPeek] v1.0 loading");

const NODE_TYPE = "PromptPeek";
const PAD = 10;
const LINE_H = 13;
const FONT = "11px monospace";
const HEADER_FONT = "bold 11px monospace";
const PREVIEW_MIN_H = 60;

// ─── PNG tEXt chunk parsing (client-side) ────────────────────────────────────

function parsePngTextChunks(buffer) {
    const view = new DataView(buffer);
    const bytes = new Uint8Array(buffer);
    // PNG signature check
    if (bytes.length < 8 || bytes[0] !== 0x89 || bytes[1] !== 0x50) return null;
    let off = 8;
    const texts = {};
    const decoder = new TextDecoder("utf-8", { fatal: false });
    while (off + 8 <= bytes.length) {
        const len = view.getUint32(off);
        const type = String.fromCharCode(bytes[off + 4], bytes[off + 5], bytes[off + 6], bytes[off + 7]);
        const dataStart = off + 8;
        if (type === "tEXt") {
            const data = bytes.subarray(dataStart, dataStart + len);
            const nul = data.indexOf(0);
            if (nul > 0) {
                const key = decoder.decode(data.subarray(0, nul));
                const val = decoder.decode(data.subarray(nul + 1));
                texts[key] = val;
            }
        } else if (type === "iTXt") {
            // Compressed iTXt unsupported; try uncompressed (compression flag = 0)
            const data = bytes.subarray(dataStart, dataStart + len);
            const nul = data.indexOf(0);
            if (nul > 0 && data[nul + 1] === 0) {
                const key = decoder.decode(data.subarray(0, nul));
                const val = decoder.decode(data.subarray(nul + 3)); // skip comp flag + method
                texts[key] = val;
            }
        } else if (type === "IEND") {
            break;
        }
        off = dataStart + len + 4; // skip CRC
    }
    return texts;
}

// ─── Prompt graph summarizer (mirrors prompt_peek.py) ───────────────────────

function resolveText(graph, ref) {
    if (Array.isArray(ref) && ref.length === 2) {
        const node = graph[String(ref[0])];
        if (node && node.inputs && typeof node.inputs.text === "string") return node.inputs.text;
    }
    return null;
}

function summarizeGraph(graph) {
    const meta = { positive: "", negative: "", model: "", loras: [], seed: "", steps: "", cfg: "", sampler: "" };
    let sampler = null;
    for (const id of Object.keys(graph)) {
        const node = graph[id];
        if (!node || typeof node !== "object") continue;
        const ct = String(node.class_type || "");
        const inputs = node.inputs || {};
        if ((ct === "KSampler" || ct === "KSamplerAdvanced") && !sampler) {
            sampler = inputs;
            meta.positive = resolveText(graph, inputs.positive) || meta.positive;
            meta.negative = resolveText(graph, inputs.negative) || meta.negative;
        }
        if ((ct === "CheckpointLoaderSimple" || ct === "UNETLoader" || ct === "CheckpointLoader") && !meta.model) {
            meta.model = inputs.ckpt_name || inputs.unet_name || "";
        }
        if (ct === "LoraLoader" && inputs.lora_name) meta.loras.push(inputs.lora_name);
        if (ct === "CLIPTextEncodeSDXL" && !meta.positive) {
            meta.positive = inputs.text || ""; // SDXL refiner-style standalone
        }
    }
    if (!meta.positive) {
        // Longest CLIPTextEncode text is the positive prompt
        for (const id of Object.keys(graph)) {
            const node = graph[id];
            if (node && String(node.class_type || "") === "CLIPTextEncode") {
                const t = node.inputs && node.inputs.text;
                if (typeof t === "string" && t.length > meta.positive.length) meta.positive = t;
            }
        }
    }
    if (sampler) {
        meta.seed = String(sampler.seed ?? sampler.noise_seed ?? "");
        meta.steps = String(sampler.steps ?? "");
        meta.cfg = String(sampler.cfg ?? "");
        meta.sampler = String(sampler.sampler_name ?? "");
    }
    return meta;
}

function textsToInfo(texts) {
    if (!texts) return null;
    let meta = null;
    if (texts.prompt) {
        try {
            const graph = JSON.parse(texts.prompt);
            if (graph && typeof graph === "object") meta = summarizeGraph(graph);
        } catch (_) { /* fall through */ }
    }
    if (!meta && texts.parameters) {
        meta = { positive: texts.parameters, negative: "", model: "", loras: [], seed: "", steps: "", cfg: "", sampler: "" };
    }
    return meta;
}

// ─── Fetch + cache ───────────────────────────────────────────────────────────

const metaCache = new Map();   // filename -> {meta, raw} | {meta:null}
const imgCache = new Map();    // filename -> HTMLImageElement

async function inspectImage(filename) {
    if (metaCache.has(filename)) return metaCache.get(filename);
    let entry = { meta: null, raw: "" };
    try {
        const resp = await fetch(`/view?filename=${encodeURIComponent(filename)}&type=input`);
        if (resp.ok) {
            const buf = await resp.arrayBuffer();
            const texts = parsePngTextChunks(buf);
            entry = { meta: textsToInfo(texts), raw: (texts && (texts.prompt || texts.parameters)) || "" };
        }
    } catch (e) {
        console.warn("[PromptPeek] fetch/parse failed for", filename, e);
    }
    metaCache.set(filename, entry);
    return entry;
}

function getImageEl(filename, cb) {
    if (imgCache.has(filename)) { cb(imgCache.get(filename)); return; }
    const img = new Image();
    img.onload = () => { imgCache.set(filename, img); cb(img); };
    img.onerror = () => cb(null);
    img.src = `/view?filename=${encodeURIComponent(filename)}&type=input`;
}

// ─── Text layout helpers ─────────────────────────────────────────────────────

function wrapText(ctx, text, maxWidth) {
    const lines = [];
    for (const para of String(text).split("\n")) {
        if (!para) { lines.push(""); continue; }
        let line = "";
        for (const word of para.split(/\s+/)) {
            const test = line ? line + " " + word : word;
            if (ctx.measureText(test).width > maxWidth && line) {
                lines.push(line);
                line = word;
            } else {
                line = test;
            }
        }
        lines.push(line);
    }
    return lines;
}

// ─── Extension ───────────────────────────────────────────────────────────────

app.registerExtension({
    name: "EllieFoxAI.PromptPeek",

    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== NODE_TYPE) return;

        const origCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = origCreated?.apply(this, arguments);

            if (!this.properties) this.properties = {};
            this._ppScroll = 0;
            this._ppLines = [];
            this._ppMeta = null;
            this._ppHeaderLines = [];
            this._ppScrollDrag = false;
            this._ppCopyHover = false;
            this._ppInspected = null;      // filename currently shown
            this._ppDnDOver = false;

            // sensible default size — tall enough for header + text + preview
            this.size = [360, 480];

            const imgWidget = this.widgets?.find((w) => w.name === "image");

            const refresh = (filename) => {
                if (!filename) return;
                this._ppInspected = filename;
                this._ppScroll = 0;
                inspectImage(filename).then(({ meta }) => {
                    // ignore stale responses if the widget changed meanwhile
                    if (this._ppInspected !== filename) return;
                    this._ppMeta = meta;
                    this.setDirtyCanvas(true, true);
                });
                getImageEl(filename, () => this.setDirtyCanvas(true, true));
                this.setDirtyCanvas(true, true);
            };

            if (imgWidget) {
                const origCb = imgWidget.callback;
                imgWidget.callback = (...args) => {
                    const r = origCb?.apply(imgWidget, args);
                    refresh(imgWidget.value);
                    return r;
                };
                // Initial paint (deferred so widgets are populated)
                const t = setTimeout(() => refresh(imgWidget.value), 100);
                this._ppInitTimer = t;
                this.onRemoved = function () { clearTimeout(this._ppInitTimer); };
            }

            return result;
        };

        // Layout regions (recomputed every draw)
        const regions = (node) => {
            const w = node.size[0];
            const h = node.size[1];
            // start below the image combo widget, not just below the title bar
            const lastW = node.widgets && node.widgets.length ? node.widgets[node.widgets.length - 1] : null;
            let top = 56; // static fallback: title bar (~26) + combo widget (~26)
            if (lastW && typeof lastW.y === "number" && lastW.y > 0) {
                top = lastW.y + (lastW.height || 26) + 8;
            }
            const copyBarH = 18;
            const textTop = top + 2;
            const headerH = node._ppHeaderLines ? node._ppHeaderLines.length * LINE_H + 6 : 0;
            const previewH = Math.max(PREVIEW_MIN_H, Math.min(h * 0.32, h - top - 140));
            const textAreaTop = textTop + copyBarH;
            const textAreaH = h - textAreaTop - previewH - PAD;
            return {
                w, h, top, textTop, copyBarH, headerH, previewH,
                textX: PAD, textAreaTop, textAreaH,
                textW: w - PAD * 2 - 8,       // room for scrollbar
                scrollbarX: w - PAD - 4,
                copyRect: [PAD, textTop, 70, copyBarH],
            };
        };

        // enforce a minimum size so the layout never collapses
        const origResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            const MIN_W = 320, MIN_H = 440;
            if (size) {
                if (size[0] < MIN_W) size[0] = MIN_W;
                if (size[1] < MIN_H) size[1] = MIN_H;
            }
            this.size[0] = Math.max(this.size[0], MIN_W);
            this.size[1] = Math.max(this.size[1], MIN_H);
            return origResize?.apply(this, arguments);
        };

        nodeType.prototype.onDrawForeground = function (ctx) {
            if (this.flags?.collapsed) return;
            const r = regions(this);

            // background panel
            ctx.fillStyle = "rgba(20,20,25,0.92)";
            ctx.fillRect(0, r.top, r.w, r.h - r.top);

            // copy button
            const [cx, cy, cw, ch] = r.copyRect;
            ctx.font = FONT;
            ctx.fillStyle = this._ppCopyHover ? "#8ab4f8" : "#9aa0a6";
            ctx.textBaseline = "middle";
            ctx.fillText("⧉ copy prompt", cx + 2, cy + ch / 2);

            if (!this._ppInspected) {
                ctx.fillStyle = "#9aa0a6";
                ctx.fillText("select / drop an image…", r.textX, r.textTop + r.copyBarH + 14);
                return;
            }

            const meta = this._ppMeta;
            // header: model · seed · steps · loras
            if (this._ppHeaderLines.length === 0 && meta) {
                const bits = [];
                if (meta.model) bits.push(meta.model);
                if (meta.seed) bits.push(`seed ${meta.seed}`);
                if (meta.steps) bits.push(`${meta.steps} steps`);
                if (meta.sampler) bits.push(meta.sampler);
                if (meta.loras && meta.loras.length) bits.push(meta.loras.map((l) => l.replace(/^.*[\\/]/, "")).join(" + "));
                if (bits.length) this._ppHeaderLines = wrapText({ measureText: (t) => ctx.measureText(t) }, bits.join(" · "), r.textW);
            }
            if (this._ppHeaderLines.length) {
                ctx.font = HEADER_FONT;
                ctx.fillStyle = "#8ab4f8";
                let y = r.textAreaTop + LINE_H;
                for (const hl of this._ppHeaderLines) {
                    ctx.fillText(hl, r.textX, y);
                    y += LINE_H;
                }
                ctx.fillStyle = "rgba(138,180,248,0.25)";
                ctx.fillRect(r.textX, y + 2, r.textW, 1);
            }

            const bodyTop = r.textAreaTop + r.headerH;

            if (meta === null) {
                ctx.font = FONT;
                ctx.fillStyle = "#f28b82";
                ctx.fillText("(no prompt metadata found in PNG)", r.textX, bodyTop + LINE_H);
            } else if (meta) {
                // wrap lazily, cache per size
                const wrapKey = `${this._ppInspected}:${Math.round(r.textW)}`;
                if (this._ppWrapKey !== wrapKey) {
                    const lines = [];
                    if (meta.positive) {
                        ctx.font = FONT;
                        for (const l of wrapText(ctx, meta.positive, r.textW)) lines.push({ t: l, c: "#e8eaed" });
                    }
                    if (meta.negative && meta.negative.trim()) {
                        lines.push({ t: "", c: "#e8eaed" });
                        lines.push({ t: "— negative —", c: "#f28b82" });
                        for (const l of wrapText(ctx, meta.negative, r.textW)) lines.push({ t: l, c: "#f28b82" });
                    }
                    this._ppLines = lines;
                    this._ppWrapKey = wrapKey;
                }
                const total = this._ppLines.length;
                const visible = Math.max(0, Math.floor((r.textAreaH - r.headerH - 8) / LINE_H));
                const maxScroll = Math.max(0, total - visible);
                this._ppScroll = Math.min(this._ppScroll, maxScroll);
                ctx.font = FONT;
                ctx.textBaseline = "alphabetic";
                let y = bodyTop + LINE_H;
                const clipH = r.textAreaH - r.headerH;
                ctx.save();
                ctx.beginPath();
                ctx.rect(0, bodyTop, r.w, Math.max(0, clipH));
                ctx.clip();
                for (let i = this._ppScroll; i < Math.min(total, this._ppScroll + visible + 1); i++) {
                    ctx.fillStyle = this._ppLines[i].c;
                    ctx.fillText(this._ppLines[i].t, r.textX, y);
                    y += LINE_H;
                }
                ctx.restore();

                // scrollbar
                if (total > visible) {
                    const trackH = clipH - 4;
                    const thumbH = Math.max(18, (visible / total) * trackH);
                    const thumbY = bodyTop + 2 + (this._ppScroll / maxScroll) * (trackH - thumbH);
                    ctx.fillStyle = "rgba(255,255,255,0.12)";
                    ctx.fillRect(r.scrollbarX, bodyTop + 2, 4, trackH);
                    ctx.fillStyle = "rgba(255,255,255,0.45)";
                    ctx.fillRect(r.scrollbarX, thumbY, 4, thumbH);
                }
            }

            // image preview band at the bottom
            const pvTop = r.h - r.previewH;
            ctx.fillStyle = "rgba(0,0,0,0.35)";
            ctx.fillRect(0, pvTop, r.w, r.previewH);
            const img = imgCache.get(this._ppInspected);
            if (img && img.naturalWidth) {
                const maxW = r.w - PAD * 2;
                const maxH = r.previewH - PAD;
                const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight);
                const dw = img.naturalWidth * scale;
                const dh = img.naturalHeight * scale;
                ctx.drawImage(img, (r.w - dw) / 2, pvTop + (r.previewH - dh) / 2, dw, dh);
            } else {
                ctx.fillStyle = "#5f6368";
                ctx.font = FONT;
                ctx.fillText("(image preview)", PAD + 4, pvTop + r.previewH / 2);
            }
        };

        // ── interaction: scrollbar drag + copy ──
        const origMouseDown = nodeType.prototype.onMouseDown;
        nodeType.prototype.onMouseDown = function (e, ...rest) {
            const r = regions(this);
            // copy button
            const [cx, cy, cw, ch] = r.copyRect;
            if (e.canvasX >= cx && e.canvasX <= cx + cw && e.canvasY >= cy && e.canvasY <= cy + ch) {
                if (this._ppMeta?.positive && navigator.clipboard) {
                    navigator.clipboard.writeText(this._ppMeta.positive).then(() => {
                        console.log("[PromptPeek] prompt copied to clipboard");
                    });
                }
                return true;
            }
            // scrollbar track/thumb
            if (e.canvasX >= r.scrollbarX - 4 && e.canvasY >= r.textAreaTop + r.headerH && this._ppLines.length) {
                this._ppScrollDrag = true;
                return true;
            }
            // wheel-less fallback: click in text area = page down
            if (e.canvasX <= r.w && e.canvasY >= r.textAreaTop && e.canvasY <= r.h - r.previewH) {
                const visible = Math.max(1, Math.floor((r.textAreaH - r.headerH - 8) / LINE_H));
                this._ppScroll = Math.min(Math.max(0, this._ppLines.length - visible), this._ppScroll + visible);
                this.setDirtyCanvas(true, true);
                return true;
            }
            return origMouseDown?.apply(this, [e, ...rest]);
        };

        const origMouseMove = nodeType.prototype.onMouseMove;
        nodeType.prototype.onMouseMove = function (e, ...rest) {
            const r = regions(this);
            const [cx, cy, cw, ch] = r.copyRect;
            const hover = e.canvasX >= cx && e.canvasX <= cx + cw && e.canvasY >= cy && e.canvasY <= cy + ch;
            if (hover !== this._ppCopyHover) {
                this._ppCopyHover = hover;
                this.setDirtyCanvas(true, true);
            }
            if (this._ppScrollDrag) {
                const clipH = r.textAreaH - r.headerH;
                const total = this._ppLines.length;
                const visible = Math.max(1, Math.floor((clipH - 8) / LINE_H));
                const maxScroll = Math.max(0, total - visible);
                const frac = Math.min(1, Math.max(0, (e.canvasY - r.textAreaTop - r.headerH) / Math.max(1, clipH)));
                this._ppScroll = Math.round(frac * maxScroll);
                this.setDirtyCanvas(true, true);
                return true;
            }
            return origMouseMove?.apply(this, [e, ...rest]);
        };

        const origMouseUp = nodeType.prototype.onMouseUp;
        nodeType.prototype.onMouseUp = function (...args) {
            if (this._ppScrollDrag) {
                this._ppScrollDrag = false;
                return true;
            }
            return origMouseUp?.apply(this, args);
        };

        // wheel to scroll when hovering the text area
        const origOnWheel = nodeType.prototype.onWheel;
        nodeType.prototype.onWheel = function (e, ...rest) {
            const r = regions(this);
            if (e.canvasX >= 0 && e.canvasX <= r.w && e.canvasY >= r.textAreaTop && e.canvasY <= r.h - r.previewH) {
                const dir = e.deltaY > 0 ? 3 : -3;
                const visible = Math.max(1, Math.floor((r.textAreaH - r.headerH - 8) / LINE_H));
                const maxScroll = Math.max(0, this._ppLines.length - visible);
                this._ppScroll = Math.min(Math.max(0, maxScroll), Math.max(0, this._ppScroll + dir));
                this.setDirtyCanvas(true, true);
                return true;
            }
            return origOnWheel?.apply(this, [e, ...rest]);
        };

        console.log("[PromptPeek] node registered:", NODE_TYPE);
    },
});

// ─── Drag & drop (canvas-level, pattern from inpaint_painter) ───────────────

let dndAttached = false;

function canvasCoords(e) {
    if (app.canvas?.adjustMouseEvent) {
        try {
            app.canvas.adjustMouseEvent(e);
            if (e.canvasX !== undefined) return [e.canvasX, e.canvasY];
        } catch (_) {}
    }
    const el = app.canvas?.canvas || document.querySelector("#graph-canvas");
    if (!el) return [0, 0];
    const rect = el.getBoundingClientRect();
    return [(e.clientX - rect.left) / (app.canvas?.scale || 1), (e.clientY - rect.top) / (app.canvas?.scale || 1)];
}

function nodeAt(x, y) {
    for (const n of app.graph?._nodes || []) {
        if (n.type !== NODE_TYPE) continue;
        const [nx, ny] = n.pos;
        const [nw, nh] = n.size;
        if (x >= nx && x <= nx + nw && y >= ny && y <= ny + nh) return n;
    }
    return null;
}

async function uploadFile(file) {
    const fd = new FormData();
    fd.append("image", file);
    fd.append("type", "input");
    fd.append("overwrite", "false");
    const resp = await fetch("/upload/image", { method: "POST", body: fd });
    return resp.json();
}

function attachDnD() {
    if (dndAttached) return;
    const el = app.canvas?.canvas || document.querySelector("#graph-canvas");
    if (!el) { setTimeout(attachDnD, 500); return; }
    dndAttached = true;

    el.addEventListener("dragover", (e) => {
        if (!e.dataTransfer?.types?.includes("Files")) return;
        const [cx, cy] = canvasCoords(e);
        const node = nodeAt(cx, cy);
        if (node) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            node._ppDnDOver = true;
            node.setDirtyCanvas(true, true);
        }
    });

    el.addEventListener("drop", async (e) => {
        const [cx, cy] = canvasCoords(e);
        const node = nodeAt(cx, cy);
        if (!node) return;
        e.preventDefault();
        e.stopPropagation();
        node._ppDnDOver = false;
        const file = e.dataTransfer?.files?.[0];
        if (!file) return;
        try {
            const data = await uploadFile(file);
            if (data?.name) {
                const w = node.widgets?.find((x) => x.name === "image");
                if (w) {
                    // add to combo options if missing, then select + inspect
                    if (w.options?.values && !w.options.values.includes(data.name)) w.options.values.push(data.name);
                    w.value = data.name;
                    if (w.callback) w.callback(data.name);
                    node.setDirtyCanvas(true, true);
                }
            }
        } catch (err) {
            console.error("[PromptPeek] drop upload failed:", err);
        }
    });
}

app.ui?.config?.addEventListener?.("loaded", attachDnD);
attachDnD();

/**
 * Scene Generator frontend — live bbox preview on the node canvas.
 *
 * Each filter dropdown has a "🎲 random" option. When selected, the seed
 * decides that layer. The preview fetches template metadata from the API
 * and renders bbox layouts live — no execution needed.
 *
 * For random filters, we fetch ALL matching templates so the preview can
 * show a representative layout.
 */

import { app } from "../../../scripts/app.js";

console.log("[SceneGen] Extension loading...");

const COLORS = {
    background: { fill: "rgba(74, 138, 202, 0.12)", stroke: "rgba(74, 138, 202, 0.75)", label: "BG" },
    subject:    { fill: "rgba(202, 74, 74, 0.15)",  stroke: "rgba(202, 74, 74, 0.85)",  label: "S" },
    prop:       { fill: "rgba(74, 202, 108, 0.12)",  stroke: "rgba(74, 202, 108, 0.75)", label: "P" },
    threshold:  { fill: "rgba(202, 180, 74, 0.12)",  stroke: "rgba(202, 180, 74, 0.75)", label: "T" },
};

const RANDOM = "🎲 random";

const tplCache = {};

async function fetchTemplates(sceneType, shotWidth) {
    // For random filters, fetch broader to get representative templates
    const params = new URLSearchParams();
    if (sceneType && sceneType !== RANDOM) params.set("scene_type", sceneType);
    if (shotWidth && shotWidth !== RANDOM) params.set("shot_width", shotWidth);
    const key = params.toString();
    if (tplCache[key]) return tplCache[key];
    try {
        const url = `/scene_gen/templates${params.toString() ? "?" + params : ""}`;
        const resp = await fetch(url);
        if (!resp.ok) return [];
        const data = await resp.json();
        const tpls = data.templates || [];
        tplCache[key] = tpls;
        return tpls;
    } catch (e) {
        console.warn("[SceneGen] Fetch error:", e);
        return [];
    }
}

function invalidateCache() {
    for (const k in tplCache) delete tplCache[k];
}


app.registerExtension({
    name: "scene_gen.SceneGenerator",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SceneGenerator") return;

        console.log("[SceneGen] Registering hooks");

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            this._sgTemplates = [];
            this._sgLoaded = false;

            // Grow node for preview
            const origH = this.size[1];
            this.size = [Math.max(this.size[0], 320), origH + 220];
            this.setDirtyCanvas(true, true);

            this._sgRefresh = async () => {
                const st = this.widgets?.find(w => w.name === "scene_type")?.value || RANDOM;
                const sw = this.widgets?.find(w => w.name === "shot_width")?.value || RANDOM;
                this._sgTemplates = await fetchTemplates(st, sw);
                this._sgLoaded = true;
                this.setDirtyCanvas(true, true);
            };

            // Watch all relevant widgets
            const watchNames = ["scene_type", "shot_width", "num_subjects",
                                "template_index", "template_mode"];
            for (const wname of watchNames) {
                const widget = this.widgets?.find(w => w.name === wname);
                if (!widget) continue;
                const origCb = widget.callback;
                widget.callback = (...args) => {
                    const r = origCb?.apply(widget, args);
                    if (wname === "scene_type" || wname === "shot_width") {
                        invalidateCache();
                    }
                    this._sgRefresh();
                    return r;
                };
            }

            this._sgRefresh();
            return result;
        };

        nodeType.prototype.onDrawForeground = function (ctx) {
            if (this.flags?.collapsed) return;
            if (!this.widgets || this.widgets.length === 0) return;

            const nodeW = this.size[0];
            const margin = 8;
            const panelW = nodeW - margin * 2;
            const panelH = 200;

            // Find Y after last widget
            let afterY = 10;
            for (const w of this.widgets) {
                if (w.y !== undefined && w.y !== null) {
                    const widgetH = w.computeSize ? w.computeSize(nodeW)[1] : 26;
                    afterY = Math.max(afterY, w.y + widgetH + 4);
                }
            }

            const px = margin;
            const py = afterY;

            // Panel
            ctx.fillStyle = "rgba(18, 18, 26, 0.95)";
            ctx.fillRect(px, py, panelW, panelH);
            ctx.strokeStyle = "rgba(60, 60, 75, 0.7)";
            ctx.lineWidth = 1;
            ctx.strokeRect(px, py, panelW, panelH);

            // Header
            ctx.fillStyle = "#b0b0c0";
            ctx.font = "bold 11px monospace";
            ctx.textAlign = "left";
            ctx.fillText("📐 Layout Preview", px + 8, py + 16);

            // Active filters summary
            const stVal = this.widgets?.find(w => w.name === "scene_type")?.value || RANDOM;
            const swVal = this.widgets?.find(w => w.name === "shot_width")?.value || RANDOM;
            const nsVal = this.widgets?.find(w => w.name === "num_subjects")?.value;
            const tplMode = this.widgets?.find(w => w.name === "template_mode")?.value || "random";
            const tplIdx = this.widgets?.find(w => w.name === "template_index")?.value || 0;

            // Show filter state with lock/random indicators
            ctx.font = "9px monospace";
            ctx.textAlign = "left";
            let filterX = px + 8;
            const filterY = py + 30;

            const filters = [
                { label: "scene", value: stVal === RANDOM ? "🎲" : stVal.substring(0, 8), random: stVal === RANDOM },
                { label: "shot", value: swVal === RANDOM ? "🎲" : swVal.substring(0, 6), random: swVal === RANDOM },
                { label: "subj", value: nsVal === -1 ? "🎲" : String(nsVal), random: nsVal === -1 },
            ];

            for (const f of filters) {
                ctx.fillStyle = f.random ? "#606068" : "#8a8aaa";
                ctx.fillText(`${f.label}:`, filterX, filterY);
                filterX += ctx.measureText(`${f.label}:`).width + 3;
                ctx.fillStyle = f.random ? "#d0a040" : "#a0c0e0";
                ctx.fillText(f.value, filterX, filterY);
                filterX += ctx.measureText(f.value).width + 12;
            }

            // Template count on right
            ctx.fillStyle = "#707080";
            ctx.textAlign = "right";
            const tpls = this._sgTemplates || [];
            ctx.fillText(`${tpls.length} templates`, px + panelW - 8, py + 16);

            // Preview area
            const innerX = px + 8;
            const innerY = py + 38;
            const innerW = panelW - 16;
            const innerH = panelH - 58;

            ctx.fillStyle = "rgba(25, 25, 32, 0.95)";
            ctx.fillRect(innerX, innerY, innerW, innerH);
            ctx.strokeStyle = "rgba(50, 50, 60, 0.6)";
            ctx.lineWidth = 1;
            ctx.strokeRect(innerX, innerY, innerW, innerH);

            const scaleX = innerW / 1000;
            const scaleY = innerH / 1000;

            // Grid
            ctx.strokeStyle = "rgba(40, 40, 48, 0.7)";
            ctx.lineWidth = 0.5;
            for (let i = 200; i < 1000; i += 200) {
                const gx = innerX + i * scaleX;
                const gy = innerY + i * scaleY;
                ctx.beginPath();
                ctx.moveTo(gx, innerY); ctx.lineTo(gx, innerY + innerH); ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(innerX, gy); ctx.lineTo(innerX + innerW, gy); ctx.stroke();
            }

            if (!this._sgLoaded) {
                ctx.fillStyle = "#707080";
                ctx.font = "10px monospace";
                ctx.textAlign = "center";
                ctx.fillText("Loading...", innerX + innerW / 2, innerY + innerH / 2);
                return;
            }

            if (tpls.length === 0) {
                ctx.fillStyle = "#606068";
                ctx.font = "10px monospace";
                ctx.textAlign = "center";
                ctx.fillText("No templates match these filters", innerX + innerW / 2, innerY + innerH / 2);
                return;
            }

            // Determine template to display
            const showIdx = tplMode === "select" ? Math.min(tplIdx, tpls.length - 1) : 0;
            const tpl = tpls[showIdx];
            if (!tpl) return;

            // Template name
            ctx.fillStyle = "#9090a0";
            ctx.font = "9px monospace";
            ctx.textAlign = "left";
            const name = tpl.name || `Template ${showIdx + 1}`;
            const truncName = name.length > 45 ? name.substring(0, 43) + "…" : name;
            ctx.fillText(truncName, px + 8, py + panelH - 12);

            // ── Collect elements ──
            const elements = [];

            // Determine subject count for preview
            let previewSubj = nsVal;
            if (previewSubj === -1) {
                // Show a representative layout (middle of range)
                const minS = tpl.min_subjects || 0;
                const maxS = Math.min(tpl.max_subjects || 4, 6);
                previewSubj = Math.round((minS + maxS) / 2);
            }

            // Background elements
            for (const bg of (tpl.background_elements || [])) {
                if (bg.bbox && bg.bbox.length === 4) {
                    elements.push({ bbox: bg.bbox, type: "background", label: "BG" });
                }
            }

            // Subject elements
            const layouts = tpl.subject_layouts || {};
            let layoutKey = String(previewSubj);
            if (!(layoutKey in layouts)) {
                const available = Object.keys(layouts).map(Number).sort((a, b) => a - b);
                if (available.length > 0) {
                    let best = available[0];
                    for (const a of available) {
                        if (Math.abs(a - previewSubj) < Math.abs(best - previewSubj)) best = a;
                    }
                    layoutKey = String(best);
                }
            }
            const boxes = layouts[layoutKey] || [];
            let subjIdx = 0;
            for (const box of boxes) {
                subjIdx++;
                elements.push({ bbox: box, type: "subject", label: `S${subjIdx}` });
            }

            // Prop elements
            for (const prop of (tpl.prop_elements || [])) {
                if (prop.bbox && prop.bbox.length === 4) {
                    elements.push({ bbox: prop.bbox, type: "prop", label: "PROP" });
                }
            }

            // Draw boxes
            // bbox format: [ymin, xmin, ymax, xmax] in 0-1000 space
            for (const elem of elements) {
                const [yMin, xMin, yMax, xMax] = elem.bbox;
                const bx = innerX + xMin * scaleX;
                const by = innerY + yMin * scaleY;
                const bw = (xMax - xMin) * scaleX;
                const bh = (yMax - yMin) * scaleY;
                const color = COLORS[elem.type] || COLORS.subject;

                ctx.fillStyle = color.fill;
                ctx.fillRect(bx, by, bw, bh);
                ctx.strokeStyle = color.stroke;
                ctx.lineWidth = 1.5;
                ctx.strokeRect(bx, by, bw, bh);

                // Label
                ctx.font = "bold 9px monospace";
                const textW = ctx.measureText(elem.label).width;
                ctx.fillStyle = color.stroke;
                ctx.fillRect(bx, by, textW + 8, 13);
                ctx.fillStyle = "rgba(0, 0, 0, 0.9)";
                ctx.textAlign = "left";
                ctx.fillText(elem.label, bx + 4, by + 10);
            }

            // If subjects are random, show a hint
            if (nsVal === -1) {
                ctx.fillStyle = "#d0a040";
                ctx.font = "italic 9px monospace";
                ctx.textAlign = "right";
                ctx.fillText("🎲 subjects = preview only",
                    innerX + innerW - 4, innerY + innerH - 4);
            }
        };

        console.log("[SceneGen] Hooks registered");
    },
});

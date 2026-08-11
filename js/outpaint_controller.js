/**
 * Outpaint Controller v4.2 — drag-and-drop + integrated upload
 *
 * Changes from v4.1:
 *   - HTML5 drag-and-drop: drop image files directly from OS onto the node
 *   - Visual feedback overlay during drag-over
 *   - Reuses existing upload pipeline (/upload/image)
 *
 * v4.1:
 *   - Removed image_upload flag (was causing DOM preview to overlay grid)
 *   - Added canvas-drawn upload button in the grid panel header
 *   - Hidden <input type=file> handles actual upload via /upload/image
 */

import { app } from "../../../scripts/app.js";

console.log("[OutpaintController] v4.2 loading...");

const ASPECT_RATIOS = {
    "16:9":  [1.0,       9.0/16.0],
    "3:2":   [1.0,       2.0/3.0],
    "4:3":   [1.0,       3.0/4.0],
    "1:1":   [1.0,       1.0],
    "4:3 v": [3.0/4.0,   1.0],
    "3:2 v": [2.0/3.0,   1.0],
    "9:16":  [9.0/16.0,  1.0],
};

function getTargetDims(node) {
    const arWidget = node.widgets?.find(w => w.name === "aspect_ratio");
    const twWidget = node.widgets?.find(w => w.name === "target_width");
    const thWidget = node.widgets?.find(w => w.name === "target_height");
    const ar = arWidget?.value || "custom";

    if (ar !== "custom" && ASPECT_RATIOS[ar]) {
        const [rw, rh] = ASPECT_RATIOS[ar];
        const longSide = Math.max(twWidget?.value || 1024, thWidget?.value || 1024);
        if (rw >= rh) {
            return { w: longSide, h: Math.max(8, Math.round(longSide * rh / 8) * 8) };
        } else {
            return { w: Math.max(8, Math.round(longSide * rw / 8) * 8), h: longSide };
        }
    }
    return { w: twWidget?.value || 1024, h: thWidget?.value || 1024 };
}

const HANDLE_SIZE = 8;
const HANDLES = ["nw", "ne", "sw", "se"];

// Cache of loaded images: filename → {w, h, img}
const imageCache = new Map();

function fetchSourceImage(filename, subfolder, callback) {
    if (!filename) { callback(null); return; }
    const cacheKey = `${subfolder || ""}/${filename}`;
    if (imageCache.has(cacheKey)) { callback(imageCache.get(cacheKey)); return; }

    const params = new URLSearchParams({ filename, type: "input" });
    if (subfolder) params.set("subfolder", subfolder);

    const img = new Image();
    img.onload = () => {
        const data = { w: img.naturalWidth, h: img.naturalHeight, img };
        imageCache.set(cacheKey, data);
        callback(data);
    };
    img.onerror = () => { callback(null); };
    img.src = `/view?${params.toString()}`;
}

// Upload image via ComfyUI API
async function uploadImage(file, callback) {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("type", "input");
    formData.append("overwrite", "false");

    try {
        const resp = await fetch("/upload/image", {
            method: "POST",
            body: formData,
        });
        const data = await resp.json();
        callback(data); // {name, subfolder, type}
    } catch (e) {
        console.error("[OutpaintController] Upload failed:", e);
        callback(null);
    }
}

// Refresh the file list in a dropdown widget
async function refreshFileList(node) {
    const imgWidget = node.widgets?.find(w => w.name === "image");
    if (!imgWidget) return;
    try {
        const resp = await fetch("/object_info/OutpaintController");
        const data = await resp.json();
        const newNode = data?.OutpaintController;
        if (newNode?.input?.required?.image) {
            const [files] = newNode.input.required.image;
            imgWidget.options.values = files;
            // Don't overwrite current value
        }
    } catch (e) {
        console.warn("[OutpaintController] Could not refresh file list");
    }
}

// --- Drag and Drop ---
let dndListenersAttached = false;
let dndCurrentNode = null;

function getCanvasCoords(e) {
    // Try LiteGraph's built-in conversion first
    if (app.canvas?.adjustMouseEvent) {
        try {
            app.canvas.adjustMouseEvent(e);
            if (e.canvasX !== undefined) return [e.canvasX, e.canvasY];
        } catch (_) {}
    }
    // Manual fallback: compute from DOM rect + canvas camera
    const canvasEl = app.canvas?.canvas || document.querySelector('#graph-canvas');
    if (!canvasEl) return [0, 0];
    const rect = canvasEl.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const scale = app.canvas?.scale || 1;
    const ox = app.canvas?.offset?.[0] || 0;
    const oy = app.canvas?.offset?.[1] || 0;
    return [(x - ox) / scale, (y - oy) / scale];
}

function findOcNodeAt(canvasX, canvasY) {
    if (!app.graph?._nodes) return null;
    for (const node of app.graph._nodes) {
        if (node.type !== "OutpaintController") continue;
        const [nx, ny] = node.pos;
        const [nw, nh] = node.size;
        if (canvasX >= nx && canvasX <= nx + nw &&
            canvasY >= ny && canvasY <= ny + nh) {
            return node;
        }
    }
    return null;
}

function attachDnDListeners() {
    if (dndListenersAttached) return;
    const canvasEl = app.canvas?.canvas || document.querySelector('#graph-canvas');
    if (!canvasEl) {
        setTimeout(attachDnDListeners, 500);
        return;
    }
    dndListenersAttached = true;

    canvasEl.addEventListener('dragover', (e) => {
        if (!e.dataTransfer?.types?.includes('Files')) return;
        const [cx, cy] = getCanvasCoords(e);
        const node = findOcNodeAt(cx, cy);
        if (node) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            if (dndCurrentNode !== node) {
                if (dndCurrentNode) {
                    dndCurrentNode._ocDnDOver = false;
                    dndCurrentNode.setDirtyCanvas(true, true);
                }
                dndCurrentNode = node;
                node._ocDnDOver = true;
                node.setDirtyCanvas(true, true);
            }
        } else if (dndCurrentNode) {
            dndCurrentNode._ocDnDOver = false;
            dndCurrentNode.setDirtyCanvas(true, true);
            dndCurrentNode = null;
        }
    });

    canvasEl.addEventListener('dragleave', () => {
        if (dndCurrentNode) {
            dndCurrentNode._ocDnDOver = false;
            dndCurrentNode.setDirtyCanvas(true, true);
            dndCurrentNode = null;
        }
    });

    canvasEl.addEventListener('drop', async (e) => {
        if (!e.dataTransfer?.files?.length) return;
        const [cx, cy] = getCanvasCoords(e);
        const node = findOcNodeAt(cx, cy);
        if (!node) return;

        e.preventDefault();
        e.stopPropagation();

        if (dndCurrentNode) {
            dndCurrentNode._ocDnDOver = false;
            dndCurrentNode.setDirtyCanvas(true, true);
            dndCurrentNode = null;
        }

        const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith('image/'));
        if (!file) return;

        uploadImage(file, (data) => {
            if (!data) return;
            const imgWidget = node.widgets?.find(w => w.name === 'image');
            if (imgWidget) {
                if (imgWidget.options?.values && !imgWidget.options.values.includes(data.name)) {
                    imgWidget.options.values.push(data.name);
                    imgWidget.options.values.sort();
                }
                imgWidget.value = data.name;
                if (imgWidget.callback) imgWidget.callback(data.name);
            }
        });
    });

    console.log("[OutpaintController] Drag-and-drop listeners attached");
}

app.registerExtension({
    name: "EllieFoxAI.OutpaintController",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "OutpaintController") return;

        attachDnDListeners();

        console.log("[OutpaintController] v4.2 registering hooks");

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            let hovering = false;
            let dragMode = null;
            let dragHandle = null;
            let hoverHandle = null;
            let hoverOnSource = false;
            let hoverNx = 0.5, hoverNy = 0.5;
            let hoverUpload = false;
            let resizeStartDist = 0;
            let resizeStartSR = 0;
            let sourcePreview = null;
            let sourceDims = { w: 0, h: 0 };

            const origW = this.size[0];
            const origH = this.size[1];
            this.size = [Math.max(origW, 340), origH + 280];
            this.setDirtyCanvas(true, true);

            const getWidget = (name) => this.widgets?.find(w => w.name === name);
            const self = this;

            // Hidden file input for upload
            const fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.accept = "image/*";
            fileInput.style.display = "none";
            function selectUploadedImage(data) {
                if (!data) return;
                const imgWidget = getWidget("image");
                if (imgWidget) {
                    // Add to dropdown if not already listed
                    if (imgWidget.options?.values && !imgWidget.options.values.includes(data.name)) {
                        imgWidget.options.values.push(data.name);
                        imgWidget.options.values.sort();
                    }
                    imgWidget.value = data.name;
                    if (imgWidget.callback) imgWidget.callback(data.name);
                }
            }

            fileInput.addEventListener("change", async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                uploadImage(file, selectUploadedImage);
                fileInput.value = ""; // reset for re-upload
            });
            document.body.appendChild(fileInput);

            // --- Load image from widget for preview + dims ---
            function refreshSourceImage() {
                const imgWidget = getWidget("image");
                if (!imgWidget) return;
                const filename = imgWidget.value;
                if (!filename) { sourcePreview = null; sourceDims = { w: 0, h: 0 }; return; }

                fetchSourceImage(filename, "", (data) => {
                    if (data) {
                        sourcePreview = data.img;
                        sourceDims = { w: data.w, h: data.h };
                        // Auto-populate source_resize to natural longest edge
                        // so resize handles work from the actual displayed size
                        const srWidget = getWidget("source_resize");
                        if (srWidget) {
                            srWidget.value = Math.max(data.w, data.h);
                        }
                    } else {
                        sourcePreview = null;
                        sourceDims = { w: 0, h: 0 };
                    }
                    self.setDirtyCanvas(true, true);
                });
            }

            setTimeout(() => refreshSourceImage(), 300);

            // Hook image widget callback for swaps
            const imgWidget = getWidget("image");
            if (imgWidget) {
                const origCb = imgWidget.callback;
                imgWidget.callback = (...args) => {
                    const r = origCb?.apply(imgWidget, args);
                    refreshSourceImage();
                    return r;
                };
            }

            // --- Upload button geometry ---
            function getUploadBtnRect(g) {
                const btnW = 70;
                const btnH = 16;
                return {
                    x: g.px + g.panelW - btnW - 8,
                    y: g.py + 4,
                    w: btnW,
                    h: btnH,
                };
            }

            // --- Geometry ---
            function getEffectiveSourceDims(tw, th) {
                let sw = sourceDims.w;
                let sh = sourceDims.h;
                if (sw <= 0 || sh <= 0) {
                    const est = Math.min(tw, th) * 0.6;
                    return { sw: est, sh: est, estimated: true };
                }
                const srWidget = getWidget("source_resize");
                const sr = srWidget?.value || 0;
                if (sr > 0) {
                    const longest = Math.max(sw, sh);
                    if (longest > sr) {
                        const scale = sr / longest;
                        sw *= scale; sh *= scale;
                    }
                }
                if (sw > tw || sh > th) {
                    const scale = Math.min(tw / sw, th / sh);
                    sw *= scale; sh *= scale;
                }
                return { sw, sh, estimated: false };
            }

            function getMaxSourceResize(tw, th) {
                let sw = sourceDims.w;
                let sh = sourceDims.h;
                if (sw <= 0 || sh <= 0) return Math.max(tw, th);
                const longest = Math.max(sw, sh);
                const maxByW = tw * longest / sw;
                const maxByH = th * longest / sh;
                return Math.min(maxByW, maxByH);
            }

            function getGridGeom(node) {
                const nodeW = node.size[0];
                const margin = 8;
                const panelW = nodeW - margin * 2;
                const panelH = 240;

                let afterY = 10;
                for (const w of node.widgets || []) {
                    if (w.y !== undefined && w.y !== null) {
                        const widgetH = w.computeSize ? w.computeSize(nodeW)[1] : 26;
                        afterY = Math.max(afterY, w.y + widgetH + 4);
                    }
                }

                const innerSize = Math.min(panelW - 16, panelH - 44);
                const { w: tw, h: th } = getTargetDims(node);
                const { sw: srcW, sh: srcH, estimated } = getEffectiveSourceDims(tw, th);

                const targetScale = innerSize / Math.max(tw, th);
                const fw = tw * targetScale;
                const fh = th * targetScale;
                const sw_scaled = srcW * targetScale;
                const sh_scaled = srcH * targetScale;

                const px = margin;
                const py = afterY;
                const gridX = px + 8 + (panelW - 16 - innerSize) / 2;
                const gridY = py + 26;
                const foffX = gridX + (innerSize - fw) / 2;
                const foffY = gridY + (innerSize - fh) / 2;

                const availW = Math.max(0, fw - sw_scaled);
                const availH = Math.max(0, fh - sh_scaled);

                return {
                    gridX, gridY, innerSize,
                    foffX, foffY, fw, fh,
                    sw_scaled, sh_scaled,
                    availW, availH,
                    tw, th, srcW, srcH,
                    targetScale, estimated,
                    panelW, panelH, px, py, margin,
                    srcX: foffX + (parseFloat(getWidget("center_x")?.value ?? 0.5)) * availW,
                    srcY: foffY + (parseFloat(getWidget("center_y")?.value ?? 0.5)) * availH,
                };
            }

            function dist(ax, ay, bx, by) {
                return Math.sqrt((ax - bx) ** 2 + (ay - by) ** 2);
            }

            function getHandlePositions(g) {
                const hs = HANDLE_SIZE;
                return {
                    nw: [g.srcX - hs/2, g.srcY - hs/2],
                    ne: [g.srcX + g.sw_scaled - hs/2, g.srcY - hs/2],
                    sw: [g.srcX - hs/2, g.srcY + g.sh_scaled - hs/2],
                    se: [g.srcX + g.sw_scaled - hs/2, g.srcY + g.sh_scaled - hs/2],
                };
            }

            function hitTest(g, lx, ly) {
                // Upload button check
                const btn = getUploadBtnRect(g);
                if (lx >= btn.x && lx <= btn.x + btn.w &&
                    ly >= btn.y && ly <= btn.y + btn.h) {
                    return { type: "upload" };
                }

                const handles = getHandlePositions(g);
                const hs = HANDLE_SIZE;
                for (const h of HANDLES) {
                    const [hx, hy] = handles[h];
                    if (lx >= hx - 2 && lx <= hx + hs + 2 &&
                        ly >= hy - 2 && ly <= hy + hs + 2) {
                        return { type: "handle", handle: h };
                    }
                }
                if (lx >= g.srcX && lx <= g.srcX + g.sw_scaled &&
                    ly >= g.srcY && ly <= g.srcY + g.sh_scaled) {
                    return { type: "source" };
                }
                if (lx >= g.foffX && lx <= g.foffX + g.fw &&
                    ly >= g.foffY && ly <= g.foffY + g.fh) {
                    return { type: "frame" };
                }
                return null;
            }

            function pointToNorm(g, lx, ly) {
                const travelW = g.fw - g.sw_scaled;
                const travelH = g.fh - g.sh_scaled;
                if (travelW <= 0 && travelH <= 0) return { nx: 0.5, ny: 0.5 };
                const nx = travelW > 0 ? (lx - g.foffX - g.sw_scaled / 2) / travelW : 0.5;
                const ny = travelH > 0 ? (ly - g.foffY - g.sh_scaled / 2) / travelH : 0.5;
                return {
                    nx: Math.max(0, Math.min(1, nx)),
                    ny: Math.max(0, Math.min(1, ny))
                };
            }

            // --- Drawing ---
            this._ocDraw = (ctx) => {
                if (this.flags?.collapsed) return;
                if (!this.widgets || this.widgets.length === 0) return;

                const cxWidget = getWidget("center_x");
                const cyWidget = getWidget("center_y");
                const cx = parseFloat(cxWidget?.value ?? 0.5);
                const cy = parseFloat(cyWidget?.value ?? 0.5);
                const g = getGridGeom(this);

                // Panel background
                ctx.fillStyle = "rgba(18, 18, 26, 0.95)";
                ctx.fillRect(g.px, g.py, g.panelW, g.panelH);
                ctx.strokeStyle = "rgba(60, 60, 75, 0.7)";
                ctx.lineWidth = 1;
                ctx.strokeRect(g.px, g.py, g.panelW, g.panelH);

                // Header text
                ctx.fillStyle = "#b0b0c0";
                ctx.font = "bold 11px monospace";
                ctx.textAlign = "left";
                const srcLabel = g.estimated
                    ? `${Math.round(g.srcW)}×${Math.round(g.srcH)} (est.)`
                    : `${Math.round(g.srcW)}×${Math.round(g.srcH)}`;
                ctx.fillText(`🎯 ${g.tw}×${g.th} · src ${srcLabel}`, g.px + 8, g.py + 16);

                // Upload button
                const btn = getUploadBtnRect(g);
                ctx.fillStyle = hoverUpload ? "rgba(122, 184, 255, 0.3)" : "rgba(122, 184, 255, 0.15)";
                ctx.fillRect(btn.x, btn.y, btn.w, btn.h);
                ctx.strokeStyle = hoverUpload ? "#9fd0ff" : "rgba(122, 184, 255, 0.5)";
                ctx.lineWidth = 1;
                ctx.strokeRect(btn.x, btn.y, btn.w, btn.h);
                ctx.fillStyle = hoverUpload ? "#cfe8ff" : "#8ab4f0";
                ctx.font = "10px monospace";
                ctx.textAlign = "center";
                ctx.fillText("📁 Upload", btn.x + btn.w / 2, btn.y + 12);

                // Grid background
                ctx.fillStyle = "rgba(25, 25, 32, 0.95)";
                ctx.fillRect(g.gridX, g.gridY, g.innerSize, g.innerSize);

                // Target frame
                ctx.strokeStyle = "rgba(80, 80, 95, 0.8)";
                ctx.lineWidth = 1.5;
                ctx.strokeRect(g.foffX, g.foffY, g.fw, g.fh);

                const sx = g.srcX;
                const sy = g.srcY;

                // Padding regions
                ctx.fillStyle = "rgba(100, 150, 255, 0.10)";
                if (sy > g.foffY) ctx.fillRect(g.foffX, g.foffY, g.fw, sy - g.foffY);
                if (sy + g.sh_scaled < g.foffY + g.fh)
                    ctx.fillRect(g.foffX, sy + g.sh_scaled, g.fw, (g.foffY + g.fh) - (sy + g.sh_scaled));
                if (sx > g.foffX) ctx.fillRect(g.foffX, sy, sx - g.foffX, g.sh_scaled);
                if (sx + g.sw_scaled < g.foffX + g.fw)
                    ctx.fillRect(sx + g.sw_scaled, sy, (g.foffX + g.fw) - (sx + g.sw_scaled), g.sh_scaled);

                // Grid lines
                ctx.strokeStyle = "rgba(255,255,255,0.04)";
                ctx.lineWidth = 1;
                for (let i = 1; i < 4; i++) {
                    const gx2 = g.gridX + (g.innerSize / 4) * i;
                    ctx.beginPath(); ctx.moveTo(gx2, g.gridY); ctx.lineTo(gx2, g.gridY + g.innerSize); ctx.stroke();
                    const gy2 = g.gridY + (g.innerSize / 4) * i;
                    ctx.beginPath(); ctx.moveTo(g.gridX, gy2); ctx.lineTo(g.gridX + g.innerSize, gy2); ctx.stroke();
                }

                // Source image preview
                if (sourcePreview && sourcePreview.complete && sourcePreview.naturalWidth > 0) {
                    ctx.save();
                    ctx.beginPath();
                    ctx.rect(sx, sy, g.sw_scaled, g.sh_scaled);
                    ctx.clip();
                    ctx.drawImage(sourcePreview, sx, sy, g.sw_scaled, g.sh_scaled);
                    ctx.restore();
                } else {
                    ctx.fillStyle = "rgba(122, 184, 255, 0.08)";
                    ctx.fillRect(sx, sy, g.sw_scaled, g.sh_scaled);
                }

                // Source border
                const bodyHighlight = (dragMode === "move") || (hovering && hoverOnSource && dragMode !== "resize");
                ctx.strokeStyle = bodyHighlight ? "#9fd0ff" : "#7ab8ff";
                ctx.lineWidth = bodyHighlight ? 2.5 : 2;
                ctx.strokeRect(sx, sy, g.sw_scaled, g.sh_scaled);

                // Centerpoint crosshair
                const dotX = sx + g.sw_scaled / 2;
                const dotY = sy + g.sh_scaled / 2;
                ctx.strokeStyle = "rgba(255,255,255,0.6)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(dotX - 7, dotY); ctx.lineTo(dotX + 7, dotY);
                ctx.moveTo(dotX, dotY - 7); ctx.lineTo(dotX, dotY + 7);
                ctx.stroke();

                // Corner handles
                const handles = getHandlePositions(g);
                for (const h of HANDLES) {
                    const [hx, hy] = handles[h];
                    const isActive = (dragMode === "resize" && dragHandle === h) ||
                                     (hovering && hoverHandle === h && dragMode !== "move");
                    if (isActive) {
                        ctx.fillStyle = "#9fd0ff";
                        ctx.fillRect(hx - 1, hy - 1, HANDLE_SIZE + 2, HANDLE_SIZE + 2);
                    } else {
                        ctx.fillStyle = "#7ab8ff";
                    }
                    ctx.fillRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);
                    ctx.strokeStyle = "rgba(0,0,0,0.5)";
                    ctx.lineWidth = 1;
                    ctx.strokeRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);
                }

                // Hover ghost
                if (hovering && !hoverOnSource && hoverHandle === null && dragMode === null && !hoverUpload) {
                    const hx = g.foffX + hoverNx * g.availW;
                    const hy = g.foffY + hoverNy * g.availH;
                    ctx.strokeStyle = "rgba(255,255,255,0.20)";
                    ctx.lineWidth = 1;
                    ctx.setLineDash([3, 3]);
                    ctx.strokeRect(hx, hy, g.sw_scaled, g.sh_scaled);
                    ctx.setLineDash([]);
                }

                // Padding readout
                const padL = Math.max(0, Math.round(cx * (g.tw - g.srcW)));
                const padR = Math.max(0, Math.round((g.tw - g.srcW) - cx * (g.tw - g.srcW)));
                const padT = Math.max(0, Math.round(cy * (g.th - g.srcH)));
                const padB = Math.max(0, Math.round((g.th - g.srcH) - cy * (g.th - g.srcH)));
                ctx.fillStyle = "#8a8a9a";
                ctx.font = "10px monospace";
                ctx.textAlign = "center";
                ctx.fillText(`L:${padL}  R:${padR}  T:${padT}  B:${padB}`,
                    g.px + g.panelW / 2, g.py + g.panelH - 8);

                // Drag-and-drop overlay
                if (self._ocDnDOver) {
                    ctx.fillStyle = "rgba(122, 184, 255, 0.12)";
                    ctx.fillRect(g.px, g.py, g.panelW, g.panelH);
                    ctx.strokeStyle = "#9fd0ff";
                    ctx.lineWidth = 2.5;
                    ctx.setLineDash([6, 4]);
                    ctx.strokeRect(g.px + 2, g.py + 2, g.panelW - 4, g.panelH - 4);
                    ctx.setLineDash([]);
                    ctx.fillStyle = "#cfe8ff";
                    ctx.font = "bold 13px monospace";
                    ctx.textAlign = "center";
                    ctx.fillText("📂 Drop image to upload", g.px + g.panelW / 2, g.py + g.panelH / 2 + 5);
                }
            };

            // --- Mouse ---
            function applyMove(g, pos) {
                const result = pointToNorm(g, pos[0], pos[1]);
                if (!result) return false;
                const cxWidget2 = getWidget("center_x");
                const cyWidget2 = getWidget("center_y");
                if (!cxWidget2 || !cyWidget2) return false;
                cxWidget2.value = Math.round(result.nx * 100) / 100;
                cyWidget2.value = Math.round(result.ny * 100) / 100;
                self.setDirtyCanvas(true, true);
                return true;
            }

            function applyResize(g, pos) {
                const srWidget = getWidget("source_resize");
                if (!srWidget) return;
                const centerX = g.srcX + g.sw_scaled / 2;
                const centerY = g.srcY + g.sh_scaled / 2;
                const currentDist = dist(pos[0], pos[1], centerX, centerY);
                if (resizeStartDist < 1) return;
                const ratio = currentDist / resizeStartDist;
                let newSR = Math.round(resizeStartSR * ratio / 8) * 8;
                newSR = Math.max(8, newSR);
                const maxSR = getMaxSourceResize(g.tw, g.th);
                newSR = Math.min(newSR, Math.floor(maxSR / 8) * 8);
                srWidget.value = newSR;
                self.setDirtyCanvas(true, true);
            }

            this._ocMouseDown = function (pos) {
                const g = getGridGeom(self);
                const hit = hitTest(g, pos[0], pos[1]);
                if (!hit) return false;

                if (hit.type === "upload") {
                    fileInput.click();
                    return true;
                }

                if (hit.type === "handle") {
                    dragMode = "resize";
                    dragHandle = hit.handle;
                    const centerX = g.srcX + g.sw_scaled / 2;
                    const centerY = g.srcY + g.sh_scaled / 2;
                    resizeStartDist = dist(pos[0], pos[1], centerX, centerY);
                    resizeStartSR = parseFloat(getWidget("source_resize")?.value || 0);
                    self.setDirtyCanvas(true, true);
                    return true;
                }

                if (hit.type === "source" || hit.type === "frame") {
                    applyMove(g, pos);
                    dragMode = "move";
                    self.setDirtyCanvas(true, true);
                    return true;
                }

                return false;
            };

            this._ocMouseMove = function (pos) {
                if (dragMode === "move") {
                    const g = getGridGeom(self);
                    applyMove(g, pos);
                } else if (dragMode === "resize") {
                    const g = getGridGeom(self);
                    applyResize(g, pos);
                } else {
                    const g = getGridGeom(self);
                    const hit = hitTest(g, pos[0], pos[1]);
                    const wasHovering = hovering;
                    const wasHandle = hoverHandle;
                    const wasOnSource = hoverOnSource;
                    const wasUpload = hoverUpload;
                    hovering = !!hit;
                    hoverUpload = hit?.type === "upload";
                    hoverHandle = hit?.type === "handle" ? hit.handle : null;
                    hoverOnSource = hit?.type === "source";
                    if (hit?.type === "frame") {
                        const result = pointToNorm(g, pos[0], pos[1]);
                        if (result) { hoverNx = result.nx; hoverNy = result.ny; }
                    }
                    if (wasHovering || hovering || wasHandle !== hoverHandle ||
                        wasOnSource !== hoverOnSource || wasUpload !== hoverUpload) {
                        self.setDirtyCanvas(true, true);
                    }
                }
            };

            this._ocMouseUp = function () {
                if (dragMode) {
                    dragMode = null;
                    dragHandle = null;
                    self.setDirtyCanvas(true, true);
                }
            };

            this._ocMouseLeave = function () {
                hovering = false;
                hoverHandle = null;
                hoverOnSource = false;
                hoverUpload = false;
                dragMode = null;
                dragHandle = null;
                self.setDirtyCanvas(true, true);
            };

            // Watch widgets for redraw
            const watchNames = [
                "center_x", "center_y",
                "target_width", "target_height",
                "source_resize", "aspect_ratio",
                "edge_crop"
            ];
            for (const wname of watchNames) {
                const widget = this.widgets?.find(w => w.name === wname);
                if (!widget) continue;
                const origCb = widget.callback;
                widget.callback = (...args) => {
                    const r = origCb?.apply(widget, args);
                    self.setDirtyCanvas(true, true);
                    return r;
                };
            }

            console.log("[OutpaintController] v4.2 hooks registered");
            return result;
        };

        nodeType.prototype.onDrawForeground = function (ctx) {
            if (this.flags?.collapsed) return;
            if (this._ocDraw) this._ocDraw(ctx);
        };

        nodeType.prototype.onMouseDown = function (e, pos) {
            if (this._ocMouseDown) return this._ocMouseDown(pos);
            return false;
        };
        nodeType.prototype.onMouseMove = function (e, pos) {
            if (this._ocMouseMove) this._ocMouseMove(pos);
        };
        nodeType.prototype.onMouseUp = function (e, pos) {
            if (this._ocMouseUp) return this._ocMouseUp(pos);
        };
        nodeType.prototype.onMouseLeave = function (e, pos) {
            if (this._ocMouseLeave) this._ocMouseLeave(pos);
        };

        console.log("[OutpaintController] v4.2 loaded");
    },
});

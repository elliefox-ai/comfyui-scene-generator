/**
 * Inpaint Painter v1.1 — direct-canvas mask painting + drag-and-drop
 *
 * Paint masks directly on the node canvas. No popup editors.
 * Modes: Paint (default), Erase, Clear.
 * Drop image files from OS directly onto the node.
 * Mouse immediately paints — no mode switching needed to start.
 *
 * Mask is rendered to an offscreen canvas at source resolution,
 * serialized as base64 PNG into the mask_data widget on mouseup.
 */

import { app } from "../../../scripts/app.js";

console.log("[InpaintPainter] v1.1 loading...");

// Cache of loaded images
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

async function uploadImage(file, callback) {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("type", "input");
    formData.append("overwrite", "false");
    try {
        const resp = await fetch("/upload/image", { method: "POST", body: formData });
        const data = await resp.json();
        callback(data);
    } catch (e) {
        console.error("[InpaintPainter] Upload failed:", e);
        callback(null);
    }
}

// --- Drag and Drop ---
let dndListenersAttached = false;
let dndCurrentNode = null;

function getCanvasCoords(e) {
    if (app.canvas?.adjustMouseEvent) {
        try {
            app.canvas.adjustMouseEvent(e);
            if (e.canvasX !== undefined) return [e.canvasX, e.canvasY];
        } catch (_) {}
    }
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

function findIpNodeAt(canvasX, canvasY) {
    if (!app.graph?._nodes) return null;
    for (const node of app.graph._nodes) {
        if (node.type !== "InpaintPainter") continue;
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
        const node = findIpNodeAt(cx, cy);
        if (node) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            if (dndCurrentNode !== node) {
                if (dndCurrentNode) {
                    dndCurrentNode._ipDnDOver = false;
                    dndCurrentNode.setDirtyCanvas(true, true);
                }
                dndCurrentNode = node;
                node._ipDnDOver = true;
                node.setDirtyCanvas(true, true);
            }
        } else if (dndCurrentNode) {
            dndCurrentNode._ipDnDOver = false;
            dndCurrentNode.setDirtyCanvas(true, true);
            dndCurrentNode = null;
        }
    });

    canvasEl.addEventListener('dragleave', () => {
        if (dndCurrentNode) {
            dndCurrentNode._ipDnDOver = false;
            dndCurrentNode.setDirtyCanvas(true, true);
            dndCurrentNode = null;
        }
    });

    canvasEl.addEventListener('drop', async (e) => {
        if (!e.dataTransfer?.files?.length) return;
        const [cx, cy] = getCanvasCoords(e);
        const node = findIpNodeAt(cx, cy);
        if (!node) return;

        e.preventDefault();
        e.stopPropagation();

        if (dndCurrentNode) {
            dndCurrentNode._ipDnDOver = false;
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

    console.log("[InpaintPainter] Drag-and-drop listeners attached");
}

app.registerExtension({
    name: "EllieFoxAI.InpaintPainter",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "InpaintPainter") return;

        console.log("[InpaintPainter] v1.1 registering hooks");

        attachDnDListeners();

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const self = this;

            // State
            let sourceImg = null;
            let sourceW = 0, sourceH = 0;
            let lastFetchedImage = ""; // tracks current preview to detect external changes (clipspace, workflow load)
            let displayScale = 1;
            let isPainting = false;
            let lastPaintX = -1, lastPaintY = -1;
            let strokeOriginX = -1, strokeOriginY = -1; // anchor for shift-constrain
            let paintMode = "paint"; // "paint" | "erase"
            let hovering = false;
            let hoverX = 0, hoverY = 0;
            let hoverMode = null;
            let shiftHeld = false;

            // Track shift key for axis-constrained painting
            const onKeyDown = (e) => {
                if (e.key === 'Shift') { shiftHeld = true; self.setDirtyCanvas(true, true); }
            };
            const onKeyUp = (e) => {
                if (e.key === 'Shift') { shiftHeld = false; self.setDirtyCanvas(true, true); }
            };
            document.addEventListener('keydown', onKeyDown);
            document.addEventListener('keyup', onKeyUp);

            // Clean up listeners when node is removed
            const origOnRemoved = self.onRemoved;
            self.onRemoved = function () {
                document.removeEventListener('keydown', onKeyDown);
                document.removeEventListener('keyup', onKeyUp);
                return origOnRemoved?.apply(self, arguments);
            };

            // Offscreen mask canvas (at source resolution)
            let maskCanvas = null;
            let maskCtx = null;

            // Expand node size
            const origW = this.size[0];
            const origH = this.size[1];
            this.size = [Math.max(origW, 340), origH + 320];
            this.setDirtyCanvas(true, true);

            const getWidget = (name) => this.widgets?.find(w => w.name === name);

            // Hidden file input for upload button
            const fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.accept = "image/*";
            fileInput.style.display = "none";
            fileInput.addEventListener("change", (e) => {
                const file = e.target.files[0];
                if (!file) return;
                uploadImage(file, (data) => {
                    if (!data) return;
                    const imgWidget = getWidget("image");
                    if (imgWidget) {
                        if (imgWidget.options?.values && !imgWidget.options.values.includes(data.name)) {
                            imgWidget.options.values.push(data.name);
                            imgWidget.options.values.sort();
                        }
                        imgWidget.value = data.name;
                        if (imgWidget.callback) imgWidget.callback(data.name);
                    }
                });
                fileInput.value = "";
            });
            document.body.appendChild(fileInput);

            // --- Initialize mask canvas ---
            function initMaskCanvas(w, h) {
                if (!maskCanvas) {
                    maskCanvas = document.createElement("canvas");
                    maskCtx = maskCanvas.getContext("2d");
                }
                if (maskCanvas.width !== w || maskCanvas.height !== h) {
                    maskCanvas.width = w;
                    maskCanvas.height = h;
                    maskCtx.clearRect(0, 0, w, h);
                    serializeMask();
                }
            }

            // --- Serialize mask to base64 PNG in widget ---
            function serializeMask() {
                if (!maskCanvas || !maskCtx) return;
                const imgData = maskCtx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
                let hasContent = false;
                for (let i = 3; i < imgData.data.length; i += 4) {
                    if (imgData.data[i] > 0) { hasContent = true; break; }
                }
                const mdWidget = getWidget("mask_data");
                if (!mdWidget) return;
                if (hasContent) {
                    mdWidget.value = maskCanvas.toDataURL("image/png");
                } else {
                    mdWidget.value = "";
                }
            }

            // --- Load image ---
            function refreshSourceImage() {
                const imgWidget = getWidget("image");
                if (!imgWidget) return;
                const filename = imgWidget.value;
                if (!filename) { sourceImg = null; sourceW = 0; sourceH = 0; lastFetchedImage = ""; return; }

                fetchSourceImage(filename, "", (data) => {
                    if (data) {
                        sourceImg = data.img;
                        sourceW = data.w;
                        sourceH = data.h;
                        lastFetchedImage = filename;
                        initMaskCanvas(sourceW, sourceH);
                    } else {
                        sourceImg = null;
                        sourceW = 0;
                        sourceH = 0;
                    }
                    self.setDirtyCanvas(true, true);
                });
            }

            setTimeout(() => refreshSourceImage(), 300);

            // Hook image widget callback
            const imgWidget = getWidget("image");
            if (imgWidget) {
                const origCb = imgWidget.callback;
                imgWidget.callback = (...args) => {
                    const r = origCb?.apply(imgWidget, args);
                    refreshSourceImage();
                    return r;
                };
            }

            // --- Geometry ---
            function getPanelGeom() {
                const nodeW = self.size[0];
                const margin = 8;
                const panelW = nodeW - margin * 2;
                let afterY = 10;
                for (const w of self.widgets || []) {
                    if (w.y !== undefined && w.y !== null) {
                        const widgetH = w.computeSize ? w.computeSize(nodeW)[1] : 26;
                        afterY = Math.max(afterY, w.y + widgetH + 4);
                    }
                }

                const toolbarH = 28;
                const px = margin;
                const py = afterY;
                const panelH = self.size[1] - py - 4;
                const imgAreaH = panelH - toolbarH - 8;
                const imgAreaW = panelW - 16;

                let dw = 0, dh = 0;
                if (sourceW > 0 && sourceH > 0) {
                    const scaleFit = Math.min(imgAreaW / sourceW, imgAreaH / sourceH, 1.0);
                    dw = sourceW * scaleFit;
                    dh = sourceH * scaleFit;
                    displayScale = scaleFit;
                }

                const imgX = px + 8 + (imgAreaW - dw) / 2;
                const imgY = py + toolbarH + (imgAreaH - dh) / 2;

                return { px, py, panelW, panelH, imgX, imgY, imgW: dw, imgH: dh, imgAreaW, imgAreaH, toolbarH, margin };
            }

            // --- Mode buttons geometry ---
            function getButtons(g) {
                const btnW = 60;
                const btnH = 18;
                const gap = 6;
                const uploadW = 60;
                const startX = g.px + 8;

                return {
                    paint:  { x: startX,                    y: g.py + 5, w: btnW,    h: btnH, label: "🖌 Paint" },
                    erase:  { x: startX + (btnW + gap),      y: g.py + 5, w: btnW,    h: btnH, label: "🧹 Erase" },
                    clear:  { x: startX + (btnW + gap) * 2,  y: g.py + 5, w: btnW,    h: btnH, label: "✖ Clear" },
                    upload: { x: startX + (btnW + gap) * 3,  y: g.py + 5, w: uploadW, h: btnH, label: "📁 Upload" },
                };
            }

            // --- Coordinate conversion: local canvas → mask canvas ---
            function canvasToMask(g, lx, ly) {
                if (displayScale <= 0) return null;
                const mx = (lx - g.imgX) / displayScale;
                const my = (ly - g.imgY) / displayScale;
                if (mx < 0 || mx >= sourceW || my < 0 || my >= sourceH) return null;
                return [mx, my];
            }

            // --- Paint at mask coordinates ---
            function paintAtMask(mx, my, prevMx, prevMy) {
                if (!maskCtx) return;
                const brushWidget = getWidget("brush_size");
                const radius = (brushWidget?.value || 32) / 2 / displayScale;

                if (paintMode === "paint") {
                    maskCtx.globalCompositeOperation = "source-over";
                    maskCtx.fillStyle = "rgba(255, 255, 255, 1)";
                    maskCtx.strokeStyle = "rgba(255, 255, 255, 1)";
                } else {
                    maskCtx.globalCompositeOperation = "destination-out";
                    maskCtx.fillStyle = "rgba(0, 0, 0, 1)";
                    maskCtx.strokeStyle = "rgba(0, 0, 0, 1)";
                }
                maskCtx.lineWidth = radius * 2;
                maskCtx.lineCap = "round";
                maskCtx.lineJoin = "round";

                maskCtx.beginPath();
                maskCtx.arc(mx, my, radius, 0, Math.PI * 2);
                maskCtx.fill();

                if (prevMx >= 0 && prevMy >= 0) {
                    maskCtx.beginPath();
                    maskCtx.moveTo(prevMx, prevMy);
                    maskCtx.lineTo(mx, my);
                    maskCtx.stroke();
                }
            }

            // --- Hit testing ---
            function hitTest(g, btns, lx, ly) {
                for (const [name, btn] of Object.entries(btns)) {
                    if (lx >= btn.x && lx <= btn.x + btn.w &&
                        ly >= btn.y && ly <= btn.y + btn.h) {
                        return { type: "button", button: name };
                    }
                }
                if (sourceImg && lx >= g.imgX && lx <= g.imgX + g.imgW &&
                    ly >= g.imgY && ly <= g.imgY + g.imgH) {
                    return { type: "canvas" };
                }
                return null;
            }

            // --- Drawing ---
            this._ipDraw = (ctx) => {
                if (self.flags?.collapsed) return;
                if (!self.widgets || self.widgets.length === 0) return;

                // Auto-detect external widget value changes (clipspace paste, workflow load)
                const curImgWidget = getWidget("image");
                if (curImgWidget && curImgWidget.value && curImgWidget.value !== lastFetchedImage) {
                    refreshSourceImage();
                }

                const g = getPanelGeom();
                const btns = getButtons(g);

                // Panel background
                ctx.fillStyle = "rgba(18, 18, 26, 0.95)";
                ctx.fillRect(g.px, g.py, g.panelW, g.panelH);
                ctx.strokeStyle = "rgba(60, 60, 75, 0.7)";
                ctx.lineWidth = 1;
                ctx.strokeRect(g.px, g.py, g.panelW, g.panelH);

                // Toolbar buttons
                for (const [name, btn] of Object.entries(btns)) {
                    const isActive = (name === "paint" && paintMode === "paint") ||
                                     (name === "erase" && paintMode === "erase");
                    const isHover = hoverMode === name;

                    if (isActive) {
                        ctx.fillStyle = "rgba(122, 184, 255, 0.35)";
                    } else if (isHover) {
                        ctx.fillStyle = "rgba(122, 184, 255, 0.18)";
                    } else {
                        ctx.fillStyle = "rgba(122, 184, 255, 0.08)";
                    }
                    ctx.fillRect(btn.x, btn.y, btn.w, btn.h);

                    ctx.strokeStyle = isActive ? "#9fd0ff" : (isHover ? "rgba(122,184,255,0.6)" : "rgba(122,184,255,0.3)");
                    ctx.lineWidth = 1;
                    ctx.strokeRect(btn.x, btn.y, btn.w, btn.h);

                    ctx.fillStyle = isActive ? "#cfe8ff" : (isHover ? "#b0d4f8" : "#7ab8ff");
                    ctx.font = "10px monospace";
                    ctx.textAlign = "center";
                    ctx.fillText(btn.label, btn.x + btn.w / 2, btn.y + 13);
                }

                // Image area
                if (sourceImg && sourceImg.complete && sourceW > 0) {
                    ctx.fillStyle = "rgba(25, 25, 32, 0.95)";
                    ctx.fillRect(g.imgX, g.imgY, g.imgW, g.imgH);

                    ctx.drawImage(sourceImg, g.imgX, g.imgY, g.imgW, g.imgH);

                    if (maskCanvas) {
                        ctx.save();
                        ctx.globalAlpha = 0.5;
                        ctx.drawImage(maskCanvas, g.imgX, g.imgY, g.imgW, g.imgH);
                        ctx.restore();
                    }

                    ctx.strokeStyle = "rgba(80, 80, 95, 0.8)";
                    ctx.lineWidth = 1;
                    ctx.strokeRect(g.imgX, g.imgY, g.imgW, g.imgH);

                    // Brush cursor
                    if (hovering && paintMode !== null) {
                        const brushWidget = getWidget("brush_size");
                        const r = (brushWidget?.value || 32) / 2;
                        ctx.strokeStyle = paintMode === "paint" ? "rgba(159, 208, 255, 0.8)" : "rgba(255, 150, 150, 0.8)";
                        ctx.lineWidth = 1.5;
                        ctx.setLineDash([3, 3]);
                        ctx.beginPath();
                        ctx.arc(hoverX, hoverY, r, 0, Math.PI * 2);
                        ctx.stroke();
                        ctx.setLineDash([]);
                    }
                } else {
                    ctx.fillStyle = "#8a8a9a";
                    ctx.font = "11px monospace";
                    ctx.textAlign = "center";
                    ctx.fillText("Upload or select an image to begin painting",
                        g.px + g.panelW / 2, g.py + g.panelH / 2);
                }

                // Info readout
                if (sourceW > 0) {
                    ctx.fillStyle = "#8a8a9a";
                    ctx.font = "10px monospace";
                    ctx.textAlign = "left";
                    const shiftTag = shiftHeld ? " · shift-lock" : "";
                    ctx.fillText(`${sourceW}×${sourceH} · brush: ${getWidget("brush_size")?.value || 32}px · mode: ${paintMode}${shiftTag}`,
                        g.px + 8, g.py + g.panelH - 6);
                }

                // DnD overlay
                if (self._ipDnDOver) {
                    ctx.fillStyle = "rgba(122, 184, 255, 0.25)";
                    ctx.fillRect(g.px, g.py, g.panelW, g.panelH);
                    ctx.strokeStyle = "#9fd0ff";
                    ctx.lineWidth = 2;
                    ctx.setLineDash([6, 4]);
                    ctx.strokeRect(g.px, g.py, g.panelW, g.panelH);
                    ctx.setLineDash([]);
                    ctx.fillStyle = "#cfe8ff";
                    ctx.font = "14px monospace";
                    ctx.textAlign = "center";
                    ctx.fillText("📂 Drop image to load", g.px + g.panelW / 2, g.py + g.panelH / 2);
                }
            };

            // --- Mouse handlers ---
            this._ipMouseDown = function (pos) {
                const g = getPanelGeom();
                const btns = getButtons(g);
                const hit = hitTest(g, btns, pos[0], pos[1]);
                if (!hit) return false;

                if (hit.type === "button") {
                    if (hit.button === "paint") { paintMode = "paint"; }
                    else if (hit.button === "erase") { paintMode = "erase"; }
                    else if (hit.button === "clear") {
                        if (maskCtx) {
                            maskCtx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
                            serializeMask();
                        }
                    }
                    else if (hit.button === "upload") { fileInput.click(); }
                    self.setDirtyCanvas(true, true);
                    return true;
                }

                if (hit.type === "canvas") {
                    isPainting = true;
                    lastPaintX = -1; lastPaintY = -1;
                    strokeOriginX = -1; strokeOriginY = -1;
                    const mc = canvasToMask(g, pos[0], pos[1]);
                    if (mc) {
                        paintAtMask(mc[0], mc[1], -1, -1);
                        lastPaintX = mc[0]; lastPaintY = mc[1];
                    }
                    return true;
                }

                return false;
            };

            this._ipMouseMove = function (pos) {
                const g = getPanelGeom();
                const btns = getButtons(g);

                if (isPainting) {
                    let mc = canvasToMask(g, pos[0], pos[1]);
                    if (mc) {
                        // Set stroke origin on first move
                        if (strokeOriginX < 0) {
                            strokeOriginX = mc[0];
                            strokeOriginY = mc[1];
                        }
                        // Shift-constrain: lock to dominant axis from stroke origin
                        if (shiftHeld) {
                            const dx = Math.abs(mc[0] - strokeOriginX);
                            const dy = Math.abs(mc[1] - strokeOriginY);
                            if (dx > dy) {
                                mc[1] = strokeOriginY;
                            } else {
                                mc[0] = strokeOriginX;
                            }
                        } else {
                            // When shift released, re-anchor to current position
                            strokeOriginX = mc[0];
                            strokeOriginY = mc[1];
                        }
                        hoverX = g.imgX + mc[0] * displayScale;
                        hoverY = g.imgY + mc[1] * displayScale;
                        paintAtMask(mc[0], mc[1], lastPaintX, lastPaintY);
                        lastPaintX = mc[0]; lastPaintY = mc[1];
                    }
                    self.setDirtyCanvas(true, true);
                    return;
                }

                const hit = hitTest(g, btns, pos[0], pos[1]);
                const wasHovering = hovering;
                const wasHoverMode = hoverMode;

                hovering = false;
                hoverMode = null;

                if (hit?.type === "button") {
                    hoverMode = hit.button;
                    hovering = true;
                } else if (hit?.type === "canvas") {
                    hovering = true;
                    hoverX = pos[0];
                    hoverY = pos[1];
                }

                if (wasHovering || hovering || wasHoverMode !== hoverMode) {
                    self.setDirtyCanvas(true, true);
                }
            };

            this._ipMouseUp = function () {
                if (isPainting) {
                    isPainting = false;
                    serializeMask();
                }
            };

            this._ipMouseLeave = function () {
                if (isPainting) {
                    isPainting = false;
                    serializeMask();
                }
                hovering = false;
                hoverMode = null;
                self.setDirtyCanvas(true, true);
            };

            // Watch brush_size widget for redraw
            const brushWidget = getWidget("brush_size");
            if (brushWidget) {
                const origCb = brushWidget.callback;
                brushWidget.callback = (...args) => {
                    const r = origCb?.apply(brushWidget, args);
                    self.setDirtyCanvas(true, true);
                    return r;
                };
            }

            console.log("[InpaintPainter] v1.1 hooks registered");
            return result;
        };

        nodeType.prototype.onDrawForeground = function (ctx) {
            if (this.flags?.collapsed) return;
            if (this._ipDraw) this._ipDraw(ctx);
        };

        nodeType.prototype.onMouseDown = function (e, pos) {
            if (this._ipMouseDown) return this._ipMouseDown(pos);
            return false;
        };
        nodeType.prototype.onMouseMove = function (e, pos) {
            if (this._ipMouseMove) this._ipMouseMove(pos);
        };
        nodeType.prototype.onMouseUp = function (e, pos) {
            if (this._ipMouseUp) return this._ipMouseUp(pos);
        };
        nodeType.prototype.onMouseLeave = function (e, pos) {
            if (this._ipMouseLeave) this._ipMouseLeave(pos);
        };

        console.log("[InpaintPainter] v1.1 loaded");
    },
});

/**
 * Tradux Web Workbench — Client Script
 * Vanilla JS modern implementation connecting to real Tradux backend APIs.
 * Zero external dependencies.
 */

(function () {
  "use strict";

  // State
  const state = {
    selectedFile: null,
    previewUrl: null,
    analyzedDocument: null,
    translatedDocument: null,
    protectedTerms: new Set(),
    currentPageFilter: "all",
    currentBlockPage: 1,
    blocksPerPage: 30,
    filteredBlocks: [],
    isAnalyzing: false,
    isTranslating: false,
  };

  // DOM Elements
  const elements = {
    statusBar: document.getElementById("status-bar"),
    statusAlert: document.getElementById("status-alert"),
    statusMessage: document.getElementById("status-message"),
    activeDocBadge: document.getElementById("active-doc-badge"),

    // Upload & Dropzone
    uploadSection: document.getElementById("upload-section"),
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("pdf-file-input"),
    fileSummary: document.getElementById("file-summary"),
    selectedFileName: document.getElementById("selected-file-name"),
    selectedFileSize: document.getElementById("selected-file-size"),
    btnChangeFile: document.getElementById("btn-change-file"),
    btnAnalyze: document.getElementById("btn-analyze"),
    analyzeSpinner: document.getElementById("analyze-spinner"),
    analyzeBtnText: document.getElementById("analyze-btn-text"),

    // Workspace & Panels
    workspaceGrid: document.getElementById("workspace-grid"),
    
    // Stats
    statPageCountBadge: document.getElementById("stat-page-count-badge"),
    statPages: document.getElementById("stat-pages"),
    statBlocks: document.getElementById("stat-blocks"),
    statLines: document.getElementById("stat-lines"),
    statSpans: document.getElementById("stat-spans"),
    statImages: document.getElementById("stat-images"),
    statFontsCount: document.getElementById("stat-fonts-count"),
    statDimensions: document.getElementById("stat-dimensions"),
    statRotations: document.getElementById("stat-rotations"),
    fontInventoryList: document.getElementById("font-inventory-list"),

    // PDF Preview
    previewFilenameBadge: document.getElementById("preview-filename-badge"),
    previewExternalLink: document.getElementById("preview-external-link"),
    pdfObject: document.getElementById("pdf-object"),
    pdfFallbackLink: document.getElementById("pdf-fallback-link"),

    // Stepper
    step2: document.getElementById("step-2"),
    step2Status: document.getElementById("step-2-status"),
    step3: document.getElementById("step-3"),
    step3Status: document.getElementById("step-3-status"),

    // Translation Controls
    selectSourceLang: document.getElementById("select-source-lang"),
    selectTargetLang: document.getElementById("select-target-lang"),
    inputProtectedTerm: document.getElementById("input-protected-term"),
    btnAddChip: document.getElementById("btn-add-chip"),
    chipsContainer: document.getElementById("chips-container"),
    btnTranslate: document.getElementById("btn-translate"),
    translateSpinner: document.getElementById("translate-spinner"),
    translateBtnText: document.getElementById("translate-btn-text"),

    // Phase 3 Reconstruction Controls
    renderActions: document.getElementById("render-actions"),
    statFitBadge: document.getElementById("stat-fit-badge"),
    statShrunkBadge: document.getElementById("stat-shrunk-badge"),
    statReviewBadge: document.getElementById("stat-review-badge"),
    btnDownloadPdf: document.getElementById("btn-download-pdf"),
    renderSpinner: document.getElementById("render-spinner"),
    renderBtnText: document.getElementById("render-btn-text"),

    // Blocks
    blocksCountBadge: document.getElementById("blocks-count-badge"),
    filterPageSelect: document.getElementById("filter-page-select"),
    btnPrevPage: document.getElementById("btn-prev-page"),
    btnNextPage: document.getElementById("btn-next-page"),
    paginationStatus: document.getElementById("pagination-status"),
    blocksTbody: document.getElementById("blocks-tbody"),
  };

  // Utilities
  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function showAlert(message, type = "info") {
    if (!elements.statusAlert) return;
    elements.statusAlert.className = `alert alert-${type}`;
    elements.statusMessage.textContent = message;
    elements.statusAlert.classList.remove("hidden");
  }

  function hideAlert() {
    if (elements.statusAlert) {
      elements.statusAlert.classList.add("hidden");
    }
  }

  function cleanPreviewUrl() {
    if (state.previewUrl) {
      URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = null;
    }
  }

  // File Handling
  function handleFileSelected(file) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      showAlert("Por favor, selecciona exclusivamente un archivo PDF digital (.pdf).", "danger");
      return;
    }

    cleanPreviewUrl();
    state.selectedFile = file;
    state.previewUrl = URL.createObjectURL(file);
    state.analyzedDocument = null;
    state.translatedDocument = null;
    if (elements.renderActions) elements.renderActions.classList.add("hidden");
    if (elements.step2) {
      elements.step2.className = "stepper-item step-pending";
      elements.step2Status.textContent = "Pendiente de análisis";
    }
    if (elements.step3) {
      elements.step3.className = "stepper-item step-pending";
      elements.step3Status.textContent = "Disponible tras vista previa";
    }

    elements.selectedFileName.textContent = file.name;
    elements.selectedFileSize.textContent = formatBytes(file.size);
    elements.fileSummary.classList.remove("hidden");
    elements.btnAnalyze.disabled = false;
    hideAlert();
  }

  // Drag and drop listeners
  if (elements.dropzone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      elements.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropzone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      elements.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropzone.classList.remove("dragover");
      });
    });

    elements.dropzone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        handleFileSelected(dt.files[0]);
      }
    });

    elements.dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        elements.fileInput.click();
      }
    });
  }

  if (elements.fileInput) {
    elements.fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelected(e.target.files[0]);
      }
    });
  }

  if (elements.btnChangeFile) {
    elements.btnChangeFile.addEventListener("click", () => {
      elements.fileInput.value = "";
      elements.fileInput.click();
    });
  }

  // Document Analysis Action
  if (elements.btnAnalyze) {
    elements.btnAnalyze.addEventListener("click", async () => {
      if (!state.selectedFile || state.isAnalyzing) return;

      state.isAnalyzing = true;
      elements.btnAnalyze.disabled = true;
      elements.analyzeSpinner.classList.remove("hidden");
      elements.analyzeBtnText.textContent = "Analizando...";
      showAlert("Analizando estructura documental con DocumentAnalyzer...", "info");

      const formData = new FormData();
      formData.append("file", state.selectedFile);

      try {
        const response = await fetch("/api/v1/documents/analyze", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          let errMsg = `Error ${response.status} al analizar el archivo`;
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errMsg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch (_) {}
          throw new Error(errMsg);
        }

        const docModel = await response.json();
        state.analyzedDocument = docModel;
        state.translatedDocument = null;

        // Render document structure into workspace
        renderAnalyzedDocument(docModel);
        showAlert("Documento analizado correctamente. Estructura y bloques listos.", "success");
      } catch (err) {
        showAlert(err.message || "Error inesperado durante el análisis.", "danger");
      } finally {
        state.isAnalyzing = false;
        elements.btnAnalyze.disabled = false;
        elements.analyzeSpinner.classList.add("hidden");
        elements.analyzeBtnText.textContent = "Analizar documento";
      }
    });
  }

  function renderAnalyzedDocument(doc) {
    // 1. Update header & metadata
    elements.activeDocBadge.textContent = doc.filename || state.selectedFile.name;
    elements.previewFilenameBadge.textContent = doc.filename || state.selectedFile.name;

    // 2. Setup PDF Viewer preview
    if (state.previewUrl) {
      elements.pdfObject.data = state.previewUrl;
      elements.previewExternalLink.href = state.previewUrl;
      elements.pdfFallbackLink.href = state.previewUrl;
    }

    // 3. Compute Metrics
    const pageCount = doc.pages ? doc.pages.length : 0;
    let blockCount = 0;
    let lineCount = 0;
    let spanCount = 0;
    let imageCount = 0;
    const fontsSet = new Set();
    const dimensionsSet = new Set();
    const rotationsSet = new Set();

    if (doc.pages) {
      doc.pages.forEach((p) => {
        dimensionsSet.add(`${p.width.toFixed(1)} × ${p.height.toFixed(1)} pt`);
        rotationsSet.add(`${p.rotation}°`);
        if (p.images) imageCount += p.images.length;
        if (p.blocks) {
          blockCount += p.blocks.length;
          p.blocks.forEach((b) => {
            if (b.lines) {
              lineCount += b.lines.length;
              b.lines.forEach((l) => {
                if (l.spans) {
                  spanCount += l.spans.length;
                  l.spans.forEach((s) => {
                    if (s.font_name) fontsSet.add(s.font_name);
                  });
                }
              });
            }
          });
        }
      });
    }

    elements.statPageCountBadge.textContent = `${pageCount} págs`;
    elements.statPages.textContent = pageCount;
    elements.statBlocks.textContent = blockCount;
    elements.statLines.textContent = lineCount;
    elements.statSpans.textContent = spanCount;
    elements.statImages.textContent = imageCount;
    elements.statFontsCount.textContent = fontsSet.size;

    elements.statDimensions.textContent = Array.from(dimensionsSet).join(", ") || "-";
    elements.statRotations.textContent = Array.from(rotationsSet).join(", ") || "-";

    // 4. Render Font Inventory
    elements.fontInventoryList.innerHTML = "";
    if (fontsSet.size === 0) {
      const emptyLi = document.createElement("li");
      emptyLi.className = "empty-list-item";
      emptyLi.textContent = "No se detectaron fuentes explícitas";
      elements.fontInventoryList.appendChild(emptyLi);
    } else {
      fontsSet.forEach((font) => {
        const li = document.createElement("li");
        li.textContent = font;
        li.title = font;
        elements.fontInventoryList.appendChild(li);
      });
    }

    // 5. Populate page filter dropdown
    elements.filterPageSelect.innerHTML = '<option value="all">Todas las páginas</option>';
    for (let i = 1; i <= pageCount; i++) {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = `Página ${i}`;
      elements.filterPageSelect.appendChild(opt);
    }

    // 6. Reset Stepper state
    elements.step2.className = "stepper-item step-active";
    elements.step2Status.textContent = "Listo para vista previa";
    elements.btnTranslate.disabled = false;

    if (elements.renderActions) elements.renderActions.classList.add("hidden");
    if (elements.step3) {
      elements.step3.className = "stepper-item step-pending";
      elements.step3Status.textContent = "Disponible tras vista previa";
    }

    // 7. Transition view from upload to workspace
    elements.uploadSection.classList.add("hidden");
    elements.workspaceGrid.classList.remove("hidden");

    // 8. Populate comparative blocks view
    recalculateBlocks();
  }

  // Protected Terms Chips
  function addProtectedTerm(term) {
    const clean = term.trim();
    if (!clean || state.protectedTerms.has(clean)) return;

    state.protectedTerms.add(clean);
    renderChips();
    elements.inputProtectedTerm.value = "";
  }

  function removeProtectedTerm(term) {
    state.protectedTerms.delete(term);
    renderChips();
  }

  function renderChips() {
    elements.chipsContainer.innerHTML = "";
    state.protectedTerms.forEach((term) => {
      const chip = document.createElement("span");
      chip.className = "chip";

      const textSpan = document.createElement("span");
      textSpan.textContent = term;
      chip.appendChild(textSpan);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "chip-remove-btn";
      removeBtn.setAttribute("aria-label", `Eliminar término ${term}`);
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", () => removeProtectedTerm(term));
      chip.appendChild(removeBtn);

      elements.chipsContainer.appendChild(chip);
    });
  }

  if (elements.btnAddChip) {
    elements.btnAddChip.addEventListener("click", () => {
      addProtectedTerm(elements.inputProtectedTerm.value);
    });
  }

  if (elements.inputProtectedTerm) {
    elements.inputProtectedTerm.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addProtectedTerm(elements.inputProtectedTerm.value);
      }
    });
  }

  // Translation Action (Mock Provider)
  if (elements.btnTranslate) {
    elements.btnTranslate.addEventListener("click", async () => {
      if (!state.analyzedDocument || state.isTranslating) return;

      state.isTranslating = true;
      elements.btnTranslate.disabled = true;
      elements.translateSpinner.classList.remove("hidden");
      elements.translateBtnText.textContent = "Generando vista previa...";
      showAlert("Generando vista previa de prueba con TranslationEngine(MockTranslator())...", "info");

      const sourceLang = elements.selectSourceLang.value || null;
      const targetLang = elements.selectTargetLang.value || "es";
      const protectedTermsArray = Array.from(state.protectedTerms);

      const payload = {
        document: state.analyzedDocument,
        source_language: sourceLang,
        target_language: targetLang,
        protected_terms: protectedTermsArray,
      };

      try {
        const response = await fetch("/api/v1/workbench/translate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          let errMsg = `Error ${response.status} en la traducción mock`;
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errMsg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch (_) {}
          throw new Error(errMsg);
        }

        const data = await response.json();
        state.translatedDocument = data.document;

        // Update Stepper
        elements.step2.className = "stepper-item step-completed";
        elements.step2Status.textContent = `Vista previa generada (${data.translated_blocks} bloques)`;

        // Unhide Phase 3 Reconstruction Controls
        if (elements.renderActions) {
          elements.renderActions.classList.remove("hidden");
        }
        if (elements.step3) {
          elements.step3.className = "stepper-item step-active";
          elements.step3Status.textContent = "Listo para reconstruir PDF";
        }

        // Refresh blocks table
        recalculateBlocks();
        showAlert(`Vista previa generada con éxito (${data.translated_blocks} bloques procesados con MockTranslator).`, "success");
      } catch (err) {
        showAlert(err.message || "Error al generar la vista previa de demostración.", "danger");
      } finally {
        state.isTranslating = false;
        elements.btnTranslate.disabled = false;
        elements.translateSpinner.classList.add("hidden");
        elements.translateBtnText.textContent = "Generar vista previa";
      }
    });
  }

  // PDF Reconstruction Action (PyMuPDFRenderer)
  if (elements.btnDownloadPdf) {
    elements.btnDownloadPdf.addEventListener("click", async () => {
      if (!state.selectedFile || !state.translatedDocument) {
        showAlert("Debes generar primero una vista previa de traducción antes de reconstruir el PDF.", "warning");
        return;
      }

      elements.btnDownloadPdf.disabled = true;
      if (elements.renderSpinner) elements.renderSpinner.classList.remove("hidden");
      if (elements.renderBtnText) elements.renderBtnText.textContent = "Reconstruyendo PDF...";
      showAlert("Reconstruyendo documento PDF con PyMuPDFRenderer...", "info");

      const formData = new FormData();
      formData.append("file", state.selectedFile);
      const documentBlob = new Blob(
        [JSON.stringify(state.translatedDocument)],
        { type: "application/json" }
      );
      formData.append("document", documentBlob, "document.json");

      try {
        const response = await fetch("/api/v1/workbench/render", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          let errMsg = `Error ${response.status} en la reconstrucción del PDF`;
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errMsg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch (_) {}
          throw new Error(errMsg);
        }

        // Update layout badges from response headers
        const fitBlocks = response.headers.get("X-Tradux-Fit-Blocks") || "0";
        const shrunkBlocks = response.headers.get("X-Tradux-Shrunk-Blocks") || "0";
        const reviewBlocks = response.headers.get("X-Tradux-Review-Blocks") || "0";

        if (elements.statFitBadge) elements.statFitBadge.textContent = `${fitBlocks} ajuste exacto`;
        if (elements.statShrunkBadge) elements.statShrunkBadge.textContent = `${shrunkBlocks} reducidos`;
        if (elements.statReviewBadge) elements.statReviewBadge.textContent = `${reviewBlocks} revisión req.`;

        // Trigger file download
        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        const originalName = state.selectedFile.name.replace(/\.pdf$/i, "");
        a.download = `${originalName}_tradux.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(downloadUrl), 2000);

        // Complete Stepper Step 3
        if (elements.step3) {
          elements.step3.className = "stepper-item step-completed";
          elements.step3Status.textContent = "PDF reconstruido y descargado";
        }
        showAlert("Documento PDF reconstruido y descargado con éxito.", "success");
      } catch (err) {
        showAlert(err.message || "Error al reconstruir el archivo PDF.", "danger");
      } finally {
        elements.btnDownloadPdf.disabled = false;
        if (elements.renderSpinner) elements.renderSpinner.classList.add("hidden");
        if (elements.renderBtnText) elements.renderBtnText.textContent = "Descargar PDF de demostración 📥";
      }
    });
  }

  // Blocks Table & Filtering
  function recalculateBlocks() {
    const docToUse = state.translatedDocument || state.analyzedDocument;
    if (!docToUse || !docToUse.pages) {
      state.filteredBlocks = [];
      renderBlocksTable();
      return;
    }

    const blocksList = [];
    const filterPage = elements.filterPageSelect.value;

    docToUse.pages.forEach((page) => {
      if (filterPage !== "all" && String(page.page_number) !== filterPage) {
        return;
      }

      if (page.blocks) {
        // Deterministic reading order
        const sorted = [...page.blocks].sort((a, b) => a.reading_order - b.reading_order);
        sorted.forEach((block) => {
          blocksList.push({
            pageNumber: page.page_number,
            readingOrder: block.reading_order,
            bbox: block.bbox,
            sourceText: block.text,
            translatedText: block.translated_text,
          });
        });
      }
    });

    state.filteredBlocks = blocksList;
    state.currentBlockPage = 1;
    renderBlocksTable();
  }

  function renderBlocksTable() {
    elements.blocksTbody.innerHTML = "";
    const total = state.filteredBlocks.length;
    elements.blocksCountBadge.textContent = `${total} bloques`;

    if (total === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 3;
      td.className = "empty-table-cell";
      td.textContent = "No hay bloques de texto que coincidan con el filtro seleccionado.";
      tr.appendChild(td);
      elements.blocksTbody.appendChild(tr);

      elements.paginationStatus.textContent = "0 / 0";
      elements.btnPrevPage.disabled = true;
      elements.btnNextPage.disabled = true;
      return;
    }

    const totalPages = Math.ceil(total / state.blocksPerPage);
    const startIdx = (state.currentBlockPage - 1) * state.blocksPerPage;
    const endIdx = Math.min(startIdx + state.blocksPerPage, total);
    const pageItems = state.filteredBlocks.slice(startIdx, endIdx);

    pageItems.forEach((item) => {
      const tr = document.createElement("tr");

      // Col 1: Location & Bbox
      const tdMeta = document.createElement("td");
      tdMeta.className = "block-meta-cell";

      const badgeLoc = document.createElement("span");
      badgeLoc.className = "block-location-badge";
      badgeLoc.textContent = `Pág. ${item.pageNumber} · #${item.readingOrder}`;
      tdMeta.appendChild(badgeLoc);

      if (item.bbox) {
        const bboxSpan = document.createElement("span");
        bboxSpan.className = "block-bbox font-mono";
        bboxSpan.textContent = `[${item.bbox.x0.toFixed(1)}, ${item.bbox.y0.toFixed(1)}, ${item.bbox.x1.toFixed(1)}, ${item.bbox.y1.toFixed(1)}]`;
        tdMeta.appendChild(bboxSpan);
      }
      tr.appendChild(tdMeta);

      // Col 2: Source Text (SECURE: using textContent strictly)
      const tdSource = document.createElement("td");
      const sourceDiv = document.createElement("div");
      sourceDiv.className = "block-source-text";
      sourceDiv.textContent = item.sourceText || "(Bloque sin texto)";
      tdSource.appendChild(sourceDiv);
      tr.appendChild(tdSource);

      // Col 3: Translated Text (SECURE: using textContent strictly)
      const tdTrans = document.createElement("td");
      const transDiv = document.createElement("div");
      if (item.translatedText !== null && item.translatedText !== undefined) {
        transDiv.className = "block-translated-text";
        transDiv.textContent = item.translatedText;
      } else {
        transDiv.className = "block-pending-text";
        transDiv.textContent = "Traducción pendiente (ejecuta la vista mock)";
      }
      tdTrans.appendChild(transDiv);
      tr.appendChild(tdTrans);

      elements.blocksTbody.appendChild(tr);
    });

    // Pagination status
    elements.paginationStatus.textContent = `${state.currentBlockPage} / ${totalPages}`;
    elements.btnPrevPage.disabled = state.currentBlockPage <= 1;
    elements.btnNextPage.disabled = state.currentBlockPage >= totalPages;
  }

  if (elements.filterPageSelect) {
    elements.filterPageSelect.addEventListener("change", () => {
      recalculateBlocks();
    });
  }

  if (elements.btnPrevPage) {
    elements.btnPrevPage.addEventListener("click", () => {
      if (state.currentBlockPage > 1) {
        state.currentBlockPage--;
        renderBlocksTable();
      }
    });
  }

  if (elements.btnNextPage) {
    elements.btnNextPage.addEventListener("click", () => {
      const totalPages = Math.ceil(state.filteredBlocks.length / state.blocksPerPage);
      if (state.currentBlockPage < totalPages) {
        state.currentBlockPage++;
        renderBlocksTable();
      }
    });
  }

  // Cleanup on unload
  window.addEventListener("beforeunload", () => {
    cleanPreviewUrl();
  });
})();

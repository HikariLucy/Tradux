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
    capabilities: null,
    currentJobId: null,
    jobPollTimer: null,
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

    // Phase 4 MVP Job & Mode Controls
    radioModeDemo: document.getElementById("radio-mode-demo"),
    radioModeConfigured: document.getElementById("radio-mode-configured"),
    modeOptionDemo: document.getElementById("mode-option-demo"),
    modeOptionConfigured: document.getElementById("mode-option-configured"),
    configuredProviderBadge: document.getElementById("configured-provider-badge"),
    configuredProviderDesc: document.getElementById("configured-provider-desc"),
    demoNoticeBanner: document.getElementById("demo-notice-banner"),
    costNoticeBanner: document.getElementById("cost-notice-banner"),
    costProviderBadge: document.getElementById("cost-provider-badge"),

    btnStartJob: document.getElementById("btn-translate") || document.getElementById("btn-start-job"),
    jobSpinner: document.getElementById("job-spinner"),
    jobBtnText: document.getElementById("job-btn-text"),

    jobCard: document.getElementById("job-card"),
    jobIdBadge: document.getElementById("job-id-badge"),
    jobStatusBadge: document.getElementById("job-status-badge"),
    stageAnalyzing: document.getElementById("stage-analyzing"),
    stageTranslating: document.getElementById("stage-translating"),
    stageTranslatingLabel: document.getElementById("stage-translating-label"),
    stageLayout: document.getElementById("stage-layout"),
    stageRendering: document.getElementById("stage-rendering"),
    jobResults: document.getElementById("job-results"),
    jobStatFit: document.getElementById("job-stat-fit"),
    jobStatShrunk: document.getElementById("job-stat-shrunk"),
    jobStatExpanded: document.getElementById("job-stat-expanded"),
    jobStatReview: document.getElementById("job-stat-review"),
    jobReviewWarning: document.getElementById("job-review-warning"),
    btnDownloadJobResult: document.getElementById("btn-download-job-result"),
    jobErrorBanner: document.getElementById("job-error-banner"),
    jobErrorMessage: document.getElementById("job-error-message"),
    btnRetryJob: document.getElementById("btn-retry-job"),

    // Modal
    confirmModal: document.getElementById("confirm-modal"),
    btnModalClose: document.getElementById("btn-modal-close"),
    btnModalCancel: document.getElementById("btn-modal-cancel"),
    btnModalConfirm: document.getElementById("btn-modal-confirm"),
    modalFilename: document.getElementById("modal-filename"),
    modalPages: document.getElementById("modal-pages"),
    modalBlocks: document.getElementById("modal-blocks"),
    modalTargetLang: document.getElementById("modal-target-lang"),
    modalProvider: document.getElementById("modal-provider"),

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
    elements.step2Status.textContent = "Listo para procesar";
    if (elements.btnTranslate) elements.btnTranslate.disabled = false;
    if (elements.btnStartJob) elements.btnStartJob.disabled = false;

    if (elements.jobCard) elements.jobCard.classList.add("hidden");
    if (elements.renderActions) elements.renderActions.classList.add("hidden");
    if (elements.step3) {
      elements.step3.className = "stepper-item step-pending";
      elements.step3Status.textContent = "Encolado para job";
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

  // ==========================================================================
  // Phase 4 MVP: Capabilities, Mode Selection, Job Orchestration & Polling
  // ==========================================================================

  async function loadCapabilities() {
    try {
      const res = await fetch("/api/v1/capabilities");
      if (res.ok) {
        state.capabilities = await res.json();
        updateCapabilitiesUI();
      }
    } catch (e) {
      console.warn("No se pudieron cargar las capabilities del servidor:", e);
    }
  }

  function updateCapabilitiesUI() {
    if (!state.capabilities) return;
    const { configured_translation_available, configured_provider } = state.capabilities;

    if (elements.configuredProviderBadge) {
      elements.configuredProviderBadge.textContent = configured_translation_available
        ? configured_provider
        : "No configurado";
    }
    if (elements.costProviderBadge) {
      elements.costProviderBadge.textContent = configured_provider;
    }
    if (elements.modalProvider) {
      elements.modalProvider.textContent = configured_provider;
    }

    if (!configured_translation_available) {
      if (elements.radioModeConfigured) elements.radioModeConfigured.disabled = true;
      if (elements.modeOptionConfigured) elements.modeOptionConfigured.classList.add("disabled");
      if (elements.configuredProviderDesc) {
        elements.configuredProviderDesc.textContent = "No hay proveedor externo configurado en el servidor.";
      }
    } else {
      if (elements.radioModeConfigured) elements.radioModeConfigured.disabled = false;
      if (elements.modeOptionConfigured) elements.modeOptionConfigured.classList.remove("disabled");
      if (elements.configuredProviderDesc) {
        elements.configuredProviderDesc.textContent = `Traducción lingüística mediante proveedor ${configured_provider}.`;
      }
    }
  }

  function handleModeChange() {
    const selected = document.querySelector('input[name="translation-mode"]:checked');
    const selectedMode = selected ? selected.value : "demo";

    if (selectedMode === "demo") {
      if (elements.modeOptionDemo) elements.modeOptionDemo.classList.add("active");
      if (elements.modeOptionConfigured) elements.modeOptionConfigured.classList.remove("active");
      if (elements.demoNoticeBanner) elements.demoNoticeBanner.classList.remove("hidden");
      if (elements.costNoticeBanner) elements.costNoticeBanner.classList.add("hidden");
      if (elements.jobBtnText) elements.jobBtnText.textContent = "Iniciar trabajo de traducción";
    } else {
      if (elements.modeOptionConfigured) elements.modeOptionConfigured.classList.add("active");
      if (elements.modeOptionDemo) elements.modeOptionDemo.classList.remove("active");
      if (elements.demoNoticeBanner) elements.demoNoticeBanner.classList.add("hidden");
      if (elements.costNoticeBanner) elements.costNoticeBanner.classList.remove("hidden");
      if (elements.jobBtnText) elements.jobBtnText.textContent = "Iniciar traducción real";
    }
  }

  if (elements.radioModeDemo) elements.radioModeDemo.addEventListener("change", handleModeChange);
  if (elements.radioModeConfigured) elements.radioModeConfigured.addEventListener("change", handleModeChange);

  // Confirmation Modal
  function openConfirmModal() {
    if (!state.selectedFile) return;
    if (elements.modalFilename) elements.modalFilename.textContent = state.selectedFile.name;
    if (elements.modalPages) elements.modalPages.textContent = elements.statPages ? elements.statPages.textContent : "-";
    if (elements.modalBlocks) elements.modalBlocks.textContent = elements.statBlocks ? elements.statBlocks.textContent : "-";
    if (elements.modalTargetLang) elements.modalTargetLang.textContent = elements.selectTargetLang.value;
    if (elements.modalProvider && state.capabilities) {
      elements.modalProvider.textContent = state.capabilities.configured_provider;
    }
    if (elements.confirmModal) elements.confirmModal.classList.remove("hidden");
  }

  function closeConfirmModal() {
    if (elements.confirmModal) elements.confirmModal.classList.add("hidden");
  }

  if (elements.btnModalClose) elements.btnModalClose.addEventListener("click", closeConfirmModal);
  if (elements.btnModalCancel) elements.btnModalCancel.addEventListener("click", closeConfirmModal);
  if (elements.confirmModal) {
    elements.confirmModal.addEventListener("click", (e) => {
      if (e.target === elements.confirmModal) closeConfirmModal();
    });
  }

  // Launching Translation Job
  if (elements.btnStartJob) {
    elements.btnStartJob.addEventListener("click", () => {
      if (!state.selectedFile) {
        showAlert("Por favor, selecciona y analiza un archivo PDF primero.", "warning");
        return;
      }
      const selected = document.querySelector('input[name="translation-mode"]:checked');
      const selectedMode = selected ? selected.value : "demo";

      if (selectedMode === "configured") {
        openConfirmModal();
      } else {
        launchTranslationJob("demo", false);
      }
    });
  }

  if (elements.btnModalConfirm) {
    elements.btnModalConfirm.addEventListener("click", () => {
      closeConfirmModal();
      launchTranslationJob("configured", true);
    });
  }

  async function launchTranslationJob(mode, confirmed = false) {
    if (!state.selectedFile) {
      showAlert("Por favor, selecciona y analiza un archivo PDF primero.", "warning");
      return;
    }

    elements.btnStartJob.disabled = true;
    if (elements.jobSpinner) elements.jobSpinner.classList.remove("hidden");
    if (elements.jobBtnText) elements.jobBtnText.textContent = "Iniciando trabajo...";

    // Hide previous job results / errors
    if (elements.jobResults) elements.jobResults.classList.add("hidden");
    if (elements.jobErrorBanner) elements.jobErrorBanner.classList.add("hidden");
    if (elements.jobReviewWarning) elements.jobReviewWarning.classList.add("hidden");

    // Reset stages
    resetJobStages();
    if (elements.jobCard) elements.jobCard.classList.remove("hidden");
    if (elements.jobStatusBadge) {
      elements.jobStatusBadge.className = "job-status-badge badge badge-subtle";
      elements.jobStatusBadge.textContent = "Iniciando";
    }

    const sourceLang = elements.selectSourceLang.value || "";
    const targetLang = elements.selectTargetLang.value || "es";
    const protectedTermsArray = Array.from(state.protectedTerms);

    const formData = new FormData();
    formData.append("file", state.selectedFile);
    formData.append("target_language", targetLang);
    if (sourceLang) formData.append("source_language", sourceLang);
    formData.append("mode", mode);
    if (mode === "configured") {
      formData.append("confirm_configured", confirmed ? "true" : "false");
    }
    if (protectedTermsArray.length > 0) {
      formData.append("protected_terms", JSON.stringify(protectedTermsArray));
    }

    try {
      const response = await fetch("/api/v1/jobs", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let errMsg = `Error ${response.status} al crear el trabajo`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errMsg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
          }
        } catch (_) {}
        throw new Error(errMsg);
      }

      const jobData = await response.json();
      state.currentJobId = jobData.job_id;
      if (elements.jobIdBadge) elements.jobIdBadge.textContent = `Job #${jobData.job_id.slice(0, 8)}`;
      showAlert(`Trabajo de traducción #${jobData.job_id.slice(0, 8)} creado con éxito. Procesando...`, "info");

      // Begin polling
      if (state.jobPollTimer) clearInterval(state.jobPollTimer);
      state.jobPollTimer = setInterval(() => pollJobStatus(state.currentJobId), 1000);
      pollJobStatus(state.currentJobId);
    } catch (err) {
      elements.btnStartJob.disabled = false;
      if (elements.jobSpinner) elements.jobSpinner.classList.add("hidden");
      if (elements.jobBtnText) elements.jobBtnText.textContent = "Iniciar trabajo de traducción";
      showJobError(err.message || "Error al iniciar el trabajo de traducción.");
    }
  }

  function resetJobStages() {
    const stages = [
      elements.stageAnalyzing,
      elements.stageTranslating,
      elements.stageLayout,
      elements.stageRendering,
    ];
    stages.forEach((el) => {
      if (el) {
        el.className = "job-stage-item stage-pending";
        const icon = el.querySelector(".stage-icon");
        if (icon) icon.textContent = "○";
      }
    });
    if (elements.stageTranslatingLabel) {
      elements.stageTranslatingLabel.textContent = "Traduciendo bloques";
    }
  }

  async function pollJobStatus(jobId) {
    if (!jobId || state.currentJobId !== jobId) return;

    try {
      const response = await fetch(`/api/v1/jobs/${jobId}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("El trabajo ha expirado o no fue encontrado en memoria.");
        }
        throw new Error(`Error ${response.status} consultando el trabajo.`);
      }

      const job = await response.json();
      updateJobProgress(job);

      if (job.status === "completed" || job.status === "failed") {
        if (state.jobPollTimer) {
          clearInterval(state.jobPollTimer);
          state.jobPollTimer = null;
        }
      }
    } catch (err) {
      if (state.jobPollTimer) {
        clearInterval(state.jobPollTimer);
        state.jobPollTimer = null;
      }
      showJobError(err.message || "Error consultando el progreso del trabajo.");
    }
  }

  function updateJobProgress(job) {
    if (!job) return;

    if (elements.jobStatusBadge) {
      elements.jobStatusBadge.textContent = job.stage_message || job.status;
    }

    const setStage = (el, status, iconText) => {
      if (!el) return;
      el.className = `job-stage-item stage-${status}`;
      const icon = el.querySelector(".stage-icon");
      if (icon) icon.textContent = iconText;
    };

    if (job.status === "created") {
      setStage(elements.stageAnalyzing, "pending", "○");
      setStage(elements.stageTranslating, "pending", "○");
      setStage(elements.stageLayout, "pending", "○");
      setStage(elements.stageRendering, "pending", "○");
    } else if (job.status === "analyzing") {
      setStage(elements.stageAnalyzing, "active", "●");
      setStage(elements.stageTranslating, "pending", "○");
      setStage(elements.stageLayout, "pending", "○");
      setStage(elements.stageRendering, "pending", "○");
    } else if (job.status === "translating") {
      setStage(elements.stageAnalyzing, "completed", "✓");
      setStage(elements.stageTranslating, "active", "●");
      if (elements.stageTranslatingLabel && job.translated_blocks !== null && job.total_blocks !== null) {
        elements.stageTranslatingLabel.textContent = `Traduciendo bloques (${job.translated_blocks}/${job.total_blocks})`;
      }
      setStage(elements.stageLayout, "pending", "○");
      setStage(elements.stageRendering, "pending", "○");
    } else if (job.status === "layout") {
      setStage(elements.stageAnalyzing, "completed", "✓");
      setStage(elements.stageTranslating, "completed", "✓");
      setStage(elements.stageLayout, "active", "●");
      setStage(elements.stageRendering, "pending", "○");
    } else if (job.status === "rendering") {
      setStage(elements.stageAnalyzing, "completed", "✓");
      setStage(elements.stageTranslating, "completed", "✓");
      setStage(elements.stageLayout, "completed", "✓");
      setStage(elements.stageRendering, "active", "●");
    } else if (job.status === "completed") {
      setStage(elements.stageAnalyzing, "completed", "✓");
      setStage(elements.stageTranslating, "completed", "✓");
      setStage(elements.stageLayout, "completed", "✓");
      setStage(elements.stageRendering, "completed", "✓");

      if (elements.jobStatusBadge) {
        elements.jobStatusBadge.className = "job-status-badge badge badge-accent";
        elements.jobStatusBadge.textContent = "Completado";
      }

      if (job.layout_stats) {
        if (elements.jobStatFit) elements.jobStatFit.textContent = `${job.layout_stats.fit_count} ajuste`;
        if (elements.jobStatShrunk) elements.jobStatShrunk.textContent = `${job.layout_stats.shrunk_count} reducidos`;
        if (elements.jobStatExpanded) elements.jobStatExpanded.textContent = `${job.layout_stats.expanded_count} expandidos`;
        if (elements.jobStatReview) elements.jobStatReview.textContent = `${job.layout_stats.review_required_count} revisión`;

        if (elements.jobReviewWarning) {
          if (job.layout_stats.review_required_count > 0) {
            elements.jobReviewWarning.classList.remove("hidden");
          } else {
            elements.jobReviewWarning.classList.add("hidden");
          }
        }
      }

      if (elements.btnDownloadJobResult) {
        elements.btnDownloadJobResult.href = `/api/v1/jobs/${job.job_id}/result`;
      }
      if (elements.jobResults) elements.jobResults.classList.remove("hidden");

      elements.btnStartJob.disabled = false;
      if (elements.jobSpinner) elements.jobSpinner.classList.add("hidden");
      elements.jobBtnText.textContent = "Iniciar nuevo trabajo";

      if (elements.step2) {
        elements.step2.className = "stepper-item step-completed";
        elements.step2Status.textContent = "Traducción completada";
      }
      if (elements.step3) {
        elements.step3.className = "stepper-item step-completed";
        elements.step3Status.textContent = "PDF reconstruido y descargable";
      }
      showAlert("Trabajo completado con éxito. El PDF traducido está listo para descargar.", "success");
    } else if (job.status === "failed") {
      showJobError(job.error_message || "Error en el procesamiento del trabajo.");
    }
  }

  function showJobError(msg) {
    if (elements.jobStatusBadge) {
      elements.jobStatusBadge.className = "job-status-badge badge badge-danger";
      elements.jobStatusBadge.textContent = "Fallo";
    }
    if (elements.jobErrorMessage) {
      elements.jobErrorMessage.textContent = msg;
    }
    if (elements.jobErrorBanner) {
      elements.jobErrorBanner.classList.remove("hidden");
    }
    elements.btnStartJob.disabled = false;
    if (elements.jobSpinner) elements.jobSpinner.classList.add("hidden");
    elements.jobBtnText.textContent = "Iniciar trabajo de traducción";
    showAlert(msg, "danger");
  }

  if (elements.btnRetryJob) {
    elements.btnRetryJob.addEventListener("click", () => {
      const selected = document.querySelector('input[name="translation-mode"]:checked');
      const selectedMode = selected ? selected.value : "demo";
      if (selectedMode === "configured") {
        openConfirmModal();
      } else {
        launchTranslationJob("demo", false);
      }
    });
  }

  // Load server capabilities on startup
  loadCapabilities();

  // Cleanup on unload
  window.addEventListener("beforeunload", () => {
    if (state.jobPollTimer) clearInterval(state.jobPollTimer);
    cleanPreviewUrl();
  });
})();

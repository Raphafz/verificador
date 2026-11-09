/**
 * Upload de mapas CTO — drag-and-drop, múltiplos arquivos, validação e envio AJAX.
 */
(function () {
  "use strict";

  const ALLOWED_TYPES = [".xlsx", ".xls", ".csv", ".kml", ".kmz"];
  const MAX_BYTES = 50 * 1024 * 1024;
  const MAX_FILES_PER_BATCH = 25;

  function getCsrfToken() {
    const input = document.querySelector(
      '#csrfHelperForm input[name="csrfmiddlewaretoken"]'
    );
    if (input && input.value) return input.value;
    const name = "csrftoken";
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return "";
  }

  function showError(message, title) {
    if (window.showError) {
      window.showError(message, title || "Erro", 6000);
    } else {
      alert(message);
    }
  }

  function showSuccess(message, title) {
    if (window.showSuccess) {
      window.showSuccess(message, title || "Sucesso", 6000);
    } else {
      alert(message);
    }
  }

  function getExtension(fileName) {
    const parts = fileName.split(".");
    if (parts.length < 2) return "";
    return "." + parts.pop().toLowerCase();
  }

  function validateFile(file) {
    const ext = getExtension(file.name);
    if (!ALLOWED_TYPES.includes(ext)) {
      return (
        '"' +
        file.name +
        '": tipo não suportado. Use .xlsx, .xls, .csv, .kml ou .kmz'
      );
    }
    if (file.size > MAX_BYTES) {
      return '"' + file.name + '": arquivo maior que 50MB';
    }
    return null;
  }

  function init() {
    const uploadArea = document.getElementById("uploadArea");
    const fileInput = document.getElementById("fileInput");
    const loadingOverlay = document.getElementById("uploadLoadingOverlay");
    const selectLabel = document.getElementById("selectFileLabel");

    if (!uploadArea || !fileInput) return;

    if (window.globalLoadingScreen?.forceHide) {
      window.globalLoadingScreen.forceHide();
    }

    const uploadUrl = uploadArea.dataset.uploadUrl;
    if (!uploadUrl) {
      console.error("upload-page: data-upload-url ausente");
      return;
    }

    if (selectLabel) {
      selectLabel.addEventListener("click", (e) => e.stopPropagation());
    }

    uploadArea.addEventListener("click", (e) => {
      if (e.target.closest("#selectFileLabel, .upload-area-actions")) return;
      fileInput.click();
    });

    uploadArea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fileInput.click();
      }
    });

    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        handleFiles(
          e.dataTransfer.files,
          uploadUrl,
          uploadArea,
          fileInput,
          loadingOverlay
        );
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        handleFiles(
          e.target.files,
          uploadUrl,
          uploadArea,
          fileInput,
          loadingOverlay
        );
      }
    });
  }

  function setLoading(loadingOverlay, active, title, detail) {
    if (!loadingOverlay) return;
    loadingOverlay.hidden = !active;
    loadingOverlay.setAttribute("aria-hidden", active ? "false" : "true");
    const titleEl = document.getElementById("uploadProgressTitle");
    const detailEl = document.getElementById("uploadProgressDetail");
    if (titleEl && title) titleEl.textContent = title;
    if (detailEl && detail !== undefined) detailEl.textContent = detail;
  }

  function uploadFile(file, uploadUrl) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("description", "Upload via interface web");

    return fetch(uploadUrl, {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": getCsrfToken() || "",
        "X-Requested-With": "XMLHttpRequest",
        "X-Skip-Global-Loading": "1",
        Accept: "application/json",
      },
      credentials: "same-origin",
    }).then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        let message = "HTTP " + response.status;
        try {
          const json = JSON.parse(text);
          if (json.message) message = json.message;
        } catch (_) {
          if (text) message = text.substring(0, 200);
        }
        throw new Error(message);
      }
      return response.json();
    });
  }

  async function handleFiles(fileList, uploadUrl, uploadArea, fileInput, loadingOverlay) {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    if (files.length > MAX_FILES_PER_BATCH) {
      showError(
        "Selecione no máximo " + MAX_FILES_PER_BATCH + " arquivos por vez.",
        "Muitos arquivos"
      );
      fileInput.value = "";
      return;
    }

    const validFiles = [];
    const validationErrors = [];

    files.forEach((file) => {
      const err = validateFile(file);
      if (err) validationErrors.push(err);
      else validFiles.push(file);
    });

    if (validationErrors.length > 0) {
      showError(validationErrors.join("\n"), "Arquivos inválidos");
    }

    if (validFiles.length === 0) {
      fileInput.value = "";
      return;
    }

    uploadArea.classList.remove("dragover");
    uploadArea.setAttribute("aria-busy", "true");
    setLoading(
      loadingOverlay,
      true,
      "Enviando arquivos...",
      "0 de " + validFiles.length + " concluído(s)"
    );

    let successCount = 0;
    const failed = [];

    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i];
      setLoading(
        loadingOverlay,
        true,
        "Enviando " + (i + 1) + " de " + validFiles.length,
        file.name
      );

      try {
        const data = await uploadFile(file, uploadUrl);
        if (data.success) {
          successCount++;
        } else {
          failed.push(
            (data.file_name || file.name) + ": " + (data.message || "erro no envio")
          );
        }
      } catch (error) {
        failed.push(file.name + ": " + (error.message || "falha na conexão"));
      }
    }

    setLoading(loadingOverlay, false);
    uploadArea.setAttribute("aria-busy", "false");
    fileInput.value = "";

    if (successCount > 0 && failed.length === 0) {
      showSuccess(
        successCount === 1
          ? "1 arquivo enviado com sucesso!"
          : successCount + " arquivos enviados com sucesso!",
        "Upload concluído"
      );
      setTimeout(() => location.reload(), 1500);
      return;
    }

    if (successCount > 0 && failed.length > 0) {
      showSuccess(
        successCount + " arquivo(s) enviado(s). " + failed.length + " falhou(ram).",
        "Upload parcial"
      );
      showError(failed.join("\n"), "Arquivos com erro");
      setTimeout(() => location.reload(), 2000);
      return;
    }

    showError(
      failed.length ? failed.join("\n") : "Nenhum arquivo foi enviado.",
      "Erro no upload"
    );
  }

  function initMapSearch() {
    const input = document.getElementById("uploadMapSearch");
    const table = document.getElementById("uploadMapsTable");
    if (!input || !table) return;

    const rows = table.querySelectorAll("tbody tr");
    input.addEventListener("input", function () {
      const q = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(function (row) {
        const name = row.getAttribute("data-map-name") || "";
        const show = !q || name.indexOf(q) !== -1;
        row.hidden = !show;
        if (show) visible++;
      });
    });
  }

  function boot() {
    init();
    initMapSearch();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

(function () {
  "use strict";

  const PING_MS = 12000;

  const qEl = document.getElementById("q");
  const rowsEl = document.getElementById("rows");
  const tableEl = document.getElementById("data-table");
  const emptyEl = document.getElementById("empty-state");
  const btnOpenAdd = document.getElementById("btn-open-add");

  const modalSaveBackdrop = document.getElementById("modal-save-backdrop");
  const modalSave = document.getElementById("modal-save");
  const modalSaveTitle = document.getElementById("modal-save-title");
  const modalSaveError = document.getElementById("modal-save-error");
  const modalTitle = document.getElementById("modal-title");
  const modalUrl = document.getElementById("modal-url");
  const modalSaveCancel = document.getElementById("modal-save-cancel");
  const modalSaveConfirm = document.getElementById("modal-save-confirm");
  const DEFAULT_ROW_ICON = "/static/zap-icon.png";

  const modalDelBackdrop = document.getElementById("modal-del-backdrop");
  const modalDel = document.getElementById("modal-del");
  const modalDelMessage = document.getElementById("modal-del-message");
  const modalDelCancel = document.getElementById("modal-del-cancel");
  const modalDelConfirm = document.getElementById("modal-del-confirm");

  const DEBOUNCE_MS = 220;
  let debounceTimer = null;
  let lastController = null;

  /** @type {string | null} original bookmark title when editing (for rename) */
  let saveOriginalTitle = null;
  /** @type {string | null} pending delete target */
  let deleteTargetTitle = null;

  function ping() {
    fetch("/api/ping", { method: "POST", keepalive: true }).catch(() => {});
  }

  function renderRows(items) {
    rowsEl.textContent = "";
    if (!items.length) {
      tableEl.hidden = true;
      emptyEl.hidden = false;
      return;
    }
    emptyEl.hidden = true;
    tableEl.hidden = false;

    items.forEach((item) => {
      const tr = document.createElement("tr");

      const tdIcon = document.createElement("td");
      tdIcon.className = "col-icon";
      const img = document.createElement("img");
      img.className = "row-favicon";
      img.width = 28;
      img.height = 28;
      img.alt = "";
      img.decoding = "async";
      img.loading = "lazy";
      img.src = item.iconUrl || DEFAULT_ROW_ICON;
      img.referrerPolicy = "no-referrer";
      tdIcon.appendChild(img);

      const tdTitle = document.createElement("td");
      tdTitle.textContent = item.title;

      const tdUrl = document.createElement("td");
      const a = document.createElement("a");
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = item.url;
      tdUrl.appendChild(a);

      const tdAct = document.createElement("td");
      tdAct.className = "col-actions";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-ghost edit";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", () => {
        openSaveModal({
          mode: "edit",
          originalTitle: item.title,
          title: item.title,
          url: item.url,
        });
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-danger del";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", () => {
        openDeleteModal(item.title);
      });

      tdAct.appendChild(editBtn);
      tdAct.appendChild(delBtn);
      tr.appendChild(tdIcon);
      tr.appendChild(tdTitle);
      tr.appendChild(tdUrl);
      tr.appendChild(tdAct);
      rowsEl.appendChild(tr);
    });
  }

  async function loadBookmarks() {
    const q = qEl.value.trim();
    if (lastController) lastController.abort();
    lastController = new AbortController();
    try {
      const res = await fetch(
        "/api/bookmarks?q=" + encodeURIComponent(q),
        { signal: lastController.signal }
      );
      const data = await res.json();
      renderRows(Array.isArray(data) ? data : []);
    } catch (e) {
      if (e.name === "AbortError") return;
      console.error(e);
    }
  }

  function scheduleLoad() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      loadBookmarks();
    }, DEBOUNCE_MS);
  }

  function setSaveError(msg) {
    if (!msg) {
      modalSaveError.hidden = true;
      modalSaveError.textContent = "";
      return;
    }
    modalSaveError.textContent = msg;
    modalSaveError.hidden = false;
  }

  function openSaveModal(opts) {
    const mode = opts.mode || "add";
    saveOriginalTitle = mode === "edit" ? opts.originalTitle : null;
    modalSaveTitle.textContent = mode === "edit" ? "Edit bookmark" : "Add bookmark";
    modalTitle.value = opts.title || "";
    modalUrl.value = opts.url || "";
    setSaveError("");
    modalSaveBackdrop.hidden = false;
    modalSave.hidden = false;
    modalSaveBackdrop.setAttribute("aria-hidden", "false");
    modalSave.removeAttribute("aria-hidden");
    setTimeout(() => modalTitle.focus(), 0);
  }

  function closeSaveModal() {
    modalSaveBackdrop.hidden = true;
    modalSave.hidden = true;
    modalSaveBackdrop.setAttribute("aria-hidden", "true");
    modalSave.setAttribute("aria-hidden", "true");
    saveOriginalTitle = null;
    setSaveError("");
  }

  function openDeleteModal(title) {
    deleteTargetTitle = title;
    modalDelMessage.textContent =
      "Remove “" + title + "” from your bookmarks? This cannot be undone.";
    modalDelBackdrop.hidden = false;
    modalDel.hidden = false;
    modalDelBackdrop.setAttribute("aria-hidden", "false");
    modalDel.removeAttribute("aria-hidden");
    setTimeout(() => modalDelCancel.focus(), 0);
  }

  function closeDeleteModal() {
    modalDelBackdrop.hidden = true;
    modalDel.hidden = true;
    modalDelBackdrop.setAttribute("aria-hidden", "true");
    modalDel.setAttribute("aria-hidden", "true");
    deleteTargetTitle = null;
  }

  async function submitSave() {
    const title = modalTitle.value.trim();
    const url = modalUrl.value.trim();
    if (!title) {
      setSaveError("Title is required.");
      modalTitle.focus();
      return;
    }
    if (!url) {
      setSaveError("URL is required.");
      modalUrl.focus();
      return;
    }
    setSaveError("");
    modalSaveConfirm.disabled = true;
    modalSaveConfirm.textContent = "Saving…";
    try {
      if (saveOriginalTitle && saveOriginalTitle !== title) {
        await fetch("/api/bookmarks/" + encodeURIComponent(saveOriginalTitle), {
          method: "DELETE",
        });
      }
      const res = await fetch("/api/bookmarks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, url }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setSaveError(err.error || "Save failed.");
        return;
      }
      closeSaveModal();
      await loadBookmarks();
    } catch (e) {
      setSaveError("Network error.");
      console.error(e);
    } finally {
      modalSaveConfirm.disabled = false;
      modalSaveConfirm.textContent = "Save";
    }
  }

  async function submitDelete() {
    if (!deleteTargetTitle) return;
    const t = deleteTargetTitle;
    try {
      await fetch("/api/bookmarks/" + encodeURIComponent(t), { method: "DELETE" });
      closeDeleteModal();
      await loadBookmarks();
    } catch (e) {
      console.error(e);
    }
  }

  qEl.addEventListener("input", scheduleLoad);
  qEl.addEventListener("search", () => {
    if (debounceTimer) clearTimeout(debounceTimer);
    loadBookmarks();
  });

  btnOpenAdd.addEventListener("click", () => {
    openSaveModal({ mode: "add" });
  });

  modalSaveCancel.addEventListener("click", closeSaveModal);
  modalSaveBackdrop.addEventListener("click", closeSaveModal);
  modalSaveConfirm.addEventListener("click", submitSave);

  modalDelCancel.addEventListener("click", closeDeleteModal);
  modalDelBackdrop.addEventListener("click", closeDeleteModal);
  modalDelConfirm.addEventListener("click", submitDelete);

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!modalSave.hidden) closeSaveModal();
    else if (!modalDel.hidden) closeDeleteModal();
  });

  setInterval(ping, PING_MS);
  ping();

  loadBookmarks();
})();

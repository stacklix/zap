(function () {
  "use strict";

  const PING_MS = 12000;

  const qEl = document.getElementById("q");
  const langSelectEl = document.getElementById("lang-select");
  const appVersionEl = document.getElementById("app-version");
  const rowsEl = document.getElementById("rows");
  const tableEl = document.getElementById("data-table");
  const emptyEl = document.getElementById("empty-state");
  const btnOpenAdd = document.getElementById("btn-open-add");
  const btnOpenHelp = document.getElementById("btn-open-help");

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
  const modalHelpBackdrop = document.getElementById("modal-help-backdrop");
  const modalHelp = document.getElementById("modal-help");
  const modalHelpClose = document.getElementById("modal-help-close");
  const labelSearchEl = document.getElementById("label-search");
  const hintLiveEl = document.getElementById("hint-live");
  const emptyTitleEl = document.getElementById("empty-title");
  const emptySubEl = document.getElementById("empty-sub");
  const thIconEl = document.getElementById("th-icon");
  const thTitleEl = document.getElementById("th-title");
  const thUrlEl = document.getElementById("th-url");
  const thActionsEl = document.getElementById("th-actions");
  const labelModalTitleEl = document.getElementById("label-modal-title");
  const labelModalUrlEl = document.getElementById("label-modal-url");
  const helpItemSearchEl = document.getElementById("help-item-search");
  const helpItemEditUrlEl = document.getElementById("help-item-edit-url");
  const helpItemEditEl = document.getElementById("help-item-edit");
  const helpItemDelEl = document.getElementById("help-item-del");
  const helpItemWebEl = document.getElementById("help-item-web");
  let toastTimer = null;

  const I18N = {
    en: {
      help: "Help",
      add: "Add",
      search: "Search",
      hint: "Results update as you type. Server stops shortly after you close this tab.",
      noMatch: "No bookmarks match",
      noMatchSub: "Try another search or add a bookmark.",
      thIcon: "Icon",
      thTitle: "Title",
      thUrl: "URL",
      thActions: "Actions",
      title: "Title",
      url: "URL",
      cancel: "Cancel",
      save: "Save",
      saving: "Saving…",
      addBookmark: "Add bookmark",
      editBookmark: "Edit bookmark",
      deleteBookmark: "Delete bookmark",
      delete: "Delete",
      edit: "Edit",
      visit: "Visit",
      helpTitle: "Zap command help",
      close: "Close",
      reqTitle: "Title is required.",
      reqUrl: "URL is required.",
      saveFailed: "Save failed.",
      netErr: "Network error.",
      removeMsg: (t) => "Remove “" + t + "” from your bookmarks? This cannot be undone.",
      helpSearch: "<code>zap &lt;text&gt;</code> Search bookmarks by title or URL.",
      helpEditUrl: "<code>zap edit &lt;title&gt; &lt;url&gt;</code> Add or update a bookmark.",
      helpEdit: "<code>zap edit &lt;title&gt;</code> Add/update and prompt URL in dialog.",
      helpDel: "<code>zap del &lt;title&gt;</code> Delete a bookmark with confirmation.",
      helpWeb: "<code>zap web</code> Open this web manager page.",
      iconFetchFail: "Bookmark saved, but icon fetch failed.",
    },
    "zh-Hans": {
      help: "帮助",
      add: "新增",
      search: "搜索",
      hint: "输入时会实时刷新结果。关闭所有标签页后，服务会很快自动停止。",
      noMatch: "未匹配到书签",
      noMatchSub: "请尝试其他关键词，或新增一个书签。",
      thIcon: "图标",
      thTitle: "标题",
      thUrl: "链接",
      thActions: "操作",
      title: "标题",
      url: "链接",
      cancel: "取消",
      save: "保存",
      saving: "保存中…",
      addBookmark: "新增书签",
      editBookmark: "编辑书签",
      deleteBookmark: "删除书签",
      delete: "删除",
      edit: "编辑",
      visit: "访问",
      helpTitle: "Zap 命令帮助",
      close: "关闭",
      reqTitle: "标题不能为空。",
      reqUrl: "链接不能为空。",
      saveFailed: "保存失败。",
      netErr: "网络错误。",
      removeMsg: (t) => "要从书签中删除“" + t + "”吗？此操作不可撤销。",
      helpSearch: "<code>zap &lt;text&gt;</code> 按标题或链接搜索书签。",
      helpEditUrl: "<code>zap edit &lt;title&gt; &lt;url&gt;</code> 新增或更新书签。",
      helpEdit: "<code>zap edit &lt;title&gt;</code> 新增/更新，并通过弹窗输入链接。",
      helpDel: "<code>zap del &lt;title&gt;</code> 删除书签（会二次确认）。",
      helpWeb: "<code>zap web</code> 打开当前网页管理界面。",
      iconFetchFail: "书签已保存，但图标抓取失败。",
    },
    "zh-Hant": {
      help: "說明",
      add: "新增",
      search: "搜尋",
      hint: "輸入時會即時更新結果。關閉所有分頁後，服務會很快自動停止。",
      noMatch: "找不到符合的書籤",
      noMatchSub: "請嘗試其他關鍵字，或新增一個書籤。",
      thIcon: "圖示",
      thTitle: "標題",
      thUrl: "連結",
      thActions: "操作",
      title: "標題",
      url: "連結",
      cancel: "取消",
      save: "儲存",
      saving: "儲存中…",
      addBookmark: "新增書籤",
      editBookmark: "編輯書籤",
      deleteBookmark: "刪除書籤",
      delete: "刪除",
      edit: "編輯",
      visit: "造訪",
      helpTitle: "Zap 指令說明",
      close: "關閉",
      reqTitle: "標題不可為空。",
      reqUrl: "連結不可為空。",
      saveFailed: "儲存失敗。",
      netErr: "網路錯誤。",
      removeMsg: (t) => "要從書籤中移除「" + t + "」嗎？此動作無法復原。",
      helpSearch: "<code>zap &lt;text&gt;</code> 依標題或連結搜尋書籤。",
      helpEditUrl: "<code>zap edit &lt;title&gt; &lt;url&gt;</code> 新增或更新書籤。",
      helpEdit: "<code>zap edit &lt;title&gt;</code> 新增/更新，並以對話框輸入連結。",
      helpDel: "<code>zap del &lt;title&gt;</code> 刪除書籤（會再次確認）。",
      helpWeb: "<code>zap web</code> 開啟目前網頁管理介面。",
      iconFetchFail: "書籤已儲存，但圖示抓取失敗。",
    },
  };
  let currentLang = "en";

  function normalizeLang(raw) {
    const s = String(raw || "").toLowerCase();
    if (s.includes("hant") || s.startsWith("zh-tw") || s.startsWith("zh-hk") || s.startsWith("zh-mo")) return "zh-Hant";
    if (s.startsWith("zh")) return "zh-Hans";
    return "en";
  }

  function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
  }

  function applyI18n() {
    document.documentElement.lang = currentLang;
    btnOpenHelp.textContent = t("help");
    btnOpenAdd.textContent = t("add");
    labelSearchEl.textContent = t("search");
    hintLiveEl.textContent = t("hint");
    emptyTitleEl.textContent = t("noMatch");
    emptySubEl.textContent = t("noMatchSub");
    thIconEl.textContent = t("thIcon");
    thTitleEl.textContent = t("thTitle");
    thUrlEl.textContent = t("thUrl");
    thActionsEl.textContent = t("thActions");
    modalSaveTitle.textContent = saveOriginalTitle ? t("editBookmark") : t("addBookmark");
    labelModalTitleEl.textContent = t("title");
    labelModalUrlEl.textContent = t("url");
    modalSaveCancel.textContent = t("cancel");
    modalSaveConfirm.textContent = t("save");
    modalDel.querySelector("#modal-del-title").textContent = t("deleteBookmark");
    modalDelCancel.textContent = t("cancel");
    modalDelConfirm.textContent = t("delete");
    modalHelp.querySelector("#modal-help-title").textContent = t("helpTitle");
    modalHelpClose.textContent = t("close");
    helpItemSearchEl.innerHTML = t("helpSearch");
    helpItemEditUrlEl.innerHTML = t("helpEditUrl");
    helpItemEditEl.innerHTML = t("helpEdit");
    helpItemDelEl.innerHTML = t("helpDel");
    helpItemWebEl.innerHTML = t("helpWeb");
  }

  function showToast(msg) {
    let toast = document.getElementById("toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "toast";
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("show");
      toastTimer = null;
    }, 2800);
  }

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

  async function loadVersion() {
    try {
      const res = await fetch("/api/version");
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.version && appVersionEl) {
        appVersionEl.textContent = "v" + data.version;
      }
    } catch (_e) {
      // noop: version is optional UI hint
    }
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
      editBtn.className = "btn btn-edit edit";
      editBtn.textContent = t("edit");
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
      delBtn.textContent = t("delete");
      delBtn.addEventListener("click", () => {
        openDeleteModal(item.title);
      });

      tdAct.appendChild(delBtn);
      tdAct.appendChild(editBtn);
      const visitBtn = document.createElement("button");
      visitBtn.type = "button";
      visitBtn.className = "btn btn-ghost visit";
      visitBtn.textContent = t("visit");
      visitBtn.addEventListener("click", () => {
        window.open(item.url, "_blank", "noopener,noreferrer");
      });
      tdAct.appendChild(visitBtn);
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
    modalSaveTitle.textContent = mode === "edit" ? t("editBookmark") : t("addBookmark");
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
      t("removeMsg")(title);
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

  function openHelpModal() {
    modalHelpBackdrop.hidden = false;
    modalHelp.hidden = false;
    modalHelpBackdrop.setAttribute("aria-hidden", "false");
    modalHelp.removeAttribute("aria-hidden");
    setTimeout(() => modalHelpClose.focus(), 0);
  }

  function closeHelpModal() {
    modalHelpBackdrop.hidden = true;
    modalHelp.hidden = true;
    modalHelpBackdrop.setAttribute("aria-hidden", "true");
    modalHelp.setAttribute("aria-hidden", "true");
  }

  async function submitSave() {
    const title = modalTitle.value.trim();
    const url = modalUrl.value.trim();
    if (!title) {
      setSaveError(t("reqTitle"));
      modalTitle.focus();
      return;
    }
    if (!url) {
      setSaveError(t("reqUrl"));
      modalUrl.focus();
      return;
    }
    setSaveError("");
    modalSaveConfirm.disabled = true;
    modalSaveConfirm.textContent = t("saving");
    try {
      if (saveOriginalTitle && saveOriginalTitle !== title) {
        await fetch("/api/bookmarks/" + encodeURIComponent(saveOriginalTitle), {
          method: "DELETE",
        });
      }
      const res = await fetch("/api/bookmarks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          url,
          mode: saveOriginalTitle ? "edit" : "add",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setSaveError(err.error || t("saveFailed"));
        return;
      }
      const payload = await res.json().catch(() => ({}));
      closeSaveModal();
      await loadBookmarks();
      if (!payload.icon) {
        console.warn("Icon fetch failed", {
          title,
          url,
          reason: payload.iconError || null,
          response: payload,
        });
        showToast(t("iconFetchFail"));
      }
    } catch (e) {
      setSaveError(t("netErr"));
      console.error(e);
    } finally {
      modalSaveConfirm.disabled = false;
      modalSaveConfirm.textContent = t("save");
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
  langSelectEl.addEventListener("change", () => {
    currentLang = langSelectEl.value;
    try { localStorage.setItem("zap.lang", currentLang); } catch (_e) {}
    applyI18n();
    loadBookmarks();
  });
  btnOpenHelp.addEventListener("click", openHelpModal);

  modalSaveCancel.addEventListener("click", closeSaveModal);
  modalSaveBackdrop.addEventListener("click", closeSaveModal);
  modalSaveConfirm.addEventListener("click", submitSave);

  modalDelCancel.addEventListener("click", closeDeleteModal);
  modalDelBackdrop.addEventListener("click", closeDeleteModal);
  modalDelConfirm.addEventListener("click", submitDelete);
  modalHelpClose.addEventListener("click", closeHelpModal);
  modalHelpBackdrop.addEventListener("click", closeHelpModal);

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!modalSave.hidden) closeSaveModal();
    else if (!modalDel.hidden) closeDeleteModal();
    else if (!modalHelp.hidden) closeHelpModal();
  });

  setInterval(ping, PING_MS);
  ping();
  let savedLang = "";
  try { savedLang = localStorage.getItem("zap.lang") || ""; } catch (_e) {}
  currentLang = savedLang
    ? normalizeLang(savedLang)
    : normalizeLang((navigator.languages && navigator.languages[0]) || navigator.language || "en");
  langSelectEl.value = currentLang;
  applyI18n();
  loadVersion();

  loadBookmarks();
})();

(function () {
  "use strict";

  const I18N = window.__I18N__ || {};
  function t(key, vars) {
    let s = I18N[key] || key;
    if (vars) {
      for (const k of Object.keys(vars)) {
        s = s.replace(new RegExp("\\{" + k + "\\}", "g"), String(vars[k]));
      }
    }
    return s;
  }

  const state = {
    tab: "files",
    relDir: "",
    page: 1,
    totalPages: 1,
    trusted: false,
    showHidden: false,
    activeFolder: "downloads",
    selected: new Set(),
    galleryAlbum: "",
    galleryOffset: 0,
    galleryHasMore: false,
    galleryGroups: [],
    galleryAlbums: [],
    parallaxEnabled: localStorage.getItem("airshare_parallax") !== "0",
    wideView: localStorage.getItem("airshare_wide") === "1",
    pendingDeletePaths: [],
    pickerMode: "move",
    pickerPaths: [],
    pickerDest: "",
    accessTargetKey: null,
    accessPoll: null
  };

  function toast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 2600);
  }

  function esc(str) {
    return String(str || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[c]));
  }

  function encPath(rel) {
    return String(rel || "").split("/").map(encodeURIComponent).join("/");
  }

  function fileIconSvg(name, isDir, kind) {
    if (isDir) {
      return `<svg viewBox="0 0 40 40" width="36" height="36" fill="none">
        <path d="M4 11a4 4 0 0 1 4-4h8l3 4h13a4 4 0 0 1 4 4v15a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V11z" fill="rgba(59,130,246,0.18)" stroke="#3b82f6" stroke-width="2"/>
      </svg>`;
    }
    const ext = (name.includes(".") ? name.split(".").pop() : "").toLowerCase();
    let label = ext ? ext.slice(0, 4).toUpperCase() : "FILE";
    let color = "#64748b";

    if (ext === "pdf") { color = "#ef4444"; label = "PDF"; }
    else if (["doc", "docx", "rtf", "odt"].includes(ext)) { color = "#2563eb"; label = ext === "doc" ? "DOC" : "DOCX"; }
    else if (["xls", "xlsx", "csv", "ods"].includes(ext)) { color = "#16a34a"; label = ext.toUpperCase(); }
    else if (["ppt", "pptx", "odp"].includes(ext)) { color = "#ea580c"; label = "PPT"; }
    else if (["fb2", "epub", "mobi", "djvu"].includes(ext)) { color = "#a855f7"; label = ext.toUpperCase(); }
    else if (["apk", "xapk", "aab"].includes(ext)) { color = "#22c55e"; label = ext.toUpperCase(); }
    else if (["exe", "msi", "iso", "dmg"].includes(ext)) { color = "#0284c7"; label = ext.toUpperCase(); }
    else if (["torrent", "db", "sqlite"].includes(ext)) { color = "#0d9488"; label = ext === "torrent" ? "TOR" : "DB"; }
    else if (kind === "img" || ["jpg", "jpeg", "png", "webp", "gif", "bmp", "heic", "svg"].includes(ext)) { color = "#ec4899"; label = "IMG"; }
    else if (kind === "vid" || ["mp4", "mkv", "mov", "webm", "avi", "m4v"].includes(ext)) { color = "#8b5cf6"; label = "VID"; }
    else if (kind === "aud" || ["mp3", "wav", "flac", "ogg", "m4a", "aac"].includes(ext)) { color = "#f59e0b"; label = "AUD"; }
    else if (["zip", "rar", "7z", "tar", "gz"].includes(ext)) { color = "#d97706"; label = ext.toUpperCase(); }
    else if (["py", "kt", "java", "js", "ts", "html", "css", "json", "xml", "md", "txt", "sh", "c", "cpp"].includes(ext)) { color = "#06b6d4"; label = ext.toUpperCase(); }

    return `<svg viewBox="0 0 40 40" width="36" height="36" fill="none">
      <path d="M9 5h15l8 8v21a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" fill="${color}22" stroke="${color}" stroke-width="1.8"/>
      <path d="M24 5v8h8" stroke="${color}" stroke-width="1.8"/>
      <rect x="6" y="21" width="28" height="12" rx="4" fill="${color}"/>
      <text x="20" y="29.5" text-anchor="middle" fill="#fff" font-size="8.2" font-weight="800" font-family="system-ui,sans-serif">${esc(label)}</text>
    </svg>`;
  }

  function sha256Bytes(bytes) {
    const K = new Uint32Array([
      0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ]);
    const l = bytes.length;
    const bitLen = l * 8;
    const padLen = ((l + 9 + 63) & ~63);
    const buf = new Uint8Array(padLen);
    buf.set(bytes);
    buf[l] = 0x80;
    const dv = new DataView(buf.buffer);
    dv.setUint32(padLen - 8, Math.floor(bitLen / 0x100000000), false);
    dv.setUint32(padLen - 4, bitLen >>> 0, false);

    let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
    let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
    const w = new Uint32Array(64);
    for (let off = 0; off < padLen; off += 64) {
      for (let i = 0; i < 16; i++) w[i] = dv.getUint32(off + i * 4, false);
      for (let i = 16; i < 64; i++) {
        const s0 = ((w[i-15] >>> 7) | (w[i-15] << 25)) ^ ((w[i-15] >>> 18) | (w[i-15] << 14)) ^ (w[i-15] >>> 3);
        const s1 = ((w[i-2] >>> 17) | (w[i-2] << 15)) ^ ((w[i-2] >>> 19) | (w[i-2] << 13)) ^ (w[i-2] >>> 10);
        w[i] = (w[i-16] + s0 + w[i-7] + s1) >>> 0;
      }
      let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
      for (let i = 0; i < 64; i++) {
        const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + K[i] + w[i]) >>> 0;
        const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0;
        d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
      h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
    }
    return [h0,h1,h2,h3,h4,h5,h6,h7].map(x => x.toString(16).padStart(8, "0")).join("");
  }

  function initSky() {
    const far = document.getElementById("layer-far");
    const near = document.getElementById("layer-near");
    for (let i = 0; i < 65; i++) {
      const s = document.createElement("div");
      s.className = "star";
      const sz = (1 + Math.random() * 2.1).toFixed(1) + "px";
      s.style.width = sz; s.style.height = sz;
      s.style.left = (Math.random() * 100).toFixed(2) + "%";
      s.style.top = (Math.random() * 100).toFixed(2) + "%";
      s.style.animationDelay = (Math.random() * 4).toFixed(2) + "s";
      (i % 2 === 0 ? far : near).appendChild(s);
    }
    for (let i = 0; i < 7; i++) {
      const c = document.createElement("div");
      c.className = "cloud";
      c.style.width = (150 + Math.random() * 200) + "px";
      c.style.height = (50 + Math.random() * 46) + "px";
      c.style.top = (6 + i * 13) + "%";
      c.style.left = (-20 + i * 15) + "%";
      c.style.animationDuration = (34 + i * 7) + "s";
      (i % 2 === 0 ? far : near).appendChild(c);
    }
    window.addEventListener("mousemove", (e) => {
      if (!state.parallaxEnabled) {
        far.style.transform = "none";
        near.style.transform = "none";
        return;
      }
      const dx = (e.clientX / window.innerWidth - 0.5) * 2;
      const dy = (e.clientY / window.innerHeight - 0.5) * 2;
      far.style.transform = `translate3d(${(-dx * 10).toFixed(1)}px, ${(-dy * 10).toFixed(1)}px, 0)`;
      near.style.transform = `translate3d(${(-dx * 22).toFixed(1)}px, ${(-dy * 22).toFixed(1)}px, 0)`;
    });
  }

  function updateSelectionUi() {
    const n = state.selected.size;
    const btnZip = document.getElementById("btn-download-zip");
    const btnMove = document.getElementById("btn-bulk-move");
    const btnCopy = document.getElementById("btn-bulk-copy");
    const btnDel = document.getElementById("btn-bulk-delete");
  const btnHide = document.getElementById("btn-bulk-hide");

    btnZip.style.display = (n > 0 && state.tab !== "trash") ? "inline-flex" : "none";
    btnZip.textContent = `⬇ ${t("web_download_zip")} (${n})`;

    const canEdit = state.trusted && state.tab !== "trash" && state.tab !== "gallery";
    btnMove.style.display = (n > 0 && canEdit) ? "inline-flex" : "none";
    btnMove.textContent = `📦 ${t("web_move_btn")} (${n})`;
    btnCopy.style.display = (n > 0 && canEdit) ? "inline-flex" : "none";
    btnCopy.textContent = `📋 ${t("web_copy_btn")} (${n})`;
    btnDel.style.display = (n > 0 && state.trusted && state.tab !== "gallery") ? "inline-flex" : "none";
    btnDel.textContent = `🗑 ${t("web_delete_btn")} (${n})`;
if (btnHide) {
  btnHide.style.display = (n > 0 && canEdit) ? "inline-flex" : "none";
  btnHide.textContent = `👁 ${t("web_ctx_hide")} (${n})`;
}
  }

  function folderTitleByKey(key) {
    const map = {
      downloads: t("folder_dl_title"),
      camera: t("folder_cam_title"),
      documents: t("folder_doc_title"),
      all: t("folder_all_title")
    };
    return map[key] || key;
  }

  function applyRoleUi() {
    const badge = document.getElementById("role-badge");
    badge.className = "badge " + (state.trusted ? "badge-trusted" : "badge-guest");
    badge.textContent = state.trusted ? t("web_trusted_badge") : t("web_guest_badge");
    document.getElementById("active-folder-label").textContent = "📁 " + folderTitleByKey(state.activeFolder);

    document.getElementById("btn-access").style.display = state.trusted ? "inline-flex" : "none";
    document.getElementById("tab-trash").style.display = state.trusted ? "inline-block" : "none";
    document.getElementById("btn-hidden").style.display = (state.trusted && state.tab === "files") ? "inline-flex" : "none";
    document.getElementById("btn-hidden").classList.toggle("active", state.showHidden);
    document.getElementById("btn-upload").style.display = (state.trusted && state.tab === "files") ? "inline-flex" : "none";
    document.getElementById("btn-mkdir").style.display = (state.trusted && state.tab === "files") ? "inline-flex" : "none";
    document.getElementById("dropzone").style.display = (state.trusted && state.tab === "files") ? "block" : "none";
    document.getElementById("btn-empty-trash").style.display = (state.trusted && state.tab === "trash") ? "inline-flex" : "none";
  }

  async function apiOp(op, body) {
    const r = await fetch("/api/op?op=" + encodeURIComponent(op), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    if (r.status === 401) { window.location.href = "/"; return null; }
    return r.json();
  }

  function renderFileRows(items, opts) {
    const area = document.getElementById("content-area");
    if (!items || !items.length) {
      area.innerHTML = `<div class="empty-state">${esc(t("web_no_files"))}</div>`;
      return;
    }
    const list = document.createElement("div");
    list.className = "file-list";

    for (const item of items) {
      const row = document.createElement("div");
      row.className = "file-row" + (state.selected.has(item.rel_path) ? " selected" : "");
      const isDir = !!item.is_dir;

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "file-cb";
      cb.checked = state.selected.has(item.rel_path);
      cb.addEventListener("change", () => {
        if (cb.checked) state.selected.add(item.rel_path);
        else state.selected.delete(item.rel_path);
        row.classList.toggle("selected", cb.checked);
        updateSelectionUi();
      });

      const icon = document.createElement("div");
      icon.className = "file-icon";
      icon.innerHTML = fileIconSvg(item.name, isDir, item.kind);

      const main = document.createElement("div");
      main.className = "file-main";
      main.innerHTML = `<div class="file-name">${esc(item.name)}</div>
        <div class="file-sub">${esc(item.size_str || "")}${opts && opts.showPath ? " • " + esc(item.rel_path) : ""}</div>`;
      main.addEventListener("click", () => {
        if (isDir) {
          state.tab = "files";
          state.relDir = item.rel_path;
          state.page = 1;
          syncTabButtons();
          loadFiles();
        } else if (item.kind === "img" || item.kind === "image" || item.kind === "vid" || item.kind === "video" || item.kind === "aud" || item.kind === "audio") {
          openCinema(item.name, "/file/" + encPath(item.rel_path) + "?preview=1", "/file/" + encPath(item.rel_path), item.kind);
        } else {
          window.location.href = "/file/" + encPath(item.rel_path);
        }
      });

      const actions = document.createElement("div");
      actions.className = "file-actions";

          const dlBtn = document.createElement("a");
    dlBtn.className = "download-btn";
    if (isDir) {
      dlBtn.href = "/zip?dir=" + encodeURIComponent(item.rel_path);
      dlBtn.title = "ZIP";
    } else {
      dlBtn.href = "/file/" + encPath(item.rel_path) + "?download=1";
      dlBtn.setAttribute("download", item.name);
      dlBtn.title = t("web_ctx_download") || "Download";
    }
    dlBtn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg>`;
    dlBtn.addEventListener("click", (e) => e.stopPropagation());
    actions.appendChild(dlBtn);
    row.addEventListener("contextmenu", (ev) => { ev.preventDefault(); openCtxMenu(ev, item); });

      row.append(cb, icon, main, actions);
      list.appendChild(row);
    }
    area.innerHTML = "";
    area.appendChild(list);
  }

  async function loadFiles() {
    state.selected.clear();
    document.getElementById("cb-select-all").checked = false;
    updateSelectionUi();

    const r = await fetch(`/api/list?dir=${encodeURIComponent(state.relDir)}&page=${state.page}`);
    if (r.status === 401) { window.location.href = "/"; return; }
    const data = await r.json();
    state.trusted = !!data.trusted;
    state.showHidden = !!data.show_hidden;
    state.activeFolder = data.active_folder || "downloads";
    state.totalPages = data.total_pages || 1;
    applyRoleUi();

    const favEl = document.getElementById("favorites-strip");
    if (data.favorites && data.favorites.length && !state.relDir) {
      favEl.style.display = "flex";
      favEl.innerHTML = "";
      for (const f of data.favorites) {
        const chip = document.createElement("button");
        chip.className = "fav-chip";
        chip.type = "button";
        chip.textContent = "★ " + f;
        chip.addEventListener("click", () => {
          state.relDir = f;
          state.page = 1;
          loadFiles();
        });
        favEl.appendChild(chip);
      }
    } else {
      favEl.style.display = "none";
    }

    const bc = document.getElementById("breadcrumbs");
    bc.style.display = "flex";
    bc.innerHTML = "";
    const rootCrumb = document.createElement("span");
    rootCrumb.className = "crumb";
    rootCrumb.textContent = "🏠 " + folderTitleByKey(state.activeFolder);
    rootCrumb.addEventListener("click", () => { state.relDir = ""; state.page = 1; loadFiles(); });
    bc.appendChild(rootCrumb);
    if (state.relDir) {
      let acc = "";
      for (const part of state.relDir.split("/").filter(Boolean)) {
        const sep = document.createElement("span");
        sep.textContent = "/";
        bc.appendChild(sep);
        acc = acc ? acc + "/" + part : part;
        const target = acc;
        const c = document.createElement("span");
        c.className = "crumb";
        c.textContent = part;
        c.addEventListener("click", () => { state.relDir = target; state.page = 1; loadFiles(); });
        bc.appendChild(c);
      }
    }

    renderFileRows(data.items || [], { showPath: false });
    renderPager(); const ic = document.getElementById("items-count"); if (ic) ic.textContent = t("web_total_items", { count: data.total_items ?? (data.items ? data.items.length : 0) });
  }

  function renderPager() {
    const pager = document.getElementById("pager");
    if (state.tab !== "files" || state.totalPages <= 1) {
      pager.style.display = "none";
      return;
    }
    pager.style.display = "flex";
    pager.innerHTML = "";
    const prev = document.createElement("button");
    prev.className = "btn";
    prev.textContent = "←";
    prev.disabled = state.page <= 1;
    prev.addEventListener("click", () => { state.page--; loadFiles(); });

    const info = document.createElement("span");
    info.style.fontSize = "13px";
    info.style.color = "var(--muted)";
    info.textContent = `${state.page} / ${state.totalPages}`;

    const next = document.createElement("button");
    next.className = "btn";
    next.textContent = "→";
    next.disabled = state.page >= state.totalPages;
    next.addEventListener("click", () => { state.page++; loadFiles(); });

    pager.append(prev, info, next);
  }

  async function loadGallery(reset) {
    if (reset) {
      state.galleryOffset = 0;
      state.galleryGroups = [];
    }
    state.selected.clear();
    updateSelectionUi();
    applyRoleUi();
    document.getElementById("breadcrumbs").style.display = "none";
    document.getElementById("favorites-strip").style.display = "none";
    document.getElementById("pager").style.display = "none";

    const url = `/api/gallery?album=${encodeURIComponent(state.galleryAlbum)}&offset=${state.galleryOffset}&limit=120`;
    const r = await fetch(url);
    if (r.status === 401) { window.location.href = "/"; return; }
    const data = await r.json();
    state.galleryAlbums = data.albums || [];
    state.galleryHasMore = !!data.has_more;
    state.galleryOffset += 120;

    for (const g of (data.groups || [])) {
      const existing = state.galleryGroups.find(x => x.date === g.date);
      if (existing) existing.items.push(...g.items);
      else state.galleryGroups.push({ date: g.date, items: [...g.items] });
    }
    renderGallery(data.all_total || 0);
  }

  function renderGallery(allTotal) {
    const area = document.getElementById("content-area");
    area.innerHTML = "";

    const albumBar = document.createElement("div");
    albumBar.className = "album-bar";

    const allPill = document.createElement("button");
    allPill.className = "album-pill" + (state.galleryAlbum === "" ? " active" : "");
    allPill.type = "button";
    allPill.textContent = `${t("web_all_albums")} (${allTotal})`;
    allPill.addEventListener("click", () => { state.galleryAlbum = ""; loadGallery(true); });
    albumBar.appendChild(allPill);

    for (const alb of state.galleryAlbums) {
      if (alb.hidden && !state.showHidden) continue;
      const p = document.createElement("button");
      p.className = "album-pill" + (state.galleryAlbum === alb.name ? " active" : "");
      p.type = "button";
      p.innerHTML = `<span>${esc(alb.name)} (${alb.count})</span>`;
      p.addEventListener("click", () => { state.galleryAlbum = alb.name; loadGallery(true); });

      if (state.trusted) {
        const hx = document.createElement("span");
        hx.className = "album-hide-x";
        hx.title = alb.hidden ? t("web_unhide_album") : t("web_hide_album");
        hx.textContent = alb.hidden ? "👁" : "✕";
        hx.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          await apiOp("toggle_album", { album: alb.name });
          if (state.galleryAlbum === alb.name) state.galleryAlbum = "";
          loadGallery(true);
        });
        p.appendChild(hx);
      }
      albumBar.appendChild(p);
    }
    area.appendChild(albumBar);

    if (!state.galleryGroups.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = t("web_no_media");
      area.appendChild(empty);
      return;
    }

    for (const group of state.galleryGroups) {
      const h = document.createElement("div");
      h.className = "gallery-date-head";
      h.textContent = group.date;
      area.appendChild(h);

      const grid = document.createElement("div");
      grid.className = "gallery-grid";
      for (const item of group.items) {
        const card = document.createElement("div");
        card.className = "media-card";
        const thumbUrl = `/media/thumb/${encPath(item.rel_path)}?id=${encodeURIComponent(item.id)}`;
        const rawUrl = `/media/raw/${encPath(item.rel_path)}`;
        card.innerHTML = `<img loading="lazy" src="${thumbUrl}" alt="${esc(item.name)}">
          ${(item.kind === "vid" || item.kind === "video") ? '<div class="video-badge">▶</div>' : ""}
          <div class="media-meta">${esc(item.name)}</div>`;
        card.addEventListener("click", () => openCinema(item.name, rawUrl + "?preview=1", rawUrl, item.kind));
        grid.appendChild(card);
      }
      area.appendChild(grid);
    }

    if (state.galleryHasMore) {
      const wrap = document.createElement("div");
      wrap.className = "load-more-wrap";
      const btn = document.createElement("button");
      btn.className = "btn btn-primary";
      btn.type = "button";
      btn.textContent = t("web_load_more");
      btn.addEventListener("click", () => loadGallery(false));
      wrap.appendChild(btn);
      area.appendChild(wrap);
    }
  }

  async function loadRecent() {
    state.selected.clear();
    updateSelectionUi();
    applyRoleUi();
    document.getElementById("breadcrumbs").style.display = "none";
    document.getElementById("favorites-strip").style.display = "none";
    document.getElementById("pager").style.display = "none";

    const r = await fetch("/api/recent");
    if (r.status === 401) { window.location.href = "/"; return; }
    const data = await r.json();
    renderFileRows(data.results || [], { showPath: true });
  }

  async function loadTrash() {
    state.selected.clear();
    updateSelectionUi();
    applyRoleUi();
    document.getElementById("breadcrumbs").style.display = "none";
    document.getElementById("favorites-strip").style.display = "none";
    document.getElementById("pager").style.display = "none";

    const r = await fetch("/api/trash");
    if (r.status === 401) { window.location.href = "/"; return; }
    const data = await r.json();
    const area = document.getElementById("content-area");
    const items = data.items || [];
    if (!items.length) {
      area.innerHTML = `<div class="empty-state">${esc(t("web_trash_empty"))}</div>`;
      return;
    }

    const hint = document.createElement("div");
    hint.className = "status-box";
    hint.textContent = t("web_open_trash_hint");

    const list = document.createElement("div");
    list.className = "file-list";

    for (const item of items) {
      const row = document.createElement("div");
      row.className = "file-row";
      const icon = document.createElement("div");
      icon.className = "file-icon";
      icon.innerHTML = fileIconSvg(item.name, item.is_dir, "");
      const main = document.createElement("div");
      main.className = "file-main";
      main.innerHTML = `<div class="file-name">${esc(item.name)}</div>
        <div class="file-sub">${esc(item.size_str)} • ${esc(item.orig_rel)}</div>`;

      const actions = document.createElement("div");
      actions.className = "file-actions";

      const bRest = document.createElement("button");
      bRest.className = "btn";
      bRest.type = "button";
      bRest.textContent = "↩";
      bRest.addEventListener("click", async () => {
        await apiOp("restore", { ids: [item.id] });
        toast(t("web_restored"));
        loadTrash();
      });

      const bPurge = document.createElement("button");
      bPurge.className = "btn btn-danger";
      bPurge.type = "button";
      bPurge.textContent = "✕";
      bPurge.addEventListener("click", async () => {
        await apiOp("purge", { ids: [item.id] });
        toast(t("web_purged"));
        loadTrash();
      });

      actions.append(bRest, bPurge);
      row.append(icon, main, actions);
      list.appendChild(row);
    }

    area.innerHTML = "";
    area.append(hint, list);
  }

  let searchDebounce = null;
  async function runSearch(q) {
    if (!q) { reloadCurrentTab(); return; }
    state.selected.clear();
    updateSelectionUi();
    document.getElementById("breadcrumbs").style.display = "none";
    document.getElementById("favorites-strip").style.display = "none";
    document.getElementById("pager").style.display = "none";
    const r = await fetch("/api/search?q=" + encodeURIComponent(q));
    if (r.status === 401) { window.location.href = "/"; return; }
    const data = await r.json();
    renderFileRows(data.results || [], { showPath: true });
  }

  async function uploadFiles(fileList) {
    if (!state.trusted || !fileList || !fileList.length) return;
    const prog = document.getElementById("upload-progress");
    const statusTxt = document.getElementById("upload-status-text");
    const fill = document.getElementById("upload-fill");
    prog.style.display = "block";

    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];
      statusTxt.textContent = `${f.name} (${i + 1}/${fileList.length})...`;
      fill.style.width = "10%";
      const buf = new Uint8Array(await f.arrayBuffer());
      const sha = buf.length <= 25 * 1024 * 1024 ? sha256Bytes(buf) : "";

      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/upload?dir=${encodeURIComponent(state.relDir)}&name=${encodeURIComponent(f.name)}`);
        if (sha) xhr.setRequestHeader("X-AirShare-SHA256", sha);
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            fill.style.width = Math.round((ev.loaded / ev.total) * 100) + "%";
          }
        };
        xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(xhr.responseText)));
        xhr.onerror = () => reject(new Error("Upload failed"));
        xhr.send(f);
      }).catch((err) => toast(err.message || "Upload error"));
    }

    prog.style.display = "none";
    fill.style.width = "0%";
    toast(t("uploaded", { file: fileList.length + " file(s)" }));
    loadFiles();
  }

  function openDeleteModal(paths) {
    state.pendingDeletePaths = paths;
    const title = paths.length === 1
      ? t("web_del_title_one")
      : t("web_del_title_many", { n: paths.length });
    document.getElementById("del-modal-title").textContent = title;
    document.getElementById("del-modal-hint").textContent = t("web_del_hint");
    document.getElementById("del-cancel").textContent = t("web_del_no");
    document.getElementById("del-confirm").textContent = t("web_del_yes");
    document.getElementById("modal-delete").classList.add("open");
  }

  async function openFolderPicker(mode, paths) {
    state.pickerMode = mode;
    state.pickerPaths = paths;
    state.pickerDest = "";
    document.getElementById("picker-title").textContent = t("web_choose_folder");
    document.getElementById("picker-cancel").textContent = t("web_del_no");
    document.getElementById("picker-confirm").textContent = mode === "copy" ? t("web_copy_here") : t("web_move_here");

    const listEl = document.getElementById("picker-list");
    listEl.innerHTML = "...";
    document.getElementById("modal-folder-picker").classList.add("open");

    const r = await fetch("/api/folders");
    const data = await r.json();
    listEl.innerHTML = "";
    for (const f of (data.folders || [])) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "folder-opt" + (f.rel === state.pickerDest ? " selected" : "");
      btn.textContent = "📁 " + f.label;
      btn.addEventListener("click", () => {
        state.pickerDest = f.rel;
        listEl.querySelectorAll(".folder-opt").forEach(x => x.classList.remove("selected"));
        btn.classList.add("selected");
      });
      listEl.appendChild(btn);
    }
  }

  function stopAccessPoll() {
    if (state.accessPoll) { clearInterval(state.accessPoll); state.accessPoll = null; }
  }

  function openAccessModal() {
    stopAccessPoll();
    state.accessTargetKey = null;
    document.getElementById("access-title").textContent = t("web_access_title");
    document.getElementById("access-sub").textContent = t("web_access_sub");
    document.getElementById("access-close").textContent = t("close");
    document.getElementById("access-btn-bio").textContent = "👆 " + t("auth_btn_bio");
    document.getElementById("access-btn-pairs").textContent = "🔢 " + t("web_login_use_pairs");
    document.getElementById("access-pin-summary").textContent = "🔑 " + t("web_access_pin_hint");
    document.getElementById("access-confirm-area").style.display = "none";

    const folders = [
      { key: "downloads", title: t("folder_dl_title"), desc: t("folder_dl_desc") },
      { key: "camera", title: t("folder_cam_title"), desc: t("folder_cam_desc") },
      { key: "documents", title: t("folder_doc_title"), desc: t("folder_doc_desc") },
      { key: "all", title: t("folder_all_title"), desc: t("folder_all_desc") }
    ];
    const grid = document.getElementById("access-grid");
    grid.innerHTML = "";
    for (const f of folders) {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "access-card" + (f.key === state.activeFolder ? " active" : "");
      card.innerHTML = `<div class="access-card-title">${esc(f.title)}</div><div class="access-card-desc">${esc(f.desc)}</div>`;
      card.addEventListener("click", () => {
        state.accessTargetKey = f.key;
        grid.querySelectorAll(".access-card").forEach(x => x.classList.remove("active"));
        card.classList.add("active");
        document.getElementById("access-confirm-area").style.display = "block";
        startAccessAuth("biometric");
      });
      grid.appendChild(card);
    }
    document.getElementById("modal-access").classList.add("open");
  }

  async function startAccessAuth(mode) {
    if (!state.accessTargetKey) return;
    stopAccessPoll();
    const stEl = document.getElementById("access-status");
    const codeEl = document.getElementById("access-code");
    codeEl.style.display = "none";
    stEl.className = "status-box";
    stEl.textContent = t("web_access_wait", { folder: folderTitleByKey(state.accessTargetKey) });

    const r = await fetch("/auth/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, action: "access_change", folder_key: state.accessTargetKey })
    });
    const d = await r.json();
    if (!r.ok) {
      stEl.className = "status-box error";
      stEl.textContent = d.error || "Error";
      return;
    }
    if (mode === "pairs" && d.target) {
      codeEl.textContent = d.target;
      codeEl.style.display = "block";
    }
    const cid = d.cid;
    state.accessPoll = setInterval(async () => {
      const sr = await fetch("/auth/status?cid=" + encodeURIComponent(cid));
      const sd = await sr.json();
      if (sd.status === "approved") {
        stopAccessPoll();
        const cr = await fetch("/auth/claim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cid })
        });
        if (cr.ok) window.location.href = "/";
      } else if (sd.status === "denied") {
        stopAccessPoll();
        stEl.className = "status-box error";
        stEl.textContent = t("auth_deny");
      } else if (sd.status === "cancelled" || sd.status === "expired") {
        stopAccessPoll();
        codeEl.style.display = "none";
        stEl.textContent = t("web_cancelled_retry");
      }
    }, 950);
  }

 let _ambilightEnabled = true;
let _ambilightRaf = 0;
let _cinemaMediaEl = null;

function formatCinemaTime(sec) {
  if (!isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + (s < 10 ? "0" : "") + s;
}

function stopCinemaMedia() {
  if (_ambilightRaf) { cancelAnimationFrame(_ambilightRaf); _ambilightRaf = 0; }
  if (_cinemaMediaEl) {
    try { _cinemaMediaEl.pause(); _cinemaMediaEl.removeAttribute("src"); _cinemaMediaEl.load(); } catch (_) {}
    _cinemaMediaEl = null;
  }
  const body = document.getElementById("cinema-body");
  if (body) {
    body.querySelectorAll("video,audio").forEach((m) => {
      try { m.pause(); m.removeAttribute("src"); m.load(); } catch (_) {}
    });
    body.innerHTML = "";
  }
  const modal = document.getElementById("modal-cinema");
  if (modal) modal.classList.remove("open");
  if (document.fullscreenElement) {
    try { document.exitFullscreen(); } catch (_) {}
  }
}

function openCinema(title, previewUrl, dlUrl, kind) {
  if (typeof title === "object" && title !== null) {
    const item = title;
    title = item.name || "";
    previewUrl = "/file/" + encPath(item.rel_path);
    dlUrl = previewUrl + "?download=1";
    kind = item.kind || "other";
  }
  stopCinemaMedia();
  const modal = document.getElementById("modal-cinema");
  const body = document.getElementById("cinema-body");
  const titleEl = document.getElementById("cinema-title");
  const dlEl = document.getElementById("cinema-dl");
  const ambCanvas = document.getElementById("ambilightCanvas");
  const ambBtn = document.getElementById("cinema-ambient-btn");
  const controls = document.getElementById("cinema-controls");
  const playBtn = document.getElementById("c-play");
  const seekEl = document.getElementById("c-seek");
  const timeEl = document.getElementById("c-time");
  const speedBtn = document.getElementById("c-speed");
  const fsBtn = document.getElementById("c-fs");
  const closeBtn = document.getElementById("cinema-close");

  if (titleEl) titleEl.textContent = title || "";
  if (dlEl) { dlEl.href = dlUrl || "#"; dlEl.setAttribute("download", title || ""); }
  if (closeBtn) closeBtn.onclick = stopCinemaMedia;

  if (ambCanvas) {
    ambCanvas.width = 64;
    ambCanvas.height = 36;
    ambCanvas.style.display = _ambilightEnabled ? "" : "none";
  }
  if (ambBtn) {
    ambBtn.classList.toggle("active", _ambilightEnabled);
    ambBtn.onclick = () => {
      _ambilightEnabled = !_ambilightEnabled;
      ambBtn.classList.toggle("active", _ambilightEnabled);
      if (ambCanvas) {
        ambCanvas.style.display = _ambilightEnabled ? "" : "none";
        if (!_ambilightEnabled) ambCanvas.getContext("2d").clearRect(0, 0, 64, 36);
      }
    };
  }

  if (kind === "img" || kind === "image") {
    if (controls) controls.style.display = "none";
    const img = document.createElement("img");
    img.className = "cinema-media";
    img.src = previewUrl;
    img.onload = () => {
      if (_ambilightEnabled && ambCanvas) {
        try { ambCanvas.getContext("2d").drawImage(img, 0, 0, 64, 36); } catch (_) {}
      }
    };
    body.appendChild(img);
  } else if (kind === "vid" || kind === "video" || kind === "aud" || kind === "audio") {
    const isVid = kind === "vid" || kind === "video";
    const m = document.createElement(isVid ? "video" : "audio");
    m.className = "cinema-media";
    m.autoplay = true;
    if (isVid) m.playsInline = true;
    m.controls = !controls;
    m.src = previewUrl;
    _cinemaMediaEl = m;
    body.appendChild(m); if (isVid) { const pipBtn = document.getElementById("c-pip"); if (pipBtn) { pipBtn.style.display = document.pictureInPictureEnabled ? "" : "none"; pipBtn.onclick = () => { if (document.pictureInPictureElement) document.exitPictureInPicture().catch(() => {}); else if (m.requestPictureInPicture) m.requestPictureInPicture().catch(() => {}); }; } const miniBtn = document.getElementById("c-mini"); const cardEl = document.getElementById("cinema-card"); if (miniBtn && cardEl) { cardEl.classList.remove("mini-mode"); miniBtn.onclick = () => cardEl.classList.toggle("mini-mode"); } const resBox = document.getElementById("cinema-resume"); const resTxt = document.getElementById("c-resume-text"); const resBtn = document.getElementById("c-resume-btn"); const posKey = "airshare_pos_" + title; if (resBox) resBox.style.display = "none"; let savedPos = 0; try { savedPos = parseFloat(localStorage.getItem(posKey) || "0"); } catch (_) {} if (savedPos > 5 && resBox && resTxt && resBtn) { const mm = Math.floor(savedPos / 60), ss = String(Math.floor(savedPos % 60)).padStart(2, "0"); resTxt.textContent = mm + ":" + ss; resBox.style.display = "flex"; resBtn.onclick = () => { m.currentTime = savedPos; resBox.style.display = "none"; }; } m.addEventListener("timeupdate", () => { if (m.currentTime > 5) try { localStorage.setItem(posKey, String(Math.floor(m.currentTime))); } catch (_) {} }); }

    if (controls) {
      controls.style.display = "flex";
      const speeds = [1, 1.25, 1.5, 2, 0.5];
      let sIdx = 0;
      if (speedBtn) {
        speedBtn.textContent = "1x";
        speedBtn.onclick = () => {
          sIdx = (sIdx + 1) % speeds.length;
          m.playbackRate = speeds[sIdx];
          speedBtn.textContent = speeds[sIdx] + "x";
        };
      }
      if (playBtn) {
        playBtn.textContent = "⏸";
        playBtn.onclick = () => { if (m.paused) m.play(); else m.pause(); };
      }
      if (seekEl) {
        seekEl.value = 0;
        seekEl.oninput = () => {
          if (m.duration) m.currentTime = (Number(seekEl.value) / 100) * m.duration;
        };
      }
      if (timeEl) timeEl.textContent = "0:00 / 0:00";
      if (fsBtn) {
        fsBtn.onclick = () => {
          if (document.fullscreenElement) document.exitFullscreen();
          else (modal.querySelector(".cinema-stage") || modal).requestFullscreen().catch(() => {});
        };
      }
      m.addEventListener("timeupdate", () => {
        if (seekEl && m.duration) seekEl.value = String((m.currentTime / m.duration) * 100);
        if (timeEl) timeEl.textContent = formatCinemaTime(m.currentTime) + " / " + formatCinemaTime(m.duration);
      });
      m.addEventListener("pause", () => { if (playBtn) playBtn.textContent = "▶"; });
    }
    let lastDraw = 0;
    const drawAmb = (now) => {
      if (_cinemaMediaEl !== m) return;
      if (!m.paused && !m.ended) {
        if (isVid && _ambilightEnabled && ambCanvas && now - lastDraw >= 180) {
          lastDraw = now;
          try { ambCanvas.getContext("2d").drawImage(m, 0, 0, 64, 36); } catch (_) {}
        }
        _ambilightRaf = requestAnimationFrame(drawAmb);
      }
    };
    m.addEventListener("play", () => {
      if (playBtn) playBtn.textContent = "⏸";
      if (isVid) _ambilightRaf = requestAnimationFrame(drawAmb);
    });
  }
  if (modal) modal.classList.add("open");
}

function hideCtxMenu() {
  const m = document.getElementById("ctxMenu");
  if (m) m.style.display = "none";
}

function openCtxMenu(ev, item) {
  const m = document.getElementById("ctxMenu");
  if (!m) return;
  const isDir = item.kind === "dir" || item.is_dir;
  const canEdit = !!(state.trusted && state.tab !== "trash");
  const canFav = !!(state.trusted && isDir);
  m.innerHTML = "";
  const addItem = (label, fn, danger = false) => {
    const btn = document.createElement("button");
    btn.className = "ctx-item" + (danger ? " danger" : "");
    btn.textContent = label;
    btn.onclick = (e) => { e.stopPropagation(); hideCtxMenu(); fn(); };
    m.appendChild(btn);
  };
  const addSep = () => { const d = document.createElement("div"); d.className = "ctx-sep"; m.appendChild(d); };

  if (isDir) {
    addItem("📂 " + (t("web_ctx_open") || "Open"), () => { state.curDir = item.rel_path; loadFiles(); });
    addItem("⬇ ZIP", () => { window.location.href = "/zip?dir=" + encodeURIComponent(item.rel_path); });
  } else {
    addItem("👁 " + (t("web_ctx_open") || "Open"), () => {
      const k = item.kind || "other";
      if (k === "img" || k === "image" || k === "vid" || k === "video" || k === "aud" || k === "audio") openCinema(item);
      else window.open("/file/" + encPath(item.rel_path), "_blank");
    });
    addItem("⬇ " + (t("web_ctx_download") || "Download"), () => {
      const a = document.createElement("a");
      a.href = "/file/" + encPath(item.rel_path) + "?download=1";
      a.setAttribute("download", item.name);
      document.body.appendChild(a); a.click(); a.remove();
    });
    addItem("🔐 SHA-256", () => showSha(item.rel_path));
  }
  if (canFav) {
    addItem((item.is_fav ? "★ " : "☆ ") + (t("web_ctx_fav") || "Favorite"), async () => {
      await apiOp("fav", { rel_path: item.rel_path });
      reloadCurrentTab();
    });
  }
  if (canEdit) {
    addSep();
    addItem("✏ " + (t("web_ctx_rename") || "Rename"), async () => {
      const nw = prompt(t("web_rename_prompt") || "New name:", item.name);
      if (!nw || nw === item.name) return;
      const res = await apiOp("rename", { path: item.rel_path, new_name: nw });
      if (res && res.ok) reloadCurrentTab();
      else toast((res && res.msg) || "Error");
    });
    addItem("📁 " + (t("web_ctx_move") || "Move"), () => openFolderPicker("move", [item.rel_path]));
    addItem("📋 " + (t("web_ctx_copy") || "Copy"), () => openFolderPicker("copy", [item.rel_path]));
    addItem("👁 " + (t("web_ctx_hide") || "Hide"), async () => {
      await apiOp("hide", { rel_path: item.rel_path });
      reloadCurrentTab();
    });
    addSep();
    addItem("🗑 " + (t("web_ctx_trash") || "Delete"), () => openDeleteModal([item.rel_path]), true);
  }
  m.style.display = "block";
  const mw = m.offsetWidth || 190, mh = m.offsetHeight || 220;
  const x = Math.min(ev.clientX, window.innerWidth - mw - 8);
  const y = Math.min(ev.clientY, window.innerHeight - mh - 8);
  m.style.left = Math.max(8, x) + "px";
  m.style.top = Math.max(8, y) + "px";
}
document.addEventListener("click", hideCtxMenu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideCtxMenu(); });

function initSkyCanvas() { const c = document.getElementById("sky-canvas"); if (!c) return; const ctx = c.getContext("2d"); let w = 0, h = 0, mx = 0, my = 0; const resize = () => { w = c.width = window.innerWidth; h = c.height = window.innerHeight; }; resize(); window.addEventListener("resize", resize); window.addEventListener("mousemove", e => { if (!state.parallaxEnabled) return; mx = (e.clientX / Math.max(1, w) - 0.5) * 40; my = (e.clientY / Math.max(1, h) - 0.5) * 40; }); window.addEventListener("deviceorientation", e => { if (!state.parallaxEnabled || e.gamma == null || e.beta == null) return; mx = Math.max(-30, Math.min(30, e.gamma)) * 1.2; my = Math.max(-30, Math.min(30, e.beta - 45)) * 1.2; }); const starColors = ["255,255,255", "200,225,255", "255,235,205", "180,210,255", "255,215,240"]; const stars = Array.from({ length: 260 }, () => ({ x: Math.random(), y: Math.random(), r: Math.random() * 1.7 + 0.4, a: Math.random() * Math.PI * 2, s: Math.random() * 0.025 + 0.008, d: Math.random() * 0.8 + 0.2, col: starColors[Math.floor(Math.random() * starColors.length)] })); const meteors = []; const spawnMeteor = () => { meteors.push({ x: Math.random() * w * 0.8 + w * 0.1, y: Math.random() * h * 0.35, vx: -(Math.random() * 6 + 7), vy: Math.random() * 3 + 3, len: Math.random() * 70 + 60, alpha: 1 }); }; const clouds = Array.from({ length: 11 }, () => ({ x: Math.random(), y: Math.random() * 0.55 + 0.05, sc: Math.random() * 0.7 + 0.6, sp: Math.random() * 0.00018 + 0.00008, d: Math.random() * 0.5 + 0.25 })); const drawCloud = (cx, cy, sc) => { ctx.save(); ctx.translate(cx, cy); ctx.scale(sc, sc); ctx.fillStyle = "rgba(255, 255, 255, 0.72)"; ctx.beginPath(); ctx.arc(0, 0, 28, 0, Math.PI * 2); ctx.arc(26, -8, 22, 0, Math.PI * 2); ctx.arc(-26, -4, 20, 0, Math.PI * 2); ctx.arc(46, 4, 16, 0, Math.PI * 2); ctx.arc(-44, 6, 15, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }; const frame = () => { ctx.clearRect(0, 0, w, h); const isLight = document.documentElement.getAttribute("data-theme") === "light"; if (isLight) { const g = ctx.createLinearGradient(0, 0, 0, h); g.addColorStop(0, "#cfe4ff"); g.addColorStop(1, "#f2f7ff"); ctx.fillStyle = g; ctx.fillRect(0, 0, w, h); for (const cl of clouds) { cl.x = (cl.x + cl.sp) % 1.25; const cx = (cl.x - 0.12) * w - mx * cl.d; const cy = cl.y * h - my * cl.d; drawCloud(cx, cy, cl.sc); } } else { for (const st of stars) { st.a += st.s; const alpha = 0.25 + 0.75 * (0.5 + 0.5 * Math.sin(st.a)); const px = ((st.x * w - mx * st.d) % w + w) % w; const py = ((st.y * h - my * st.d) % h + h) % h; ctx.fillStyle = `rgba(${st.col}, ${alpha.toFixed(3)})`; ctx.beginPath(); ctx.arc(px, py, st.r, 0, Math.PI * 2); ctx.fill(); } if (Math.random() < 0.008 && meteors.length < 3) spawnMeteor(); for (let i = meteors.length - 1; i >= 0; i--) { const mt = meteors[i]; const tx = mt.x - mt.vx * (mt.len / 10); const ty = mt.y - mt.vy * (mt.len / 10); const grad = ctx.createLinearGradient(mt.x, mt.y, tx, ty); grad.addColorStop(0, `rgba(255,255,255,${mt.alpha.toFixed(3)})`); grad.addColorStop(1, "rgba(180,220,255,0)"); ctx.strokeStyle = grad; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(mt.x, mt.y); ctx.lineTo(tx, ty); ctx.stroke(); mt.x += mt.vx; mt.y += mt.vy; mt.alpha -= 0.015; if (mt.alpha <= 0) meteors.splice(i, 1); } } requestAnimationFrame(frame); }; requestAnimationFrame(frame); }

  async function showSha(relPath) {
    document.getElementById("sha-title").textContent = t("web_sha_title");
    document.getElementById("sha-file").textContent = relPath;
    document.getElementById("sha-value").textContent = "...";
    document.getElementById("sha-close").textContent = t("close");
    document.getElementById("modal-sha").classList.add("open");
    const r = await fetch("/api/hash?path=" + encodeURIComponent(relPath));
    const d = await r.json();
    document.getElementById("sha-value").textContent = d.sha256 || d.error || "Error";
  }

  function syncTabButtons() {
    document.querySelectorAll(".tab-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.tab === state.tab);
    });
  }

  function reloadCurrentTab() {
    if (state.tab === "files") loadFiles();
    else if (state.tab === "gallery") loadGallery(true);
    else if (state.tab === "recent") loadRecent();
    else if (state.tab === "trash") loadTrash();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("airshare_theme") || window.__INIT_THEME__ || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);
  document.body.classList.remove("dark", "light"); document.body.classList.add(savedTheme);
    document.body.classList.toggle("wide-view", state.wideView);

 const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt("btn-access", "🔐 " + t("web_access_btn"));
setTxt("btn-wide", "▫ " + t("web_wide_view"));
document.getElementById("btn-wide")?.classList.toggle("active", state.wideView);
setTxt("lbl-parallax", "✨ " + t("web_parallax"));
setTxt("tab-files", "📁 " + t("web_tab_files"));
setTxt("tab-gallery", "🖼 " + t("web_tab_gallery"));
setTxt("tab-recent", "🕒 " + t("web_tab_recent"));
setTxt("tab-trash", "🗑 " + t("web_tab_trash"));
const searchEl = document.getElementById("search-input");
if (searchEl) searchEl.placeholder = t("web_search_placeholder");
setTxt("lbl-select-all", t("web_select_all"));
setTxt("btn-upload", "⬆ " + t("web_upload_btn"));
setTxt("btn-mkdir", "+ " + t("web_new_folder"));
setTxt("btn-hidden", "👁 " + t("web_hidden_btn"));
setTxt("btn-empty-trash", "🧹 " + t("web_empty_trash"));
setTxt("dropzone", "⬆ " + t("web_drop_hint"));
setTxt("cinema-ambient-btn", t("web_ambilight"));
setTxt("c-pip", t("web_pip"));
setTxt("c-mini", t("web_mini"));

    const langFlags = {
    en: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="16" fill="#012169"/><path d="M0,0 L24,16 M24,0 L0,16" stroke="#fff" stroke-width="3"/><path d="M0,0 L24,16 M24,0 L0,16" stroke="#C8102E" stroke-width="1.5"/><path d="M12,0 V16 M0,8 H24" stroke="#fff" stroke-width="5"/><path d="M12,0 V16 M0,8 H24" stroke="#C8102E" stroke-width="3"/></svg>`,
    ru: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="5.33" fill="#fff"/><rect y="5.33" width="24" height="5.33" fill="#0039A6"/><rect y="10.67" width="24" height="5.33" fill="#D52B1E"/></svg>`,
    uk: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="8" fill="#005BBB"/><rect y="8" width="24" height="8" fill="#FFD500"/></svg>`,
    es: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="4" fill="#AA151B"/><rect y="4" width="24" height="8" fill="#F1BF00"/><rect y="12" width="24" height="4" fill="#AA151B"/></svg>`,
    de: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="5.33" fill="#000"/><rect y="5.33" width="24" height="5.33" fill="#DD0000"/><rect y="10.67" width="24" height="5.33" fill="#FFCE00"/></svg>`,
    lt: `<svg viewBox="0 0 24 16" width="20" height="14"><rect width="24" height="5.33" fill="#FDB913"/><rect y="5.33" width="24" height="5.33" fill="#006A44"/><rect y="10.67" width="24" height="5.33" fill="#C1272D"/></svg>`
  };
 const cookieLang = (document.cookie.match(/(?:^|;\s*)airshare_lang=([^;]+)/) || [])[1];
const curLang = window.__INIT_LANG__ || cookieLang || "en";
  const langBtn = document.getElementById("lang-btn");
  const langDrop = document.getElementById("lang-dropdown");
  if (langBtn && langDrop) {
     langBtn.innerHTML = (langFlags[curLang] || langFlags.en) + " " + curLang.toUpperCase() + " ▾";
    langDrop.innerHTML = "";
    for (const [code, svg] of Object.entries(langFlags)) {
      const opt = document.createElement("button");
      opt.type = "button";
      opt.className = "lang-opt" + (code === curLang ? " active" : "");
      opt.innerHTML = svg + ` <span>${code.toUpperCase()}</span>`;
      opt.onclick = (e) => {
        e.stopPropagation();
        document.cookie = "airshare_lang=" + code + "; path=/; max-age=31536000";
        window.location.href = "/?lang=" + encodeURIComponent(code);
      };
      langDrop.appendChild(opt);
    }
     langBtn.addEventListener("click", (ev) => {
  ev.stopPropagation();
  langDrop.style.display = langDrop.style.display === "flex" ? "none" : "flex";
});
document.addEventListener("click", () => { langDrop.style.display = "none"; });
  }

 const tToggle = document.getElementById("themeToggle");
if (tToggle) {
  tToggle.checked = document.documentElement.getAttribute("data-theme") !== "light";
  tToggle.addEventListener("change", () => {
    const cur = tToggle.checked ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", cur);
    document.body.classList.remove("dark", "light");
    document.body.classList.add(cur);
    localStorage.setItem("airshare_theme", cur);
  });
}

    document.getElementById("btn-wide").addEventListener("click", () => {
      state.wideView = !state.wideView;
      document.body.classList.toggle("wide-view", state.wideView);
      document.getElementById("btn-wide").classList.toggle("active", state.wideView);
      localStorage.setItem("airshare_wide", state.wideView ? "1" : "0");
    });

 const pToggle = document.getElementById("parallaxToggle");
if (pToggle) {
  pToggle.checked = !!state.parallaxEnabled;
  pToggle.addEventListener("change", () => {
    state.parallaxEnabled = !!pToggle.checked;
    localStorage.setItem("airshare_parallax", state.parallaxEnabled ? "1" : "0");
  });
}

    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        state.tab = btn.dataset.tab;
        document.getElementById("search-input").value = "";
        syncTabButtons();
        reloadCurrentTab();
      });
    });

    document.getElementById("search-input").addEventListener("input", (e) => {
      clearTimeout(searchDebounce);
      const q = e.target.value.trim();
      searchDebounce = setTimeout(() => runSearch(q), 260);
    });

    document.getElementById("cb-select-all").addEventListener("change", (e) => {
      const checked = e.target.checked;
      document.querySelectorAll("#content-area .file-cb").forEach((cb) => {
        if (cb.checked !== checked) {
          cb.checked = checked;
          cb.dispatchEvent(new Event("change"));
        }
      });
    });

    document.getElementById("btn-hidden").addEventListener("click", async () => {
      const res = await apiOp("toggle_hidden", {});
      if (res && res.ok) {
        state.showHidden = !!res.show_hidden;
        reloadCurrentTab();
      }
    });

    document.getElementById("btn-mkdir").addEventListener("click", async () => {
      const name = prompt(t("web_mkdir_prompt"));
      if (!name) return;
      const res = await apiOp("mkdir", { dir: state.relDir, name });
      if (res && res.ok) loadFiles();
      else toast((res && res.msg) || "Error");
    });

    document.getElementById("btn-upload").addEventListener("click", () => document.getElementById("file-input").click());
    document.getElementById("file-input").addEventListener("change", (e) => {
      uploadFiles(e.target.files);
      e.target.value = "";
    });

    const dz = document.getElementById("dropzone");
    dz.addEventListener("click", () => document.getElementById("file-input").click());
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
      uploadFiles(e.dataTransfer.files);
    });
  const hdz = document.getElementById("header-dropzone");
if (hdz) {
  ["dragenter", "dragover"].forEach(ev => hdz.addEventListener(ev, (e) => { e.preventDefault(); hdz.classList.add("drag-over"); }));
  ["dragleave", "drop"].forEach(ev => hdz.addEventListener(ev, (e) => { e.preventDefault(); hdz.classList.remove("drag-over"); }));
  hdz.addEventListener("drop", (e) => { if (state.trusted && e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files); });
}
    
    document.getElementById("btn-download-zip").addEventListener("click", () => {
      const qs = Array.from(state.selected).map(p => "p=" + encodeURIComponent(p)).join("&");
      if (qs) window.location.href = "/download_selected?" + qs;
    });

    document.getElementById("btn-bulk-move").addEventListener("click", () => openFolderPicker("move", Array.from(state.selected)));
    document.getElementById("btn-bulk-copy").addEventListener("click", () => openFolderPicker("copy", Array.from(state.selected)));
    document.getElementById("btn-bulk-delete").addEventListener("click", () => openDeleteModal(Array.from(state.selected)));

    document.getElementById("btn-empty-trash").addEventListener("click", async () => {
      if (!confirm(t("web_empty_trash_confirm"))) return;
      await apiOp("empty_trash", {});
      toast(t("web_purged"));
      loadTrash();
    });

    document.getElementById("del-cancel").addEventListener("click", () => document.getElementById("modal-delete").classList.remove("open"));
    document.getElementById("del-confirm").addEventListener("click", async () => {
      document.getElementById("modal-delete").classList.remove("open");
      const res = await apiOp("delete", { paths: state.pendingDeletePaths });
      if (res && res.ok) {
        toast(t("web_deleted"));
        reloadCurrentTab();
      }
    });

    document.getElementById("picker-cancel").addEventListener("click", () => document.getElementById("modal-folder-picker").classList.remove("open"));
    document.getElementById("picker-confirm").addEventListener("click", async () => {
      document.getElementById("modal-folder-picker").classList.remove("open");
      const res = await apiOp(state.pickerMode, { paths: state.pickerPaths, dest_dir: state.pickerDest });
      if (res && res.ok) {
        toast(state.pickerMode === "copy" ? t("web_copied") : t("web_moved"));
        reloadCurrentTab();
      }
    });

    document.getElementById("btn-access").addEventListener("click", openAccessModal);
    document.getElementById("access-close").addEventListener("click", () => {
      stopAccessPoll();
      document.getElementById("modal-access").classList.remove("open");
    });
    document.getElementById("access-btn-bio").addEventListener("click", () => startAccessAuth("biometric"));
    document.getElementById("access-btn-pairs").addEventListener("click", () => startAccessAuth("pairs"));
    document.getElementById("access-pin-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!state.accessTargetKey) return;
      const pin = document.getElementById("access-pin-input").value.trim();
      const r = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin, action: "access_change", folder_key: state.accessTargetKey })
      });
      const d = await r.json();
      if (r.ok && d.ok) window.location.href = "/";
      else {
        const stEl = document.getElementById("access-status");
        stEl.className = "status-box error";
        stEl.textContent = d.error || t("pin_hint");
      }
    });

    document.getElementById("cinema-close").addEventListener("click", () => {
      document.getElementById("cinema-body").innerHTML = "";
      document.getElementById("modal-cinema").classList.remove("open");
    });
    document.getElementById("sha-close").addEventListener("click", () => {
      document.getElementById("modal-sha").classList.remove("open");
    });
  const btnBulkHide = document.getElementById("btn-bulk-hide");
  if (btnBulkHide) {
    btnBulkHide.addEventListener("click", async () => {
      const items = Array.from(state.selected);
      if (!items.length) return;
      for (const p of items) await apiOp("hide", { rel_path: p });
      state.selected.clear();
      reloadCurrentTab();
    });
  }

  const roleBadge = document.getElementById("role-badge");
  if (roleBadge) {
    roleBadge.style.cursor = "pointer";
    roleBadge.addEventListener("click", async () => {
      if (state.trusted) {
        const r = await fetch("/api/role", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trusted: false })
        });
        if (r.ok) {
          state.trusted = false;
          if (typeof applyRoleUi === "function") applyRoleUi();
          reloadCurrentTab();
        }
      } else {
        const r = await fetch("/auth/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "biometric", action: "upgrade_trusted", folder_key: state.activeFolder || "" })
        });
        if (!r.ok) return;
        const d = await r.json();
        const reqId = d.request_id || d.id;
        if (!reqId) return;
        toast(t("web_auth_waiting") || "Waiting for host approval...");
        const poll = setInterval(async () => {
          try {
            const sr = await fetch("/auth/status?cid=" + encodeURIComponent(reqId));
            if (!sr.ok) { clearInterval(poll); return; }
            const sd = await sr.json();
            if (sd.status === "approved") {
              clearInterval(poll);
              window.location.href = "/auth/claim?id=" + encodeURIComponent(reqId);
            } else if (sd.status === "denied" || sd.status === "expired") {
              clearInterval(poll);
              toast(sd.status);
            }
          } catch (_) { clearInterval(poll); }
        }, 1200);
      }
    });
  }

  setInterval(async () => {
    try {
      const r = await fetch("/api/status");
      if (r.status === 401 || r.status === 403) {
        window.location.href = "/";
        return;
      }
      if (!r.ok) return;
      const d = await r.json();
      let changed = false;
      if (typeof d.trusted === "boolean" && d.trusted !== state.trusted) {
        state.trusted = d.trusted;
        changed = true;
      }
      if (d.active_folder !== undefined && d.active_folder !== state.activeFolder) {
        state.activeFolder = d.active_folder;
        changed = true;
      }
      if (changed) {
        if (typeof applyRoleUi === "function") applyRoleUi();
        reloadCurrentTab();
      }
    } catch (_) {}
  }, 2500);

  initSkyCanvas();
    initSky();
    loadFiles();
  });
})();

(() => {
  const shell = document.querySelector(".control-shell");
  const content = document.getElementById("dashboard-content");
  const alertBox = document.getElementById("dashboard-alert");
  const refreshButton = document.getElementById("manual-refresh");
  const clock = document.getElementById("dashboard-clock");
  let section = "overview";
  let timer = null;

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const status = (value) => `<span class="status ${esc(value)}">${esc(value || "unknown")}</span>`;
  const progress = (value) => `<div class="progress"><span style="width:${Math.max(0, Math.min(100, Number(value || 0)))}%"></span></div>`;
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";
  const sectionUrl = (name) => shell.dataset.sectionUrlTemplate.replace(/overview\/?$/, `${name}/`);

  function showAlert(message, isError = false) {
    alertBox.hidden = false;
    alertBox.textContent = message;
    alertBox.style.borderColor = isError ? "rgba(255,90,96,.5)" : "rgba(255,204,77,.35)";
    clearTimeout(showAlert._timer);
    showAlert._timer = setTimeout(() => (alertBox.hidden = true), 4200);
  }

  function kpi(label, value, sub = "") {
    return `<div class="card"><span class="kpi-label">${esc(label)}</span><strong class="kpi-value">${esc(value)}</strong><div class="kpi-sub">${esc(sub)}</div></div>`;
  }

  function renderLive(live) {
    const current = live.current || {};
    const setting = live.settings || {};
    const poster = current.poster_url ? `background-image:url('${esc(current.poster_url)}')` : "";
    const tickerText = setting.default_ticker_text || current.ticker_text || "Live updates";
    const tickerLabel = setting.default_ticker_label || "ताजा खबर";
    return `<div class="card">
      <h2>Live Now</h2>
      <div class="live-preview">
        <div class="poster" style="${poster}"></div>
        ${setting.show_live_badge ? `<div class="live-badge">● ${esc(setting.live_label || "LIVE")}</div>` : ""}
        <div class="live-meta"><h2>${esc(current.title || "Live is going soon")}</h2><p>${esc(current.seek_display || "00:00")} / ${esc(current.duration_display || "00:00")}</p></div>
        ${setting.show_ticker ? `<div class="ticker-sim"><div class="ticker-label">${esc(tickerLabel)}</div><div class="ticker-cut"></div><div class="ticker-text">${esc(tickerText)}</div></div>` : ""}
      </div>
      <div class="pill-row" style="margin-top:14px">
        <span class="pill">Current: ${esc(current.title || "-")}</span>
        <span class="pill">Next: ${esc((live.next || {}).title || "-")}</span>
        <span class="pill">Remaining: ${esc(current.remaining_display || "00:00")}</span>
      </div>
    </div>`;
  }

  function renderSchedule(rows = []) {
    return `<div class="card"><h2>Upcoming Schedule</h2><table class="table"><thead><tr><th>Slot</th><th>Video</th><th>Time</th><th>Duration</th><th>Status</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${esc(row.position)}</td><td>${esc(row.title)}</td><td>${esc(row.time)}</td><td>${esc(row.duration)}</td><td>${status(row.status)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">Playlist empty</td></tr>`}</tbody></table></div>`;
  }

  function renderProcessing(processing) {
    const renderJobs = processing.render_jobs || [];
    const liveProcessing = processing.live_processing || [];
    const shortProcessing = processing.short_processing || [];
    return `<div class="grid two-col">
      <div class="card"><h2>Render Queue</h2><table class="table"><thead><tr><th>Title</th><th>Status</th><th>Progress</th><th>Updated</th></tr></thead><tbody>${renderJobs.map((job) => `<tr><td>${esc(job.title)}</td><td>${status(job.status)}</td><td>${progress(job.progress_percent)}</td><td>${esc(job.updated_at)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No render jobs</td></tr>`}</tbody></table></div>
      <div class="card"><h2>HLS Processing</h2><div class="mini-list">${[...liveProcessing, ...shortProcessing].map((item) => `<div class="mini-item"><span>${esc(item.title)}</span><span>${progress(item.hls_progress_percent || item.progress_percent)}</span></div>`).join("") || `<div class="muted">No active processing</div>`}</div></div>
    </div>`;
  }

  function renderServer(payload) {
    const server = payload.server || {};
    const bandwidth = (payload.bandwidth || {}).periods || {};
    const storage = payload.storage || [];
    return `<div class="grid two-col">
      <div class="card"><h2>Server Health</h2><div class="grid three-col">
        <div><div class="server-ring" style="--p:${Number(server.cpu_percent || 0)}">${esc(server.cpu_percent ?? "-")}%</div><p class="muted">CPU</p></div>
        <div><div class="server-ring" style="--p:${Number(server.ram_percent || 0)}">${esc(server.ram_percent ?? "-")}%</div><p class="muted">RAM ${esc(server.ram_used_display)} / ${esc(server.ram_total_display)}</p></div>
        <div><div class="server-ring" style="--p:${Number(server.disk_percent || 0)}">${esc(server.disk_percent ?? "-")}%</div><p class="muted">SSD ${esc(server.disk_used_display)} / ${esc(server.disk_total_display)}</p></div>
      </div><p class="muted">Host: ${esc(server.hostname)} | Load: ${esc(server.load_average || "-")}</p></div>
      <div class="card"><h2>Bandwidth</h2><table class="table"><thead><tr><th>Period</th><th>Total</th><th>Mobile</th><th>Web</th></tr></thead><tbody>${Object.entries(bandwidth).map(([key,row]) => `<tr><td>${esc(key)}</td><td>${esc(row.display)}</td><td>${esc(row.mobile_display)}</td><td>${esc(row.web_display)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Apache logs not found on local system</td></tr>`}</tbody></table></div>
      <div class="card" style="grid-column:1/-1"><h2>Storage Map</h2><table class="table"><thead><tr><th>Section</th><th>Used</th><th>Path</th></tr></thead><tbody>${storage.map((row) => `<tr><td>${esc(row.label)}</td><td>${esc(row.display)}</td><td class="muted">${esc(row.path)}</td></tr>`).join("")}</tbody></table></div>
    </div>`;
  }

  function renderUploads(uploads) {
    const videos = uploads.videos || [];
    const shorts = uploads.shorts || [];
    return `<div class="grid two-col"><div class="card"><h2>Live Uploads</h2><table class="table"><thead><tr><th>Video</th><th>HLS</th><th>Size</th><th>Updated</th></tr></thead><tbody>${videos.map((v) => `<tr><td>${esc(v.title)}</td><td>${status(v.hls_status)} ${progress(v.hls_progress_percent)}</td><td>${esc(v.file_size_display)}</td><td>${esc(v.updated_at)}</td></tr>`).join("")}</tbody></table></div><div class="card"><h2>Shorts Uploads</h2><table class="table"><thead><tr><th>Short</th><th>HLS</th><th>Duration</th></tr></thead><tbody>${shorts.map((v) => `<tr><td>${esc(v.title)}</td><td>${status(v.status)} ${progress(v.progress_percent)}</td><td>${esc(v.duration_display)}</td></tr>`).join("")}</tbody></table></div></div>`;
  }

  function renderRenders(renders) {
    const rows = renders.items || [];
    return `<div class="card"><h2>Rendered Videos</h2><table class="table"><thead><tr><th>Title</th><th>Source</th><th>Status</th><th>Progress</th><th>Size</th><th>Completed</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${esc(row.title)}</td><td>${esc(row.source_video)}</td><td>${status(row.status)}</td><td>${progress(row.progress_percent)}</td><td>${esc(row.file_size_display)}</td><td>${esc(row.completed_at || row.created_at)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function renderControls(payload) {
    const setting = payload.settings || {};
    return `<div class="card"><h2>Controls</h2><div class="actions">
      <button class="action-btn" data-action="rebuild_playlist">Rebuild Playlist</button>
      <button class="action-btn" data-action="retry_failed_hls">Retry Failed HLS</button>
      <button class="action-btn" data-action="retry_failed_renders">Retry Failed Renders</button>
      <button class="action-btn" data-action="toggle_ticker">Ticker: ${setting.show_ticker ? "ON" : "OFF"}</button>
      <button class="action-btn" data-action="toggle_live_badge">Live Badge: ${setting.show_live_badge ? "ON" : "OFF"}</button>
      <button class="action-btn" data-action="toggle_channel_logo">Logo: ${setting.show_channel_logo ? "ON" : "OFF"}</button>
      <button class="action-btn" data-action="toggle_lower_third">Lower Third: ${setting.show_lower_third ? "ON" : "OFF"}</button>
    </div><p class="muted">Settings save karne ke liye detailed Django Admin me Live TV Settings open karein.</p></div>`;
  }

  function render(payload) {
    const live = payload.live || {};
    clock.textContent = live.server_time || new Date().toLocaleTimeString();
    if (payload.section === "live") content.innerHTML = `<div class="grid two-col">${renderLive(live)}${renderSchedule(live.schedule)}</div>`;
    else if (payload.section === "playlist") content.innerHTML = `${renderLive(live)}<div style="height:16px"></div>${renderSchedule(live.schedule)}<div style="height:16px"></div>${renderUploads({ videos: payload.items || [], shorts: [] })}`;
    else if (payload.section === "processing") content.innerHTML = renderProcessing(payload.processing || {});
    else if (payload.section === "uploads") content.innerHTML = renderUploads(payload.uploads || {});
    else if (payload.section === "renders") content.innerHTML = renderRenders(payload.renders || {});
    else if (payload.section === "server") content.innerHTML = renderServer(payload);
    else if (payload.section === "controls") content.innerHTML = renderControls(payload);
    else {
      const p = payload.processing || {};
      const uploads = payload.uploads || {};
      content.innerHTML = `<div class="grid kpis">${kpi("Playlist Videos", (live.playlist || {}).count || 0, (live.playlist || {}).duration_display || "")}${kpi("Rendered Processing", (p.renders || {}).processing || 0, `${(p.renders || {}).pending || 0} pending`)}${kpi("Live HLS Processing", (p.live_hls || {}).processing || 0, `${(p.live_hls || {}).failed || 0} failed`)}${kpi("Total Uploads", (uploads.videos_total || 0) + (uploads.shorts_total || 0), `${uploads.shorts_total || 0} shorts`)}</div><div class="grid two-col">${renderLive(live)}${renderSchedule(live.schedule)}</div>`;
    }
  }

  async function load(nextSection = section) {
    section = nextSection;
    try {
      const res = await fetch(sectionUrl(section), { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await res.json();
      if (!data.ok) throw new Error(data.message || "Dashboard failed");
      render(data.payload);
    } catch (error) {
      showAlert(error.message || "Dashboard data load failed", true);
    }
  }

  async function runAction(action) {
    const form = new FormData();
    form.append("action", action);
    const res = await fetch(shell.dataset.actionUrl, { method: "POST", body: form, headers: { "X-CSRFToken": csrf() } });
    const data = await res.json();
    showAlert(data.message || (data.ok ? "Done" : "Action failed"), !data.ok);
    await load(section);
  }

  document.querySelectorAll(".side-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".side-item").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      load(button.dataset.section);
    });
  });
  refreshButton.addEventListener("click", () => load(section));
  content.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (button) runAction(button.dataset.action);
  });
  load("overview");
  timer = setInterval(() => load(section), 5000);
  window.addEventListener("beforeunload", () => clearInterval(timer));
})();

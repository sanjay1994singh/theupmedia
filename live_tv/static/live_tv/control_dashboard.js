(() => {
  const shell = document.querySelector(".control-shell");
  const content = document.getElementById("dashboard-content");
  const alertBox = document.getElementById("dashboard-alert");
  const refreshButton = document.getElementById("manual-refresh");
  const sideServerTime = document.getElementById("side-server-time");
  const searchInput = document.querySelector(".search-box input");
  let section = "overview";
  let timer = null;
  let requestId = 0;

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const norm = (value) => String(value || "unknown").toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
  const status = (value) => `<span class="status ${norm(value)}">${esc(value || "unknown")}</span>`;
  const pct = (value, state = "") => {
    const normalized = String(state || "").toLowerCase();
    if (["completed", "done"].includes(normalized)) return 100;
    const number = Number(value || 0);
    return Math.max(0, Math.min(100, Math.round(number)));
  };
  const progress = (value, state = "") => {
    const valuePct = pct(value, state);
    return `<div class="progress-wrap"><div class="progress"><span style="width:${valuePct}%"></span></div><strong>${valuePct}%</strong></div>`;
  };
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";
  const sectionUrl = (name) => shell.dataset.sectionUrlTemplate.replace(/overview\/?$/, `${name}/`);
  const count = (obj, key) => Number((obj || {})[key] || 0);
  const isActiveState = (value) => ["pending", "processing", "queued", "started"].includes(String(value || "").toLowerCase());
  const jobProgress = (job) => pct(job?.progress_percent ?? job?.hls_progress_percent, job?.status || job?.hls_status);
  const averageProgress = (jobs) => {
    const list = (jobs || []).filter(Boolean);
    if (!list.length) return 0;
    return Math.round(list.reduce((total, job) => total + jobProgress(job), 0) / list.length);
  };

  function showAlert(message, isError = false) {
    alertBox.hidden = false;
    alertBox.textContent = message;
    alertBox.style.borderColor = isError ? "rgba(255,90,96,.5)" : "rgba(255,204,77,.35)";
    clearTimeout(showAlert._timer);
    showAlert._timer = setTimeout(() => (alertBox.hidden = true), 4200);
  }

  function setLoading(active, message = "Loading live dashboard...") {
    content.classList.toggle("is-loading", active);
    content.dataset.loadingText = message;
    refreshButton.disabled = active;
    if (active && !content.innerHTML.trim()) {
      content.innerHTML = `<div class="dashboard-loader"><span></span><strong>${esc(message)}</strong><p>Fetching live reports and processing data</p></div>`;
    }
  }

  async function readJsonResponse(response, fallbackMessage) {
    const body = await response.text();
    if (!body.trim()) {
      throw new Error(`${fallbackMessage} (HTTP ${response.status}: empty response)`);
    }

    let data;
    try {
      data = JSON.parse(body);
    } catch (_) {
      throw new Error(`${fallbackMessage} (HTTP ${response.status}: server returned non-JSON data)`);
    }

    if (!response.ok) {
      throw new Error(data.message || data.detail || `${fallbackMessage} (HTTP ${response.status})`);
    }
    return data;
  }

  function pageTitle(title, subtitle, live) {
    if (sideServerTime && live?.server_time) sideServerTime.textContent = `Server Time: ${live.server_time}`;
    return `<div class="page-title"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="dashboard-clock">${esc(live?.server_time || "--")}</div></div>`;
  }

  function kpi(label, value, sub = "", tone = "") {
    return `<div class="kpi-card ${tone}"><span class="kpi-label">${esc(label)}</span><strong class="kpi-value">${esc(value)}</strong><div class="kpi-sub">${esc(sub)}</div></div>`;
  }

  function renderLive(live) {
    const current = live.current || {};
    const setting = live.settings || {};
    const poster = current.poster_url ? `background-image:url('${esc(current.poster_url)}')` : "";
    const tickerText = setting.default_ticker_text || current.ticker_text || "Live updates";
    const tickerLabel = setting.default_ticker_label || "TODAY'S";
    return `<section class="dashboard-card">
      <div class="card-head"><h2>Live TV Preview</h2><button class="ghost-btn" data-section-jump="live">View</button></div>
      <div class="live-preview">
        <div class="poster" style="${poster}"></div>
        ${setting.show_live_badge ? `<div class="live-badge">LIVE</div>` : ""}
        <div class="live-meta"><h2>${esc(current.title || "Live is going soon")}</h2><p>${esc(current.seek_display || "00:00")} / ${esc(current.duration_display || "00:00")} | Next: ${esc((live.next || {}).title || "-")}</p></div>
        <div class="preview-actions"><span>View</span><span>Live</span><span>Sync</span><span>Full</span></div>
        ${setting.show_ticker ? `<div class="ticker-sim"><div class="ticker-label">${esc(tickerLabel)}</div><div class="ticker-cut"></div><div class="ticker-text">${esc(tickerText)}</div></div>` : ""}
      </div>
      <div class="pill-row">
        <span class="pill">Seek ${esc(current.seek_display || "00:00")}</span>
        <span class="pill">Remaining ${esc(current.remaining_display || "00:00")}</span>
        <span class="pill">Playlist ${(live.playlist || {}).count || 0} videos</span>
      </div>
    </section>`;
  }

  function renderSchedule(rows = [], title = "Upcoming Programs") {
    return `<section class="dashboard-card">
      <div class="card-head"><h2>${esc(title)}</h2><button class="ghost-btn" data-section-jump="epg">View All</button></div>
      <div class="schedule">${rows.map((row, index) => `<div class="schedule-row"><div><span class="dot" style="background:${index === 0 ? "#7c4dff" : index === 1 ? "#e8466d" : "#f08b22"}"></span>${esc(row.time)}</div><div><div class="schedule-title">${esc(row.title)}</div><div class="schedule-sub">${esc(row.duration)} | ${esc(row.status)}</div></div></div>`).join("") || `<p class="muted">Playlist empty</p>`}</div>
    </section>`;
  }

  function renderPlaylistTable(items = [], title = "Playlist Items") {
    return `<section class="dashboard-card"><div class="card-head"><h2>${esc(title)}</h2></div><table class="table"><thead><tr><th>#</th><th>Title</th><th>HLS</th><th>Duration</th><th>Active</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.position || "-")}</td><td>${esc(item.title)}</td><td>${status(item.hls_status)} ${progress(item.hls_progress_percent, item.hls_status)}</td><td>${esc(item.duration_display)}</td><td>${item.is_active ? "Yes" : "No"}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">No playlist items</td></tr>`}</tbody></table></section>`;
  }

  function renderProcessingCard(processing) {
    const liveJobs = processing.live_processing || [];
    const shortJobs = processing.short_processing || [];
    const renderJobs = (processing.render_jobs || []).filter((job) => isActiveState(job.status));
    const downloadJobs = (processing.downloads_recent || []).filter((job) => isActiveState(job.status));
    const pendingRenderCount = count(processing.renders, "pending");
    const pendingDownloadCount = count(processing.downloads, "pending");
    const activeJobs = [...liveJobs, ...shortJobs, ...renderJobs, ...downloadJobs];
    const rows = [
      ["Live HLS", liveJobs.length || count(processing.live_hls, "processing"), averageProgress(liveJobs)],
      ["Shorts HLS", shortJobs.length || count(processing.short_hls, "processing"), averageProgress(shortJobs)],
      ["Rendering", renderJobs.length || count(processing.renders, "processing"), averageProgress(renderJobs)],
      ["Downloads", downloadJobs.length || count(processing.downloads, "processing"), averageProgress(downloadJobs)],
      ["Pending", pendingRenderCount + pendingDownloadCount, 0],
    ];
    const total = rows.reduce((sum, [, amount]) => sum + Number(amount || 0), 0);
    const percent = activeJobs.length ? averageProgress(activeJobs) : total ? 0 : 100;
    return `<section class="dashboard-card">
      <div class="card-head"><h2>System Processing</h2><button class="ghost-btn" data-section-jump="processing">Open</button></div>
      <div class="processing-layout">
        <div class="donut" style="--p:${percent}"><div><strong>${percent}%</strong><small>Processing</small></div></div>
        <div class="task-list">${rows.map(([name, amount, rowPct]) => `<div class="task-row"><label>${esc(name)} <b>${amount}</b></label>${progress(amount ? rowPct : 0, amount ? "" : "pending")}</div>`).join("")}<p class="muted">Total Tasks: ${total}</p></div>
      </div>
    </section>`;
  }

  function renderBandwidthCard(payload) {
    const periods = (payload.bandwidth || {}).periods || {};
    const today = periods.today || {};
    return `<section class="dashboard-card bandwidth-card">
      <div class="card-head" style="padding:0 0 14px;border:0"><h2>Project Bandwidth Usage</h2><div class="pill-row" style="padding:0"><span class="pill">Daily</span><span class="pill">Week</span><span class="pill">Month</span></div></div>
      <div class="bandwidth-flex"><div class="bandwidth-donut"><div><strong>${esc(today.display || "0 B")}</strong><small>Project Traffic</small></div></div><div class="mini-list"><div class="mini-item"><span>Mobile App</span><b>${esc(today.mobile_display || "0 B")}</b></div><div class="mini-item"><span>Web App</span><b>${esc(today.web_display || "0 B")}</b></div><div class="mini-item"><span>Project Requests</span><b>${esc(today.requests || 0)}</b></div></div></div>
    </section>`;
  }

  function renderServerCard(server) {
    const projectPercent = Number(server.project_disk_percent ?? server.disk_percent ?? 0);
    const partitionPercent = Number(server.project_partition_used_percent ?? server.disk_percent ?? 0);
    return `<section class="dashboard-card server-card">
      <div class="card-head" style="padding:0 0 14px;border:0"><h2>Project Resources</h2><span class="muted">${esc(server.hostname || "")}</span></div>
      <div class="server-rings">
        <div class="ring" style="--p:${Number(server.cpu_percent || 0)};--c:#5fe17c"><div><strong>${esc(server.cpu_percent ?? "-")}%</strong><small>CPU</small></div></div>
        <div class="ring" style="--p:${Number(server.ram_percent || 0)};--c:#78e560"><div><strong>${esc(server.ram_percent ?? "-")}%</strong><small>RAM</small></div></div>
        <div class="ring" style="--p:${projectPercent};--c:#f4a52f"><div><strong>${esc(projectPercent)}%</strong><small>Project</small></div></div>
        <div class="ring" style="--p:${partitionPercent};--c:#80d95e"><div><strong>${esc(server.load_average || "0")}</strong><small>Load</small></div></div>
      </div>
      <div class="pill-row" style="padding:16px 0 0">
        <span class="pill">Project Used ${esc(server.project_used_display || "-")}</span>
        <span class="pill">Project Disk Free ${esc(server.project_disk_free_display || server.disk_free_display || "-")}</span>
        <span class="pill">RAM ${esc(server.ram_used_display)} / ${esc(server.ram_total_display)}</span>
        <span class="pill">Root ${esc(server.project_root || "-")}</span>
      </div>
    </section>`;
  }

  function renderAnalyticsCard(payload) {
    const bandwidth = ((payload.bandwidth || {}).periods || {}).today || {};
    const processing = payload.processing || {};
    return `<section class="dashboard-card bandwidth-card"><div class="card-head" style="padding:0 0 14px;border:0"><h2>Analysis Summary</h2><span class="muted">Today</span></div><div class="mini-list">
      <div class="mini-item"><span>Traffic</span><b>${esc(bandwidth.display || "0 B")}</b></div>
      <div class="mini-item"><span>Live HLS failed</span><b>${count(processing.live_hls, "failed")}</b></div>
      <div class="mini-item"><span>Render failed</span><b>${count(processing.renders, "failed")}</b></div>
      <div class="mini-item"><span>Active jobs</span><b>${(processing.live_processing || []).length + (processing.short_processing || []).length}</b></div>
    </div></section>`;
  }

  function renderSparkline() {
    return `<section class="dashboard-card bandwidth-card"><div class="card-head" style="padding:0 0 14px;border:0"><h2>Bandwidth Analytics</h2><span class="muted">This Month</span></div><div class="sparkline"></div></section>`;
  }

  function renderTables(payload) {
    const storage = payload.storage || [];
    const live = payload.live || {};
    const rows = live.schedule || [];
    return `<div class="grid mini-grid">
      <section class="dashboard-card storage-card"><h2>Project Storage Overview</h2><table class="table"><tbody>${storage.slice(0,4).map((row) => `<tr><td>${esc(row.label)}</td><td>${esc(row.display)}</td></tr>`).join("")}</tbody></table></section>
      <section class="dashboard-card top-card"><h2>Top Live Channels</h2><table class="table"><tbody>${rows.slice(0,4).map((row, index) => `<tr><td>${index + 1}. ${esc(row.title)}</td><td>${esc(row.duration)}</td></tr>`).join("") || `<tr><td class="muted">No playlist data</td></tr>`}</tbody></table></section>
      <section class="dashboard-card activity-card"><h2>Recent Activities</h2><div class="mini-list"><div class="mini-item"><span>Live state refreshed</span><span>Now</span></div><div class="mini-item"><span>Playlist version</span><span>${esc((live.playlist || {}).version || 0)}</span></div><div class="mini-item"><span>Current video</span><span>${esc((live.current || {}).title || "-")}</span></div></div></section>
      <section class="dashboard-card alert-card"><h2>Alerts & Notifications</h2><div class="mini-list"><div class="mini-item"><span>Failed HLS</span><span>${count((payload.processing || {}).live_hls, "failed")}</span></div><div class="mini-item"><span>Failed renders</span><span>${count((payload.processing || {}).renders, "failed")}</span></div><div class="mini-item"><span>Project disk free</span><span>${esc((payload.server || {}).project_disk_free_display || (payload.server || {}).disk_free_display || "-")}</span></div></div></section>
    </div>`;
  }

  function renderProcessing(processing) {
    const activeRows = [
      ...(processing.live_processing || []).map((job) => ({ ...job, kind: "Live HLS" })),
      ...(processing.short_processing || []).map((job) => ({ ...job, kind: "Shorts HLS" })),
      ...(processing.render_jobs || []).filter((job) => isActiveState(job.status)).map((job) => ({ ...job, kind: "Render" })),
      ...(processing.downloads_recent || []).filter((job) => isActiveState(job.status)).map((job) => ({ ...job, kind: "Download" })),
    ];
    return `${pageTitle("Upload & Processing", "Live status of HLS, uploads, downloads and render jobs", {})}<div class="grid main-grid two-col">${renderProcessingCard(processing)}<section class="dashboard-card"><div class="card-head"><h2>Active Jobs</h2></div><table class="table"><thead><tr><th>Type</th><th>Title</th><th>Status</th><th>Progress</th></tr></thead><tbody>${activeRows.map((job) => `<tr><td>${esc(job.kind)}</td><td>${esc(job.title)}</td><td>${status(job.status || job.hls_status)}</td><td>${progress(job.progress_percent ?? job.hls_progress_percent, job.status || job.hls_status)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No active processing</td></tr>`}</tbody></table></section></div>`;
  }

  function renderServer(payload) {
    return `${pageTitle("Server Monitor", "Project storage, RAM, CPU and load health", {})}<div class="grid lower-grid">${renderServerCard(payload.server || {})}<section class="dashboard-card storage-card"><h2>Project Storage Detail</h2><table class="table"><tbody>${(payload.storage || []).map((row) => `<tr><td>${esc(row.label)}</td><td>${esc(row.display)}</td><td class="muted">${esc(row.path || "")}</td></tr>`).join("") || `<tr><td class="muted">No storage data</td></tr>`}</tbody></table></section>${renderAnalyticsCard(payload)}</div>`;
  }

  function renderBandwidth(payload) {
    const periods = (payload.bandwidth || {}).periods || {};
    return `${pageTitle("Bandwidth", "Mobile app, web app and project request usage", {})}<div class="grid lower-grid">${renderBandwidthCard(payload)}${renderSparkline()}${renderAnalyticsCard(payload)}</div><div style="height:18px"></div><section class="dashboard-card"><div class="card-head"><h2>Bandwidth Detail</h2></div><table class="table"><thead><tr><th>Period</th><th>Total</th><th>Mobile</th><th>Web</th><th>Requests</th></tr></thead><tbody>${Object.entries(periods).map(([key,row]) => `<tr><td>${esc(key)}</td><td>${esc(row.display)}</td><td>${esc(row.mobile_display)}</td><td>${esc(row.web_display)}</td><td>${esc(row.requests || 0)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">Apache logs not available to Django user</td></tr>`}</tbody></table></section>`;
  }

  function renderUploads(uploads) {
    const videos = uploads.videos || [];
    const shorts = uploads.shorts || [];
    return `${pageTitle("Uploads Library", "Latest uploaded videos and shorts", {})}<div class="grid lower-grid two-col"><section class="dashboard-card"><div class="card-head"><h2>Live Uploads</h2></div><table class="table"><thead><tr><th>Video</th><th>HLS</th><th>Size</th><th>Updated</th></tr></thead><tbody>${videos.map((v) => `<tr><td>${esc(v.title)}</td><td>${status(v.hls_status)} ${progress(v.hls_progress_percent, v.hls_status)}</td><td>${esc(v.file_size_display)}</td><td>${esc(v.updated_at)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No videos</td></tr>`}</tbody></table></section><section class="dashboard-card"><div class="card-head"><h2>Shorts Uploads</h2></div><table class="table"><thead><tr><th>Short</th><th>HLS</th><th>Duration</th></tr></thead><tbody>${shorts.map((v) => `<tr><td>${esc(v.title)}</td><td>${status(v.status)} ${progress(v.progress_percent, v.status)}</td><td>${esc(v.duration_display)}</td></tr>`).join("") || `<tr><td colspan="3" class="muted">No shorts</td></tr>`}</tbody></table></section></div>`;
  }

  function renderRenders(renders) {
    const rows = renders.items || [];
    return `${pageTitle("Video Library", "Rendered videos from live stream cycle", {})}<section class="dashboard-card"><div class="card-head"><h2>Rendered Videos</h2></div><table class="table"><thead><tr><th>Title</th><th>Source</th><th>Status</th><th>Progress</th><th>Size</th><th>Completed</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${esc(row.title)}</td><td>${esc(row.source_video)}</td><td>${status(row.status)}</td><td>${progress(row.progress_percent, row.status)}</td><td>${esc(row.file_size_display)}</td><td>${esc(row.completed_at || row.created_at)}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">No rendered videos</td></tr>`}</tbody></table></section>`;
  }

  function renderUsers(payload) {
    const users = payload.users || {};
    const devices = users.recent_devices || [];
    return `${pageTitle("Users & Devices", "Mobile admin sessions, followers and viewer interactions", {})}<div class="grid kpi-grid">
      ${kpi("Total Users", users.total_users || 0, `${users.active_users || 0} active`)}
      ${kpi("Staff/Admin", users.staff_users || 0, "control access", "green")}
      ${kpi("Mobile Devices", users.mobile_tokens || 0, `${users.mobile_tokens_today || 0} today`, "blue")}
      ${kpi("Followers", users.channel_follows || 0, "channel follows", "orange")}
      ${kpi("Shorts Activity", (users.shorts_likes || 0) + (users.shorts_comments || 0), `${users.shorts_likes || 0} likes / ${users.shorts_comments || 0} comments`, "pink")}
    </div><section class="dashboard-card"><div class="card-head"><h2>Recent Mobile Admin Devices</h2></div><table class="table"><thead><tr><th>User</th><th>Device</th><th>Created</th><th>Last Used</th></tr></thead><tbody>${devices.map((row) => `<tr><td>${esc(row.user)}</td><td>${esc(row.device)}</td><td>${esc(row.created_at)}</td><td>${esc(row.last_used_at)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No mobile devices</td></tr>`}</tbody></table></section>`;
  }

  function renderAnalyticsSection(payload) {
    const live = payload.live || {};
    const processing = payload.processing || {};
    const uploads = payload.uploads || {};
    const renders = payload.renders || {};
    const users = payload.users || {};
    const blogs = payload.blogs || {};
    return `${pageTitle("Analytics", "Project level live TV, render, viewer and upload analysis", live)}
      <div class="grid kpi-grid">
        ${kpi("Blogs Today", blogs.today || 0, "published today", "green")}
        ${kpi("Blogs Yesterday", blogs.yesterday || 0, "published yesterday", "blue")}
        ${kpi("Blogs This Month", blogs.this_month || 0, "published this month", "orange")}
        ${kpi("Playlist Videos", (live.playlist || {}).count || 0, (live.playlist || {}).duration_display || "00:00")}
        ${kpi("Live Uploads", (uploads.videos || []).length, "latest loaded", "green")}
        ${kpi("Shorts", (uploads.shorts || []).length, "latest loaded", "blue")}
        ${kpi("Rendered", (renders.items || []).length, `${count(processing.renders, "processing")} processing`, "orange")}
        ${kpi("Users", users.total_users || 0, `${users.channel_follows || 0} follows`, "pink")}
      </div>
      <div class="grid lower-grid">${renderLive(live)}${renderProcessingCard(processing)}${renderAnalyticsCard(payload)}</div>
      ${renderTables(payload)}`;
  }

  function renderSettings(payload) {
    const setting = payload.settings || {};
    const fb = payload.facebook_live || {};
    const processing = payload.processing || {};
    return `${pageTitle("Settings", "Live TV controls and broadcast visibility", {})}<div class="grid lower-grid">
      <section class="dashboard-card controls-card"><div class="card-head"><h2>Live Controls</h2></div><div class="actions">
        <button class="action-btn" data-action="rebuild_playlist">Rebuild Playlist</button>
        <button class="action-btn" data-action="repair_live_health">Repair Live Health</button>
        <button class="action-btn" data-action="retry_failed_hls">Retry Failed HLS</button>
        <button class="action-btn" data-action="retry_failed_renders">Retry Failed Renders</button>
        <button class="action-btn" data-action="toggle_ticker">Ticker: ${setting.show_ticker ? "ON" : "OFF"}</button>
        <button class="action-btn" data-action="toggle_live_badge">Live Badge: ${setting.show_live_badge ? "ON" : "OFF"}</button>
        <button class="action-btn" data-action="toggle_channel_logo">Logo: ${setting.show_channel_logo ? "ON" : "OFF"}</button>
        <button class="action-btn" data-action="toggle_lower_third">Lower Third: ${setting.show_lower_third ? "ON" : "OFF"}</button>
      </div></section>
      <section class="dashboard-card storage-card"><h2>Current Broadcast Settings</h2><div class="mini-list"><div class="mini-item"><span>Ticker</span><b>${setting.show_ticker ? "ON" : "OFF"}</b></div><div class="mini-item"><span>Live Badge</span><b>${setting.show_live_badge ? "ON" : "OFF"}</b></div><div class="mini-item"><span>Channel Logo</span><b>${setting.show_channel_logo ? "ON" : "OFF"}</b></div><div class="mini-item"><span>Lower Third</span><b>${setting.show_lower_third ? "ON" : "OFF"}</b></div></div></section>
      <section class="dashboard-card storage-card"><h2>Facebook Live</h2><div class="mini-list"><div class="mini-item"><span>Status</span><b>${esc(fb.status || "-")}</b></div><div class="mini-item"><span>Enabled</span><b>${fb.is_enabled ? "Yes" : "No"}</b></div><div class="mini-item"><span>Last Error</span><b>${esc(fb.last_error || "-")}</b></div></div></section>
      ${renderProcessingCard(processing)}
    </div>`;
  }

  function renderOverview(payload) {
    const live = payload.live || {};
    const processing = payload.processing || {};
    const server = payload.server || {};
    const uploads = payload.uploads || {};
    const blogs = payload.blogs || {};
    return `${pageTitle("Dashboard Overview", "Real-time overview of your Live TV platform", live)}
      <div class="grid kpi-grid">
        ${kpi("Blogs Today", blogs.today || 0, "published today", "green")}
        ${kpi("Blogs Yesterday", blogs.yesterday || 0, "published yesterday", "blue")}
        ${kpi("Blogs This Month", blogs.this_month || 0, "published this month", "orange")}
        ${kpi("Live TV Channels", (live.playlist || {}).count || 0, "+ playlist items")}
        ${kpi("On Air Now", live.current ? "01" : "00", live.current?.title || "No live video", "green")}
        ${kpi("Total Uploads", (uploads.videos_total || 0) + (uploads.shorts_total || 0), `${uploads.shorts_total || 0} shorts`, "blue")}
        ${kpi("Render Jobs", (processing.renders || {}).completed || (processing.renders || {}).done || 0, `${(processing.renders || {}).processing || 0} processing`, "orange")}
        ${kpi("Project Used", server.project_used_display || "-", `${server.project_disk_percent || 0}% of project disk`, "pink")}
      </div>
      <div class="grid main-grid">${renderLive(live)}${renderProcessingCard(processing)}${renderSchedule(live.schedule || [])}</div>
      <div class="grid lower-grid">${renderBandwidthCard(payload)}${renderServerCard(server)}${renderSparkline()}</div>
      ${renderTables(payload)}`;
  }

  function render(payload) {
    const currentSection = payload.section || section;
    if (currentSection === "live") content.innerHTML = `${pageTitle("Live TV Preview", "Same backend live cycle with current and next video", payload.live || {})}<div class="grid main-grid two-col">${renderLive(payload.live || {})}${renderSchedule((payload.live || {}).schedule || [])}</div>`;
    else if (currentSection === "programs") content.innerHTML = `${pageTitle("Programs", "Current and upcoming live program sequence", payload.live || {})}<div class="grid main-grid two-col">${renderSchedule((payload.live || {}).schedule || [], "Program Timeline")}${renderPlaylistTable(payload.items || [], "Program Playlist")}</div>`;
    else if (currentSection === "epg" || currentSection === "playlist") content.innerHTML = `${pageTitle("EPG / Schedule", "Future live playlist timing and active items", payload.live || {})}${renderSchedule((payload.live || {}).schedule || [], "EPG Timeline")}<div style="height:18px"></div>${renderPlaylistTable(payload.items || [], "Full Schedule")}`;
    else if (currentSection === "processing") content.innerHTML = renderProcessing(payload.processing || {});
    else if (currentSection === "uploads") content.innerHTML = renderUploads(payload.uploads || {});
    else if (currentSection === "users") content.innerHTML = renderUsers(payload);
    else if (currentSection === "library" || currentSection === "renders") content.innerHTML = renderRenders(payload.renders || {});
    else if (currentSection === "analytics") content.innerHTML = renderAnalyticsSection(payload);
    else if (currentSection === "bandwidth") content.innerHTML = renderBandwidth(payload);
    else if (currentSection === "server") content.innerHTML = renderServer(payload);
    else if (currentSection === "settings" || currentSection === "controls") content.innerHTML = renderSettings(payload);
    else content.innerHTML = renderOverview(payload);
    applySearchFilter();
  }

  async function load(nextSection = section, options = {}) {
    const currentRequest = ++requestId;
    section = nextSection;
    if (!options.silent) setLoading(true, `Loading ${section.replace(/-/g, " ")}...`);
    try {
      const res = await fetch(sectionUrl(section), { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await readJsonResponse(res, "Dashboard data load failed");
      if (currentRequest !== requestId) return;
      if (!data.ok) throw new Error(data.message || "Dashboard failed");
      render(data.payload);
    } catch (error) {
      showAlert(error.message || "Dashboard data load failed", true);
    } finally {
      if (currentRequest === requestId) setLoading(false);
    }
  }

  async function runAction(action) {
    const form = new FormData();
    form.append("action", action);
    setLoading(true, "Running dashboard action...");
    try {
      const res = await fetch(shell.dataset.actionUrl, { method: "POST", body: form, headers: { "X-CSRFToken": csrf() } });
      const data = await readJsonResponse(res, "Dashboard action failed");
      showAlert(data.message || (data.ok ? "Done" : "Action failed"), !data.ok);
      await load(section, { silent: true });
    } catch (error) {
      showAlert(error.message || "Action failed", true);
    } finally {
      setLoading(false);
    }
  }

  function applySearchFilter() {
    const query = (searchInput?.value || "").trim().toLowerCase();
    content.querySelectorAll("tbody tr, .schedule-row, .mini-item").forEach((row) => {
      row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query);
    });
  }

  function activateButton(button) {
    document.querySelectorAll(".side-item").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  }

  document.querySelectorAll(".side-item").forEach((button) => {
    button.addEventListener("click", () => {
      activateButton(button);
      load(button.dataset.section);
    });
  });
  refreshButton.addEventListener("click", () => load(section));
  searchInput?.addEventListener("input", applySearchFilter);
  content.addEventListener("click", (event) => {
    const jump = event.target.closest("[data-section-jump]");
    if (jump) {
      const target = jump.dataset.sectionJump;
      document.querySelector(`.side-item[data-section="${target}"]`)?.click();
      return;
    }
    const button = event.target.closest("[data-action]");
    if (button) runAction(button.dataset.action);
  });

  try {
    const initial = JSON.parse(document.getElementById("initial-dashboard-json")?.textContent || "{}");
    if (initial && initial.section) render(initial);
  } catch (_) {}
  load("overview", { silent: true });
  timer = setInterval(() => load(section, { silent: true }), 5000);
  window.addEventListener("beforeunload", () => clearInterval(timer));
})();

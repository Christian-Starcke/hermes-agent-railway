(() => {
  let workspaces = [];
  let currentId = null;
  let selectedId = null;

  const listEl = document.getElementById("workspace-list");
  const emptyEl = document.getElementById("empty-state");
  const detailEl = document.getElementById("detail");
  const createDialog = document.getElementById("create-dialog");

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || res.statusText);
    }
    return data;
  }

  function badge(ws) {
    const parts = [ws.status, ws.agent_backend].filter(Boolean);
    return parts.join(" · ");
  }

  function renderList() {
    listEl.innerHTML = "";
    workspaces.forEach((ws) => {
      const item = document.createElement("div");
      item.className = "ws-item" + (ws.id === selectedId ? " active" : "") + (ws.id === currentId ? " current" : "");
      item.innerHTML = `<div class="title">${escapeHtml(ws.name)}</div><div class="sub">${escapeHtml(ws.branch)}<br>${escapeHtml(badge(ws))}</div>`;
      item.addEventListener("click", () => selectWorkspace(ws.id));
      listEl.appendChild(item);
    });
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function loadWorkspaces() {
    const data = await api("/api/workspaces");
    workspaces = data.workspaces || [];
    currentId = data.current_workspace_id || null;
    renderList();
    if (selectedId) await selectWorkspace(selectedId, { skipReload: true });
  }

  async function selectWorkspace(id, opts = {}) {
    selectedId = id;
    renderList();
    const ws = workspaces.find((w) => w.id === id);
    if (!ws) return;

    emptyEl.classList.add("hidden");
    detailEl.classList.remove("hidden");
    document.getElementById("ws-name").textContent = ws.name;
    document.getElementById("ws-meta").innerHTML = [
      ws.branch,
      ws.repo_root,
      ws.issue_url ? `<a href="${escapeHtml(ws.issue_url)}" target="_blank" rel="noopener">issue</a>` : null,
      ws.pr_url ? `<a href="${escapeHtml(ws.pr_url)}" target="_blank" rel="noopener">PR</a>` : null,
    ].filter(Boolean).join(" · ");

    document.getElementById("ws-backend").value = ws.agent_backend || "hermes";

    const diffData = await api(`/api/workspaces/${id}/diff`);
    const patch = diffData.diff?.patch || "";
    const container = document.getElementById("diff-container");
    if (!patch.trim()) {
      container.innerHTML = "<p class='empty'>No diff yet vs base ref.</p>";
    } else {
      container.innerHTML = Diff2Html.html(patch, { drawFileList: true, matching: "lines", outputFormat: "side-by-side" });
    }
  }

  document.getElementById("btn-new").addEventListener("click", () => createDialog.showModal());
  document.getElementById("create-cancel").addEventListener("click", () => createDialog.close());

  document.getElementById("create-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const body = {
        name: fd.get("name"),
        repo_root: fd.get("repo_root"),
        base_ref: fd.get("base_ref") || "main",
        issue_url: fd.get("issue_url") || null,
        activate: fd.get("activate") === "on",
      };
      const data = await api("/api/workspaces", { method: "POST", body: JSON.stringify(body) });
      createDialog.close();
      await loadWorkspaces();
      if (data.workspace?.id) await selectWorkspace(data.workspace.id);
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("btn-activate").addEventListener("click", async () => {
    if (!selectedId) return;
    try {
      await api(`/api/workspaces/${selectedId}/activate`, { method: "PUT" });
      await loadWorkspaces();
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("btn-chat").addEventListener("click", async () => {
    if (!selectedId) return;
    try {
      await api(`/api/workspaces/${selectedId}/chat-link`);
      window.location.href = "/";
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("btn-pr").addEventListener("click", async () => {
    if (!selectedId) return;
    try {
      const data = await api(`/api/workspaces/${selectedId}/pr`, { method: "POST", body: "{}" });
      alert(data.pr_url ? `PR created: ${data.pr_url}` : "PR created");
      await loadWorkspaces();
      await selectWorkspace(selectedId, { skipReload: true });
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("btn-archive").addEventListener("click", async () => {
    if (!selectedId || !confirm("Archive this workspace and remove the worktree?")) return;
    try {
      await api(`/api/workspaces/${selectedId}/archive`, { method: "POST" });
      selectedId = null;
      detailEl.classList.add("hidden");
      emptyEl.classList.remove("hidden");
      await loadWorkspaces();
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("ws-backend").addEventListener("change", async (e) => {
    if (!selectedId) return;
    try {
      await api(`/api/workspaces/${selectedId}`, {
        method: "PATCH",
        body: JSON.stringify({ agent_backend: e.target.value }),
      });
      await loadWorkspaces();
    } catch (err) {
      alert(err.message);
    }
  });

  loadWorkspaces().catch((err) => {
    listEl.innerHTML = `<p class="sub">${escapeHtml(err.message)}</p>`;
  });
})();

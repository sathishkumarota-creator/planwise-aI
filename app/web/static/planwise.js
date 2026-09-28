/* PlanWise client runtime.
   One renderer serves the three planners and the history detail modal;
   the original duplicated per-planner result markup and AJAX instead. */

(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);

  /* ---------------- theme ---------------- */
  const themeToggle = $("#themeToggle");
  if (themeToggle) {
    const apply = (mode) => {
      document.documentElement.dataset.theme = mode;
      localStorage.setItem("pw-theme", mode);
      themeToggle.innerHTML = `<i class="fa-solid fa-${mode === "dark" ? "sun" : "moon"}"></i>`;
    };
    apply(document.documentElement.dataset.theme || "light");
    themeToggle.addEventListener("click", () =>
      apply(document.documentElement.dataset.theme === "dark" ? "light" : "dark")
    );
  }

  /* ---------------- modal ---------------- */
  const modal = $("#reportModal");
  const openModal = (title, node) => {
    if (!modal) return;
    $("#reportModalTitle").textContent = title;
    const body = $("#reportModalBody");
    body.replaceChildren(node);
    modal.hidden = false;
  };
  const closeModal = () => { if (modal) modal.hidden = true; };
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-modal]")) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeModal();
  });

  /* ---------------- API helpers ---------------- */
  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Please sign in again.");
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof payload.detail === "string"
        ? payload.detail
        : "Request failed. Check the values and try again.";
      throw new Error(message);
    }
    return payload;
  }

  const inr = (value) => {
    const num = Number(value) || 0;
    return "₹" + num.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  };

  /* ---------------- report rendering (shared) ---------------- */
  function renderReport(report) {
    const wrap = document.createElement("div");

    const stats = document.createElement("div");
    stats.className = "stats";
    const items = [
      ["Total budget", inr(report.budget)],
      ["Planned", inr(report.planned_total)],
      ["Reserve", inr(report.reserve)],
      ["Remaining", inr(report.remaining)],
    ];
    for (const [label, value] of items) {
      const stat = document.createElement("div");
      stat.className = "stat";
      stat.innerHTML = `<div class="stat__label">${label}</div><div class="stat__value">${value}</div>`;
      stats.appendChild(stat);
    }
    wrap.appendChild(stats);

    const source = report.source === "gemini" ? "AI-assisted plan" : "Catalog plan (offline)";
    const head = document.createElement("div");
    head.className = "result__head";
    head.innerHTML = `<h2>Allocation plan</h2><span class="result__badge"><i class="fa-solid fa-bolt"></i> ${source}</span>`;
    wrap.appendChild(head);

    const grid = document.createElement("div");
    grid.className = "cat-grid";
    const maxShare = Math.max(...report.calculation.map((row) => row.budget_share), 1);
    for (const category of report.categories) {
      const calcRow = report.calculation.find((r) => r.category === category.name) || {};
      const cat = document.createElement("article");
      cat.className = "cat";
      cat.innerHTML = `
        <div class="cat__head"><span class="cat__name">${category.name}</span>
          <span class="cat__amount">${inr(category.amount)}</span></div>
        <div class="cat__share">${calcRow.budget_share ?? 0}% of budget · ${calcRow.units ?? 0} unit(s)</div>
        <div class="bar"><span style="width:${Math.round(((calcRow.budget_share ?? 0) / maxShare) * 100)}%"></span></div>
        <ul></ul>`;
      const list = $("ul", cat);
      for (const item of category.items) {
        const li = document.createElement("li");
        const links = Object.entries(item.marketplaces || {})
          .map(([key, url]) => `<a href="${url}" target="_blank" rel="noopener">${key}</a>`)
          .join("");
        li.innerHTML = `
          <strong>${item.name} <small>× ${item.quantity} · ${inr(item.unit_price)} each</small></strong>
          <div class="desc">${item.description || ""}</div>
          ${links ? `<div class="links">${links}</div>` : ""}`;
        list.appendChild(li);
      }
      grid.appendChild(cat);
    }
    wrap.appendChild(grid);

    if (report.extras?.venues?.length) {
      const venues = document.createElement("div");
      venues.className = "insights";
      venues.innerHTML = "<h3><i class='fa-solid fa-location-dot'></i> Venue ideas</h3>";
      for (const venue of report.extras.venues) {
        const links = Object.entries(venue.search_links || {})
          .map(([key, url]) => `<a href="${url}" target="_blank" rel="noopener">${key}</a>`)
          .join(" · ");
        venues.insertAdjacentHTML(
          "beforeend",
          `<div class="venue-card"><strong>${venue.name}</strong>
             <span>up to ${venue.capacity} guests · about ${inr(venue.estimated_cost)}</span>
             ${links ? `<div class="links">${links}</div>` : ""}</div>`
        );
      }
      wrap.appendChild(venues);
    }

    if (report.extras?.outfit) {
      const outfit = document.createElement("div");
      outfit.className = "insights";
      outfit.innerHTML = `<h3><i class='fa-solid fa-palette'></i> Outfit analysis</h3>
        <p style="margin:0 0 .4rem">Colors: <strong>${report.extras.outfit.colors.join(", ")}</strong>
        · Style: <strong>${report.extras.outfit.style}</strong>
        · Formality: <strong>${report.extras.outfit.formality}</strong></p>`;
      wrap.appendChild(outfit);
    }

    if (report.insights?.length) {
      const tips = document.createElement("div");
      tips.className = "insights";
      tips.innerHTML = "<h3><i class='fa-solid fa-lightbulb'></i> Planning notes</h3><ul>" +
        report.insights.map((tip) => `<li>${tip}</li>`).join("") + "</ul>";
      wrap.appendChild(tips);
    }

    const table = document.createElement("table");
    table.className = "calc";
    table.innerHTML = `
      <thead><tr><th>Category</th><th>Units</th><th>Cost</th><th>Share</th></tr></thead>
      <tbody>
        ${report.calculation.map((row) => `
          <tr><td>${row.category}</td><td>${row.units}</td>
          <td>${inr(row.cost)}</td><td>${row.budget_share}%</td></tr>`).join("")}
      </tbody>`;
    wrap.appendChild(table);
    return wrap;
  }

  function skeletons(target) {
    target.hidden = false;
    target.innerHTML = `
      <div class="stats">
        ${'<div class="skeleton skeleton--stat"></div>'.repeat(4)}
      </div>
      <div class="cat-grid">
        ${'<div class="skeleton skeleton--cat"></div>'.repeat(3)}
      </div>`;
  }

  function showError(form, message) {
    const box = $("[data-error]", form);
    if (box) {
      box.textContent = message;
      box.hidden = false;
    } else {
      alert(message);
    }
  }

  /* ---------------- planner forms ---------------- */
  const form = $("#plannerForm");
  if (form) {
    const result = $("#result");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = $("button[type=submit]", form);
      submit.disabled = true;
      if (result) skeletons(result);

      try {
        const kind = form.dataset.kind;
        const data = new FormData(form);
        const spec = { kind };
        for (const [key, value] of data.entries()) {
          if (key === "rooms") {
            (spec.rooms = spec.rooms || []).push(value);
          } else if (key.startsWith("include_")) {
            spec[key] = value === "on";
          } else if (key === "budget") {
            spec[key] = Number(value);
          } else if (/(_count|guest_count)$/.test(key)) {
            spec[key] = Number(value);
          } else {
            spec[key] = value;
          }
        }
        if (form.dataset.kind === "jewelry" && window.__outfitPhotoId) {
          spec.outfit_photo_id = window.__outfitPhotoId;
        }

        const payload = await api("/api/plans", {
          method: "POST",
          body: JSON.stringify({ spec }),
        });
        if (result) {
          result.replaceChildren(renderReport(payload.report));
          result.scrollIntoView({ behavior: "smooth" });
        }
      } catch (error) {
        if (result) result.hidden = true;
        showError(form, error.message);
      } finally {
        submit.disabled = false;
      }
    });
  }

  /* ---------------- outfit photo upload ---------------- */
  const photoPick = $("#photoPick");
  if (photoPick) {
    const input = $("#photoInput");
    const preview = $("#photoPreview");
    const status = $("#photoStatus");
    photoPick.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      status.textContent = "Uploading…";
      const body = new FormData();
      body.append("photo", file);
      try {
        const response = await fetch("/api/plans/outfit-photo", { method: "POST", body });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Upload failed.");
        window.__outfitPhotoId = payload.photo_id;
        preview.src = URL.createObjectURL(file);
        preview.hidden = false;
        status.textContent = "Photo ready - it will be analyzed when you generate the plan.";
      } catch (error) {
        status.textContent = error.message;
        window.__outfitPhotoId = null;
      }
    });
  }

  /* ---------------- history actions ---------------- */
  document.addEventListener("click", async (event) => {
    const viewButton = event.target.closest(".js-view-plan");
    if (viewButton) {
      const details = await api(`/api/plans/${viewButton.dataset.planId}`);
      openModal(details.title || "Plan details", renderReport(details.report));
      return;
    }
    const deleteButton = event.target.closest(".js-delete-plan");
    if (deleteButton && confirm("Delete this plan?")) {
      await api(`/api/plans/${deleteButton.dataset.planId}`, { method: "DELETE" });
      deleteButton.closest(".plan-list__item").remove();
    }
  });
})();

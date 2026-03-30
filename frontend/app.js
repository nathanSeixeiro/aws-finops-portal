/* ============================================================
   CostWatch — Application Logic
   ============================================================ */

// ---------- CONFIG ----------
const CONFIG = {
  apiBase: "https://pjwgnl7k38.execute-api.us-east-1.amazonaws.com/prod",
  apiKey: "8V9asI6yRD6oFPIx0vJWca6b2F3wOyoXf1hJSL3g",
};

// ---------- State ----------
let currentCurrency = "USD";
let summaryData = null;
let trendGranularity = "DAILY";
let trendChart = null;
let servicesChart = null;
let accountDonutChart = null;
let teamData = [];
let teamSortCol = null;
let teamSortAsc = true;

// ---------- Helpers ----------
function currencySymbol() {
  return currentCurrency === "USD" ? "$" : "R$";
}

function amountKey() {
  return currentCurrency === "USD" ? "amount_usd" : "amount_brl";
}

function totalKey() {
  return currentCurrency === "USD" ? "total_usd" : "total_brl";
}

function fmt(value) {
  const n = Number(value) || 0;
  return `${currencySymbol()}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pctFmt(value) {
  const n = Number(value) || 0;
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

// ---------- API Layer ----------
async function apiFetch(path, params = {}) {
  const url = new URL(`${CONFIG.apiBase}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const res = await fetch(url.toString(), {
    headers: { "x-api-key": CONFIG.apiKey },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

async function fetchSummary() {
  return apiFetch("/summary");
}

async function fetchServices(granularity, period) {
  return apiFetch("/services", { granularity, period });
}

async function fetchTrend(granularity, n) {
  return apiFetch("/trend", { granularity, n });
}

async function fetchForecast() {
  return apiFetch("/forecast");
}

// ---------- Error Toast ----------
function showError(msg) {
  let toast = document.getElementById("errorToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "errorToast";
    toast.setAttribute("role", "alert");
    Object.assign(toast.style, {
      position: "fixed", bottom: "24px", right: "24px", zIndex: "9999",
      background: "var(--accent-coral)", color: "#fff", padding: "12px 20px",
      borderRadius: "8px", fontFamily: "var(--font-body)", fontSize: "0.875rem",
      maxWidth: "400px", boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
      transition: "opacity 0.3s ease",
    });
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = "1";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = "0"; }, 5000);
}

// ---------- Sparkline SVG ----------
function renderSparkline(svgEl, values) {
  if (!values || values.length < 2) return;
  const poly = svgEl.querySelector("polyline");
  if (!poly) return;
  const w = 60, h = 24, pad = 2;
  const nums = values.map(Number);
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const range = max - min || 1;
  const pts = nums.map((v, i) => {
    const x = pad + (i / (nums.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  poly.setAttribute("points", pts.join(" "));
}

// ---------- Animated Counter (easeOutExpo) ----------
function animateValue(el, target, duration = 1200) {
  const start = performance.now();
  const from = 0;
  function easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }
  function tick(now) {
    const elapsed = Math.min((now - start) / duration, 1);
    const val = from + (target - from) * easeOutExpo(elapsed);
    el.textContent = fmt(val);
    if (elapsed < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ---------- KPI Cards ----------
function renderKPI(data) {
  if (!data) return;
  summaryData = data;

  const cards = [
    { id: "Today", key: "today", sparkKey: "today_trend" },
    { id: "Mtd", key: "mtd", sparkKey: "mtd_trend" },
    { id: "Prev", key: "prev_month", sparkKey: "prev_trend" },
    { id: "Forecast", key: "forecast", sparkKey: "forecast_trend" },
  ];

  cards.forEach(({ id, key, sparkKey }) => {
    const valEl = document.getElementById(`kpi${id}`);
    const deltaEl = document.getElementById(`delta${id}`);
    const sparkEl = document.getElementById(`sparkline${id}`);

    const usdVal = Number(data[`${key}_usd`] ?? data[key]?.amount_usd ?? 0);
    const brlVal = Number(data[`${key}_brl`] ?? data[key]?.amount_brl ?? 0);
    const target = currentCurrency === "USD" ? usdVal : brlVal;

    // Store both values for currency toggle
    valEl.dataset.usd = usdVal;
    valEl.dataset.brl = brlVal;

    animateValue(valEl, target);

    // Delta badge
    const delta = Number(data[`${key}_delta_pct`] ?? 0);
    if (delta !== 0) {
      deltaEl.textContent = pctFmt(delta);
      // For costs, going up is bad (coral), going down is good (green)
      deltaEl.className = `kpi-card__delta ${delta > 0 ? "kpi-card__delta--up" : "kpi-card__delta--down"}`;
    } else {
      deltaEl.textContent = "—";
      deltaEl.className = "kpi-card__delta";
    }

    // Sparkline
    const sparkData = data[sparkKey];
    if (Array.isArray(sparkData)) {
      const vals = sparkData.map((d) => Number(currentCurrency === "USD" ? (d.amount_usd ?? d) : (d.amount_brl ?? d)));
      renderSparkline(sparkEl, vals);
    }
  });
}

// ---------- Trend Line Chart ----------
function chartColors() {
  return {
    line: getComputedStyle(document.documentElement).getPropertyValue("--accent-green").trim(),
    grid: getComputedStyle(document.documentElement).getPropertyValue("--border").trim(),
    text: getComputedStyle(document.documentElement).getPropertyValue("--text-muted").trim(),
    blue: getComputedStyle(document.documentElement).getPropertyValue("--accent-blue").trim(),
    green: getComputedStyle(document.documentElement).getPropertyValue("--accent-green").trim(),
    coral: getComputedStyle(document.documentElement).getPropertyValue("--accent-coral").trim(),
    amber: getComputedStyle(document.documentElement).getPropertyValue("--accent-amber").trim(),
  };
}

async function renderTrendChart(granularity) {
  const n = granularity === "DAILY" ? 30 : granularity === "WEEKLY" ? 12 : 12;
  let data;
  try {
    data = await fetchTrend(granularity, n);
  } catch (e) {
    showError(`Trend: ${e.message}`);
    return;
  }

  const items = Array.isArray(data) ? data : data.trend ?? [];
  const labels = items.map((d) => d.period);
  const values = items.map((d) => Number(d[totalKey()] ?? 0));
  const c = chartColors();
  const ctx = document.getElementById("trendChart");

  if (trendChart) {
    trendChart.data.labels = labels;
    trendChart.data.datasets[0].data = values;
    trendChart.update("active");
    return;
  }

  trendChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: c.line,
        backgroundColor: `${c.line}18`,
        fill: true,
        tension: 0.35,
        pointRadius: 2,
        pointHoverRadius: 5,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (tip) => fmt(tip.raw) },
        },
      },
      scales: {
        x: { ticks: { color: c.text, maxRotation: 45 }, grid: { color: c.grid } },
        y: {
          ticks: { color: c.text, callback: (v) => fmt(v) },
          grid: { color: c.grid },
        },
      },
    },
  });
}

// ---------- Top 10 Services Bar Chart ----------
async function renderServicesChart() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");

  // Aggregate daily data for the current month
  const dayCount = now.getDate();
  const allServices = {};
  for (let d = 1; d <= dayCount; d++) {
    const day = `${year}-${month}-${String(d).padStart(2, "0")}`;
    try {
      const dayData = await fetchServices("DAILY", day);
      const items = Array.isArray(dayData) ? dayData : dayData.services ?? [];
      for (const svc of items) {
        if (!allServices[svc.service_name]) {
          allServices[svc.service_name] = { amount_usd: 0, amount_brl: 0 };
        }
        allServices[svc.service_name].amount_usd += Number(svc.amount_usd ?? 0);
        allServices[svc.service_name].amount_brl += Number(svc.amount_brl ?? 0);
      }
    } catch (_) { /* skip missing days */ }
  }

  let data = Object.entries(allServices)
    .map(([name, v]) => ({ service_name: name, amount_usd: v.amount_usd, amount_brl: v.amount_brl }))
    .sort((a, b) => b[amountKey()] - a[amountKey()]);

  const items = (Array.isArray(data) ? data : data.services ?? []).slice(0, 10);
  const labels = items.map((d) => d.service_name);
  const values = items.map((d) => Number(d[amountKey()] ?? 0));
  const total = values.reduce((a, b) => a + b, 0);
  const c = chartColors();
  const ctx = document.getElementById("servicesChart");

  // Gradient fill per bar
  const barColors = values.map((_, i) => {
    const ratio = i / Math.max(values.length - 1, 1);
    // Interpolate blue → green
    return ratio < 0.5 ? c.blue : c.green;
  });

  if (servicesChart) {
    servicesChart.data.labels = labels;
    servicesChart.data.datasets[0].data = values;
    servicesChart.data.datasets[0].backgroundColor = barColors;
    servicesChart.update("active");
    return;
  }

  servicesChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: barColors,
        hoverBackgroundColor: c.green,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (tip) => {
              const pct = total > 0 ? ((tip.raw / total) * 100).toFixed(1) : 0;
              return `${fmt(tip.raw)} (${pct}%)`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: c.text, callback: (v) => fmt(v) }, grid: { color: c.grid } },
        y: { ticks: { color: c.text }, grid: { display: false } },
      },
    },
  });
}

// ---------- Account Donut Chart ----------
function renderAccountDonut(serviceData) {
  const items = (Array.isArray(serviceData) ? serviceData : serviceData?.services ?? []).slice(0, 8);
  if (!items.length) return;

  const labels = items.map((d) => d.service_name ?? d.account_id ?? "Other");
  const values = items.map((d) => Number(d[amountKey()] ?? 0));
  const total = values.reduce((a, b) => a + b, 0);
  const c = chartColors();
  const palette = [c.blue, c.green, c.amber, c.coral, "#8B5CF6", "#06B6D4", "#F472B6", "#A3E635"];
  const ctx = document.getElementById("accountDonut");

  if (accountDonutChart) {
    accountDonutChart.data.labels = labels;
    accountDonutChart.data.datasets[0].data = values;
    accountDonutChart.update("active");
    return;
  }

  accountDonutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "65%",
      animation: { duration: 600 },
      plugins: {
        legend: { position: "bottom", labels: { color: c.text, boxWidth: 12, padding: 10 } },
        tooltip: {
          callbacks: {
            label: (tip) => {
              const pct = total > 0 ? ((tip.raw / total) * 100).toFixed(1) : 0;
              return `${fmt(tip.raw)} (${pct}%)`;
            },
          },
        },
      },
    },
    plugins: [{
      id: "centerLabel",
      afterDraw(chart) {
        const { ctx: c2, width, height } = chart;
        c2.save();
        c2.font = `700 1.1rem 'Space Mono', monospace`;
        c2.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text-primary").trim();
        c2.textAlign = "center";
        c2.textBaseline = "middle";
        c2.fillText(fmt(total), width / 2, height / 2 - 6);
        c2.font = `500 0.65rem 'DM Sans', sans-serif`;
        c2.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text-secondary").trim();
        c2.fillText("Total", width / 2, height / 2 + 14);
        c2.restore();
      },
    }],
  });
}

// ---------- Service Heatmap ----------
async function renderHeatmap() {
  const grid = document.getElementById("heatmapGrid");
  if (!grid) return;
  grid.innerHTML = "";

  // Fetch last 8 daily periods for the heatmap
  const periods = [];
  const now = new Date();
  for (let i = 7; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i - 1);
    periods.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
  }

  // Fetch service data for each period
  const periodData = {};
  const serviceSet = new Set();
  for (const p of periods) {
    try {
      const res = await fetchServices("DAILY", p);
      const items = Array.isArray(res) ? res : res.services ?? [];
      periodData[p] = items;
      items.forEach((s) => serviceSet.add(s.service_name));
    } catch {
      periodData[p] = [];
    }
  }

  // Pick top 10 services by total spend across all periods
  const serviceTotals = {};
  Object.values(periodData).flat().forEach((s) => {
    serviceTotals[s.service_name] = (serviceTotals[s.service_name] || 0) + Number(s[amountKey()] ?? 0);
  });
  const topServices = Object.entries(serviceTotals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name]) => name);

  if (!topServices.length) return;

  // Collect all values for min/max
  const allVals = [];
  topServices.forEach((svc) => {
    periods.forEach((p) => {
      const item = (periodData[p] || []).find((s) => s.service_name === svc);
      allVals.push(Number(item?.[amountKey()] ?? 0));
    });
  });
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const range = maxVal - minVal || 1;

  function intensityClass(val) {
    const ratio = (val - minVal) / range;
    if (ratio < 0.33) return "heatmap-cell--low";
    if (ratio < 0.66) return "heatmap-cell--medium";
    return "heatmap-cell--high";
  }

  // Header row: empty corner + period labels
  const corner = document.createElement("div");
  corner.className = "heatmap-cell heatmap-cell--header";
  grid.appendChild(corner);
  periods.forEach((p) => {
    const cell = document.createElement("div");
    cell.className = "heatmap-cell heatmap-cell--header";
    cell.textContent = p;
    grid.appendChild(cell);
  });

  // Data rows
  topServices.forEach((svc) => {
    const label = document.createElement("div");
    label.className = "heatmap-cell heatmap-cell--label";
    label.textContent = svc;
    label.title = svc;
    grid.appendChild(label);

    periods.forEach((p) => {
      const item = (periodData[p] || []).find((s) => s.service_name === svc);
      const val = Number(item?.[amountKey()] ?? 0);
      const cell = document.createElement("div");
      cell.className = `heatmap-cell ${intensityClass(val)}`;
      cell.textContent = val > 0 ? fmt(val) : "—";
      cell.title = `${svc} · ${p}: ${fmt(val)}`;
      cell.setAttribute("role", "gridcell");
      grid.appendChild(cell);
    });
  });
}

// ---------- Budget Tracker ----------
function renderBudgets(budgets) {
  const list = document.getElementById("budgetList");
  if (!list) return;
  list.innerHTML = "";

  if (!Array.isArray(budgets) || !budgets.length) {
    list.innerHTML = '<p style="color:var(--text-muted);font-size:0.8125rem;">No budgets configured.</p>';
    return;
  }

  budgets.forEach((b) => {
    const budgetAmt = Number(currentCurrency === "USD" ? b.budget_usd : b.budget_brl) || 1;
    const spent = Number(currentCurrency === "USD" ? b.spent_usd : b.spent_brl) || 0;
    const pct = (spent / budgetAmt) * 100;
    const clampedPct = Math.min(pct, 100);

    let barClass = "budget-row__bar-fill--green";
    if (pct >= 90) barClass = "budget-row__bar-fill--coral";
    else if (pct >= 70) barClass = "budget-row__bar-fill--amber";

    const row = document.createElement("div");
    row.className = "budget-row";

    const label = b.team ?? b.account_id ?? "Unknown";
    row.innerHTML = `
      <span class="budget-row__label" title="${label}">${label}</span>
      <div class="budget-row__bar-track">
        <div class="budget-row__bar-fill ${barClass}" style="width:0%"></div>
      </div>
      <div class="budget-row__values">
        <span>${fmt(spent)} / ${fmt(budgetAmt)}</span>
        ${pct > 100 ? '<span class="budget-row__badge">Over Budget</span>' : ""}
      </div>
    `;
    list.appendChild(row);

    // Animate bar width
    requestAnimationFrame(() => {
      row.querySelector(".budget-row__bar-fill").style.width = `${clampedPct}%`;
    });
  });
}

// ---------- Team Cost Table ----------
function renderTeamTable(teams, filter = "") {
  const tbody = document.getElementById("teamTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  teamData = Array.isArray(teams) ? teams : [];
  const lowerFilter = filter.toLowerCase();
  const filtered = teamData.filter((t) =>
    (t.team ?? "").toLowerCase().includes(lowerFilter)
  );

  // Sort
  if (teamSortCol) {
    const keyMap = { team: "team", daily: "daily_avg", weekly: "weekly_total", monthly: "monthly_total", pct: "pct_of_total" };
    const key = keyMap[teamSortCol] ?? teamSortCol;
    filtered.sort((a, b) => {
      const av = key === "team" ? (a[key] ?? "") : Number(a[key] ?? 0);
      const bv = key === "team" ? (b[key] ?? "") : Number(b[key] ?? 0);
      if (av < bv) return teamSortAsc ? -1 : 1;
      if (av > bv) return teamSortAsc ? 1 : -1;
      return 0;
    });
  }

  const total = filtered.reduce((s, t) => s + Number(t.monthly_total ?? 0), 0);

  filtered.forEach((t) => {
    const tr = document.createElement("tr");
    const pct = total > 0 ? ((Number(t.monthly_total ?? 0) / total) * 100).toFixed(1) : "0.0";

    // Mini sparkline SVG for trend column
    const trendVals = t.trend ?? [];
    let sparkSvg = "";
    if (trendVals.length >= 2) {
      const nums = trendVals.map(Number);
      const mn = Math.min(...nums), mx = Math.max(...nums), rng = mx - mn || 1;
      const pts = nums.map((v, i) => {
        const x = 2 + (i / (nums.length - 1)) * 56;
        const y = 22 - ((v - mn) / rng) * 20;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      sparkSvg = `<svg width="60" height="24" viewBox="0 0 60 24" style="color:var(--accent-green)"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
    }

    tr.innerHTML = `
      <td>${t.team ?? "—"}</td>
      <td>${fmt(t.daily_avg ?? 0)}</td>
      <td>${fmt(t.weekly_total ?? 0)}</td>
      <td>${fmt(t.monthly_total ?? 0)}</td>
      <td>${pct}%</td>
      <td>${sparkSvg}</td>
    `;
    tbody.appendChild(tr);
  });
}

// Table sorting
document.querySelectorAll(".team-table__th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const col = th.dataset.sort;
    if (teamSortCol === col) {
      teamSortAsc = !teamSortAsc;
    } else {
      teamSortCol = col;
      teamSortAsc = true;
    }
    // Update aria-sort
    document.querySelectorAll(".team-table__th[data-sort]").forEach((h) => h.setAttribute("aria-sort", "none"));
    th.setAttribute("aria-sort", teamSortAsc ? "ascending" : "descending");
    renderTeamTable(teamData, document.getElementById("teamSearch")?.value ?? "");
  });
});

// Table search
document.getElementById("teamSearch")?.addEventListener("input", (e) => {
  renderTeamTable(teamData, e.target.value);
});

// ---------- Currency Toggle ----------
document.querySelectorAll(".currency-toggle__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const newCurrency = btn.dataset.currency;
    if (newCurrency === currentCurrency) return;
    currentCurrency = newCurrency;

    // Update toggle UI
    document.querySelectorAll(".currency-toggle__btn").forEach((b) => {
      b.classList.toggle("currency-toggle__btn--active", b.dataset.currency === currentCurrency);
      b.setAttribute("aria-checked", b.dataset.currency === currentCurrency ? "true" : "false");
    });

    // Re-animate KPI values
    ["Today", "Mtd", "Prev", "Forecast"].forEach((id) => {
      const el = document.getElementById(`kpi${id}`);
      if (el) {
        const target = Number(currentCurrency === "USD" ? el.dataset.usd : el.dataset.brl) || 0;
        animateValue(el, target);
      }
    });

    // Refresh charts with new currency
    renderTrendChart(trendGranularity);
    renderServicesChart();
    renderHeatmap();
  });
});

// ---------- Trend Tab Switching ----------
document.querySelectorAll(".trend-tabs__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    trendGranularity = btn.dataset.granularity;
    document.querySelectorAll(".trend-tabs__btn").forEach((b) => {
      b.classList.toggle("trend-tabs__btn--active", b === btn);
      b.setAttribute("aria-selected", b === btn ? "true" : "false");
    });
    renderTrendChart(trendGranularity);
  });
});

// ---------- Init ----------
async function init() {
  const synced = document.getElementById("lastSynced");

  try {
    // Fetch summary + forecast in parallel
    const [summary, forecast] = await Promise.all([
      fetchSummary().catch((e) => { showError(`Summary: ${e.message}`); return null; }),
      fetchForecast().catch((e) => { showError(`Forecast: ${e.message}`); return null; }),
    ]);

    // Merge forecast into summary data
    const merged = { ...(summary ?? {}), ...(forecast ?? {}) };
    renderKPI(merged);

    // Update last synced
    if (synced) synced.textContent = `Last synced: ${new Date().toLocaleTimeString()}`;

    // Render charts
    await renderTrendChart(trendGranularity);
    await renderServicesChart();

    // Use yesterday's daily data for donut (account breakdown)
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yPeriod = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
    try {
      const svcData = await fetchServices("DAILY", yPeriod);
      renderAccountDonut(svcData);
    } catch (e) {
      showError(`Donut: ${e.message}`);
    }

    // Heatmap
    await renderHeatmap();

    // Budget tracker (from summary if available)
    if (merged.budgets) renderBudgets(merged.budgets);

    // Team table (from summary if available)
    if (merged.teams) renderTeamTable(merged.teams);

  } catch (e) {
    showError(`Init failed: ${e.message}`);
  }
}

// Start when DOM is ready
document.addEventListener("DOMContentLoaded", init);

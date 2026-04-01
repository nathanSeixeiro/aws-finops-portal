/* ============================================================
   CostWatch — Application Logic
   Single /dashboard call loads all pre-computed data.
   ============================================================ */

// ---------- CONFIG ----------
const CONFIG = {
  apiBase: "https://xc2kc55o9g.execute-api.us-east-1.amazonaws.com/prod",
  apiKey: "8V9asI6yRD6oFPIx0vJWca6b2F3wOyoXf1hJSL3g",
};

// ---------- State ----------
let currentCurrency = "USD";
let dashboardData = null;
let trendGranularity = "DAILY";
let trendChart = null;
let servicesChart = null;
let accountDonutChart = null;

// ---------- Account Name Mapping ----------
const ACCOUNT_NAMES = {
  "019361054970": "Backup",
  "243197391534": "Moodle EAD SESI-SP",
  "282489000805": "Homologation",
  "365998109386": "Management",
  "499075731692": "SESISENAI-SP GSTI",
  "566105750844": "Development",
  "592197479665": "Network",
  "682120331793": "Innovation Hub",
  "869697964666": "Security",
  "941297671692": "Log",
  "967883358132": "Production",
  "default": "Consolidated",
};
function accountName(id) { return ACCOUNT_NAMES[id] || id; }

// ---------- Helpers ----------
function currencySymbol() { return currentCurrency === "USD" ? "$" : "R$"; }
function amountKey() { return currentCurrency === "USD" ? "amount_usd" : "amount_brl"; }
function totalKey() { return currentCurrency === "USD" ? "total_usd" : "total_brl"; }
function fmt(value) {
  const n = Number(value) || 0;
  return `${currencySymbol()}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function pctFmt(value) {
  const n = Number(value) || 0;
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

// ---------- API Layer ----------
async function fetchDashboard() {
  const url = `${CONFIG.apiBase}/dashboard`;
  const res = await fetch(url, { headers: { "x-api-key": CONFIG.apiKey } });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
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

// ---------- Animated Counter ----------
function animateValue(el, target, duration = 1200) {
  const start = performance.now();
  function easeOutExpo(t) { return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
  function tick(now) {
    const elapsed = Math.min((now - start) / duration, 1);
    el.textContent = fmt(target * easeOutExpo(elapsed));
    if (elapsed < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ---------- KPI Cards ----------
function renderKPI(summary) {
  if (!summary) return;
  const cards = [
    { id: "Today", key: "today" },
    { id: "Mtd", key: "mtd" },
    { id: "Prev", key: "prev_month" },
    { id: "Forecast", key: "forecast" },
  ];
  cards.forEach(({ id, key }) => {
    const valEl = document.getElementById(`kpi${id}`);
    const deltaEl = document.getElementById(`delta${id}`);
    if (!valEl) return;
    const usdVal = Number(summary[`${key}_usd`] ?? 0);
    const brlVal = Number(summary[`${key}_brl`] ?? 0);
    const target = currentCurrency === "USD" ? usdVal : brlVal;
    valEl.dataset.usd = usdVal;
    valEl.dataset.brl = brlVal;
    animateValue(valEl, target);
    if (deltaEl) { deltaEl.textContent = "—"; deltaEl.className = "kpi-card__delta"; }
  });
}

// ---------- Chart Colors ----------
function chartColors() {
  const s = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  return {
    line: s("--accent-green"), grid: s("--border"), text: s("--text-muted"),
    blue: s("--accent-blue"), green: s("--accent-green"),
    coral: s("--accent-coral"), amber: s("--accent-amber"),
  };
}

// ---------- Aggregate daily data into ISO weeks ----------
function aggregateToWeeks(dailyItems) {
  const weeks = {};
  for (const d of dailyItems) {
    const dt = new Date(d.period + "T00:00:00");
    // ISO week: get the Monday of this week
    const day = dt.getDay();
    const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(dt);
    monday.setDate(diff);
    const weekKey = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, "0")}-${String(monday.getDate()).padStart(2, "0")}`;
    if (!weeks[weekKey]) weeks[weekKey] = { total_usd: 0, total_brl: 0 };
    weeks[weekKey].total_usd += Number(d.total_usd || 0);
    weeks[weekKey].total_brl += Number(d.total_brl || 0);
  }
  return Object.entries(weeks)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([period, totals]) => ({ period: `W ${period}`, total_usd: totals.total_usd, total_brl: totals.total_brl }));
}

// ---------- Trend Line Chart ----------
function renderTrendChart(granularity) {
  let items;
  if (granularity === "DAILY") {
    // Exclude today (incomplete data makes graph look like it's dropping)
    const today = new Date().toISOString().slice(0, 10);
    items = (dashboardData?.daily_trend || []).filter(d => d.period !== today);
  } else if (granularity === "WEEKLY") {
    const today = new Date().toISOString().slice(0, 10);
    items = aggregateToWeeks((dashboardData?.daily_trend || []).filter(d => d.period !== today));
  } else {
    // Exclude current month (incomplete data)
    const curMonth = new Date().toISOString().slice(0, 7);
    items = (dashboardData?.monthly_trend || []).filter(d => d.period !== curMonth);
  }
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
    data: { labels, datasets: [{ data: values, borderColor: c.line, backgroundColor: `${c.line}18`, fill: true, tension: 0.35, pointRadius: 2, pointHoverRadius: 5, borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (tip) => fmt(tip.raw) } } },
      scales: {
        x: { ticks: { color: c.text, maxRotation: 45 }, grid: { color: c.grid } },
        y: { ticks: { color: c.text, callback: (v) => fmt(v) }, grid: { color: c.grid } },
      },
    },
  });
}

// ---------- Top 10 Services Bar Chart ----------
function renderServicesChart() {
  const items = (dashboardData?.services || []).slice(0, 10);
  if (!items.length) return;
  const labels = items.map((d) => d.service_name);
  const values = items.map((d) => Number(d[amountKey()] ?? 0));
  const total = values.reduce((a, b) => a + b, 0);
  const c = chartColors();
  const ctx = document.getElementById("servicesChart");
  const barColors = values.map((_, i) => i / Math.max(values.length - 1, 1) < 0.5 ? c.blue : c.green);
  if (servicesChart) {
    servicesChart.data.labels = labels;
    servicesChart.data.datasets[0].data = values;
    servicesChart.data.datasets[0].backgroundColor = barColors;
    servicesChart.update("active");
    return;
  }
  servicesChart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: barColors, hoverBackgroundColor: c.green, borderRadius: 4, borderSkipped: false }] },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (tip) => { const pct = total > 0 ? ((tip.raw / total) * 100).toFixed(1) : 0; return `${fmt(tip.raw)} (${pct}%)`; } } } },
      scales: {
        x: { ticks: { color: c.text, callback: (v) => fmt(v) }, grid: { color: c.grid } },
        y: { ticks: { color: c.text }, grid: { display: false } },
      },
    },
  });
}

// ---------- Account Donut Chart ----------
function renderAccountDonut() {
  const data = (dashboardData?.accounts || []).slice(0, 8);
  if (!data.length) return;
  const labels = data.map((d) => accountName(d.account_id));
  const values = data.map((d) => Number(d[amountKey()] ?? 0));
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
    data: { labels, datasets: [{ data: values, backgroundColor: palette.slice(0, labels.length), borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "65%", animation: { duration: 600 },
      plugins: {
        legend: { position: "bottom", labels: { color: c.text, boxWidth: 12, padding: 10 } },
        tooltip: { callbacks: { label: (tip) => { const pct = total > 0 ? ((tip.raw / total) * 100).toFixed(1) : 0; return `${fmt(tip.raw)} (${pct}%)`; } } },
      },
    },
    plugins: [{
      id: "centerLabel",
      afterDraw(chart) {
        const { ctx: c2, width, height } = chart;
        c2.save();
        c2.font = `700 1.1rem 'Space Mono', monospace`;
        c2.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text-primary").trim();
        c2.textAlign = "center"; c2.textBaseline = "middle";
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
function renderHeatmap() {
  const grid = document.getElementById("heatmapGrid");
  if (!grid) return;
  grid.innerHTML = "";
  const heatmap = dashboardData?.heatmap || {};
  const periods = Object.keys(heatmap).sort();
  if (!periods.length) return;

  const periodData = {};
  for (const p of periods) {
    periodData[p] = Array.isArray(heatmap[p]) ? heatmap[p] : [];
  }
  const serviceTotals = {};
  Object.values(periodData).flat().forEach((s) => {
    serviceTotals[s.service_name] = (serviceTotals[s.service_name] || 0) + Number(s[amountKey()] ?? 0);
  });
  const topServices = Object.entries(serviceTotals).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([name]) => name);
  if (!topServices.length) return;
  const allVals = [];
  topServices.forEach((svc) => periods.forEach((p) => {
    const item = (periodData[p] || []).find((s) => s.service_name === svc);
    allVals.push(Number(item?.[amountKey()] ?? 0));
  }));
  const minVal = Math.min(...allVals), maxVal = Math.max(...allVals), range = maxVal - minVal || 1;
  function intensityClass(val) {
    const ratio = (val - minVal) / range;
    if (ratio < 0.33) return "heatmap-cell--low";
    if (ratio < 0.66) return "heatmap-cell--medium";
    return "heatmap-cell--high";
  }
  const corner = document.createElement("div");
  corner.className = "heatmap-cell heatmap-cell--header";
  grid.appendChild(corner);
  periods.forEach((p) => {
    const cell = document.createElement("div");
    cell.className = "heatmap-cell heatmap-cell--header";
    cell.textContent = p.slice(5);
    grid.appendChild(cell);
  });
  topServices.forEach((svc) => {
    const label = document.createElement("div");
    label.className = "heatmap-cell heatmap-cell--label";
    label.textContent = svc; label.title = svc;
    grid.appendChild(label);
    periods.forEach((p) => {
      const item = (periodData[p] || []).find((s) => s.service_name === svc);
      const val = Number(item?.[amountKey()] ?? 0);
      const cell = document.createElement("div");
      cell.className = `heatmap-cell ${intensityClass(val)}`;
      cell.textContent = val > 0 ? fmt(val) : "—";
      cell.title = `${svc} · ${p}: ${fmt(val)}`;
      grid.appendChild(cell);
    });
  });
}

// ---------- Account Cost Table ----------
function renderAccountTable() {
  const tbody = document.getElementById("accountTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  const items = dashboardData?.accounts || [];
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;padding:24px;">No account data available</td></tr>';
    return;
  }
  items.forEach((a) => {
    const tr = document.createElement("tr");
    const val = Number(a[amountKey()] ?? 0);
    const pct = Number(a.percentage_of_total ?? 0);
    tr.innerHTML = `
      <td style="font-weight:500">${accountName(a.account_id)}</td>
      <td style="color:var(--text-muted);font-size:0.75rem">${a.account_id}</td>
      <td style="font-family:'Space Mono',monospace">${fmt(val)}</td>
      <td>${pct.toFixed(1)}%</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------- Currency Toggle ----------
document.querySelectorAll(".currency-toggle__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const newCurrency = btn.dataset.currency;
    if (newCurrency === currentCurrency) return;
    currentCurrency = newCurrency;
    document.querySelectorAll(".currency-toggle__btn").forEach((b) => {
      b.classList.toggle("currency-toggle__btn--active", b.dataset.currency === currentCurrency);
    });
    renderAll();
  });
});

// ---------- Trend Tab Switching ----------
document.querySelectorAll(".trend-tabs__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    trendGranularity = btn.dataset.granularity;
    document.querySelectorAll(".trend-tabs__btn").forEach((b) => {
      b.classList.toggle("trend-tabs__btn--active", b === btn);
    });
    renderTrendChart(trendGranularity);
  });
});

// ---------- Month name helper ----------
function prevMonthLabel() {
  const pm = dashboardData?.prev_month;
  if (!pm) return "";
  const [y, m] = pm.split("-");
  const name = new Date(Number(y), Number(m) - 1).toLocaleString("en-US", { month: "long" });
  return `${name} ${y}`;
}

// ---------- Render All (from cached data) ----------
function renderAll() {
  if (!dashboardData) return;
  renderKPI(dashboardData.summary);
  renderTrendChart(trendGranularity);
  renderServicesChart();
  renderAccountDonut();
  renderAccountTable();
  renderHeatmap();

  // Update section titles with previous month name
  const label = prevMonthLabel();
  if (label) {
    document.querySelectorAll(".panel__title").forEach(el => {
      if (el.textContent.startsWith("Top 10 Services")) el.textContent = `Top 10 Services (${label})`;
      if (el.textContent.startsWith("Account Breakdown")) el.textContent = `Account Breakdown (${label})`;
      if (el.textContent.startsWith("Service Heatmap")) el.textContent = `Service Heatmap (${label})`;
      if (el.textContent.startsWith("Cost per Account")) el.textContent = `Cost per Account (${label})`;
    });
  }

  // Render Kubecost panels from cached data
  renderAllKubecost();
}

// ---------- Init ----------
async function init() {
  const synced = document.getElementById("lastSynced");
  try {
    // Fetch AWS and Kubecost data in parallel
    const [awsResult] = await Promise.allSettled([
      fetchDashboard(),
      initKubecost(),
    ]);
    if (awsResult.status === "fulfilled") {
      dashboardData = awsResult.value;
      renderAll();
      if (synced) synced.textContent = `Last synced: ${new Date().toLocaleTimeString()}`;
    } else {
      throw awsResult.reason;
    }
  } catch (e) {
    showError(`Failed to load dashboard: ${e.message}`);
  }
}

// ============================================================
// Kubecost Integration — API Client & Data Layer
// ============================================================

// ---------- Kubecost Config ----------
const KUBECOST_CONFIG = {
  baseUrl: "https://kubecost-eks-prd.sesisenaisp.org.br",
};

// ---------- Kubecost State ----------
let kubecostData = null;
let kubecostWindow = "7d";
let kubecostAvailable = true;
let clusterBreakdownChart = null;
let namespaceChart = null;

// ---------- Kubecost Helpers ----------
const KUBECOST_BRL_RATE = 5.05;

function k8sConvert(usdValue) {
  const n = Number(usdValue) || 0;
  return currentCurrency === "BRL" ? n * KUBECOST_BRL_RATE : n;
}

function fmtK8s(value) {
  const converted = k8sConvert(value);
  return `${currencySymbol()}${converted.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ---------- Kubecost Fetch ----------
async function fetchKubecostEndpoint(path, params = {}) {
  const url = new URL(path, KUBECOST_CONFIG.baseUrl);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(url.toString(), { signal: controller.signal });
    if (!res.ok) throw new Error(`Kubecost ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Kubecost fetch failed [${path}]:`, err);
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchClusterCosts(window = "7d") {
  // Use allocation?aggregate=cluster since /model/clusterCosts is not available
  return fetchKubecostEndpoint("/model/allocation", { window, aggregate: "cluster" });
}

async function fetchAllocation(window = "7d", aggregate = "namespace") {
  return fetchKubecostEndpoint("/model/allocation", { window, aggregate });
}

async function fetchAssets(window = "7d") {
  return fetchKubecostEndpoint("/model/assets", { window });
}

async function fetchSavings() {
  return fetchKubecostEndpoint("/model/savings");
}

// ---------- Kubecost Data Normalization ----------
function normalizeClusterCosts(raw) {
  if (!raw || !raw.data) return {};
  const items = Array.isArray(raw.data) ? raw.data : [raw.data];
  const clusters = {};
  for (const bucket of items) {
    if (!bucket) continue;
    for (const [name, info] of Object.entries(bucket)) {
      if (name === "__idle__") continue;
      if (!clusters[name]) {
        clusters[name] = { totalCost: 0, cpuCost: 0, memoryCost: 0, storageCost: 0, networkCost: 0, cpuEfficiency: 0, memoryEfficiency: 0, efficiency: 0, _count: 0 };
      }
      const c = clusters[name];
      c.totalCost += Number(info.totalCost ?? 0);
      c.cpuCost += Number(info.cpuCost ?? 0);
      c.memoryCost += Number(info.ramCost ?? info.memoryCost ?? 0);
      c.storageCost += Number(info.pvCost ?? info.storageCost ?? 0);
      c.networkCost += Number(info.networkCost ?? 0);
      c.cpuEfficiency += Number(info.cpuEfficiency ?? 0);
      c.memoryEfficiency += Number(info.ramEfficiency ?? info.memoryEfficiency ?? 0);
      c.efficiency += Number(info.totalEfficiency ?? info.efficiency ?? 0);
      c._count += 1;
    }
  }
  // Average the efficiency values across daily buckets
  for (const c of Object.values(clusters)) {
    if (c._count > 0) {
      c.cpuEfficiency /= c._count;
      c.memoryEfficiency /= c._count;
      c.efficiency /= c._count;
    }
    delete c._count;
  }
  return clusters;
}

function normalizeAllocation(raw) {
  if (!raw || !raw.data || !Array.isArray(raw.data)) return [];
  const nsMap = {};
  for (const bucket of raw.data) {
    if (!bucket) continue;
    for (const [name, info] of Object.entries(bucket)) {
      if (name === "__idle__") continue;
      if (!nsMap[name]) {
        nsMap[name] = {
          name: info.name || name,
          cluster: info.properties?.cluster || "",
          cpuCost: 0, memoryCost: 0, storageCost: 0, networkCost: 0, totalCost: 0,
          networkCrossZoneCost: 0, networkInternetCost: 0, networkRegionCost: 0,
        };
      }
      const ns = nsMap[name];
      ns.cpuCost += Number(info.cpuCost ?? 0);
      ns.memoryCost += Number(info.ramCost ?? info.memoryCost ?? 0);
      ns.storageCost += Number(info.pvCost ?? info.storageCost ?? 0);
      ns.networkCost += Number(info.networkCost ?? 0);
      ns.totalCost += Number(info.totalCost ?? 0);
      ns.networkCrossZoneCost += Number(info.networkCrossZoneCost ?? 0);
      ns.networkInternetCost += Number(info.networkInternetCost ?? 0);
      ns.networkRegionCost += Number(info.networkCrossRegionCost ?? info.networkRegionCost ?? 0);
    }
  }
  return Object.values(nsMap).sort((a, b) => b.totalCost - a.totalCost);
}

function normalizeSavings(raw) {
  if (!raw || !raw.data) return { totalMonthlySavings: 0, recommendations: [] };
  const data = raw.data;

  // Savings API returns category objects with savingsPerMonth, not a recommendations array
  const categoryLabels = {
    abandonedWorkloads: "Abandoned workloads",
    nodeGroupSizing: "Node group right-sizing",
    orphanedResources: "Orphaned resources",
    underutilizedLocalDisks: "Underutilized local disks",
    persistentVolumeSizing: "Persistent volume right-sizing",
    unclaimedVolumes: "Unclaimed volumes",
    containerRequestSizing: "Container request right-sizing",
  };

  const recs = [];
  let totalMonthlySavings = 0;

  for (const [key, label] of Object.entries(categoryLabels)) {
    const cat = data[key];
    if (cat && typeof cat.savingsPerMonth === "number") {
      totalMonthlySavings += cat.savingsPerMonth;
      if (cat.savingsPerMonth > 0) {
        recs.push({ type: key, description: label, monthlySavings: cat.savingsPerMonth });
      }
    }
  }

  recs.sort((a, b) => b.monthlySavings - a.monthlySavings);
  return { totalMonthlySavings, recommendations: recs };
}

function computeTotals(clusterCosts) {
  const entries = Object.values(clusterCosts);
  if (!entries.length) return { totalK8sCost: 0, overallEfficiency: 0 };
  const totalK8sCost = entries.reduce((sum, c) => sum + c.totalCost, 0);
  const overallEfficiency = totalK8sCost > 0
    ? entries.reduce((sum, c) => sum + c.efficiency * c.totalCost, 0) / totalK8sCost
    : 0;
  return { totalK8sCost, overallEfficiency };
}

function computeNetworkTotals(allocation) {
  return allocation.reduce(
    (acc, ns) => ({
      crossZone: acc.crossZone + ns.networkCrossZoneCost,
      internet: acc.internet + ns.networkInternetCost,
      region: acc.region + ns.networkRegionCost,
    }),
    { crossZone: 0, internet: 0, region: 0 }
  );
}

// ============================================================
// Kubecost — Loading, Error & KPI Rendering
// ============================================================

const K8S_PANEL_IDS = [
  "k8sKpiGrid",
  "k8sChartsRow",
  "k8sNetworkPanel",
];

// ---------- Loading State ----------
function showKubecostLoading() {
  K8S_PANEL_IDS.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.add("k8s-loading");
  });
}

function hideKubecostLoading() {
  K8S_PANEL_IDS.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.remove("k8s-loading");
  });
}

// ---------- Unavailable State ----------
function showKubecostUnavailable() {
  hideKubecostLoading();
  K8S_PANEL_IDS.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });
  const section = document.getElementById("k8sSection");
  if (!section) return;
  let msg = section.querySelector(".k8s-unavailable");
  if (!msg) {
    msg = document.createElement("div");
    msg.className = "k8s-unavailable";
    msg.setAttribute("role", "status");
    msg.textContent = "Kubecost data unavailable \u2014 connect to internal network";
    section.appendChild(msg);
  }
  msg.style.display = "";
}

function hideKubecostUnavailable() {
  const section = document.getElementById("k8sSection");
  if (!section) return;
  const msg = section.querySelector(".k8s-unavailable");
  if (msg) msg.style.display = "none";
  K8S_PANEL_IDS.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = "";
  });
}

// ---------- Per-Panel Error ----------
function showPanelUnavailable(panelEl) {
  if (!panelEl) return;
  let msg = panelEl.querySelector(".k8s-panel-error");
  if (!msg) {
    msg = document.createElement("div");
    msg.className = "k8s-panel-error";
    msg.setAttribute("role", "status");
    msg.style.cssText = "color:var(--text-muted);text-align:center;padding:24px;font-size:0.875rem;";
    msg.textContent = "Data unavailable";
    panelEl.appendChild(msg);
  }
  msg.style.display = "";
}

function hidePanelUnavailable(panelEl) {
  if (!panelEl) return;
  const msg = panelEl.querySelector(".k8s-panel-error");
  if (msg) msg.style.display = "none";
}

// ---------- K8s KPI Cards ----------
function animateK8sValue(el, target, duration = 1200) {
  const converted = k8sConvert(target);
  const start = performance.now();
  function easeOutExpo(t) { return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
  function tick(now) {
    const elapsed = Math.min((now - start) / duration, 1);
    const current = converted * easeOutExpo(elapsed);
    el.textContent = `${currencySymbol()}${current.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (elapsed < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function renderK8sKPIs(clusterCosts) {
  const totals = computeTotals(clusterCosts || {});

  const costEl = document.getElementById("kpiK8sCost");

  if (costEl) animateK8sValue(costEl, totals.totalK8sCost);
}

// ---------- Cluster Breakdown Chart ----------
function renderClusterBreakdownChart(clusterCosts) {
  if (!clusterCosts || !Object.keys(clusterCosts).length) {
    showPanelUnavailable(document.getElementById("clusterBreakdownChart")?.closest(".panel"));
    return;
  }
  const sorted = Object.entries(clusterCosts).sort((a, b) => b[1].totalCost - a[1].totalCost);
  const labels = sorted.map(([name]) => name);
  const values = sorted.map(([, c]) => c.totalCost);
  const total = values.reduce((a, b) => a + b, 0);
  const c = chartColors();
  const palette = [c.blue, c.green, c.amber];
  const ctx = document.getElementById("clusterBreakdownChart");
  if (!ctx) return;

  if (clusterBreakdownChart) {
    clusterBreakdownChart.data.labels = labels;
    clusterBreakdownChart.data.datasets[0].data = values;
    clusterBreakdownChart.data.datasets[0].backgroundColor = palette.slice(0, labels.length);
    clusterBreakdownChart.update("active");
    return;
  }

  clusterBreakdownChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: palette.slice(0, labels.length),
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
              const pct = total > 0 ? ((tip.raw / total) * 100).toFixed(1) : "0.0";
              return `${fmtK8s(tip.raw)} (${pct}%)`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: c.text, callback: (v) => fmtK8s(v) }, grid: { color: c.grid } },
        y: { ticks: { color: c.text }, grid: { display: false } },
      },
    },
  });
}

// ---------- Namespace Allocation Chart ----------
function renderNamespaceChart(allocation) {
  if (!allocation || !allocation.length) {
    showPanelUnavailable(document.getElementById("namespaceChart")?.closest(".panel"));
    return;
  }
  const top10 = allocation.slice(0, 10);
  const labels = top10.map((ns) => ns.name);
  const values = top10.map((ns) => ns.totalCost);
  const total = allocation.reduce((sum, ns) => sum + ns.totalCost, 0);
  const c = chartColors();
  const barColors = values.map((_, i) => i / Math.max(values.length - 1, 1) < 0.5 ? c.blue : c.green);
  const ctx = document.getElementById("namespaceChart");
  if (!ctx) return;

  if (namespaceChart) {
    namespaceChart.data.labels = labels;
    namespaceChart.data.datasets[0].data = values;
    namespaceChart.data.datasets[0].backgroundColor = barColors;
    namespaceChart.update("active");
    return;
  }

  namespaceChart = new Chart(ctx, {
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
              const ns = top10[tip.dataIndex];
              const pct = total > 0 ? ((ns.totalCost / total) * 100).toFixed(1) : "0.0";
              return [
                `Total: ${fmtK8s(ns.totalCost)} (${pct}%)`,
                `CPU: ${fmtK8s(ns.cpuCost)}`,
                `Memory: ${fmtK8s(ns.memoryCost)}`,
              ];
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: c.text, callback: (v) => fmtK8s(v) }, grid: { color: c.grid } },
        y: { ticks: { color: c.text }, grid: { display: false } },
      },
    },
  });
}

// ---------- Efficiency Panel ----------
function renderEfficiencyPanel(clusterCosts) {
  const panel = document.getElementById("k8sEfficiencyPanel");
  if (!panel) return;
  const content = panel.querySelector(".efficiency-panel-content");
  if (!content) return;

  if (!clusterCosts || !Object.keys(clusterCosts).length) {
    showPanelUnavailable(panel);
    return;
  }
  hidePanelUnavailable(panel);

  const totals = computeTotals(clusterCosts);
  const sorted = Object.entries(clusterCosts).sort((a, b) => b[1].totalCost - a[1].totalCost);

  function gaugeColor(pct) {
    if (pct > 60) return "green";
    if (pct >= 30) return "amber";
    return "coral";
  }

  function gaugeHTML(label, value) {
    const pct = (value * 100).toFixed(1);
    const color = gaugeColor(parseFloat(pct));
    return `
      <div class="efficiency-gauge efficiency-gauge--${color}">
        <div class="efficiency-gauge__label">
          <span>${label}</span>
          <span>${pct}%</span>
        </div>
        <div class="efficiency-gauge__track">
          <div class="efficiency-gauge__fill" style="width:${Math.min(parseFloat(pct), 100)}%"></div>
        </div>
      </div>`;
  }

  let html = `<div class="efficiency-cluster">
    <span class="efficiency-cluster__name" style="font-family:var(--font-heading);font-size:1.25rem;color:var(--accent-green);">Overall: ${(totals.overallEfficiency * 100).toFixed(1)}%</span>
  </div>`;

  for (const [name, c] of sorted) {
    html += `<div class="efficiency-cluster">
      <span class="efficiency-cluster__name">${name}</span>
      ${gaugeHTML("CPU", c.cpuEfficiency)}
      ${gaugeHTML("Memory", c.memoryEfficiency)}
    </div>`;
  }

  content.innerHTML = html;
}

// ---------- Network Costs Panel ----------
function renderNetworkCosts(allocation) {
  const panel = document.getElementById("k8sNetworkPanel");
  if (!panel) return;
  const list = panel.querySelector(".network-costs-list");
  if (!list) return;

  if (!kubecostData || !kubecostData.networkTotals) {
    showPanelUnavailable(panel);
    return;
  }
  hidePanelUnavailable(panel);

  const nt = kubecostData.networkTotals;
  const items = [
    { label: "Cross-Zone", value: nt.crossZone },
    { label: "Internet Egress", value: nt.internet },
    { label: "Region Egress", value: nt.region },
  ];

  list.innerHTML = items.map((item) => `
    <div class="network-costs-item">
      <span class="network-costs-item__label">${item.label}</span>
      <span class="network-costs-item__value">${fmtK8s(item.value)}</span>
    </div>`).join("");
}

// ---------- Savings Recommendations Panel ----------
function renderSavingsPanel(savings) {
  const panel = document.getElementById("k8sSavingsPanel");
  if (!panel) return;
  const list = panel.querySelector(".savings-list");
  if (!list) return;

  if (!savings || (!savings.totalMonthlySavings && !savings.recommendations.length)) {
    showPanelUnavailable(panel);
    return;
  }
  hidePanelUnavailable(panel);

  const totalHtml = `<div class="savings-item" style="background:var(--bg-card-hover);">
    <span class="savings-item__description" style="font-weight:700;">Total Potential Monthly Savings</span>
    <span class="savings-item__amount" style="font-size:1.1rem;">${fmtK8s(savings.totalMonthlySavings)}</span>
  </div>`;

  const recsHtml = savings.recommendations
    .sort((a, b) => b.monthlySavings - a.monthlySavings)
    .map((r) => `<div class="savings-item">
      <span class="savings-item__description">${r.description}</span>
      <span class="savings-item__amount">${fmtK8s(r.monthlySavings)}/mo</span>
    </div>`).join("");

  list.innerHTML = totalHtml + recsHtml;
}

// ============================================================
// Kubecost — Time Window Selector
// ============================================================

document.querySelectorAll(".k8s-time-tabs__btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const newWindow = btn.dataset.k8sWindow;
    if (newWindow === kubecostWindow) return;
    kubecostWindow = newWindow;
    document.querySelectorAll(".k8s-time-tabs__btn").forEach((b) => {
      const isActive = b === btn;
      b.classList.toggle("k8s-time-tabs__btn--active", isActive);
      b.setAttribute("aria-checked", isActive ? "true" : "false");
    });
    // Set chart animation duration for smooth transitions
    if (clusterBreakdownChart) {
      clusterBreakdownChart.options.animation = { duration: 600 };
    }
    if (namespaceChart) {
      namespaceChart.options.animation = { duration: 600 };
    }
    await initKubecost();
  });
});

// ============================================================
// Kubecost — Init & Render Orchestration
// ============================================================

function renderAllKubecost() {
  if (!kubecostData) {
    showKubecostUnavailable();
    return;
  }
  hideKubecostUnavailable();
  renderK8sKPIs(kubecostData.clusterCosts);
  renderClusterBreakdownChart(kubecostData.clusterCosts);
  renderNamespaceChart(kubecostData.allocation);
  renderNetworkCosts(kubecostData.allocation);
}

async function initKubecost() {
  showKubecostLoading();

  const [clusterRes, allocRes, assetsRes] = await Promise.allSettled([
    fetchClusterCosts(kubecostWindow),
    fetchAllocation(kubecostWindow, "namespace"),
    fetchAssets(kubecostWindow),
  ]);

  const clusterRaw = clusterRes.status === "fulfilled" ? clusterRes.value : null;
  const allocRaw = allocRes.status === "fulfilled" ? allocRes.value : null;

  // If all critical endpoints failed, mark unavailable
  if (!clusterRaw && !allocRaw) {
    kubecostData = null;
    kubecostAvailable = false;
    hideKubecostLoading();
    showKubecostUnavailable();
    return;
  }

  const clusterCosts = normalizeClusterCosts(clusterRaw);
  const allocation = normalizeAllocation(allocRaw);
  const totals = computeTotals(clusterCosts);
  const networkTotals = computeNetworkTotals(allocation);

  kubecostData = {
    clusterCosts,
    allocation,
    totals,
    networkTotals,
    fetchedAt: new Date(),
  };
  kubecostAvailable = true;

  hideKubecostLoading();
  renderAllKubecost();

  const synced = document.getElementById("k8sLastSynced");
  if (synced) synced.textContent = `Last synced: ${kubecostData.fetchedAt.toLocaleTimeString()}`;
}

document.addEventListener("DOMContentLoaded", init);

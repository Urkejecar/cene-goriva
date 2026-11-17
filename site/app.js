import {
  cardStale, chartEnd, dayMs, extensionPoints, formatChange, formatPrice, isStale, priceStates, rangeStart, shortDate,
  shouldRefresh, stepPoints, todayLjubljana,
} from "./logic.js";

const COUNTRY = { SI: "Slovenija", HR: "Hrvaška" };
const FUEL_LABEL = {
  SI: { petrol95: "Bencin 95", diesel: "Dizel" },
  HR: { petrol95: "Eurosuper 95", diesel: "Eurodizel" },
};
const SOURCE = { "gov.si": "gov.si", mzoe: "mzoe-gor.hr", "eu-bulletin": "povprečje EU" };
const WEEKDAY_GENITIVE = ["nedelje", "ponedeljka", "torka", "srede", "četrtka", "petka", "sobote"];
const PREFS_KEY = "cene-goriva-prefs";
const DEFAULTS = { fuel: "petrol95", countries: ["SI", "HR"], range: "1m" };

let data = null;
let chart = null;
let prefs = loadPrefs();

function loadPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    return {
      fuel: ["petrol95", "diesel"].includes(p.fuel) ? p.fuel : DEFAULTS.fuel,
      countries: Array.isArray(p.countries) && p.countries.length ? p.countries.filter((c) => c in COUNTRY) : DEFAULTS.countries,
      range: ["1w", "1m", "1y", "5y"].includes(p.range) ? p.range : DEFAULTS.range,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function savePrefs() {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* private mode */ }
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

function dayName(iso) {
  return WEEKDAY_GENITIVE[new Date(dayMs(iso)).getUTCDay()];
}

// ---------- cards ----------

function renderCard(country, today) {
  const card = document.getElementById(`card-${country}`);
  const states = { petrol95: priceStates(data, country, "petrol95", today), diesel: priceStates(data, country, "diesel", today) };
  card.replaceChildren(el("h2", {}, el("span", { class: `dot ${country.toLowerCase()}` }), COUNTRY[country]));

  if (!states.petrol95.current && !states.diesel.current) {
    card.append(el("p", { class: "empty" }, "Ni podatkov."));
    return;
  }
  for (const fuel of ["petrol95", "diesel"]) {
    const { current, previous } = states[fuel];
    if (!current) continue;
    const price = el("span", {}, el("span", { class: "price" }, formatPrice(current.p)));
    if (previous) price.append(el("span", { class: "change", title: "sprememba od prejšnjega obdobja" }, formatChange(current.p, previous.p)));
    card.append(el("div", { class: "row" }, el("span", { class: "name" }, FUEL_LABEL[country][fuel]), price));
  }

  const cur = states.petrol95.current || states.diesel.current;
  const validText = country === "SI" && cur.s === "gov.si"
    ? `velja od ${shortDate(cur.from)} do ${shortDate(cur.to)}`
    : `velja od ${shortDate(cur.from)}`;
  card.append(el("p", { class: "valid" }, validText));
  if (cardStale(data, country, today)) {
    card.append(el("p", { class: "stale-note" }, "Cena morda ni več aktualna – vir trenutno ni dosegljiv."));
  }

  const up = states.petrol95.upcoming || states.diesel.upcoming;
  if (up) {
    card.append(el("p", { class: "next official" },
      el("strong", {}, `Uradno od ${dayName(up.from)} ${shortDate(up.from)}: `), nextPrices(country, states, "upcoming")));
    return;
  }
  const fc = states.petrol95.forecast || states.diesel.forecast;
  if (fc) {
    const kind = fc.status === "final" ? "končna napoved" : "prva napoved";
    card.append(el("p", { class: "next forecast" },
      `Pričakovano od ${dayName(fc.from)} ${shortDate(fc.from)}: `, nextPrices(country, states, "forecast"),
      ` (${kind}, vir: `, el("a", { href: "https://napovedgoriv.si/", rel: "noopener" }, "napovedgoriv.si"), ")"));
  }
}

function nextPrices(country, states, key) {
  const parts = [];
  for (const fuel of ["petrol95", "diesel"]) {
    const item = states[fuel][key];
    if (item) parts.push(`${FUEL_LABEL[country][fuel].toLowerCase()} ${formatPrice(item.p)}`);
  }
  return parts.join(" · ");
}

// ---------- chart ----------

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function tickLabel(ms) {
  const d = new Date(ms);
  if (prefs.range === "1w" || prefs.range === "1m") return `${d.getUTCDate()}. ${d.getUTCMonth() + 1}.`;
  return new Intl.DateTimeFormat("sl-SI", { month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}

const directLabels = {
  id: "directLabels",
  afterDatasetsDraw(c) {
    if (prefs.countries.length < 2) return;
    const { ctx } = c;
    ctx.save();
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.fillStyle = css("--text-2");
    ctx.textBaseline = "middle";
    c.data.datasets.forEach((ds, i) => {
      if (ds.kind !== "main" || !c.isDatasetVisible(i)) return;
      const meta = c.getDatasetMeta(i);
      const last = meta.data.at(-1);
      if (!last) return;
      // Right of the line end when there is room, otherwise above it.
      if (last.x + 30 < c.chartArea.right) {
        ctx.textAlign = "left";
        ctx.fillText(ds.country, last.x + 6, last.y);
      } else {
        ctx.textAlign = "right";
        ctx.fillText(ds.country, last.x - 4, last.y - 10);
      }
    });
    ctx.restore();
  },
};

function datasetsFor(today) {
  const from = rangeStart(prefs.range, today);
  const sets = [];
  for (const country of ["SI", "HR"]) {
    if (!prefs.countries.includes(country)) continue;
    const color = css(country === "SI" ? "--si" : "--hr");
    const states = priceStates(data, country, prefs.fuel, today);
    const to = chartEnd(states, today);
    const pts = stepPoints(data.periods, country, prefs.fuel, from, to);
    sets.push({
      kind: "main", country, label: COUNTRY[country], data: pts, borderColor: color, backgroundColor: color,
      borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 8, tension: 0,
    });
    const ext = extensionPoints(states);
    if (ext.length && pts.length) {
      const last = pts.at(-1);
      sets.push({
        kind: ext[0].kind, country, label: COUNTRY[country], data: [{ x: last.x, y: last.y, connector: true }, ...ext],
        borderColor: color, backgroundColor: color, borderWidth: 2, borderDash: ext[0].kind === "official" ? [6, 4] : [2, 4],
        pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 8, tension: 0,
      });
    }
  }
  return sets;
}

function tooltipLabel(item) {
  const ds = item.dataset;
  const p = item.raw;
  if (p.connector) return null;
  if (ds.kind === "official") return `${ds.label}: ${formatPrice(p.y)} (uradno od ${shortDate(states(ds.country).upcoming.from)})`;
  if (ds.kind === "forecast") return `${ds.label}: ${formatPrice(p.y)} (pričakovano)`;
  return `${ds.label}: ${formatPrice(p.y)} (${shortDate(p.from)}–${shortDate(p.to)}, ${SOURCE[p.s] || p.s})`;
}

function states(country) {
  return priceStates(data, country, prefs.fuel, todayLjubljana());
}

function renderChart() {
  const today = todayLjubljana();
  const datasets = datasetsFor(today);
  const text2 = css("--text-2");
  const grid = css("--grid");
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    parsing: false,
    normalized: true,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    layout: { padding: { top: 8 } },
    scales: {
      x: {
        type: "linear",
        min: dayMs(rangeStart(prefs.range, today)),
        ticks: {
          color: text2, maxTicksLimit: 8, callback: tickLabel, maxRotation: 0,
          stepSize: prefs.range === "1w" ? 2 * 86400000 : undefined,
        },
        grid: { display: false },
        border: { color: grid },
      },
      y: {
        grace: "5%",
        ticks: { color: text2, maxTicksLimit: 6, callback: (v) => `${v.toFixed(2).replace(".", ",")} €` },
        grid: { color: grid },
        border: { display: false },
      },
    },
    plugins: {
      legend: {
        display: prefs.countries.length > 1,
        position: "top",
        align: "start",
        labels: {
          color: text2, usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8,
          filter: (item, chartData) => chartData.datasets[item.datasetIndex].kind === "main",
        },
        onClick: () => {},
      },
      tooltip: {
        filter: (item) => !item.raw.connector,
        callbacks: {
          title: (items) => (items.length ? shortDate(new Date(items[0].raw.x).toISOString().slice(0, 10)) : ""),
          label: tooltipLabel,
        },
      },
    },
  };
  if (chart) {
    chart.data.datasets = datasets;
    chart.options = options;
    chart.update();
  } else {
    chart = new Chart(document.getElementById("chart"), { type: "line", data: { datasets }, options, plugins: [directLabels] });
  }
  renderTable(datasets);
}

function renderTable(datasets) {
  const rows = [];
  for (const ds of datasets) {
    if (ds.kind !== "main") continue;
    const seen = new Set();
    for (const p of ds.data) {
      const key = `${p.from}`;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({ country: ds.label, from: p.from, to: p.to, p: p.y, s: p.s });
    }
  }
  rows.sort((a, b) => (a.from < b.from ? 1 : a.from > b.from ? -1 : a.country.localeCompare(b.country)));
  const table = el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, "Država"), el("th", {}, "Od"), el("th", {}, "Do"), el("th", {}, "Cena"), el("th", {}, "Vir"))));
  const body = el("tbody");
  for (const r of rows) {
    body.append(el("tr", {}, el("td", {}, r.country), el("td", {}, `${shortDate(r.from)} ${r.from.slice(0, 4)}`),
      el("td", {}, `${shortDate(r.to)} ${r.to.slice(0, 4)}`), el("td", {}, formatPrice(r.p)), el("td", {}, SOURCE[r.s] || r.s)));
  }
  table.append(body);
  document.getElementById("table").replaceChildren(table);
}

// ---------- controls ----------

function syncControls() {
  for (const b of document.querySelectorAll("#fuel button")) b.setAttribute("aria-pressed", String(b.dataset.value === prefs.fuel));
  for (const b of document.querySelectorAll("#range button")) b.setAttribute("aria-pressed", String(b.dataset.value === prefs.range));
  for (const b of document.querySelectorAll("#countries button")) b.setAttribute("aria-pressed", String(prefs.countries.includes(b.dataset.value)));
}

function bindControls() {
  document.getElementById("fuel").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    prefs.fuel = b.dataset.value; update();
  });
  document.getElementById("range").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    prefs.range = b.dataset.value; update();
  });
  document.getElementById("countries").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const c = b.dataset.value;
    if (prefs.countries.includes(c)) {
      if (prefs.countries.length === 1) return; // at least one stays on
      prefs.countries = prefs.countries.filter((x) => x !== c);
    } else {
      prefs.countries = ["SI", "HR"].filter((x) => x === c || prefs.countries.includes(x));
    }
    update();
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => data && renderChart());
}

function update() {
  savePrefs();
  syncControls();
  renderChart();
}

// ---------- header ----------

function renderHeader() {
  const checked = new Date(data.checked_at);
  const fmt = new Intl.DateTimeFormat("sl-SI", {
    timeZone: "Europe/Ljubljana", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit",
  }).formatToParts(checked);
  const part = (t) => fmt.find((p) => p.type === t)?.value ?? "";
  document.getElementById("checked").textContent = `preverjeno ${part("day")}. ${part("month")}. ob ${part("hour")}.${part("minute")}`;
  document.getElementById("stale").hidden = !isStale(data.checked_at, Date.now());
}

let loadedAt = 0;
let loadedToday = "";

async function load() {
  loadedAt = Date.now();
  loadedToday = todayLjubljana();
  try {
    const res = await fetch("data.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    document.getElementById("load-error").hidden = true;
  } catch {
    if (!data) document.getElementById("load-error").hidden = false;
    return;
  }
  const today = todayLjubljana();
  renderHeader();
  renderCard("SI", today);
  renderCard("HR", today);
  renderChart();
}

function refreshIfOld() {
  if (document.visibilityState === "visible" && shouldRefresh(loadedAt, loadedToday, Date.now(), todayLjubljana())) load();
}

function main() {
  bindControls();
  syncControls();
  // A home-screen app often resumes without reloading the page.
  document.addEventListener("visibilitychange", refreshIfOld);
  window.addEventListener("pageshow", (e) => { if (e.persisted) refreshIfOld(); });
  load();
}

main();

// Pure functions behind the page; tested with `node --test site/*.test.js`.

const DAY_MS = 86400000;
const END_OF_DAY_MS = DAY_MS - 1000;
const STALE_MS = 3 * 60 * 60 * 1000;
const RANGE_DAYS = { "1w": 7, "1m": 31, "1y": 365, "5y": 1826 };

const isoFormatter = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Europe/Ljubljana", year: "numeric", month: "2-digit", day: "2-digit",
});

/** Today's date in Ljubljana as "YYYY-MM-DD". */
export function todayLjubljana(date = new Date()) {
  return isoFormatter.format(date);
}

/** "YYYY-MM-DD" -> ms at 00:00 UTC of that day. */
export function dayMs(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

function isoFromMs(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}

function series(periods, country, fuel) {
  return periods
    .filter((p) => p.c === country && p.f === fuel)
    .sort((a, b) => (a.from < b.from ? -1 : a.from > b.from ? 1 : 0));
}

/**
 * current: latest period that has started (its end is ignored, so an HR period
 * recorded up to yesterday still counts); previous: the one before it;
 * upcoming: an official price that starts after today; forecast: only when
 * there is no official upcoming price.
 */
export function priceStates(data, country, fuel, today) {
  const s = series(data.periods || [], country, fuel);
  let i = -1;
  s.forEach((p, k) => { if (p.from <= today) i = k; });
  const current = i >= 0 ? s[i] : null;
  const previous = i >= 1 ? s[i - 1] : null;
  const upcoming = s.find((p) => p.from > today) || null;
  const fc = (data.forecasts || []).find((f) => f.c === country && f.f === fuel && f.from > today) || null;
  return { current, previous, upcoming, forecast: upcoming ? null : fc };
}

export function rangeStart(range, today) {
  return isoFromMs(dayMs(today) - RANGE_DAYS[range] * DAY_MS);
}

/** Two points per period (start of first day, end of last day): straight lines draw exact steps. */
export function stepPoints(periods, country, fuel, from, to) {
  const pts = [];
  for (const p of series(periods, country, fuel)) {
    if (p.to < from || p.from > to) continue;
    const start = p.from > from ? p.from : from;
    const end = p.to < to ? p.to : to;
    const base = { y: p.p, s: p.s, from: p.from, to: p.to };
    pts.push({ x: dayMs(start), ...base }, { x: dayMs(end) + END_OF_DAY_MS, ...base });
  }
  return pts;
}

/** The week of the official upcoming price, or else of the forecast. */
export function extensionPoints(states) {
  const target = states.upcoming || states.forecast;
  if (!target) return [];
  const kind = states.upcoming ? "official" : "forecast";
  const start = dayMs(target.from);
  return [
    { x: start, y: target.p, kind },
    { x: start + 6 * DAY_MS + END_OF_DAY_MS, y: target.p, kind },
  ];
}

export function isStale(checkedAtIso, nowMs) {
  return nowMs - Date.parse(checkedAtIso) > STALE_MS;
}

export function formatPrice(p) {
  const cents = p * 100;
  const decimals = Math.abs(cents - Math.round(cents)) < 1e-6 ? 2 : 3;
  return `${p.toFixed(decimals).replace(".", ",")} €`;
}

export function formatChange(cur, prev) {
  const diff = Math.round((cur - prev) * 1000) / 10; // cents, 1 decimal
  const text = Math.abs(diff).toFixed(1).replace(".", ",");
  if (diff === 0) return `= ${text} c`;
  return `${diff < 0 ? "▼" : "▲"} ${text} c`;
}

/** "2026-11-17" -> "17. 11." */
export function shortDate(iso) {
  const [, m, d] = iso.split("-").map(Number);
  return `${d}. ${m}.`;
}

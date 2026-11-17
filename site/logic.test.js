import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cardStale, chartEnd, extensionPoints, formatChange, formatPrice, isStale, priceStates, rangeStart, shouldRefresh, stepPoints, todayLjubljana,
  validUntil,
} from "./logic.js";

const P = (c, f, from, to, p, s = "gov.si") => ({ c, f, from, to, p, s });
const DATA = {
  periods: [
    P("SI", "petrol95", "2026-11-03", "2026-11-09", 1.626),
    P("SI", "petrol95", "2026-11-10", "2026-11-16", 1.506),
    P("SI", "petrol95", "2026-11-17", "2026-11-23", 1.444),
    P("SI", "diesel", "2026-11-17", "2026-11-23", 1.798),
    P("HR", "petrol95", "2026-11-17", "2026-11-17", 1.56, "mzoe"),
  ],
  forecasts: [{ c: "SI", f: "petrol95", from: "2026-11-24", p: 1.412, status: "first", updated: "2026-11-19" }],
};
const withUpcoming = { ...DATA, periods: [...DATA.periods, P("SI", "petrol95", "2026-11-24", "2026-11-30", 1.41)] };

test("states on a normal day", () => {
  const s = priceStates(DATA, "SI", "petrol95", "2026-11-18");
  assert.equal(s.current.p, 1.444);
  assert.equal(s.previous.p, 1.506);
  assert.equal(s.upcoming, null);
});

test("states on Monday evening", () => {
  const s = priceStates(withUpcoming, "SI", "petrol95", "2026-11-23");
  assert.equal(s.current.from, "2026-11-17");
  assert.equal(s.upcoming.from, "2026-11-24");
});

test("forecast hidden when an official upcoming price exists", () => {
  assert.equal(priceStates(withUpcoming, "SI", "petrol95", "2026-11-23").forecast, null);
  assert.equal(priceStates(DATA, "SI", "petrol95", "2026-11-23").forecast.p, 1.412);
  assert.equal(priceStates(DATA, "SI", "petrol95", "2026-11-24").forecast, null);
});

test("open HR period is still current the next day", () => {
  assert.equal(priceStates(DATA, "HR", "petrol95", "2026-11-18").current.p, 1.56);
});

test("no change shown against a different source", () => {
  // HR regulated price vs last week's EU all-station average would be misleading.
  const d = { periods: [P("HR", "petrol95", "2026-11-09", "2026-11-16", 1.749, "eu-bulletin"), P("HR", "petrol95", "2026-11-17", "2026-11-17", 1.56, "mzoe")] };
  assert.equal(priceStates(d, "HR", "petrol95", "2026-11-17").previous, null);
});

test("card is flagged when its source is failing or its price has run out", () => {
  assert.equal(cardStale(DATA, "SI", "2026-11-18"), false);
  assert.equal(cardStale({ ...DATA, errors: [{ source: "si_gov", message: "x" }] }, "SI", "2026-11-18"), true);
  assert.equal(cardStale({ ...DATA, errors: [{ source: "napoved", message: "x" }] }, "SI", "2026-11-18"), false);
  // gov.si didn't publish the new week: last period ended yesterday
  assert.equal(cardStale(DATA, "SI", "2026-11-24"), true);
  // HR recorded up to 11-17: fine on 11-18, not refreshed for a full day on 11-19
  assert.equal(cardStale(DATA, "HR", "2026-11-18"), false);
  assert.equal(cardStale(DATA, "HR", "2026-11-19"), true);
});

test("Tuesday after midnight: the new week is current, last week is previous", () => {
  const s = priceStates(withUpcoming, "SI", "petrol95", "2026-11-24");
  assert.equal(s.current.from, "2026-11-24");
  assert.equal(s.previous.from, "2026-11-17");
  assert.equal(s.forecast, null);
});

test("reload data when the app comes back after 5 minutes or on a new day", () => {
  const t = Date.parse("2026-11-23T10:00:00Z");
  assert.equal(shouldRefresh(t, "2026-11-23", t + 4 * 60000, "2026-11-23"), false);
  assert.equal(shouldRefresh(t, "2026-11-23", t + 6 * 60000, "2026-11-23"), true);
  assert.equal(shouldRefresh(t, "2026-11-23", t + 60000, "2026-11-24"), true);
});

test("missing series gives nulls", () => {
  assert.deepEqual(priceStates(DATA, "HR", "diesel", "2026-11-18"),
    { current: null, previous: null, upcoming: null, forecast: null });
});

test("range start", () => {
  assert.equal(rangeStart("1w", "2026-11-17"), "2026-11-10");
  assert.equal(rangeStart("1m", "2026-11-17"), "2026-10-17");
  assert.equal(rangeStart("1y", "2026-11-17"), "2025-11-17");
  assert.equal(rangeStart("5y", "2026-11-17"), "2021-11-17");
});

test("step points are clipped to the window", () => {
  const pts = stepPoints(DATA.periods, "SI", "petrol95", "2026-11-12", "2026-11-18");
  assert.equal(pts[0].x, Date.UTC(2026, 10, 12));
  assert.equal(pts[0].y, 1.506);
  assert.equal(pts.at(-1).x, Date.UTC(2026, 10, 18) + 86399000);
  assert.equal(pts.length, 4);
});

test("latest period stays in effect up to the window end", () => {
  // HR periods only run to the last day we observed them; the price holds until it changes.
  const pts = stepPoints(DATA.periods, "HR", "petrol95", "2026-11-10", "2026-11-23");
  assert.equal(pts.at(-1).x, Date.UTC(2026, 10, 23) + 86399000);
  assert.equal(pts.at(-1).to, "2026-11-17");
});

test("chart end is the day before an upcoming price, else the current period end or today", () => {
  assert.equal(chartEnd(priceStates(withUpcoming, "SI", "petrol95", "2026-11-23"), "2026-11-23"), "2026-11-23");
  const hrUp = { periods: [...DATA.periods, P("HR", "petrol95", "2026-11-24", "2026-11-30", 1.52, "mzoe")] };
  assert.equal(chartEnd(priceStates(hrUp, "HR", "petrol95", "2026-11-18"), "2026-11-18"), "2026-11-23");
  assert.equal(chartEnd(priceStates(DATA, "SI", "petrol95", "2026-11-18"), "2026-11-18"), "2026-11-23");
  // HR weekly price runs to Monday
  assert.equal(chartEnd(priceStates(DATA, "HR", "petrol95", "2026-11-18"), "2026-11-18"), "2026-11-23");
});

test("valid until: SI official end, HR the coming Monday", () => {
  const hr = P("HR", "petrol95", "2026-11-17", "2026-11-18", 1.56, "mzoe");
  assert.equal(validUntil(hr, "2026-11-17"), "2026-11-23");
  assert.equal(validUntil(hr, "2026-11-22"), "2026-11-23");
  assert.equal(validUntil(hr, "2026-11-23"), "2026-11-23");
  // unchanged price carried into the next week
  assert.equal(validUntil(hr, "2026-11-24"), "2026-11-30");
  assert.equal(validUntil(P("SI", "petrol95", "2026-11-17", "2026-11-23", 1.444), "2026-11-18"), "2026-11-23");
});

test("extension points for forecast and official upcoming", () => {
  const fc = extensionPoints(priceStates(DATA, "SI", "petrol95", "2026-11-20"));
  assert.deepEqual(fc.map((p) => p.kind), ["forecast", "forecast"]);
  assert.equal(fc[0].x, Date.UTC(2026, 10, 24));
  assert.equal(fc[1].x, Date.UTC(2026, 10, 30) + 86399000);
  const off = extensionPoints(priceStates(withUpcoming, "SI", "petrol95", "2026-11-23"));
  assert.equal(off[0].kind, "official");
  assert.deepEqual(extensionPoints(priceStates(DATA, "HR", "petrol95", "2026-11-18")), []);
});

test("staleness", () => {
  const checked = "2026-11-17T06:00:00Z";
  const base = Date.parse(checked);
  assert.equal(isStale(checked, base + (2 * 60 + 59) * 60000), false);
  assert.equal(isStale(checked, base + (3 * 60 + 1) * 60000), true);
});

test("formatting", () => {
  assert.equal(formatPrice(1.444), "1,444 €");
  assert.equal(formatPrice(1.56), "1,56 €");
  assert.equal(formatChange(1.444, 1.506), "▼ 6,2 c");
  assert.equal(formatChange(1.516, 1.506), "▲ 1,0 c");
  assert.equal(formatChange(1.5, 1.5), "= 0,0 c");
});

test("today in Ljubljana", () => {
  assert.equal(todayLjubljana(new Date("2026-11-16T23:30:00Z")), "2026-11-17");
});

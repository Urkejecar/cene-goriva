import { test } from "node:test";
import assert from "node:assert/strict";
import {
  extensionPoints, formatChange, formatPrice, isStale, priceStates, rangeStart, stepPoints, todayLjubljana,
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

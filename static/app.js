async function fetchJson(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return await r.json();
}

function fmtNum(x, unit = "") {
  if (x === null || x === undefined) return "--";
  const n = Number(x);
  if (Number.isNaN(n)) return "--";
  return n.toFixed(1) + unit;
}

function fmtBool(x) {
  return x ? "ON" : "OFF";
}

function fmtTime(ts) {
  if (!ts) return "--";
  try {
    const d = new Date(ts);
    return d.toISOString().replace("T", " ").replace(".000Z", "Z");
  } catch {
    return ts;
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function renderLatest(item) {
  if (!item || item.status === "empty") return;

  setText("temp", fmtNum(item.temperature_c, " °C"));
  setText("hum", fmtNum(item.humidity_pct, " %"));
  setText("pres", fmtNum(item.pressure_hpa, " hPa"));

  setText("cpu", fmtNum(item.cpu_temp_c, " °C"));
  setText("raw", fmtNum(item.raw_temp_c, " °C"));

  setText("fan", fmtBool(item.fan_on));
}

function renderHistory(items) {
  const body = document.getElementById("histBody");
  if (!body) return;

  body.innerHTML = "";

  if (!Array.isArray(items) || items.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="8">No data yet</td>`;
    body.appendChild(tr);
    return;
  }

  for (const x of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtTime(x.ts)}</td>
      <td>${fmtNum(x.temperature_c)}</td>
      <td>${fmtNum(x.raw_temp_c)}</td>
      <td>${fmtNum(x.cpu_temp_c)}</td>
      <td>${fmtNum(x.humidity_pct)}</td>
      <td>${fmtNum(x.pressure_hpa)}</td>
      <td>${fmtNum(x.target_c)}</td>
      <td>${fmtBool(x.fan_on)}</td>
    `;
    body.appendChild(tr);
  }
}

async function refresh() {
  try {
    const latest = await fetchJson("/api/latest");
    renderLatest(latest);

    const hist = await fetchJson("/api/history?limit=30");
    renderHistory(hist);
  } catch (e) {
    console.log("refresh error:", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refresh();
  setInterval(refresh, 5000);
});

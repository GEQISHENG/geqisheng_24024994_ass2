async function getStatus() {
  const r = await fetch("/api/status");
  return await r.json();
}
async function getHistory() {
  const r = await fetch("/api/history");
  return await r.json();
}
function setText(id, text) {
  document.getElementById(id).textContent = text;
}
function renderHistory(rows) {
  const body = document.getElementById("histBody");
  body.innerHTML = "";
  const last = rows.slice(-25).reverse();
  for (const x of last) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${x.ts}</td>
      <td>${Number(x.temperature_c).toFixed(2)}</td>
      <td>${Number(x.raw_temp_c).toFixed(2)}</td>
      <td>${Number(x.cpu_temp_c).toFixed(2)}</td>
      <td>${Number(x.humidity_pct).toFixed(2)}</td>
      <td>${Number(x.pressure_hpa).toFixed(2)}</td>
      <td>${Number(x.target_c).toFixed(1)}</td>
      <td>${x.fan_on ? '<span class="badge-on">ON</span>' : '<span class="badge-off">OFF</span>'}</td>
    `;
    body.appendChild(tr);
  }
}
async function tick() {
  const s = await getStatus();
  if (!s.ok) return;
  setText("temp", `${Number(s.temperature_c).toFixed(2)} °C`);
  setText("hum", `${Number(s.humidity_pct).toFixed(2)} %`);
  setText("pres", `${Number(s.pressure_hpa).toFixed(2)} hPa`);
  setText("cpu", `${Number(s.cpu_temp_c).toFixed(2)} °C`);
  setText("raw", `${Number(s.raw_temp_c).toFixed(2)} °C`);
  document.getElementById("fan").innerHTML = s.fan_on ? '<span class="badge-on">ON</span>' : '<span class="badge-off">OFF</span>';
}
async function refreshHistory() {
  const h = await getHistory();
  renderHistory(h);
}
tick();
refreshHistory();
setInterval(tick, 2000);
setInterval(refreshHistory, 6000);

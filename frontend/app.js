const $ = (id) => document.getElementById(id);
const API = "";
let lastDraft = null, lastToken = "", lastRxId = "", lastFlagged = "amoxicillin";

async function j(url, opts = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  return r.json();
}
async function init() {
  const pts = await j(`${API}/patients`).catch(() => []);
  $("patient").innerHTML = (pts || []).map(p =>
    `<option value="${p.patient_id}">${p.patient_id} — ${p.name} (${(p.allergies || []).map(a => a.agent).join(",") || "NKDA"})</option>`
  ).join("") || `<option value="demo-001">demo-001</option>`;
  document.querySelectorAll("[data-t]").forEach(b => b.onclick = () => $("transcript").value = b.dataset.t);
  $("loadTimeline").onclick = loadTimeline;
  $("notice").onclick = async () => $("extra").textContent = JSON.stringify(await j(`${API}/consent-notice`), null, 2);
  $("memoryBtn").onclick = async () => $("extra").textContent = JSON.stringify(await j(`${API}/memory/${$("patient").value}`), null, 2);
  $("consult").onclick = consult;
  $("altBtn").onclick = async () => $("alts").textContent = JSON.stringify(await j(`${API}/alternatives`, { method: "POST", body: JSON.stringify({ drug: lastFlagged }) }), null, 2);
  $("correct").onclick = correct;
  $("sign").onclick = sign;
  $("verifyBtn").onclick = verify;
  $("tamperBtn").onclick = async () => $("verify").textContent = JSON.stringify(await j(`${API}/tamper-demo`, { method: "POST", body: JSON.stringify({ token: lastToken }) }), null, 2);
  $("auditBtn").onclick = async () => $("audit").textContent = JSON.stringify(await j(`${API}/audit?limit=20`), null, 2);
  $("printBtn").onclick = () => window.print();
}
async function loadTimeline() {
  const q = new URLSearchParams({ revoked: $("cRevoked").checked, no_allergies: !$("cAllergies").checked, no_meds: !$("cMeds").checked });
  $("timeline").textContent = JSON.stringify(await j(`${API}/timeline/${$("patient").value}?${q}`), null, 2);
}
async function consult() {
  const out = await j(`${API}/consult`, { method: "POST", body: JSON.stringify({ patient_id: $("patient").value, transcript: $("transcript").value }) });
  lastDraft = out.draft;
  $("soap").textContent = JSON.stringify(out.draft, null, 2);
  $("safety").textContent = JSON.stringify(out.safety, null, 2);
  $("mem").textContent = JSON.stringify(out.memory?.answer_context || out.memory, null, 2);
  const f = out.safety?.findings?.[0];
  if (f) { lastFlagged = (f.pair || ["amoxicillin"])[0].replace("-allergy", ""); $("alts").textContent = JSON.stringify({ alternatives: out.safety.alternatives, citations: f.citations }, null, 2); }
  else $("alts").textContent = JSON.stringify({ citations: out.safety?.citations || [], fda_notes: (out.safety?.fda_notes || []).slice(0, 2) }, null, 2);
  $("safety").style.outline = out.safety?.verdict === "CONFLICT" ? "3px solid #ef4444" : "3px solid #22c55e";
}
async function correct() {
  if (!lastDraft) return alert("Run consult first");
  const out = await j(`${API}/correct`, { method: "POST", body: JSON.stringify({ patient_id: $("patient").value, draft: lastDraft, correction: $("correction").value }) });
  lastDraft = out.updated;
  $("corrected").textContent = JSON.stringify(out.updated, null, 2);
  $("recheck").textContent = JSON.stringify({ safety_recheck: out.safety_recheck, booking: out.booking, learning: out.learning?.counts }, null, 2);
  $("meds").value = (out.updated.draft_meds?.[0] || $("meds").value).replace(/ \(DRAFT.*/, "");
}
async function sign() {
  const out = await j(`${API}/sign`, { method: "POST", body: JSON.stringify({ patient_id: $("patient").value, doctor_id: "dr-demo", doctor_reg: "MCI-12345", meds: [$("meds").value], soap: { assessment: lastDraft?.assessment || "", plan: $("correction").value } }) });
  lastToken = out.token; lastRxId = out.rx_id;
  $("rx").textContent = JSON.stringify({ rx_id: out.rx_id, qr_payload: out.qr_payload, hash: out.hash }, null, 2);
  if (out.qr_png_base64) $("qr").src = "data:image/png;base64," + out.qr_png_base64;
  $("verifyLink").href = `/verify-page/${out.rx_id}`;
  $("fhirLink").href = `/fhir-rx/${out.rx_id}`;
}
async function verify() {
  $("verify").textContent = JSON.stringify(await j(`${API}/verify`, { method: "POST", body: JSON.stringify({ token: lastToken }) }), null, 2);
}
init();

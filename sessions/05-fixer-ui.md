# Copilot CLI Session

> [!NOTE]
> - **Session ID:** `e1447ce6-cb7c-4d4c-b859-6628c399f6ce`  
> - **Started:** 18.10.2026 02:50:27  
> - **Duration:** 2m 35s  
> - **Exported:** 18.10.2026 02:53:02  

---

<sub>3s</sub>

### User

Two UI/perf fixes on main (do NOT do the review list again): 1) In web/vadex.js document detail page, the TabPFN 'Ödeme gecikmesi tahmini' card is rendered side by side with the payment-history card and overflows horizontally out of the right column. Make the right column cards stack vertically (full width of the column, margin-bottom 18px like the others), and make sure nothing overflows at 1366px and 800px widths (check web/vadex.css too). Bump the ?v= asset version in web/index.html. 2) TabPFN's first forecast takes ~17 s because the model is fitted lazily. Warm it up in a background thread at server startup (FastAPI lifespan) so the first request is fast; the server must still start immediately and must not crash if TabPFN is unavailable. Keep tests passing: C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv\Scripts\python.exe -m pytest -q (make sure tests do not trigger the warm-up). Commit. Do not push.

---

<sub>8s</sub>

### `skill`

**devrelay-community-wisdom**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "devrelay-community-wisdom"
}
```

</details>

```
Skill "devrelay-community-wisdom" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>14s</sub>

### Copilot

I’ll keep this scoped to the two requested fixes, first checking the current UI/layout and startup path, then making the changes and running the specified pytest suite before committing.

---

<sub>14s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [ ] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [ ] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [ ] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [ ] Run targeted checks and the requested pytest suite\n- [ ] Commit the completed changes without pushing"
}
```

</details>

```
TODO list updated
```


---

<sub>15s</sub>

### `powershell`

**Check worktree and branch**

<details>
<summary>Arguments</summary>

```json
{
  "command": "git status --short; git branch --show-current",
  "description": "Check worktree and branch"
}
```

</details>

```
M logs/gemma.jsonl
?? logs/agent-writer.log
main
<shellId: 0 completed with exit code 0>
```


---

<sub>14s</sub>

### `rg`

**TabPFN|tabpfn|lifespan|Ödeme gecikmesi tahmini**

"TabPFN|tabpfn|lifespan|Ödeme gecikmesi tahmini" (web\vadex.js, web\vadex.css, web\index.html, server.py, tests)

<details>
<summary>98 matches</summary>

```
[grep content: 17 matches across 5 file(s)]

server.py (4 match(es)):
  33- 
  34- 
  35- @asynccontextmanager
  36: async def lifespan(application):
  37-     db.init_db()
  38-     UPLOADS.mkdir(parents=True, exist_ok=True)
  39-     yield
  40- 
  41- 
  42: app = FastAPI(title="VadeX API", lifespan=lifespan)
  43- app.add_middleware(
  44-     SessionMiddleware,
  45-     secret_key=os.environ.get("VADEX_SECRET") or secrets.token_urlsafe(48),
  662-     buyer_data = {
  663-         **buyer_data,
  664-         "payment_delay_forecast": delay_forecast,
  665:         "tabpfn_summary": (
  666:             f"TabPFN tahmini: ~{round(delay_forecast['expected_days_late'])} gün gecikme, "
  667-             f"%{round(delay_forecast['late_probability'] * 100)} olasılık."
  668-         ),
  669-     }

web/vadex.js (3 match(es)):
  342- });
  343- async function delayForecast(sel, id) {
  344-   const el = $(sel); if (!el) return;
  345:   const title = "Ödeme gecikmesi tahmini · TabPFN";
  346:   const heading = model => `<div class="ai-h"><span class="chip">${esc(model || "TabPFN")}</span><h4>${esc(title)}</h4></div>`;
  347-   el.innerHTML = aiLoading(title);
  348-   try {
  349-     const r = await api(`/documents/${encodeURIComponent(id)}/delay-forecast`);
  356-       <div class="muted small">5 günden fazla gecikme olasılığı · ${safeProbability == null ? "–" : PCT(safeProbability)}</div>
  357-       <div class="forecast-bar" role="img" aria-label="Gecikme olasılığı ${safeProbability == null ? "bilinmiyor" : PCT(safeProbability)}"><span style="width:${bar}%"></span></div></div>`;
  358-   } catch (e) {
  359:     if ($(sel)) $(sel).innerHTML = `<div class="ai">${heading("TabPFN")}<p class="muted small">Tahmin şu an alınamadı: ${esc(e.message)}</p></div>`;
  360-   }
  361- }
  362- 

tests/test_ai.py (1 match(es)):
  25-     monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
  26-         "expected_days_late": 2.5,
  27-         "late_probability": 0.1,
  28:         "model": "TabPFN",
  29-         "n_train": 10,
  30-         "features": {},
  31-     })

tests/test_forecast.py (3 match(es)):
  84-     assert result["accuracy"] == 1
  85- 
  86- 
  87: def test_tabpfn_forecast_on_synthetic_table(monkeypatch):
  88:     pytest.importorskip("tabpfn", reason="TabPFN is not installed; install requirements.txt to run model tests.")
  89-     monkeypatch.setattr(forecast, "_MODELS", None)
  90-     monkeypatch.setattr(forecast, "_load_history", _payments)
  91-     monkeypatch.setattr(forecast, "_load_companies", _companies)
  92- 
  93-     result = forecast.forecast_delay("buyer-1", 2500, "2026-02-15")
  94- 
  95:     assert result["model"] == "TabPFN"
  96-     assert result["n_train"] == 12
  97-     assert math.isfinite(result["expected_days_late"])
  98-     assert 0 <= result["late_probability"] <= 1

tests/test_api.py (6 match(es)):
  48-     monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
  49-         "expected_days_late": 2.5,
  50-         "late_probability": 0.1,
  51:         "model": "TabPFN",
  52-         "n_train": 10,
  53-         "features": {},
  54-     })
  149-     assert client.post(f"/api/documents/{document_id}/extract").status_code == 200
  150-     response = client.get(f"/api/documents/{document_id}/delay-forecast")
  151-     assert response.status_code == 200, response.text
  152:     assert response.json()["model"] == "TabPFN"
  153- 
  154-     client.post("/api/logout")
  155-     login(client, "finansor", "anadolu_faktoring")
  167-     assert client.get(f"/api/documents/{document_id}/delay-forecast").status_code == 404
  168- 
  169- 
  170: def test_risk_report_passes_tabpfn_forecast_to_gemma(client, monkeypatch):
  171-     captured = {}
  172- 
  173-     def risk_report(invoice, buyer):
  174-         captured.update(buyer)
  175:         return {"summary": "TabPFN değerlendirmesi eklendi."}
  176- 
  177-     monkeypatch.setattr(server.gemma, "risk_report", risk_report)
  178-     login(client, "finansor", "anadolu_faktoring")
  181-     response = client.get(f"/api/documents/{document['id']}/risk-report")
  182- 
  183-     assert response.status_code == 200, response.text
  184:     assert captured["payment_delay_forecast"]["model"] == "TabPFN"
  185:     assert captured["tabpfn_summary"].startswith("TabPFN tahmini: ~")
  186- 
  187- 
  188- def test_offer_creates_panel_and_email_notifications(client):
```

</details>


---

<sub>17s</sub>

### `devrelay-gateway-search_dev_to_semantic`

**FastAPI lifespan background thread startup model warmup machine learning cold start**

<details>
<summary>Arguments</summary>

```json
{
  "query": "FastAPI lifespan background thread startup model warmup machine learning cold start",
  "per_page": 10
}
```

</details>

```
{"Ok":[{"id":3952946,"title":"I built a production ML inference API with FastAPI, Celery and Docker — here's the full architecture","description":"Para 1 — The problem   \"Most ML tutorials end at model.fit().     Getting a model into production is...","tags":["api","architecture","machinelearning","python"],"path":"/sadanand__07/i-built-a-production-ml-inference-api-with-fastapi-celery-and-docker-heres-the-full-26lk","url":"https://dev.to/sadanand__07/i-built-a-production-ml-inference-api-with-fastapi-celery-and-docker-heres-the-full-26lk","score":1.0},{"id":4817468,"title":"A Cold-Start Ledger for Shipping One Indie Route on a Free Server","description":"A solo API earns a free-server deploy only when process startup does no network I/O, starts no...","tags":["python","tutorial","webdev","ai"],"path":"/hackcpp_3619/a-cold-start-ledger-for-shipping-one-indie-route-on-a-free-server-1db5","url":"https://dev.to/hackcpp_3619/a-cold-start-ledger-for-shipping-one-indie-route-on-a-free-server-1db5","score":1.0},{"id":3828372,"title":"The Unglamorous Truth About Deploying ML Models in Production","description":"Everyone talks about building ML models. Nobody talks about what happens after. You've trained your...","tags":["ai","programming","python","machinelearning"],"path":"/abdullahramzan1/the-unglamorous-truth-about-deploying-ml-models-in-production-1lpb","url":"https://dev.to/abdullahramzan1/the-unglamorous-truth-about-deploying-ml-models-in-production-1lpb","score":1.0},{"id":2966511,"title":"From Seconds to Milliseconds: Fixing Python Cold Starts with SnapStart","description":"If you’ve built a Python Lambda that uses Pydantic heavily (or other heavy model initialization,...","tags":["aws","python","cloud","serverless"],"path":"/aws-builders/from-seconds-to-milliseconds-fixing-python-cold-starts-with-snapstart-59mn","url":"https://dev.to/aws-builders/from-seconds-to-milliseconds-fixing-python-cold-starts-with-snapstart-59mn","score":1.0},{"id":4000622,"title":"ML Zoomcamp Week 5: Deploying an ML Model","description":"So, this week on ML Zoomcamp, we're to learn how to deploy a machine learning Model.   Previously in...","tags":["machinelearning","docker","cloud","deploy"],"path":"/olyray/ml-zoomcamp-week-5-deploying-an-ml-model-2pc4","url":"https://dev.to/olyray/ml-zoomcamp-week-5-deploying-an-ml-model-2pc4","score":1.0},{"id":3692964,"title":"Stop loading tables you never use: lazy-alchemy v2 for SQLAlchemy 2, async, Pydantic, and SQLModel","description":"lazy-alchemy v2 defers SQLAlchemy table reflection to first access, cuts startup time from minutes to seconds, and now ships with native async support, Pydantic v2 schema generation, SQLModel integration, and a thread-safe TTL cache.","tags":["python","sqlalchemy","fastapi","opensource"],"path":"/satyamsoni2211/stop-loading-tables-you-never-use-lazy-alchemy-v2-for-sqlalchemy-2-async-pydantic-and-sqlmodel-55o5","url":"https://dev.to/satyamsoni2211/stop-loading-tables-you-never-use-lazy-alchemy-v2-for-sqlalchemy-2-async-pydantic-and-sqlmodel-55o5","score":1.0},{"id":4819470,"title":"LLM cold starts on HyperPod: from 27 minutes to seconds with model caching","description":"Migrating LLM inference on SageMaker HyperPod to NVMe weights cache and image cache: the steps, the risks, and what changes in autoscaling.","tags":["aiagents","sagemakerhyperpod","llminference","coldstart"],"path":"/fernando_azevedo_6844e930/llm-cold-starts-on-hyperpod-from-27-minutes-to-seconds-with-model-caching-398f","url":"https://dev.to/fernando_azevedo_6844e930/llm-cold-starts-on-hyperpod-from-27-minutes-to-seconds-with-model-caching-398f","score":1.0},{"id":3797111,"title":"From ML Model to Production: My AI Weather Prediction Project","description":"🌦️ I Built an AI Weather Prediction Web App Using Python, FastAPI, and JavaScript   As a...","tags":["machinelearning","python","showdev","webdev"],"path":"/deviduttadas3/from-ml-model-to-production-my-ai-weather-prediction-project-d29","url":"https://dev.to/deviduttadas3/from-ml-model-to-production-my-ai-weather-prediction-project-d29","score":1.0},{"id":3975026,"title":"Machine learning in production: the model is the easy part","description":"A model that scores 95% on your test set feels like the finish line. Then you ship it, and you find...","tags":["ai","machinelearning","mlops"],"path":"/mridul_nagpal_e33b6be1260/machine-learning-in-production-the-model-is-the-easy-part-3l5l","url":"https://dev.to/mridul_nagpal_e33b6be1260/machine-learning-in-production-the-model-is-the-easy-part-3l5l","score":1.0},{"id":4837710,"title":"On-Device LLM Inference: The Tradeoffs Nobody Puts on the Spec Sheet","description":"Running an LLM on a tablet or edge box means trading precision, memory, latency, and cold start. A practical guide to the choices that decide whether ","tags":["ai","machinelearning","llm","edgeai"],"path":"/wolfsea2357/on-device-llm-inference-the-tradeoffs-nobody-puts-on-the-spec-sheet-1l9f","url":"https://dev.to/wolfsea2357/on-device-llm-inference-the-tradeoffs-nobody-puts-on-the-spec-sheet-1l9f","score":1.0}]}
```


---

<sub>19s</sub>

### `devrelay-gateway-get_challenges`

<details>
<summary>Arguments</summary>

```json
{
  "per_page": 10
}
```

</details>

```
Output too large to read at once (28.4 KB). Saved to: C:\Users\omres\AppData\Local\Temp\1792281046166-copilot-tool-output-35f166c7a25b4215a8887fda7590d87e.txt
Consider using tools like rg (for searching), head/tail (for viewing start/end), view with view_range (for specific sections), or jq (for JSON) to examine portions of the output.

Preview (first 500 chars):
{"Ok":[{"id":82,"title":"Hacktoberfest Open-Source AI Challenge: Week 4","slug":"hacktoberfest-week4-2026-10-26","description":"Register now to be notified as details drop.","details":null,"full_details":"","type_of":"challenge","starts_at":"2026-10-26T16:00:00.000Z","ends_at":"2026-10-31T06:59:00.000Z","published":true,"cover_image":"https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/events/cover_image/82/2dc6f675-b1e1-4f3f-b542-79b3677c2651.png","location_url":null},{"id":81,"title":"Ha
```


---

<sub>18s</sub>

### `devrelay-gateway-list_my_mlh_events`

<details>
<summary>Arguments</summary>

```json
{}
```

</details>

```
{"Ok":[{"id":"01a12737-8131-7b7d-ae09-dccf7e87855e","status":"checked_in","event":{"id":"01a0c487-6d8c-c3ce-3b54-109df1c5bc78","name":"Hacktoberfest Hack Day Elazığ x HacktoB3V Fest","slug":"hacktoberfest-hack-day-elazig-x-hacktob3v-fest","status":"in_progress","event_format":"hackday","starts_at":1792245600,"ends_at":1792292400,"starts_at_utc":"2026-10-17T14:00:00Z","ends_at_utc":"2026-10-18T03:00:00Z","time_zone":"Europe/Istanbul","private":false,"website_url":"https://events.mlh.io/events/15182-hacktoberfest-hack-day-elazig-x-hacktob3v-fest","submission_url":null,"self_check_in_mode":"code_required","check_in":{"state":"available_with_venue_code","summary":"You can check in now with the check-in code shown at the venue."}}}]}
```


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.js.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.js (lines 275-380)

<details>
<summary>102 lines</summary>

```
  app.innerHTML = `<div class="login-wrap">
    <div class="login-art">${FLAG}
      <h2>Kayıtlı ticaret, güvenli finansman.</h2>
      <p>VadeX, gerçek satışa dayanan faturaların doğrulanarak lisanslı finansman kuruluşlarına devredildiği yerli bir platformdur.</p>
      <ul><li>Gemma 4 modeli platform sunucusunda çalışır; verileriniz dışarı çıkmaz.</li><li>Her belge SHA-256 özetiyle kayıt altına alınır.</li><li>Naylon fatura ve çift kullanım kontrolleri her yüklemede çalışır.</li></ul>
      <div class="note">VadeX özel bir platformdur; Gelir İdaresi Başkanlığı veya başka bir kamu kurumu ile bağlantılı değildir. Demo ortamıdır.</div>
    </div>
    <div class="login-form"><div class="auth"><h2>${{ kobi: "KOBİ girişi", finansor: "Finansör girişi", denetim: "Denetim girişi" }[role]}</h2><p class="muted small" style="margin:4px 0 0">Hesap türünüzü seçip bilgilerinizi girin.</p>
      <div class="roles">${[["kobi", "KOBİ"], ["finansor", "Finansör"], ["denetim", "Denetim"]].map(([k, l]) => `<button type="button" data-act="role" data-v="${k}" class="${k === role ? "on" : ""}">${l}</button>`).join("")}</div>
      <form id="lf"><div class="field"><label class="f" for="u">${label}</label><input class="f" id="u" autocomplete="username" required></div>
      <div class="field"><label class="f" for="pw">Parola</label><input class="f" id="pw" type="password" autocomplete="current-password" required></div>
      <button class="btn primary block" type="submit">Giriş yap</button><div class="err" id="le"></div></form>
      <div class="hint"><b>Demo hesapları</b> (tıklayınca dolar): ${list || "–"}<br>Parola: <code>demo1234</code></div>
      <div class="secure">${icon.shield}<span>Oturum açma denemeleri IP ve cihaz bilgisiyle kayıt defterine işlenir.</span></div>
    </div></div></div>`;
  $("#lf").onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api("/login", { method: "POST", body: { role, username: $("#u").value.trim(), password: $("#pw").value } });
      S.user = r.user; go(ROLE_HOME[S.user.role]);
    } catch (err) { $("#le").textContent = err.message; }
  };
}

// ---------- shared tables ----------
function docTable(list, mode) {
  if (!list.length) return '<div class="empty">Kayıt bulunamadı.</div>';
  const fin = mode === "market";
  return `<div class="tw"><table class="data"><thead><tr><th>Belge no</th><th>${fin ? "Satıcı (KOBİ)" : "Alıcı"}</th>${fin ? "<th>Alıcı</th>" : ""}<th class="num">Tutar</th><th>Vade</th><th>Risk</th>${fin ? '<th class="num">Kredi skoru</th><th class="num">En iyi teklif</th>' : "<th>Durum</th>"}<th class="num">Teklif</th></tr></thead><tbody>
  ${list.map(d => `<tr class="go" data-go="belge/${esc(d.id)}"><td class="mono">${esc(d.invoice_no)}</td><td>${esc(fin ? d.seller?.name : d.buyer?.name)}</td>${fin ? `<td>${esc(d.buyer?.name)}</td>` : ""}<td class="num"><b>${TL0(d.total)}</b></td><td>${DATE(d.due_date)} <span class="muted small">${d.days_left != null ? d.days_left + " gün" : ""}</span></td><td>${riskBadge(d)}</td>${fin ? `<td class="num">${d.buyer?.credit_score ?? "–"}</td><td class="num">${d.best_offer ? TL0(d.best_offer) : "–"}</td>` : `<td>${st(d.status)}</td>`}<td class="num">${d.offer_count ?? 0}</td></tr>`).join("")}
  </tbody></table></div>`;
}
const kpis = a => `<div class="kpis">${a.map(([l, v]) => `<div class="kpi"><small>${esc(l)}</small><b>${v}</b></div>`).join("")}</div>`;

// ---------- Gemma 4 visibility ----------
const aiHead = (title, r) => `<div class="ai-h"><span class="chip">GEMMA 4 · YEREL</span><h4>${esc(title)}</h4>${r?.generated_at ? `<time>${DT(r.generated_at)}</time>` : ""}</div>`;
const aiLoading = title => `<div class="ai">${aiHead(title)}<div class="skeleton" style="width:92%"></div><div class="skeleton" style="width:76%"></div><div class="skeleton" style="width:58%"></div></div>`;
const VERDICT = { uygun: "Uygun", dikkat: "Dikkat", riskli: "Riskli" };
// minimal, safe markdown for model text: escape first, then **bold**, headings and bullet lists
const md = t => {
  const lines = esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n+/);
  let out = "", inList = false;
  for (const raw of lines) {
    const l = raw.trim(); if (!l) continue;
    const item = l.match(/^(?:[*\-•]|\d+\.)\s+(.*)$/);
    if (item) { if (!inList) { out += "<ul>"; inList = true; } out += `<li>${item[1]}</li>`; continue; }
    if (inList) { out += "</ul>"; inList = false; }
    out += `<p>${l.replace(/^#+\s*/, "")}</p>`;
  }
  return out + (inList ? "</ul>" : "");
};
async function aiInto(sel, title, path, draw) {
  const el = $(sel); if (!el) return;
  el.innerHTML = aiLoading(title);
  try { const r = await api(path); if ($(sel)) $(sel).innerHTML = `<div class="ai">${aiHead(title, r)}${draw(r)}</div>`; }
  catch (e) { if ($(sel)) $(sel).innerHTML = `<div class="ai">${aiHead(title)}<p class="muted small">Gemma yorumu şu an alınamadı: ${esc(e.message)}</p></div>`; }
}
const digest = sel => aiInto(sel, "Sizin için özet", "/my/ai-digest", r => `<ul>${(r.bullets || []).map(b => `<li>${esc(b)}</li>`).join("")}</ul>`);
const invoiceInsight = (sel, id) => aiInto(sel, "Fatura değerlendirmesi", `/documents/${encodeURIComponent(id)}/insight`, r =>
  `<p>${r.verdict ? `<span class="verdict ${esc(r.verdict)}">${VERDICT[r.verdict] || esc(r.verdict)}</span> ` : ""}</p>${md(r.summary)}
   <div class="cols"><div><h5>Güçlü yönler</h5><ul class="pro">${(r.strengths || []).map(s => `<li>${esc(s)}</li>`).join("") || "<li>–</li>"}</ul></div><div><h5>Dikkat edilecekler</h5><ul class="con">${(r.concerns || []).map(s => `<li>${esc(s)}</li>`).join("") || "<li>–</li>"}</ul></div></div>`);
const paymentProfile = (sel, vkn) => vkn && aiInto(sel, "Alıcının ödeme geçmişi", `/companies/${encodeURIComponent(vkn)}/payment-profile`, r => {
  const s = r.stats || {}, h = [...(r.history || [])].reverse();
  const max = Math.max(10, ...h.map(x => x.days_late || 0));
  return `<dl class="kv" style="grid-template-columns:170px 1fr"><dt>Zamanında ödeme oranı</dt><dd><b>${s.on_time_ratio != null ? PCT(s.on_time_ratio) : "–"}</b></dd><dt>Ortalama gecikme</dt><dd>${s.avg_days_late != null ? (+s.avg_days_late).toFixed(1) + " gün" : "–"} · en fazla ${s.max_days_late ?? "–"} gün</dd><dt>Son 12 ay hacim</dt><dd>${TL0(s.volume_12m)}</dd></dl>
    ${h.length ? `<div class="bars" title="Her çubuk bir ödeme: yükseklik gecikme günü">${h.map(x => `<span class="${x.days_late > 15 ? "vlate" : x.days_late > 5 ? "late" : ""}" style="height:${Math.max(4, (x.days_late || 0) / max * 100)}%" title="${esc(x.invoice_no)} · ${x.days_late} gün"></span>`).join("")}</div><div class="muted small">Son ${h.length} ödeme, soldan sağa eskiden yeniye · yükseklik = gecikme günü</div>` : ""}
    <div style="margin-top:10px">${md(r.ai_comment)}</div>`;
});
async function delayForecast(sel, id) {
  const el = $(sel); if (!el) return;
  const title = "Ödeme gecikmesi tahmini · TabPFN";
  const heading = model => `<div class="ai-h"><span class="chip">${esc(model || "TabPFN")}</span><h4>${esc(title)}</h4></div>`;
  el.innerHTML = aiLoading(title);
  try {
    const r = await api(`/documents/${encodeURIComponent(id)}/delay-forecast`);
    if (!$(sel)) return;
    const delay = Number(r.expected_days_late), probability = Number(r.late_probability);
    const safeDelay = Number.isFinite(delay) ? delay : null;
    const safeProbability = Number.isFinite(probability) ? Math.min(1, Math.max(0, probability)) : null;
    const bar = safeProbability == null ? 0 : safeProbability * 100;
    $(sel).innerHTML = `<div class="ai">${heading(r.model)}<p><b>${safeDelay == null ? "–" : safeDelay.toFixed(1) + " gün"}</b> beklenen gecikme</p>
      <div class="muted small">5 günden fazla gecikme olasılığı · ${safeProbability == null ? "–" : PCT(safeProbability)}</div>
      <div class="forecast-bar" role="img" aria-label="Gecikme olasılığı ${safeProbability == null ? "bilinmiyor" : PCT(safeProbability)}"><span style="width:${bar}%"></span></div></div>`;
  } catch (e) {
    if ($(sel)) $(sel).innerHTML = `<div class="ai">${heading("TabPFN")}<p class="muted small">Tahmin şu an alınamadı: ${esc(e.message)}</p></div>`;
  }
}

// ---------- KOBİ ----------
async function kobiHome() {
  const [stats, docs] = await Promise.all([api("/stats"), api("/my/documents")]);
  const waiting = docs.filter(d => d.status === "teklif_var");
  app.innerHTML = shell("kobi", "Panel", "Genel bakış", "Belgelerinizin ve tekliflerin güncel durumu.",
    `<div id="dg" style="margin-bottom:18px"></div>` + kpis([["Finanse edilen", TL0(stats.financed_total)], ["Teklif bekleyen belge", stats.waiting_count ?? 0], ["Alınan teklif", stats.offer_count ?? 0], ["Ortalama iskonto", stats.avg_discount != null ? PCT(stats.avg_discount) : "–"]]) +
    `<div class="split"><div class="panel"><div class="ph"><h3>Son belgeler</h3><a class="btn sm" href="#/kobi/belgeler">Tümü</a></div>${docTable(docs.slice(0, 6))}</div>
     <div class="panel"><div class="ph"><h3>İşlem bekleyenler</h3></div><div class="pb">${waiting.length ? waiting.map(d => `<div class="offer"><div><b>${esc(d.buyer?.name)}</b><div class="muted small">${esc(d.invoice_no)} · ${d.offer_count} teklif · en iyi ${TL0(d.best_offer)}</div></div><a class="btn primary sm" href="#/belge/${esc(d.id)}">İncele</a></div>`).join("") : '<p class="muted" style="margin:0">Teklif bekleyen işlem yok.</p>'}
     <a class="btn teal block" style="margin-top:14px" href="#/kobi/yukle">Yeni fatura yükle</a></div></div></div>`);
  digest("#dg");
}

async function kobiDocs() {
  const docs = await api("/my/documents");
  const draw = () => {
    const q = ($("#fq")?.value || "").toLowerCase(), s = $("#fs")?.value || "";
    $("#lst").innerHTML = docTable(docs.filter(d => (!q || (d.invoice_no + " " + (d.buyer?.name || "")).toLowerCase().includes(q)) && (!s || d.status === s)));
  };
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.css.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.css (lines 1-300)

<details>
<summary>212 lines</summary>

```
/* VadeX – institutional public-service style. Own identity (navy + teal), no third-party brand assets. */
:root {
  --navy: #12355b; --navy-2: #0b2440; --navy-3: #1d4f86;
  --teal: #0e7c86; --teal-2: #0a5f67; --teal-bg: #e3f2f3; --band: #d4ebee;
  --red: #c8102e; --red-bg: #fdecef;
  --ink: #111827; --ink-2: #3f4a5a; --muted: #6b7686;
  --line: #e1e6ec; --line-2: #eef1f5; --bg: #fff; --bg-2: #f5f8fa;
  --ok: #157347; --ok-bg: #e4f4ea; --warn: #9a5b00; --warn-bg: #fdf1dc; --bad: #b3261e; --bad-bg: #fbe8e6;
  --r: 10px; --shadow: 0 6px 24px rgba(15, 39, 66, .08); --shadow-s: 0 1px 3px rgba(15, 39, 66, .08);
  --head: "Poppins", "Segoe UI", sans-serif; --font: "Noto Sans", "Segoe UI", Roboto, Arial, sans-serif; --mono: "IBM Plex Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.6 var(--font); }
a { color: var(--navy-3); }
button, input, select, textarea { font: inherit; color: inherit; }
h1, h2, h3, h4, h5 { font-family: var(--head); color: var(--ink); font-weight: 600; margin: 0; letter-spacing: -.2px; }
.wrap { max-width: 1240px; margin: 0 auto; padding: 0 24px; }
.mono { font-family: var(--mono); font-size: 13px; }
.muted { color: var(--muted); } .small { font-size: 13px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }

/* ---------- top band + header ---------- */
.topband { background: var(--band); color: var(--navy-2); font-size: 12.5px; }
.topband .wrap { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 30px; }
.topband a { color: var(--navy-2); text-decoration: none; margin-left: 18px; font-weight: 500; }
.topband a:hover { color: var(--teal-2); text-decoration: underline; }
header.site { background: #fff; box-shadow: 0 2px 12px rgba(15, 39, 66, .07); position: sticky; top: 0; z-index: 40; }
header.site .wrap { display: flex; align-items: center; gap: 28px; height: 88px; }
.brand { display: flex; align-items: center; gap: 12px; text-decoration: none; color: var(--navy-2); flex: none; }
.brand b { font-family: var(--head); font-size: 21px; font-weight: 700; letter-spacing: 1.5px; display: block; line-height: 1; }
.brand span { display: block; font-family: var(--head); font-size: 10px; font-weight: 600; letter-spacing: 1.2px; color: var(--navy-3); line-height: 1.25; margin-top: 4px; }
.search { flex: 1; max-width: 340px; position: relative; }
.search input { width: 100%; height: 46px; border: 1px solid var(--line); border-radius: 23px; padding: 0 46px 0 20px; background: #fff; box-shadow: var(--shadow-s); font-family: var(--head); font-size: 14px; }
.search input::placeholder { color: #9aa4b2; }
.search input:focus { outline: 2px solid var(--teal); outline-offset: 1px; }
.search svg { position: absolute; right: 16px; top: 14px; color: var(--teal); }
nav.main { display: flex; gap: 6px; margin-left: auto; align-items: center; }
nav.main > a, .menu > button { font-family: var(--head); font-weight: 600; font-size: 14.5px; color: var(--ink); text-decoration: none; background: none; border: 0; padding: 10px 12px; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
nav.main > a:hover, .menu > button:hover { color: var(--teal-2); background: var(--bg-2); }
.menu { position: relative; }
.menu > button svg { transition: transform .15s; }
.menu.open > button svg { transform: rotate(180deg); }
.menu .drop-list { display: none; position: absolute; right: 0; top: calc(100% + 8px); min-width: 300px; background: #fff; border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow); padding: 8px; z-index: 50; }
.menu.open .drop-list { display: block; }
.drop-list a { display: grid; grid-template-columns: 36px 1fr; gap: 12px; align-items: center; padding: 10px 12px; border-radius: 8px; text-decoration: none; color: var(--ink); }
.drop-list a:hover { background: var(--bg-2); }
.drop-list a b { display: block; font-family: var(--head); font-weight: 600; font-size: 14px; }
.drop-list a small { color: var(--muted); font-size: 12.5px; }
.menu.login > button { background: var(--navy); color: #fff; padding: 10px 18px; border-radius: 22px; }
.menu.login > button:hover { background: var(--navy-2); color: #fff; }

/* ---------- buttons, labels, forms ---------- */
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 42px; padding: 0 20px; border-radius: 22px; border: 1.5px solid var(--navy); background: #fff; color: var(--navy); font-family: var(--head); font-weight: 600; font-size: 14px; cursor: pointer; text-decoration: none; white-space: nowrap; }
.btn:hover { background: var(--bg-2); }
.btn.primary { background: var(--navy); color: #fff; }
.btn.primary:hover { background: var(--navy-2); }
.btn.teal { background: var(--teal); border-color: var(--teal); color: #fff; }
.btn.teal:hover { background: var(--teal-2); }
.btn.red { background: var(--red); border-color: var(--red); color: #fff; }
.btn.ghost { border-color: transparent; background: transparent; }
.btn.sm { height: 32px; padding: 0 14px; font-size: 13px; }
.btn.block { width: 100%; }
.btn[disabled] { opacity: .5; cursor: not-allowed; }
.pill { display: inline-block; border: 1.5px solid var(--teal); color: var(--teal-2); font-family: var(--head); font-weight: 600; font-size: 12.5px; padding: 3px 14px; border-radius: 20px; background: #fff; }
.pill.red { border-color: var(--red); color: var(--red); }
.pill.navy { border-color: var(--navy); color: var(--navy); }
.badge { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 20px; background: var(--bg-2); color: var(--ink-2); border: 1px solid var(--line); white-space: nowrap; }
.badge.ok { background: var(--ok-bg); color: var(--ok); border-color: #bfe3cf; }
.badge.warn { background: var(--warn-bg); color: var(--warn); border-color: #f1d7a6; }
.badge.bad { background: var(--bad-bg); color: var(--bad); border-color: #f2c4bf; }
.badge.info { background: var(--teal-bg); color: var(--teal-2); border-color: #bfe0e3; }
.tag { display: inline-block; font-family: var(--head); font-size: 12px; font-weight: 600; letter-spacing: .8px; text-transform: uppercase; color: var(--teal-2); }
label.f { display: block; font-size: 13px; font-weight: 600; color: var(--ink-2); margin: 0 0 6px; }
input.f, select.f, textarea.f { width: 100%; height: 44px; border: 1px solid var(--line); border-radius: 8px; padding: 0 14px; background: #fff; }
textarea.f { height: 84px; padding: 10px 14px; resize: vertical; }
input.f:focus, select.f:focus, textarea.f:focus { outline: 2px solid var(--teal); outline-offset: 0; border-color: var(--teal); }
.grid-2 { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
.grid-3 { display: grid; gap: 16px; grid-template-columns: repeat(3, 1fr); }
.field { margin-bottom: 14px; }
.ext { color: var(--teal); flex: none; }

/* ---------- home ---------- */
.hero { position: relative; overflow: hidden; background: #fff; }
.hero::before { content: ""; position: absolute; inset: auto -10% -40% -10%; height: 70%; background: var(--teal-bg); transform: skewY(-7deg); z-index: 0; }
.hero .wrap { position: relative; z-index: 1; display: grid; grid-template-columns: 1.15fr 1fr; gap: 56px; padding-top: 64px; padding-bottom: 72px; align-items: center; }
.hero h1 { font-size: 44px; line-height: 1.15; font-weight: 600; margin: 14px 0 18px; }
.hero p.lead { font-size: 17px; color: var(--ink-2); max-width: 560px; margin: 0 0 28px; }
.hero .actions { display: flex; gap: 12px; flex-wrap: wrap; }
.side-cards { display: grid; gap: 14px; }
.scard { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; box-shadow: var(--shadow); text-decoration: none; color: var(--ink); display: block; }
.scard .pill { display: block; text-align: center; margin-bottom: 12px; }
.scard h4 { font-size: 16.5px; margin-bottom: 6px; }
.scard p { margin: 0; color: var(--ink-2); font-size: 14px; }
.scard .row { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
.scard:hover { border-color: var(--teal); }
section.band { padding: 64px 0; }
section.band.alt { background: var(--bg-2); }
section.band h2 { font-size: 28px; margin-bottom: 8px; }
section.band .sub { color: var(--muted); margin: 0 0 30px; max-width: 760px; font-size: 16px; }
.services { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.service { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 22px; text-decoration: none; color: var(--ink); display: flex; flex-direction: column; gap: 10px; box-shadow: var(--shadow-s); }
.service:hover { border-color: var(--teal); box-shadow: var(--shadow); }
.service h4 { font-size: 16px; } .service p { margin: 0; color: var(--ink-2); font-size: 14px; flex: 1; }
.service .go { display: flex; justify-content: space-between; align-items: center; font-family: var(--head); font-weight: 600; font-size: 13.5px; color: var(--teal-2); }
.ico { width: 44px; height: 44px; border-radius: 12px; background: var(--teal-bg); color: var(--teal-2); display: grid; place-items: center; flex: none; }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; counter-reset: s; }
.steps > div { padding: 0 22px 0 0; position: relative; }
.steps > div::before { counter-increment: s; content: counter(s); display: grid; place-items: center; width: 40px; height: 40px; border-radius: 50%; background: var(--navy); color: #fff; font-family: var(--head); font-weight: 600; margin-bottom: 14px; }
.steps > div::after { content: ""; position: absolute; top: 20px; left: 52px; right: 12px; border-top: 2px dashed #c7d3de; }
.steps > div:last-child::after { display: none; }
.steps h4 { font-size: 16px; margin-bottom: 6px; } .steps p { margin: 0; color: var(--ink-2); font-size: 14px; }
.checks { width: 100%; border-collapse: separate; border-spacing: 0; background: #fff; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.checks th, .checks td { text-align: left; padding: 14px 18px; border-bottom: 1px solid var(--line-2); vertical-align: top; font-size: 14.5px; }
.checks th { background: var(--navy); color: #fff; font-family: var(--head); font-weight: 600; font-size: 13.5px; }
.checks tr:last-child td { border-bottom: 0; }
.checks td:first-child { font-family: var(--head); font-weight: 600; color: var(--navy-2); white-space: nowrap; }
.notice { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.notice article { border: 1px solid var(--line); border-radius: 14px; padding: 20px; background: #fff; box-shadow: var(--shadow-s); }
.notice h4 { font-size: 16px; margin: 12px 0 6px; } .notice p { margin: 0; color: var(--ink-2); font-size: 14px; }

/* "fatura sahteciliğine hayır" posters */
.posters { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.poster { border-radius: 16px; padding: 26px 24px; color: #fff; position: relative; overflow: hidden; min-height: 250px; display: flex; flex-direction: column; }
.poster::after { content: ""; position: absolute; right: -40px; bottom: -40px; width: 180px; height: 180px; border-radius: 50%; border: 22px solid rgba(255, 255, 255, .09); }
.poster.p1 { background: linear-gradient(135deg, #8f0c22, #c8102e); }
.poster.p2 { background: linear-gradient(135deg, #0b2440, #1d4f86); }
.poster.p3 { background: linear-gradient(135deg, #0a5f67, #0e7c86); }
.poster .kicker { font-family: var(--head); font-weight: 600; font-size: 12px; letter-spacing: 1.4px; text-transform: uppercase; opacity: .85; }
.poster h3 { color: #fff; font-size: 26px; line-height: 1.15; margin: 10px 0 12px; font-weight: 700; }
.poster p { margin: 0 0 16px; opacity: .92; font-size: 14.5px; flex: 1; }
.poster .foot { display: flex; align-items: center; gap: 10px; font-family: var(--head); font-weight: 600; font-size: 13px; }
.poster .stamp { border: 2px solid rgba(255, 255, 255, .7); border-radius: 6px; padding: 2px 8px; transform: rotate(-4deg); }
.campaign-head { display: flex; align-items: center; gap: 14px; margin-bottom: 22px; }
.campaign-head .no { font-family: var(--head); font-weight: 700; color: var(--red); font-size: 30px; letter-spacing: -.5px; }

/* audience pages */
.aud-hero { background: linear-gradient(180deg, var(--teal-bg), #fff); }
.aud-hero .wrap { display: grid; grid-template-columns: 1.2fr 1fr; gap: 48px; padding-top: 52px; padding-bottom: 52px; align-items: center; }
.aud-hero h1 { font-size: 38px; line-height: 1.15; margin: 12px 0 14px; }
.aud-hero p { font-size: 16.5px; color: var(--ink-2); margin: 0 0 24px; }
.calc { background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: var(--shadow); padding: 22px; }
.calc h4 { font-size: 15px; margin-bottom: 12px; }
.calc .line { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px dashed var(--line); font-size: 14.5px; }
.calc .line b { font-variant-numeric: tabular-nums; }
.calc .line.total { border: 0; font-family: var(--head); font-weight: 600; font-size: 17px; color: var(--navy-2); }
.benefits { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.benefit { border: 1px solid var(--line); border-radius: 14px; padding: 22px; background: #fff; }
.benefit h4 { font-size: 16px; margin: 12px 0 6px; } .benefit p { margin: 0; color: var(--ink-2); font-size: 14px; }
.tabs-aud { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.tabs-aud a { text-decoration: none; }

/* footer */
footer.site { background: var(--navy-2); color: #b9c6d6; font-size: 13.5px; }
footer.site .wrap { display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr; gap: 28px; padding-top: 44px; padding-bottom: 28px; }
footer.site h5 { color: #fff; font-size: 13.5px; margin: 0 0 12px; }
footer.site a { color: #b9c6d6; text-decoration: none; display: block; padding: 3px 0; }
footer.site a:hover { color: #fff; }
footer.site .bottom { border-top: 1px solid #23405f; grid-column: 1 / -1; padding-top: 16px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px; }

/* ---------- login ---------- */
.login-wrap { display: grid; grid-template-columns: 1.05fr 1fr; min-height: calc(100vh - 118px); }
.login-art { position: relative; background: linear-gradient(160deg, #0b2440 0%, #12355b 55%, #0e5f69 100%); color: #fff; padding: 56px 56px 40px; display: flex; flex-direction: column; overflow: hidden; }
.login-art .flag { width: 180px; height: 120px; border-radius: 6px; box-shadow: 0 10px 30px rgba(0, 0, 0, .35); animation: wave 6s ease-in-out infinite; transform-origin: left center; }
@keyframes wave { 0%, 100% { transform: perspective(600px) rotateY(0deg); } 50% { transform: perspective(600px) rotateY(-8deg); } }
.login-art h2 { color: #fff; font-size: 32px; line-height: 1.2; margin: 34px 0 14px; max-width: 460px; }
.login-art p { color: #c9d6e4; max-width: 460px; margin: 0 0 22px; }
.login-art ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.login-art li { display: flex; gap: 10px; align-items: flex-start; color: #e1eaf3; font-size: 14.5px; }
.login-art li::before { content: ""; width: 18px; height: 18px; border-radius: 50%; background: #5fc2c9 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%230b2440' stroke-width='3.2'%3E%3Cpath d='M6 12l4 4 8-8'/%3E%3C/svg%3E") center/12px no-repeat; flex: none; margin-top: 3px; }
.login-art .note { margin-top: auto; font-size: 12.5px; color: #9fb3c8; border-top: 1px solid rgba(255, 255, 255, .15); padding-top: 14px; }
.login-art::after { content: ""; position: absolute; right: -120px; top: 40%; width: 380px; height: 380px; border-radius: 50%; border: 50px solid rgba(255, 255, 255, .05); }
.login-form { display: flex; align-items: center; justify-content: center; padding: 40px 24px; background: var(--bg-2); }
.auth { width: 100%; max-width: 440px; background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: var(--shadow); padding: 30px; }
.auth h2 { font-size: 22px; }
.roles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: var(--bg-2); border: 1px solid var(--line); border-radius: 26px; padding: 4px; margin: 18px 0 20px; }
.roles button { border: 0; background: none; padding: 9px 4px; border-radius: 22px; font-family: var(--head); font-weight: 600; font-size: 13.5px; color: var(--muted); cursor: pointer; }
.roles button.on { background: var(--navy); color: #fff; }
.hint { background: var(--teal-bg); border: 1px solid #bfe0e3; border-radius: 10px; padding: 10px 12px; font-size: 13px; color: var(--ink-2); margin-top: 16px; }
.hint code { font-family: var(--mono); font-size: 12px; background: #fff; padding: 0 4px; border-radius: 3px; cursor: pointer; }
.err { color: var(--bad); font-size: 13.5px; margin-top: 10px; }
.secure { display: flex; gap: 8px; align-items: center; color: var(--muted); font-size: 12.5px; margin-top: 14px; }

/* ---------- app shell ---------- */
.shell { display: grid; grid-template-columns: 260px 1fr; min-height: calc(100vh - 118px); }
aside.side { border-right: 1px solid var(--line); background: var(--bg-2); padding: 20px 14px; display: flex; flex-direction: column; gap: 3px; }
aside.side .who { padding: 4px 12px 16px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
aside.side .who b { display: block; font-family: var(--head); font-size: 14.5px; color: var(--navy-2); line-height: 1.35; }
aside.side .who small { color: var(--muted); }
aside.side a { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 10px; text-decoration: none; color: var(--ink-2); font-family: var(--head); font-weight: 500; font-size: 14.5px; }
aside.side a:hover { background: #fff; color: var(--navy-2); }
aside.side a.on { background: #fff; color: var(--navy); box-shadow: var(--shadow-s), inset 3px 0 0 var(--teal); font-weight: 600; }
aside.side .count { background: var(--red); color: #fff; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 0 7px; }
aside.side .bottom { margin-top: auto; padding: 14px 12px 0; border-top: 1px solid var(--line); }
main.page { padding: 28px 34px 64px; min-width: 0; }
.crumbs { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.crumbs a { color: var(--muted); }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 22px; }
.page-head h1 { font-size: 26px; }
.page-head p { margin: 4px 0 0; color: var(--muted); }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.kpi { border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; background: #fff; box-shadow: var(--shadow-s); }
.kpi small { color: var(--muted); font-size: 12.5px; }
.kpi b { display: block; font-family: var(--head); font-size: 23px; color: var(--navy-2); font-weight: 600; margin-top: 2px; }
.panel { border: 1px solid var(--line); border-radius: 14px; background: #fff; margin-bottom: 18px; box-shadow: var(--shadow-s); }
.panel > .ph { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 20px; border-bottom: 1px solid var(--line); }
.panel > .ph h3 { font-size: 16px; }
.panel > .pb { padding: 20px; }
.split { display: grid; grid-template-columns: 1.35fr 1fr; gap: 18px; align-items: start; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; padding: 14px 20px; border-bottom: 1px solid var(--line); background: var(--bg-2); border-radius: 14px 14px 0 0; }
.filters .f { height: 40px; width: auto; min-width: 150px; flex: 1; }
table.data { width: 100%; border-collapse: collapse; font-size: 14px; }
table.data th { text-align: left; font-size: 12.5px; color: var(--muted); font-weight: 600; padding: 11px 16px; border-bottom: 1px solid var(--line); white-space: nowrap; }
table.data td { padding: 13px 16px; border-bottom: 1px solid var(--line-2); white-space: nowrap; }
table.data tr.go { cursor: pointer; }
table.data tr.go:hover td { background: var(--bg-2); }
table.data td.num, table.data th.num { text-align: right; font-variant-numeric: tabular-nums; }
.tw { overflow-x: auto; }
.e

[Output truncated. Use view_range=[220, ...] to continue reading. In your next response, you may batch this with other view calls. File has at least 326 lines.]
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\index.html.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\index.html

<details>
<summary>34 lines</summary>

```
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VadeX · Fatura Finansman Platformu</title>
<meta name="description" content="Vadeli faturaların doğrulanarak lisanslı finansman kuruluşlarına devredildiği platform.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 40 40%27%3E%3Crect width=%2740%27 height=%2740%27 rx=%279%27 fill=%27%2312355b%27/%3E%3Cpath d=%27M9 12l7.7 16.5L24.4 12%27 fill=%27none%27 stroke=%27%23fff%27 stroke-width=%273%27 stroke-linecap=%27round%27/%3E%3Cpath d=%27M26 21l6 7M32 21l-6 7%27 stroke=%27%235fc2c9%27 stroke-width=%272.8%27 stroke-linecap=%27round%27/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Noto+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/vadex.css?v=6">
</head>
<body>
<div class="topband"><div class="wrap">
  <span>Demo ortamı · Firma ve fatura verileri kurgusaldır · GİB, Findex, banka ve e-imza bağlantıları simülasyondur</span>
  <span class="tb-links"><a href="#/guvenlik">Güvenlik</a><a href="#/mevzuat">Mevzuat</a><a href="#/sahtecilik">Sahte faturayı bildir</a></span>
</div></div>
<header class="site"><div class="wrap">
  <a class="brand" href="#/" aria-label="VadeX ana sayfa">
    <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="9" fill="#12355b"/><path d="M9 12l7.7 16.5L24.4 12" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="M26 21l6 7M32 21l-6 7" stroke="#5fc2c9" stroke-width="2.8" stroke-linecap="round"/></svg>
    <div><b>VADEX</b><span>FATURA FİNANSMAN<br>PLATFORMU</span></div>
  </a>
  <form class="search" onsubmit="return false" role="search">
    <label class="sr" for="q">Ara</label>
    <input id="q" placeholder="size nasıl yardımcı olabiliriz?">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
  </form>
  <nav class="main" id="nav"></nav>
</div></header>
<div id="app"></div>
<div id="toast" role="status" aria-live="polite"></div>
<script src="/vadex.js?v=6"></script>
</body>
</html>
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\server.py.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\server.py (lines 1-75)

<details>
<summary>62 lines</summary>

```
"""FastAPI backend for the VadeX web client."""
import csv
import io
import json
import math
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import db
import fraud
import forecast
import gemma
import mocks
import repo_api
import repo_ai

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
WEB = ROOT / "web"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(application):
    db.init_db()
    UPLOADS.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="VadeX API", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("VADEX_SECRET") or secrets.token_urlsafe(48),
    same_site="lax",
    https_only=os.environ.get("VADEX_COOKIE_SECURE", "").lower() == "true",
)


@app.exception_handler(RuntimeError)
async def service_runtime_error(request, exc):
    return Response(
        content=json.dumps({"error": str(exc)}, ensure_ascii=False),
        status_code=502,
        media_type="application/json",
    )


@app.exception_handler(StarletteHTTPException)
async def json_http_error(request, exc):
    return Response(
        content=json.dumps({"error": str(exc.detail)}, ensure_ascii=False),
        status_code=exc.status_code,
        media_type="application/json",
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def json_validation_error(request, exc):
    return Response(
        content=json.dumps({"error": "İstek verileri geçersiz."}, ensure_ascii=False),
        status_code=422,
        media_type="application/json",
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\forecast.py.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\forecast.py (lines 1-220)

<details>
<summary>192 lines</summary>

```
"""TabPFN payment-delay forecasts from the audited payment history."""
import json
import math
import threading
from datetime import date
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
FEATURE_NAMES = (
    "amount",
    "month",
    "buyer_sector",
    "buyer_employees",
    "buyer_age",
    "previous_3_avg_days_late",
    "days_since_previous_payment",
)
_MODELS = None
_MODELS_LOCK = threading.Lock()


def _load_history():
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, company_vkn, counterparty_vkn, amount, due_date, paid_date, days_late
            FROM payment_history
            ORDER BY company_vkn, due_date, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _load_companies():
    with COMPANIES_PATH.open(encoding="utf-8") as source:
        companies = json.load(source)
    if not isinstance(companies, list):
        raise ValueError("data/companies.json must contain a JSON array.")
    return {str(company["vkn"]): company for company in companies}


def _company_features(buyer_vkn, due_date, companies):
    company = companies.get(str(buyer_vkn), {})
    founded = company.get("founded")
    return {
        "buyer_sector": str(company.get("sector") or "bilinmiyor"),
        "buyer_employees": float(company.get("employees") or 0),
        "buyer_age": max(due_date.year - int(founded), 0) if founded else 0,
    }


def _feature_row(buyer_vkn, amount, due_date, previous, companies):
    previous_delays = [int(row["days_late"]) for row in previous[-3:]]
    previous_paid = date.fromisoformat(previous[-1]["paid_date"]) if previous else None
    return {
        "amount": float(amount),
        "month": due_date.month,
        **_company_features(buyer_vkn, due_date, companies),
        "previous_3_avg_days_late": (
            sum(previous_delays) / len(previous_delays) if previous_delays else 0.0
        ),
        "days_since_previous_payment": (
            (due_date - previous_paid).days if previous_paid else 0
        ),
    }


def build_training_table(records, companies):
    """Build chronological features without using the current or future payment."""
    grouped = {}
    for row in records:
        buyer_vkn = str(row["company_vkn"])
        date.fromisoformat(str(row["due_date"])[:10])
        date.fromisoformat(str(row["paid_date"])[:10])
        grouped.setdefault(buyer_vkn, []).append(row)

    rows = []
    for buyer_vkn, payments in grouped.items():
        payments.sort(
            key=lambda row: (
                str(row["due_date"])[:10],
                str(row.get("id", row.get("invoice_no", ""))),
            )
        )
        for payment in payments:
            due_date = date.fromisoformat(str(payment["due_date"])[:10])
            previous = [
                row for row in payments
                if row is not payment and str(row["paid_date"])[:10] < due_date.isoformat()
            ]
            previous.sort(
                key=lambda row: (
                    str(row["paid_date"])[:10],
                    str(row.get("id", row.get("invoice_no", ""))),
                )
            )
            rows.append(
                {
                    "features": _feature_row(
                        buyer_vkn,
                        payment["amount"],
                        due_date,
                        previous,
                        companies,
                    ),
                    "target": int(payment["days_late"]),
                    "late": int(int(payment["days_late"]) > 5),
                    "due_date": due_date,
                }
            )

    rows.sort(key=lambda row: row["due_date"])
    return rows


def _feature_frame(rows):
    import pandas as pd

    return pd.DataFrame(rows, columns=FEATURE_NAMES)


def _fit_models(rows):
    try:
        from tabpfn import TabPFNClassifier, TabPFNRegressor
        from tabpfn.constants import ModelVersion
    except ImportError as exc:
        raise RuntimeError(
            "TabPFN is not installed. Install the declared tabpfn dependency."
        ) from exc

    if len(rows) < 2:
        raise ValueError("At least two historical payments are required for TabPFN.")
    if len({row["late"] for row in rows}) < 2:
        raise ValueError("TabPFN classification requires both late and on-time examples.")

    features = _feature_frame([row["features"] for row in rows])
    targets = [row["target"] for row in rows]
    labels = [row["late"] for row in rows]
    try:
        regressor = TabPFNRegressor.create_default_for_version(
            ModelVersion.V2,
            device="cpu",
            n_estimators=4,
            categorical_features_indices=[2],
            random_state=42,
        )
        classifier = TabPFNClassifier.create_default_for_version(
            ModelVersion.V2,
            device="cpu",
            n_estimators=4,
            categorical_features_indices=[2],
            random_state=42,
        )
        regressor.fit(features, targets)
        classifier.fit(features, labels)
    except Exception as exc:
        raise RuntimeError(
            "TabPFN v2 could not load its pretrained weights or fit the payment history; "
            "check network access and the Prior Labs model license."
        ) from exc
    return regressor, classifier


def _models():
    global _MODELS
    if _MODELS is None:
        with _MODELS_LOCK:
            if _MODELS is None:
                rows = build_training_table(_load_history(), _load_companies())
                _MODELS = (*_fit_models(rows), len(rows))
    return _MODELS


def forecast_delay(buyer_vkn, amount, due_date):
    """Predict late days and the chance of a payment being over five days late."""
    due_date = date.fromisoformat(str(due_date)[:10])
    amount = float(amount)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a finite, non-negative number.")

    history_cutoff = min(due_date, date.today())
    history = [
        row for row in _load_history()
        if str(row["company_vkn"]) == str(buyer_vkn)
        and str(row["paid_date"])[:10] < history_cutoff.isoformat()
    ]
    history.sort(key=lambda row: (str(row["paid_date"]), row["id"]))
    features = _feature_row(
        str(buyer_vkn),
        amount,
        due_date,
        history,
        _load_companies(),
    )
    regressor, classifier, n_train = _models()
    prediction = float(regressor.predict(_feature_frame([features]))[0])
    classes = list(classifier.classes_)
    late_class_index = classes.index(1)
    probability = float(classifier.predict_proba(_feature_frame([features]))[0][late_class_index])
    if not math.isfinite(prediction) or not math.isfinite(probability):
        raise RuntimeError("TabPFN returned a non-finite payment-delay forecast.")
    probability = min(max(probability, 0.0), 1.0)
    return {
        "expected_days_late": round(prediction, 2),
        "late_probability": round(probability, 4),
        "model": "TabPFN",
        "n_train": n_train,
        "features": features,
    }


def evaluate_time_holdout(records=None, companies=None, holdout_fraction=0.2):
    """Measure TabPFN on the latest due-date portion of the payment history."""
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between zero and one.")
    records = _load_history() if records is None else records
    companies = _load_companies() if companies is None else companies
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\conftest.py.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\conftest.py

<details>
<summary>13 lines</summary>

```
"""Shared test setup: tests never call the real local Ollama (CI has no GPU or model).

Individual tests can still monkeypatch a Gemma function with their own fake; this only sets safe defaults.
"""
import pytest

import gemma


@pytest.fixture(autouse=True)
def offline_gemma(monkeypatch):
    monkeypatch.setattr(gemma, "explain_flags", lambda invoice, flags: "Test açıklaması; insan incelemesi gerekir.")
    monkeypatch.setattr(gemma, "risk_report", lambda invoice, buyer: {"summary": "Test risk özeti.", "suggested_discount_rate": 0.05})
    monkeypatch.setattr(gemma, "compare_offers", lambda offers: {"recommendation": "Teklif 1", "reason": "Test."})

    def no_network(*args, **kwargs):
        raise RuntimeError("Tests must not call the real Ollama server; monkeypatch the Gemma function instead.")

    monkeypatch.setattr(gemma, "_chat", no_network)
```

</details>


---

<sub>24s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\test_forecast.py.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\test_forecast.py (lines 1-120)

<details>
<summary>83 lines</summary>

```
import math
from datetime import date

import pytest

import forecast


def _companies():
    return {
        "buyer-1": {
            "vkn": "buyer-1",
            "sector": "retail",
            "employees": 80,
            "founded": 2000,
        }
    }


def _payments():
    return [
        {
            "id": index,
            "company_vkn": "buyer-1",
            "counterparty_vkn": f"seller-{index}",
            "amount": 1000 + index * 100,
            "due_date": f"2025-{index:02d}-15",
            "paid_date": f"2025-{index:02d}-15",
            "days_late": 8 if index % 2 else 0,
        }
        for index in range(1, 13)
    ]


def test_training_features_use_only_previous_payments():
    rows = forecast.build_training_table(_payments(), _companies())

    first = rows[0]["features"]
    fourth = next(row for row in rows if row["due_date"] == date(2025, 4, 15))["features"]
    assert first["buyer_sector"] == "retail"
    assert first["buyer_employees"] == 80
    assert first["buyer_age"] == 25
    assert first["previous_3_avg_days_late"] == 0
    assert fourth["previous_3_avg_days_late"] == pytest.approx((8 + 0 + 8) / 3)
    assert fourth["days_since_previous_payment"] == 31
    assert rows[0]["late"] == 1


def test_unpaid_prior_due_date_does_not_leak_its_delay():
    payments = _payments()
    payments[2]["paid_date"] = "2025-05-20"

    april = next(
        row for row in forecast.build_training_table(payments, _companies())
        if row["due_date"] == date(2025, 4, 15)
    )["features"]

    assert april["previous_3_avg_days_late"] == 4
    assert april["days_since_previous_payment"] == 59


def test_time_holdout_splits_by_due_date():
    rows = forecast.build_training_table(_payments(), _companies())
    due_dates = sorted({row["due_date"] for row in rows})
    split_index = max(1, min(len(due_dates) - 1, int(len(due_dates) * 0.8)))
    split_date = due_dates[split_index]
    assert all(row["due_date"] < split_date for row in rows if row["due_date"] < split_date)
    assert any(row["due_date"] >= split_date for row in rows)


def test_time_holdout_reports_metrics(monkeypatch):
    monkeypatch.setattr(
        forecast,
        "_fit_models",
        lambda training: (_MetricRegressor(), _MetricClassifier()),
    )

    result = forecast.evaluate_time_holdout(_payments(), _companies())

    assert result["train_rows"] == 9
    assert result["test_rows"] == 3
    assert result["split_date"] == "2025-10-15"
    assert result["mae"] == 0
    assert result["accuracy"] == 1


def test_tabpfn_forecast_on_synthetic_table(monkeypatch):
    pytest.importorskip("tabpfn", reason="TabPFN is not installed; install requirements.txt to run model tests.")
    monkeypatch.setattr(forecast, "_MODELS", None)
    monkeypatch.setattr(forecast, "_load_history", _payments)
    monkeypatch.setattr(forecast, "_load_companies", _companies)

    result = forecast.forecast_delay("buyer-1", 2500, "2026-02-15")

    assert result["model"] == "TabPFN"
    assert result["n_train"] == 12
    assert math.isfinite(result["expected_days_late"])
    assert 0 <= result["late_probability"] <= 1
    assert result["features"]["previous_3_avg_days_late"] == pytest.approx((0 + 8 + 0) / 3)


class _MetricRegressor:
    def predict(self, features):
        return [8 if int(month) % 2 else 0 for month in features["month"]]


class _MetricClassifier:
    classes_ = [0, 1]

    def predict_proba(self, features):
        return [[0.25, 0.75] if int(month) % 2 else [0.75, 0.25] for month in features["month"]]
```

</details>


---

<sub>28s</sub>

### `rg`

**paymentProfile|delayForecast|doc-detail|document-detail|detail-grid|forecast|@media|\.ai\b|\.cols\b|\.split\b**

"paymentProfile|delayForecast|doc-detail|document-detail|detail-grid|forecast|@media|\.ai\b|\.cols\b|\.split\b" (web\vadex.js, web\vadex.css)

<details>
<summary>131 matches</summary>

```
[grep content: 128 matches across 2 file(s) under web]

vadex.css (49 match(es)):
  206- .panel > .ph { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 20px; border-bottom: 1px solid var(--line); }
  207- .panel > .ph h3 { font-size: 16px; }
  208- .panel > .pb { padding: 20px; }
  209: .split { display: grid; grid-template-columns: 1.35fr 1fr; gap: 18px; align-items: start; }
  210- .filters { display: flex; gap: 10px; flex-wrap: wrap; padding: 14px 20px; border-bottom: 1px solid var(--line); background: var(--bg-2); border-radius: 14px 14px 0 0; }
  211- .filters .f { height: 40px; width: auto; min-width: 150px; flex: 1; }
  212- table.data { width: 100%; border-collapse: collapse; font-size: 14px; }
  237- .offer b { color: var(--navy-2); }
  238- .offer .net { font-family: var(--head); font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
  239- .offer .acts { grid-column: 1 / -1; display: flex; gap: 8px; }
  240: .offer .ai-line { grid-column: 1 / -1; }
  241- 
  242- /* ---------- AI components ---------- */
  243: .ai { border: 1px solid #b9dde1; background: linear-gradient(180deg, #f1f9fa, #fff); border-radius: 14px; padding: 16px 18px; position: relative; }
  244: .ai + .ai { margin-top: 12px; }
  245: .ai .ai-h { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  246: .ai .ai-h .chip { display: inline-flex; align-items: center; gap: 6px; background: var(--teal); color: #fff; font-family: var(--head); font-weight: 600; font-size: 11.5px; letter-spacing: .4px; border-radius: 20px; padding: 3px 10px; }
  247: .ai .ai-h .chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #9ff0f5; box-shadow: 0 0 0 3px rgba(159, 240, 245, .35); }
  248: .ai .ai-h h4 { font-size: 14.5px; }
  249: .ai .ai-h time { margin-left: auto; color: var(--muted); font-size: 12px; }
  250: .forecast-bar { height: 8px; margin: 8px 0 12px; overflow: hidden; border-radius: 8px; background: var(--line-2); }
  251: .forecast-bar span { display: block; height: 100%; border-radius: inherit; background: var(--teal); }
  252: .ai p { margin: 0 0 8px; font-size: 14.5px; }
  253: .ai ul { margin: 6px 0 0; padding-left: 18px; font-size: 14px; }
  254: .ai ul.pro li::marker { color: var(--ok); } .ai ul.con li::marker { color: var(--bad); }
  255: .ai .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 8px; }
  256: .ai .cols h5 { font-size: 12.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; }
  257: .ai-line { background: var(--teal-bg); border-radius: 8px; padding: 8px 12px; font-size: 13.5px; color: var(--ink-2); }
  258: .ai-line::before { content: "Gemma 4 · "; font-family: var(--head); font-weight: 600; color: var(--teal-2); }
  259- .verdict { font-family: var(--head); font-weight: 600; border-radius: 20px; padding: 2px 12px; font-size: 12.5px; }
  260- .verdict.uygun { background: var(--ok-bg); color: var(--ok); } .verdict.dikkat { background: var(--warn-bg); color: var(--warn); } .verdict.riskli { background: var(--bad-bg); color: var(--bad); }
  261- .skeleton { height: 12px; border-radius: 6px; background: linear-gradient(90deg, #e8eef2, #f5f8fa, #e8eef2); background-size: 200% 100%; animation: sk 1.2s linear infinite; margin: 8px 0; }
  300- .spin { display: inline-block; width: 14px; height: 14px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: s .8s linear infinite; vertical-align: -2px; }
  301- @keyframes s { to { transform: rotate(360deg); } }
  302- 
  303: @media (max-width: 980px) {
  304:   .hero .wrap, .aud-hero .wrap, .split, .grid-2, .grid-3, .notice, .posters, .benefits, footer.site .wrap, .login-wrap, .ai .cols { grid-template-columns: 1fr; }
  305-   .services, .steps, .kpis, .wizard { grid-template-columns: 1fr 1fr; }
  306-   .steps > div::after { display: none; }
  307-   .shell { grid-template-columns: 1fr; }
  317- /* legacy explanation box used by the upload wizard */
  318- .gemma { border: 1px solid #b9dde1; background: linear-gradient(180deg, #f1f9fa, #fff); border-radius: 12px; padding: 12px 14px; font-size: 14px; white-space: pre-wrap; }
  319- .gemma .by { display: block; font-family: var(--head); font-size: 11.5px; font-weight: 600; color: var(--teal-2); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .5px; }
  320: .ai .ai-h .chip { white-space: nowrap; flex: none; }
  321: .ai .ai-h h4 { flex: 1; min-width: 0; }
  322: .split > div, .shell > main { min-width: 0; }
  323- .offer > div { min-width: 0; }
  324- .offer .net { white-space: nowrap; }
  325- body { overflow-x: hidden; }

vadex.js (79 match(es)):
  93- }
  94- 
  95- async function render() {
  96:   const r = (location.hash || "#/").slice(2).split("#")[0];
  97:   const p = r.split("/");
  98-   S.ddOpen = false;
  99-   try {
  100-     if (["kobi", "finansor", "denetim", "bildirimler", "belge"].includes(p[0])) {
  110-   } catch (e) {
  111-     app.innerHTML = `<div class="wrap"><div class="panel" style="margin:40px 0"><div class="pb"><b>Bir hata oluştu.</b><p class="muted">${esc(e.message)}</p></div></div></div>`;
  112-   }
  113:   if (location.hash.includes("#surec") || location.hash.includes("#kontroller")) { const id = location.hash.split("#").pop(); document.getElementById(id)?.scrollIntoView(); }
  114-   else scrollTo(0, 0);
  115- }
  116- async function refreshNotes() { try { S.notes = await api("/notifications"); nav(); } catch { /* ignore */ } }
  312- const VERDICT = { uygun: "Uygun", dikkat: "Dikkat", riskli: "Riskli" };
  313- // minimal, safe markdown for model text: escape first, then **bold**, headings and bullet lists
  314- const md = t => {
  315:   const lines = esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n+/);
  316-   let out = "", inList = false;
  317-   for (const raw of lines) {
  318-     const l = raw.trim(); if (!l) continue;
  333- const invoiceInsight = (sel, id) => aiInto(sel, "Fatura değerlendirmesi", `/documents/${encodeURIComponent(id)}/insight`, r =>
  334-   `<p>${r.verdict ? `<span class="verdict ${esc(r.verdict)}">${VERDICT[r.verdict] || esc(r.verdict)}</span> ` : ""}</p>${md(r.summary)}
  335-    <div class="cols"><div><h5>Güçlü yönler</h5><ul class="pro">${(r.strengths || []).map(s => `<li>${esc(s)}</li>`).join("") || "<li>–</li>"}</ul></div><div><h5>Dikkat edilecekler</h5><ul class="con">${(r.concerns || []).map(s => `<li>${esc(s)}</li>`).join("") || "<li>–</li>"}</ul></div></div>`);
  336: const paymentProfile = (sel, vkn) => vkn && aiInto(sel, "Alıcının ödeme geçmişi", `/companies/${encodeURIComponent(vkn)}/payment-profile`, r => {
  337-   const s = r.stats || {}, h = [...(r.history || [])].reverse();
  338-   const max = Math.max(10, ...h.map(x => x.days_late || 0));
  339-   return `<dl class="kv" style="grid-template-columns:170px 1fr"><dt>Zamanında ödeme oranı</dt><dd><b>${s.on_time_ratio != null ? PCT(s.on_time_ratio) : "–"}</b></dd><dt>Ortalama gecikme</dt><dd>${s.avg_days_late != null ? (+s.avg_days_late).toFixed(1) + " gün" : "–"} · en fazla ${s.max_days_late ?? "–"} gün</dd><dt>Son 12 ay hacim</dt><dd>${TL0(s.volume_12m)}</dd></dl>
  340-     ${h.length ? `<div class="bars" title="Her çubuk bir ödeme: yükseklik gecikme günü">${h.map(x => `<span class="${x.days_late > 15 ? "vlate" : x.days_late > 5 ? "late" : ""}" style="height:${Math.max(4, (x.days_late || 0) / max * 100)}%" title="${esc(x.invoice_no)} · ${x.days_late} gün"></span>`).join("")}</div><div class="muted small">Son ${h.length} ödeme, soldan sağa eskiden yeniye · yükseklik = gecikme günü</div>` : ""}
  341-     <div style="margin-top:10px">${md(r.ai_comment)}</div>`;
  342- });
  343: async function delayForecast(sel, id) {
  344-   const el = $(sel); if (!el) return;
  345-   const title = "Ödeme gecikmesi tahmini · TabPFN";
  346-   const heading = model => `<div class="ai-h"><span class="chip">${esc(model || "TabPFN")}</span><h4>${esc(title)}</h4></div>`;
  347-   el.innerHTML = aiLoading(title);
  348-   try {
  349:     const r = await api(`/documents/${encodeURIComponent(id)}/delay-forecast`);
  350-     if (!$(sel)) return;
  351-     const delay = Number(r.expected_days_late), probability = Number(r.late_probability);
  352-     const safeDelay = Number.isFinite(delay) ? delay : null;
  354-     const bar = safeProbability == null ? 0 : safeProbability * 100;
  355-     $(sel).innerHTML = `<div class="ai">${heading(r.model)}<p><b>${safeDelay == null ? "–" : safeDelay.toFixed(1) + " gün"}</b> beklenen gecikme</p>
  356-       <div class="muted small">5 günden fazla gecikme olasılığı · ${safeProbability == null ? "–" : PCT(safeProbability)}</div>
  357:       <div class="forecast-bar" role="img" aria-label="Gecikme olasılığı ${safeProbability == null ? "bilinmiyor" : PCT(safeProbability)}"><span style="width:${bar}%"></span></div></div>`;
  358-   } catch (e) {
  359-     if ($(sel)) $(sel).innerHTML = `<div class="ai">${heading("TabPFN")}<p class="muted small">Tahmin şu an alınamadı: ${esc(e.message)}</p></div>`;
  360-   }
  477-         ${o.status === "beklemede" ? `<div class="ai-line" id="oc-${o.id}"><span class="skeleton" style="display:inline-block;width:60%;margin:0;vertical-align:middle"></span></div>` : ""}
  478-         ${o.status === "beklemede" && !["finanse_edildi", "reddedildi"].includes(d.status) ? `<div class="acts"><button class="btn primary sm" data-act="accept" data-id="${o.id}">Kabul et</button><button class="btn sm" data-act="reject" data-id="${o.id}">Reddet</button></div>` : ""}</div>`).join("")
  479-         : `<p class="muted" style="margin:0">${d.status === "incelemede" ? "Belge denetim incelemesinde. Onaylandıktan sonra pazara açılacak." : "Henüz teklif gelmedi. Teklif geldiğinde bildirim ve e-posta alacaksınız."}</p>`}
  480:       </div></div><div id="cmp" style="margin-bottom:18px"></div><div class="grid-2"><div id="pay"></div><div id="forecast"></div></div>`;
  481-   } else if (role === "finansor") {
  482-     const mine = offers.find(o => o.financier?.id === S.user.id && o.status === "beklemede");
  483:     right = `<div id="rr" style="margin-bottom:18px"></div><div class="grid-2" style="margin-bottom:18px"><div id="pay"></div><div id="forecast"></div></div>
  484-       <div class="panel"><div class="ph"><h3>${mine ? "Teklifinizi güncelleyin" : "Teklif ver"}</h3><span class="muted small">${offers.filter(o => o.status === "beklemede").length} aktif teklif</span></div><div class="pb">
  485-       ${["teklif_bekliyor", "teklif_var"].includes(d.status) ? `<form id="of"><div class="field"><label class="f" for="na">Ödenecek net tutar (TL)</label><input class="f" id="na" type="number" step="0.01" max="${d.total}" value="${mine ? mine.net_amount : ""}" required></div>
  486-         <div class="muted small" id="calc" style="margin:-6px 0 12px">Nominal ${TL(d.total)}</div><div class="field"><label class="f" for="nt">Not (isteğe bağlı)</label><textarea class="f" id="nt">${esc(mine?.note || "")}</textarea></div>
  493-   app.innerHTML = shell(back, `<a href="#/${back}">Geri</a> / ${esc(d.invoice_no)}`, d.invoice_no, esc(d.seller?.name) + " → " + esc(d.buyer?.name), `<div class="split"><div>${left}</div><div>${right}</div></div>`);
  494-   S.detailKey = id + ":" + offers.map(o => o.id + o.status + o.net_amount).join(",");
  495-   invoiceInsight("#ins", d.id);
  496:   paymentProfile("#pay", d.buyer?.vkn);
  497:   if (role === "kobi" || role === "finansor") delayForecast("#forecast", d.id);
  498-   if (role === "kobi" && offers.some(o => o.status === "beklemede")) {
  499-     aiInto("#cmp", "Teklif değerlendirmesi", `/documents/${encodeURIComponent(d.id)}/offers-insight`, r => {
  500-       (r.offers || []).forEach(o => { const el = $("#oc-" + o.offer_id); if (el) el.textContent = o.comment; });
  501-       return `<p><b>${esc(r.recommendation)}</b></p><div class="small">${md(r.reason)}</div>`;
  502:     }).then(() => document.querySelectorAll(".ai-line .skeleton").forEach(s => s.parentElement.textContent = "Bu teklif için ayrı yorum üretilmedi."));
  503-   }
  504-   if (role === "finansor") {
  505-     aiInto("#rr", "Risk raporu", `/documents/${encodeURIComponent(id)}/risk-report`, rr => {
  571-   svg.innerHTML = `<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#98a2b3"/></marker><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#b3261e"/></marker></defs>` +
  572-     edges.map(e => { const a = nodes[idx[e.source]], b = nodes[idx[e.target]], dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, x2 = b.x - dx / d * (b.r + 3), y2 = b.y - dy / d * (b.r + 3);
  573-       return `<line x1="${a.x}" y1="${a.y}" x2="${x2}" y2="${y2}" stroke="${e.flagged ? "#b3261e" : "#c3cad4"}" stroke-width="${e.flagged ? 2.2 : 1.2}" marker-end="url(#${e.flagged ? "arr" : "ar"})"><title>${esc(e.invoice_count)} fatura · ${esc(TL0(e.total))}</title></line>`; }).join("") +
  574:     nodes.map(n => `<g><circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${n.flagged ? "#b3261e" : n.exposed ? "#d97706" : "#17734a"}" fill-opacity=".85" stroke="#fff" stroke-width="2"><title>${esc(n.name)} · ${esc(n.sector)}${n.flagged ? " · yüksek riskli fatura kesiyor" : n.exposed ? " · yüksek riskli fatura almış" : ""} · ${esc(TL0(n.total))}</title></circle><text x="${n.x}" y="${n.y + n.r + 13}" text-anchor="middle" font-size="11" fill="#1b2430">${esc((n.name || "").split(" ").slice(0, 2).join(" "))}</text></g>`).join("");
  575- }
  576- async function ledger() {
  577-   const draw = async () => {
```

</details>


---

<sub>28s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.css.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.css (lines 180-370)

<details>
<summary>139 lines</summary>

```
.hint code { font-family: var(--mono); font-size: 12px; background: #fff; padding: 0 4px; border-radius: 3px; cursor: pointer; }
.err { color: var(--bad); font-size: 13.5px; margin-top: 10px; }
.secure { display: flex; gap: 8px; align-items: center; color: var(--muted); font-size: 12.5px; margin-top: 14px; }

/* ---------- app shell ---------- */
.shell { display: grid; grid-template-columns: 260px 1fr; min-height: calc(100vh - 118px); }
aside.side { border-right: 1px solid var(--line); background: var(--bg-2); padding: 20px 14px; display: flex; flex-direction: column; gap: 3px; }
aside.side .who { padding: 4px 12px 16px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
aside.side .who b { display: block; font-family: var(--head); font-size: 14.5px; color: var(--navy-2); line-height: 1.35; }
aside.side .who small { color: var(--muted); }
aside.side a { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 10px; text-decoration: none; color: var(--ink-2); font-family: var(--head); font-weight: 500; font-size: 14.5px; }
aside.side a:hover { background: #fff; color: var(--navy-2); }
aside.side a.on { background: #fff; color: var(--navy); box-shadow: var(--shadow-s), inset 3px 0 0 var(--teal); font-weight: 600; }
aside.side .count { background: var(--red); color: #fff; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 0 7px; }
aside.side .bottom { margin-top: auto; padding: 14px 12px 0; border-top: 1px solid var(--line); }
main.page { padding: 28px 34px 64px; min-width: 0; }
.crumbs { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.crumbs a { color: var(--muted); }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 22px; }
.page-head h1 { font-size: 26px; }
.page-head p { margin: 4px 0 0; color: var(--muted); }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.kpi { border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; background: #fff; box-shadow: var(--shadow-s); }
.kpi small { color: var(--muted); font-size: 12.5px; }
.kpi b { display: block; font-family: var(--head); font-size: 23px; color: var(--navy-2); font-weight: 600; margin-top: 2px; }
.panel { border: 1px solid var(--line); border-radius: 14px; background: #fff; margin-bottom: 18px; box-shadow: var(--shadow-s); }
.panel > .ph { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 20px; border-bottom: 1px solid var(--line); }
.panel > .ph h3 { font-size: 16px; }
.panel > .pb { padding: 20px; }
.split { display: grid; grid-template-columns: 1.35fr 1fr; gap: 18px; align-items: start; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; padding: 14px 20px; border-bottom: 1px solid var(--line); background: var(--bg-2); border-radius: 14px 14px 0 0; }
.filters .f { height: 40px; width: auto; min-width: 150px; flex: 1; }
table.data { width: 100%; border-collapse: collapse; font-size: 14px; }
table.data th { text-align: left; font-size: 12.5px; color: var(--muted); font-weight: 600; padding: 11px 16px; border-bottom: 1px solid var(--line); white-space: nowrap; }
table.data td { padding: 13px 16px; border-bottom: 1px solid var(--line-2); white-space: nowrap; }
table.data tr.go { cursor: pointer; }
table.data tr.go:hover td { background: var(--bg-2); }
table.data td.num, table.data th.num { text-align: right; font-variant-numeric: tabular-nums; }
.tw { overflow-x: auto; }
.empty { padding: 38px; text-align: center; color: var(--muted); }
dl.kv { display: grid; grid-template-columns: 150px 1fr; gap: 8px 14px; margin: 0; font-size: 14px; }
dl.kv dt { color: var(--muted); } dl.kv dd { margin: 0; }
.amount { font-family: var(--head); font-size: 30px; font-weight: 600; color: var(--navy-2); font-variant-numeric: tabular-nums; }

ol.tl { list-style: none; margin: 0; padding: 0; }
ol.tl li { display: grid; grid-template-columns: 28px 1fr; gap: 12px; padding-bottom: 16px; position: relative; }
ol.tl li:not(:last-child)::before { content: ""; position: absolute; left: 13px; top: 28px; bottom: 2px; width: 2px; background: var(--line); }
ol.tl .dot { width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--line); background: #fff; display: grid; place-items: center; font-size: 12px; font-weight: 700; color: var(--muted); }
ol.tl .done .dot { border-color: var(--ok); background: var(--ok); color: #fff; }
ol.tl .running .dot { border-color: var(--teal); color: var(--teal); }
ol.tl .failed .dot { border-color: var(--bad); background: var(--bad); color: #fff; }
ol.tl b { font-size: 14px; color: var(--navy-2); } ol.tl small { display: block; color: var(--muted); }
ul.flags { list-style: none; margin: 0; padding: 0; }
ul.flags li { border-left: 3px solid var(--warn); background: var(--warn-bg); padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0; font-size: 14px; }
ul.flags li.hi { border-left-color: var(--bad); background: var(--bad-bg); }
.offer { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 14px 0; border-bottom: 1px solid var(--line-2); align-items: center; }
.offer:last-child { border-bottom: 0; }
.offer b { color: var(--navy-2); }
.offer .net { font-family: var(--head); font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
.offer .acts { grid-column: 1 / -1; display: flex; gap: 8px; }
.offer .ai-line { grid-column: 1 / -1; }

/* ---------- AI components ---------- */
.ai { border: 1px solid #b9dde1; background: linear-gradient(180deg, #f1f9fa, #fff); border-radius: 14px; padding: 16px 18px; position: relative; }
.ai + .ai { margin-top: 12px; }
.ai .ai-h { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.ai .ai-h .chip { display: inline-flex; align-items: center; gap: 6px; background: var(--teal); color: #fff; font-family: var(--head); font-weight: 600; font-size: 11.5px; letter-spacing: .4px; border-radius: 20px; padding: 3px 10px; }
.ai .ai-h .chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #9ff0f5; box-shadow: 0 0 0 3px rgba(159, 240, 245, .35); }
.ai .ai-h h4 { font-size: 14.5px; }
.ai .ai-h time { margin-left: auto; color: var(--muted); font-size: 12px; }
.forecast-bar { height: 8px; margin: 8px 0 12px; overflow: hidden; border-radius: 8px; background: var(--line-2); }
.forecast-bar span { display: block; height: 100%; border-radius: inherit; background: var(--teal); }
.ai p { margin: 0 0 8px; font-size: 14.5px; }
.ai ul { margin: 6px 0 0; padding-left: 18px; font-size: 14px; }
.ai ul.pro li::marker { color: var(--ok); } .ai ul.con li::marker { color: var(--bad); }
.ai .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 8px; }
.ai .cols h5 { font-size: 12.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; }
.ai-line { background: var(--teal-bg); border-radius: 8px; padding: 8px 12px; font-size: 13.5px; color: var(--ink-2); }
.ai-line::before { content: "Gemma 4 · "; font-family: var(--head); font-weight: 600; color: var(--teal-2); }
.verdict { font-family: var(--head); font-weight: 600; border-radius: 20px; padding: 2px 12px; font-size: 12.5px; }
.verdict.uygun { background: var(--ok-bg); color: var(--ok); } .verdict.dikkat { background: var(--warn-bg); color: var(--warn); } .verdict.riskli { background: var(--bad-bg); color: var(--bad); }
.skeleton { height: 12px; border-radius: 6px; background: linear-gradient(90deg, #e8eef2, #f5f8fa, #e8eef2); background-size: 200% 100%; animation: sk 1.2s linear infinite; margin: 8px 0; }
@keyframes sk { to { background-position: -200% 0; } }
.bars { display: flex; align-items: flex-end; gap: 4px; height: 70px; margin: 10px 0 4px; }
.bars span { flex: 1; background: var(--ok); border-radius: 3px 3px 0 0; min-height: 3px; }
.bars span.late { background: var(--warn); } .bars span.vlate { background: var(--bad); }

/* upload wizard */
.wizard { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-bottom: 20px; }
.wizard div { display: flex; align-items: center; gap: 10px; font-family: var(--head); font-size: 13.5px; color: var(--muted); padding: 10px 6px; border-bottom: 3px solid var(--line); }
.wizard div b { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--line); color: var(--ink-2); font-size: 12.5px; }
.wizard div.on { color: var(--navy); font-weight: 600; border-bottom-color: var(--teal); }
.wizard div.on b { background: var(--teal); color: #fff; }
.wizard div.done { color: var(--ok); border-bottom-color: var(--ok); }
.wizard div.done b { background: var(--ok); color: #fff; }
.drop { display: block; border: 2px dashed #b9c6d3; border-radius: 16px; padding: 48px 20px; text-align: center; cursor: pointer; background: var(--bg-2); }
.drop:hover, .drop.over { border-color: var(--teal); background: var(--teal-bg); }
.drop b { display: block; font-family: var(--head); color: var(--navy-2); font-size: 17px; margin: 12px 0 4px; }
.filecard { display: grid; grid-template-columns: 96px 1fr; gap: 16px; align-items: center; }
.filecard img { width: 96px; height: 124px; object-fit: cover; object-position: top; border: 1px solid var(--line); border-radius: 6px; }
.items { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 6px; }
.items th, .items td { border-bottom: 1px solid var(--line-2); padding: 7px 8px; text-align: left; }
.items input { width: 100%; border: 1px solid var(--line); border-radius: 6px; height: 34px; padding: 0 8px; }
.risk { display: flex; align-items: center; gap: 16px; }
.risk .score { font-family: var(--head); font-size: 40px; font-weight: 700; font-variant-numeric: tabular-nums; }
.risk.A .score { color: var(--ok); } .risk.B .score { color: var(--warn); } .risk.C .score, .risk.D .score { color: var(--bad); }

.bell { position: relative; display: inline-flex; }
.bell .dot { position: absolute; top: 0; right: 0; background: var(--red); color: #fff; font-size: 10.5px; font-weight: 700; border-radius: 9px; padding: 0 5px; }
.dd { position: absolute; right: 0; top: 48px; width: 360px; background: #fff; border: 1px solid var(--line); border-radius: 12px; box-shadow: var(--shadow); z-index: 60; overflow: hidden; }
.dd .it { padding: 11px 14px; border-bottom: 1px solid var(--line-2); font-size: 13.5px; }
.dd .it.unread b { color: var(--navy); } .dd .it small { color: var(--muted); display: block; }
.net svg { width: 100%; height: 540px; background: var(--bg-2); border-radius: 0 0 14px 14px; }
.net .legend { display: flex; gap: 16px; font-size: 13px; color: var(--ink-2); }
.net .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }
.live { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ok); font-weight: 600; }
.live::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--ok); animation: pulse 1.6s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(21, 115, 71, .5); } 100% { box-shadow: 0 0 0 8px rgba(21, 115, 71, 0); } }
#toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); background: var(--navy-2); color: #fff; padding: 12px 20px; border-radius: 10px; font-size: 14px; opacity: 0; transition: opacity .2s; pointer-events: none; z-index: 80; }
#toast.on { opacity: 1; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: s .8s linear infinite; vertical-align: -2px; }
@keyframes s { to { transform: rotate(360deg); } }

@media (max-width: 980px) {
  .hero .wrap, .aud-hero .wrap, .split, .grid-2, .grid-3, .notice, .posters, .benefits, footer.site .wrap, .login-wrap, .ai .cols { grid-template-columns: 1fr; }
  .services, .steps, .kpis, .wizard { grid-template-columns: 1fr 1fr; }
  .steps > div::after { display: none; }
  .shell { grid-template-columns: 1fr; }
  aside.side { flex-direction: row; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  aside.side .who, aside.side .bottom { display: none; }
  .search, .topband .tb-links { display: none; }
  header.site .wrap { height: 72px; }
  main.page { padding: 18px 16px 48px; }
  .hero h1 { font-size: 32px; }
  .login-art { padding: 36px 24px; }
}

/* legacy explanation box used by the upload wizard */
.gemma { border: 1px solid #b9dde1; background: linear-gradient(180deg, #f1f9fa, #fff); border-radius: 12px; padding: 12px 14px; font-size: 14px; white-space: pre-wrap; }
.gemma .by { display: block; font-family: var(--head); font-size: 11.5px; font-weight: 600; color: var(--teal-2); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .5px; }
.ai .ai-h .chip { white-space: nowrap; flex: none; }
.ai .ai-h h4 { flex: 1; min-width: 0; }
.split > div, .shell > main { min-width: 0; }
.offer > div { min-width: 0; }
.offer .net { white-space: nowrap; }
body { overflow-x: hidden; }
```

</details>


---

<sub>28s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.js.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.js (lines 470-600)

<details>
<summary>127 lines</summary>

```
      <h4 style="margin:20px 0 10px;font-size:14px">Doğrulama adımları</h4>${timeline(d.steps)}
      ${d.flags?.length ? `<h4 style="margin:6px 0 10px;font-size:14px">Bulgular</h4><ul class="flags">${d.flags.map(fl => `<li class="${d.risk_score >= 60 ? "hi" : ""}"><b>${esc(fl.label)}</b> – ${esc(fl.detail)}</li>`).join("")}</ul>` : ""}</div></div>
      <div id="ins" style="margin-bottom:18px"></div>`;
  let right = "";
  if (role === "kobi") {
    right = `<div class="panel"><div class="ph"><h3>Gelen teklifler</h3><span class="muted small">${offers.length} teklif</span></div><div class="pb">
      ${offers.length ? [...offers].sort((a, b) => b.net_amount - a.net_amount).map((o, i) => `<div class="offer"><div><b>${esc(o.financier?.name)}</b> ${i === 0 && o.status === "beklemede" ? '<span class="badge ok">En yüksek</span>' : ""} ${o.status !== "beklemede" ? st(o.status) : ""}<div class="muted small">İskonto ${PCT(o.discount_rate)} · yıllık ${PCT(o.annual_rate)} · ${DT(o.created_at)}</div>${o.note ? `<div class="small">${esc(o.note)}</div>` : ""}</div><div class="net">${TL(o.net_amount)}</div>
        ${o.status === "beklemede" ? `<div class="ai-line" id="oc-${o.id}"><span class="skeleton" style="display:inline-block;width:60%;margin:0;vertical-align:middle"></span></div>` : ""}
        ${o.status === "beklemede" && !["finanse_edildi", "reddedildi"].includes(d.status) ? `<div class="acts"><button class="btn primary sm" data-act="accept" data-id="${o.id}">Kabul et</button><button class="btn sm" data-act="reject" data-id="${o.id}">Reddet</button></div>` : ""}</div>`).join("")
        : `<p class="muted" style="margin:0">${d.status === "incelemede" ? "Belge denetim incelemesinde. Onaylandıktan sonra pazara açılacak." : "Henüz teklif gelmedi. Teklif geldiğinde bildirim ve e-posta alacaksınız."}</p>`}
      </div></div><div id="cmp" style="margin-bottom:18px"></div><div class="grid-2"><div id="pay"></div><div id="forecast"></div></div>`;
  } else if (role === "finansor") {
    const mine = offers.find(o => o.financier?.id === S.user.id && o.status === "beklemede");
    right = `<div id="rr" style="margin-bottom:18px"></div><div class="grid-2" style="margin-bottom:18px"><div id="pay"></div><div id="forecast"></div></div>
      <div class="panel"><div class="ph"><h3>${mine ? "Teklifinizi güncelleyin" : "Teklif ver"}</h3><span class="muted small">${offers.filter(o => o.status === "beklemede").length} aktif teklif</span></div><div class="pb">
      ${["teklif_bekliyor", "teklif_var"].includes(d.status) ? `<form id="of"><div class="field"><label class="f" for="na">Ödenecek net tutar (TL)</label><input class="f" id="na" type="number" step="0.01" max="${d.total}" value="${mine ? mine.net_amount : ""}" required></div>
        <div class="muted small" id="calc" style="margin:-6px 0 12px">Nominal ${TL(d.total)}</div><div class="field"><label class="f" for="nt">Not (isteğe bağlı)</label><textarea class="f" id="nt">${esc(mine?.note || "")}</textarea></div>
        <button class="btn primary block" type="submit">${mine ? "Teklifi güncelle" : "Teklif ver"}</button>${mine ? `<button class="btn block" type="button" style="margin-top:8px" data-act="withdraw" data-id="${mine.id}">Teklifi geri çek</button>` : ""}<div class="err" id="oe"></div></form>`
        : '<p class="muted" style="margin:0">Bu belge teklife kapalı.</p>'}</div></div>`;
  } else {
    right = `<div class="panel"><div class="ph"><h3>Denetim kararı</h3></div><div class="pb">${d.status === "incelemede" ? `<div class="field"><label class="f" for="rs">Gerekçe</label><textarea class="f" id="rs" placeholder="Karar gerekçesi"></textarea></div><div style="display:flex;gap:8px"><button class="btn primary" data-act="review" data-v="approve" data-id="${esc(d.id)}">Onayla, pazara aç</button><button class="btn" data-act="review" data-v="reject" data-id="${esc(d.id)}">Reddet</button></div>` : `<p class="muted" style="margin:0">Belge durumu: ${st(d.status)}</p>`}</div></div><div id="pay"></div>`;
  }
  const back = { kobi: "kobi/belgeler", finansor: "finansor", denetim: "denetim" }[role];
  app.innerHTML = shell(back, `<a href="#/${back}">Geri</a> / ${esc(d.invoice_no)}`, d.invoice_no, esc(d.seller?.name) + " → " + esc(d.buyer?.name), `<div class="split"><div>${left}</div><div>${right}</div></div>`);
  S.detailKey = id + ":" + offers.map(o => o.id + o.status + o.net_amount).join(",");
  invoiceInsight("#ins", d.id);
  paymentProfile("#pay", d.buyer?.vkn);
  if (role === "kobi" || role === "finansor") delayForecast("#forecast", d.id);
  if (role === "kobi" && offers.some(o => o.status === "beklemede")) {
    aiInto("#cmp", "Teklif değerlendirmesi", `/documents/${encodeURIComponent(d.id)}/offers-insight`, r => {
      (r.offers || []).forEach(o => { const el = $("#oc-" + o.offer_id); if (el) el.textContent = o.comment; });
      return `<p><b>${esc(r.recommendation)}</b></p><div class="small">${md(r.reason)}</div>`;
    }).then(() => document.querySelectorAll(".ai-line .skeleton").forEach(s => s.parentElement.textContent = "Bu teklif için ayrı yorum üretilmedi."));
  }
  if (role === "finansor") {
    aiInto("#rr", "Risk raporu", `/documents/${encodeURIComponent(id)}/risk-report`, rr => {
      setTimeout(() => { const na = $("#na"); if (na && !na.value && rr.suggested_net_amount) { na.value = (+rr.suggested_net_amount).toFixed(2); na.dispatchEvent(new Event("input")); } });
      return `${md(rr.summary)}<dl class="kv"><dt>Önerilen iskonto</dt><dd><b>${PCT(rr.suggested_discount_rate)}</b></dd><dt>Önerilen net tutar</dt><dd>${TL(rr.suggested_net_amount)}</dd></dl>`;
    });
    const na = $("#na");
    if (na) {
      na.oninput = () => { const v = +na.value, disc = 1 - v / d.total, yr = disc / Math.max(1, d.days_left || 1) * 365; $("#calc").textContent = v ? (v > d.total ? "Teklif nominal tutarı aşamaz." : `İskonto ${PCT(disc)} · yıllık ${PCT(yr)} · vade sonunda kazanç ${TL(d.total - v)}`) : "Nominal " + TL(d.total); };
      $("#of").onsubmit = async e => { e.preventDefault(); try { await api("/offers", { method: "POST", body: { document_id: d.id, net_amount: +na.value, note: $("#nt").value } }); toast("Teklifiniz iletildi. KOBİ'ye bildirim gönderildi."); detail(id); } catch (err) { $("#oe").textContent = err.message; } };
    }
  }
}

// ---------- Finansör ----------
async function market() {
  const draw = async () => {
    const qs = qsOf({ q: $("#mq").value.trim(), risk: RISK_MAX[$("#mr").value], min: $("#mm").value, max_days: $("#md").value, sort: $("#ms").value });
    $("#lst").innerHTML = `<div class="empty">${spin}</div>`;
    const list = await api("/market?" + qs);
    $("#mk").innerHTML = kpis([["Açık belge", list.length], ["Toplam nominal", TL0(list.reduce((a, d) => a + (d.total || 0), 0))], ["Ortalama vade", list.length ? Math.round(list.reduce((a, d) => a + (d.days_left || 0), 0) / list.length) + " gün" : "–"], ["Teklifli belge", list.filter(d => d.offer_count).length]]);
    $("#lst").innerHTML = docTable(list, "market");
  };
  app.innerHTML = shell("finansor", "Panel / Fatura pazarı", "Fatura pazarı", "Doğrulanmış ve finansmana açılmış faturalar. Satırı seçerek risk raporunu görün ve teklif verin.",
    `<div id="dg" style="margin-bottom:18px"></div><div id="mk"></div><div class="panel"><div class="filters"><input class="f" id="mq" placeholder="Firma veya belge no"><select class="f" id="mr"><option value="">Tüm risk sınıfları</option><option value="A">A · düşük</option><option value="B">B · orta</option><option value="C">C · yüksek</option></select><input class="f" id="mm" type="number" placeholder="Min. tutar (TL)"><select class="f" id="md"><option value="">Tüm vadeler</option><option>30</option><option>60</option><option>90</option><option>120</option></select><select class="f" id="ms"><option value="amount">Tutara göre</option><option value="due">Vadeye göre</option></select></div><div id="lst"></div></div>`);
  ["mq", "mm"].forEach(i => $("#" + i).oninput = debounce(draw, 300));
  ["mr", "md", "ms"].forEach(i => $("#" + i).onchange = draw);
  takeSearch("#mq");
  digest("#dg");
  await draw();
}
const debounce = (f, ms) => { let t; return () => { clearTimeout(t); t = setTimeout(f, ms); }; };
async function myOffers() {
  const list = await api("/my/offers");
  app.innerHTML = shell("finansor/teklifler", "Panel / Tekliflerim", "Tekliflerim", "Verdiğiniz tekliflerin durumu.",
    `<div class="panel">${list.length ? `<div class="tw"><table class="data"><thead><tr><th>Belge</th><th>Satıcı</th><th class="num">Nominal</th><th class="num">Teklifim</th><th class="num">İskonto</th><th>Tarih</th><th>Durum</th></tr></thead><tbody>${list.map(o => `<tr class="go" data-go="belge/${esc(o.document_id)}"><td class="mono">${esc(o.document?.invoice_no)}</td><td>${esc(o.document?.seller?.name)}</td><td class="num">${TL0(o.document?.total)}</td><td class="num"><b>${TL0(o.net_amount)}</b></td><td class="num">${PCT(o.discount_rate)}</td><td>${DT(o.created_at)}</td><td>${st(o.status)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Henüz teklif vermediniz.</div>'}</div>`);
}
async function portfolio() {
  const p = await api("/portfolio");
  app.innerHTML = shell("finansor/portfoy", "Panel / Portföy", "Portföy", "Kazandığınız ve vadesinde tahsil edilecek alacaklar.",
    kpis([["Yatırılan", TL0(p.invested)], ["Beklenen tahsilat", TL0(p.expected_collection)], ["Beklenen kazanç", TL0(p.expected_profit)], ["İşlem sayısı", (p.documents || []).length]]) +
    `<div class="panel"><div class="ph"><h3>Finanse edilen belgeler</h3></div>${docTable(p.documents || [], "market")}</div>`);
}

// ---------- Denetim ----------
async function reviewQueue() {
  const list = await api("/review-queue");
  app.innerHTML = shell("denetim", "Denetim / İnceleme kuyruğu", "İnceleme kuyruğu", "Risk puanı 60 ve üzeri olan belgeler pazara açılmadan önce burada incelenir.",
    `<div id="dg" style="margin-bottom:18px"></div><div class="panel">${docTable(list, "market")}</div>`);
  digest("#dg");
}
async function network() {
  app.innerHTML = shell("denetim/ag", "Denetim / Fatura ağı analizi", "Fatura ağı analizi", "Firmalar arası fatura akışı. Döngüsel zincirler, paravan şirketler ve fatura simsarları kırmızıyla işaretlenir.",
    `<div class="panel net"><div class="ph"><div class="legend"><span><i style="background:#17734a"></i>Temiz</span><span><i style="background:#b3261e"></i>Yüksek riskli fatura kesen</span><span><i style="background:#d97706"></i>Yüksek riskli fatura alan</span><span class="muted">Daire boyutu: kesilen fatura toplamı</span></div><button class="btn sm" data-act="netreport">Gemma ağ raporu</button></div><div id="nr"></div><svg id="g" role="img" aria-label="Fatura ağı grafiği"></svg></div>`);
  const g = await api("/network");
  drawGraph($("#g"), g);
}
function drawGraph(svg, g) {
  const W = svg.clientWidth || 900, H = 520, nodes = g.nodes.map(n => ({ ...n })), idx = Object.fromEntries(nodes.map((n, i) => [n.id, i]));
  const edges = g.edges.filter(e => e.source in idx && e.target in idx);
  const max = Math.max(...nodes.map(n => n.total || 1));
  nodes.forEach((n, i) => { const a = i / nodes.length * Math.PI * 2; n.x = W / 2 + Math.cos(a) * W / 3.2; n.y = H / 2 + Math.sin(a) * H / 3.2; n.r = 8 + 22 * Math.sqrt((n.total || 1) / max); });
  for (let it = 0; it < 300; it++) {           // tiny force layout
    for (const a of nodes) for (const b of nodes) if (a !== b) { const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + .01, f = 2600 / d2; a.x += dx * f * .01; a.y += dy * f * .01; }
    for (const e of edges) { const a = nodes[idx[e.source]], b = nodes[idx[e.target]], dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 150) * .004; a.x += dx / d * f * d * .1; a.y += dy / d * f * d * .1; b.x -= dx / d * f * d * .1; b.y -= dy / d * f * d * .1; }
    for (const n of nodes) { n.x += (W / 2 - n.x) * .004; n.y += (H / 2 - n.y) * .004; n.x = Math.max(n.r + 4, Math.min(W - n.r - 4, n.x)); n.y = Math.max(n.r + 14, Math.min(H - n.r - 18, n.y)); }
  }
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#98a2b3"/></marker><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#b3261e"/></marker></defs>` +
    edges.map(e => { const a = nodes[idx[e.source]], b = nodes[idx[e.target]], dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, x2 = b.x - dx / d * (b.r + 3), y2 = b.y - dy / d * (b.r + 3);
      return `<line x1="${a.x}" y1="${a.y}" x2="${x2}" y2="${y2}" stroke="${e.flagged ? "#b3261e" : "#c3cad4"}" stroke-width="${e.flagged ? 2.2 : 1.2}" marker-end="url(#${e.flagged ? "arr" : "ar"})"><title>${esc(e.invoice_count)} fatura · ${esc(TL0(e.total))}</title></line>`; }).join("") +
    nodes.map(n => `<g><circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${n.flagged ? "#b3261e" : n.exposed ? "#d97706" : "#17734a"}" fill-opacity=".85" stroke="#fff" stroke-width="2"><title>${esc(n.name)} · ${esc(n.sector)}${n.flagged ? " · yüksek riskli fatura kesiyor" : n.exposed ? " · yüksek riskli fatura almış" : ""} · ${esc(TL0(n.total))}</title></circle><text x="${n.x}" y="${n.y + n.r + 13}" text-anchor="middle" font-size="11" fill="#1b2430">${esc((n.name || "").split(" ").slice(0, 2).join(" "))}</text></g>`).join("");
}
async function ledger() {
  const draw = async () => {
    const qs = qsOf({ company: $("#lc").value.trim(), action: $("#la").value, from: $("#lf1").value, to: $("#lt").value });
    $("#csv").href = "/api/audit.csv?" + qs;
    const rows = await api("/audit?" + qs);
    $("#lst").innerHTML = rows.length ? `<div class="tw"><table class="data"><thead><tr><th>Zaman</th><th>Kullanıcı</th><th>Firma</th><th>IP</th><th>İşlem</th><th>Dosya</th><th>SHA-256</th><th>Belge no</th></tr></thead><tbody>${rows.map(r => `<tr><td>${DT(r.at)}</td><td>${esc(r.username)}</td><td>${esc(r.company)}</td><td class="mono">${esc(r.ip_address)}</td><td><span class="badge">${esc(r.action)}</span></td><td>${esc(r.file_name)}</td><td class="mono" title="${esc(r.sha256)}">${short(r.sha256)}</td><td class="mono">${esc(r.invoice_no)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Kayıt yok.</div>';
  };
  app.innerHTML = shell("denetim/kayit", "Denetim / Kayıt defteri", "Kayıt defteri", "Platformdaki tüm işlemler; kullanıcı, zaman, IP ve dosya özetiyle.",
    `<div class="panel"><div class="filters"><input class="f" id="lc" placeholder="Firma VKN"><select class="f" id="la"><option value="">Tüm işlemler</option>${["login", "login_failed", "logout", "upload", "duplicate_upload", "extract", "offer_created", "offer_accepted", "offer_rejected", "transfer_mock"].map(a => `<option>${a}</option>`).join("")}</select><input class="f" id="lf1" type="date"><input class="f" id="lt" type="date"><a class="btn" id="csv" href="/api/audit.csv">CSV indir</a></div><div id="lst"></div></div>`);
  ["lc"].forEach(i => $("#" + i).oninput = debounce(draw, 300));
  ["la", "lf1", "lt"].forEach(i => $("#" + i).onchange = draw);
  takeSearch("#lc");
  await draw();
}

// ---------- notifications ----------
async function notifications() {
  await refreshNotes();
  const cur = "bildirimler";
  app.innerHTML = shell(cur, "Panel / Bildirimler", "Bildirimler", "Teklif, doğrulama ve ödeme bildirimleri. E-posta kopyaları kayıtlı adresinize gönderilir (demoda simülasyon).",
    `<div class="panel">${S.notes.length ? S.notes.map(n => `<div class="offer"><div><b style="${n.read ? "font-weight:500" : ""}">${esc(n.subject)}</b><div class="small">${esc(n.body)}</div><div class="muted small">${DT(n.created_at)}</div></div>${n.read ? "" : '<span class="badge info">Yeni</span>'}</div>`).join("").replace(/^/, '<div class="pb">') + "</div>" : '<div class="empty">Bildirim yok.</div>'}</div>`);
  if (unread()) { try { await api("/notifications/read", { method: "POST" }); S.notes.forEach(n => n.read = true); nav(); } catch { /* ignore */ } }
}

const ROUTES = {
```

</details>


---

<sub>28s</sub>

### `rg`

**TestClient|lifespan|forecast_delay|_models|_MODELS**

"TestClient|lifespan|forecast_delay|_models|_MODELS" (tests, server.py, forecast.py)

<details>
<summary>106 matches</summary>

```
[grep content: 26 matches across 5 file(s)]

server.py (4 match(es)):
  34- 
  35- @asynccontextmanager
  36: async def lifespan(application):
  37-     db.init_db()
  38-     UPLOADS.mkdir(parents=True, exist_ok=True)
  40- 
  41- 
  42: app = FastAPI(title="VadeX API", lifespan=lifespan)
  43- app.add_middleware(
  44-     SessionMiddleware,
  655-     total = float(document.get("total") or 0)
  656-     buyer_data = mocks.buyer_credit_score(invoice.get("buyer_vkn"))
  657:     delay_forecast = forecast.forecast_delay(
  658-         invoice.get("buyer_vkn"),
  659-         total,
  698-     if not buyer_vkn or not due_date:
  699-         raise HTTPException(422, "Faturada alıcı veya vade tarihi bulunamadı.")
  700:     return forecast.forecast_delay(
  701-         buyer_vkn,
  702-         float(document.get("total") or invoice.get("total") or 0),

forecast.py (13 match(es)):
  19-     "days_since_previous_payment",
  20- )
  21: _MODELS = None
  22: _MODELS_LOCK = threading.Lock()
  23- 
  24- 
  123- 
  124- 
  125: def _fit_models(rows):
  126-     try:
  127-         from tabpfn import TabPFNClassifier, TabPFNRegressor
  165- 
  166- 
  167: def _models():
  168:     global _MODELS
  169:     if _MODELS is None:
  170:         with _MODELS_LOCK:
  171:             if _MODELS is None:
  172-                 rows = build_training_table(_load_history(), _load_companies())
  173:                 _MODELS = (*_fit_models(rows), len(rows))
  174:     return _MODELS
  175- 
  176- 
  177: def forecast_delay(buyer_vkn, amount, due_date):
  178-     """Predict late days and the chance of a payment being over five days late."""
  179-     due_date = date.fromisoformat(str(due_date)[:10])
  196-         _load_companies(),
  197-     )
  198:     regressor, classifier, n_train = _models()
  199-     prediction = float(regressor.predict(_feature_frame([features]))[0])
  200-     classes = list(classifier.classes_)
  227-     training = [row for row in rows if row["due_date"] < split_date]
  228-     testing = [row for row in rows if row["due_date"] >= split_date]
  229:     regressor, classifier = _fit_models(training)
  230-     test_features = _feature_frame([row["features"] for row in testing])
  231-     predictions = regressor.predict(test_features)

tests/test_ai.py (3 match(es)):
  4- 
  5- import pytest
  6: from fastapi.testclient import TestClient
  7- 
  8- import db
  23-     monkeypatch.setattr(server.repo_ai, "ROOT", tmp_path)
  24-     server.repo_ai.clear_ai_cache()
  25:     monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
  26-         "expected_days_late": 2.5,
  27-         "late_probability": 0.1,
  94-     )
  95-     monkeypatch.setattr(server.gemma, "suspicious_network_report", lambda graph: "Ağ özeti.")
  96:     with TestClient(server.app) as test_client:
  97-         yield test_client, insight_calls
  98- 

tests/test_api.py (3 match(es)):
  4- 
  5- import pytest
  6: from fastapi.testclient import TestClient
  7- 
  8- import db
  46-     monkeypatch.setattr(server.gemma, "compare_offers", lambda offers: {"recommendation": "Teklif 1", "reason": "En yüksek net tutar."})
  47-     monkeypatch.setattr(server.gemma, "risk_report", lambda invoice, buyer: {"summary": "Düşük risk."})
  48:     monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
  49-         "expected_days_late": 2.5,
  50-         "late_probability": 0.1,
  54-     })
  55-     monkeypatch.setattr(server.gemma, "suspicious_network_report", lambda graph: "Ağ raporu.")
  56:     with TestClient(server.app) as test_client:
  57-         yield test_client
  58- 

tests/test_forecast.py (3 match(es)):
  72-     monkeypatch.setattr(
  73-         forecast,
  74:         "_fit_models",
  75-         lambda training: (_MetricRegressor(), _MetricClassifier()),
  76-     )
  87- def test_tabpfn_forecast_on_synthetic_table(monkeypatch):
  88-     pytest.importorskip("tabpfn", reason="TabPFN is not installed; install requirements.txt to run model tests.")
  89:     monkeypatch.setattr(forecast, "_MODELS", None)
  90-     monkeypatch.setattr(forecast, "_load_history", _payments)
  91-     monkeypatch.setattr(forecast, "_load_companies", _companies)
  92- 
  93:     result = forecast.forecast_delay("buyer-1", 2500, "2026-02-15")
  94- 
  95-     assert result["model"] == "TabPFN"
```

</details>


---

<sub>30s</sub>

### `devrelay-gateway-search_dev_to_semantic`

**FastAPI background thread model warmup startup readiness blocking startup failure model unavailable**

<details>
<summary>Arguments</summary>

```json
{
  "query": "FastAPI background thread model warmup startup readiness blocking startup failure model unavailable",
  "per_page": 10
}
```

</details>

```
{"Ok":[{"id":3557800,"title":"Managing Background Tasks in FastAPI: From Basic to Production-Ready Beyond Fire and Forget","description":"Handling Background Tasks in FastAPI: From Basic to Production-Ready When you build a web API, some...","tags":["api","backend","python","tutorial"],"path":"/richard_quaicoe_2398278be/managing-background-tasks-in-fastapi-from-basic-to-production-ready-beyond-fire-and-forget-ddm","url":"https://dev.to/richard_quaicoe_2398278be/managing-background-tasks-in-fastapi-from-basic-to-production-ready-beyond-fire-and-forget-ddm","score":1.0},{"id":4817468,"title":"A Cold-Start Ledger for Shipping One Indie Route on a Free Server","description":"A solo API earns a free-server deploy only when process startup does no network I/O, starts no...","tags":["python","tutorial","webdev","ai"],"path":"/hackcpp_3619/a-cold-start-ledger-for-shipping-one-indie-route-on-a-free-server-1db5","url":"https://dev.to/hackcpp_3619/a-cold-start-ledger-for-shipping-one-indie-route-on-a-free-server-1db5","score":1.0},{"id":4142743,"title":"Why Your FastAPI App Works Locally But Fails in Production","description":"FastAPI works locally but fails in production? The five usual causes: Uvicorn workers, QueuePool limits, event loop blocking, and Docker CPU limits.","tags":["softwaredevelopment","backend","production","fastapi"],"path":"/ayush_kumar_085a0f2c54e3f/why-your-fastapi-app-works-locally-but-fails-in-production-1l4d","url":"https://dev.to/ayush_kumar_085a0f2c54e3f/why-your-fastapi-app-works-locally-but-fails-in-production-1l4d","score":1.0},{"id":4142776,"title":"FastAPI Lifespan vs Startup Events: The Mistake That Breaks Async Apps","description":"Stop using @app.on_event. Learn how to use FastAPI's new Lifespan Context Managers to handle async database connections and resource cleanup correctly","tags":["refactoring","python","cleancode","fastapi"],"path":"/ayush_kumar_085a0f2c54e3f/fastapi-lifespan-vs-startup-events-the-mistake-that-breaks-async-apps-2e9m","url":"https://dev.to/ayush_kumar_085a0f2c54e3f/fastapi-lifespan-vs-startup-events-the-mistake-that-breaks-async-apps-2e9m","score":1.0},{"id":3999143,"title":"The warmup engine that worked perfectly and did nothing","description":"The bug that broke my warmup engine was not a missing save call. That is the obvious culprit when...","tags":["backend","devjournal","programming","softwareengineering"],"path":"/arihantdeva/the-warmup-engine-that-worked-perfectly-and-did-nothing-1203","url":"https://dev.to/arihantdeva/the-warmup-engine-that-worked-perfectly-and-did-nothing-1203","score":1.0},{"id":4142828,"title":"Why FastAPI Apps Slow Down Over Time (Low CPU, High Latency Explained)","description":"Why FastAPI apps slow down over time: how session leaks and blocking code cause high latency while CPU stays low, and how to fix it for good.","tags":["technology","performance","database","performanceoptimization"],"path":"/ayush_kumar_085a0f2c54e3f/why-fastapi-apps-slow-down-over-time-low-cpu-high-latency-explained-1859","url":"https://dev.to/ayush_kumar_085a0f2c54e3f/why-fastapi-apps-slow-down-over-time-low-cpu-high-latency-explained-1859","score":1.0},{"id":4767368,"title":"AI API call hangs in production, then 504: timeouts and budgets","description":"We read 1,662 public posts from builders whose apps broke at or after launch and verified 215 recent...","tags":["openai","nextjs","webdev","ai"],"path":"/gemmein/ai-api-call-hangs-in-production-then-504-timeouts-and-budgets-1bel","url":"https://dev.to/gemmein/ai-api-call-hangs-in-production-then-504-timeouts-and-budgets-1bel","score":1.0},{"id":4865956,"title":"Four Anti-Patterns That Live at the Model Boundary","description":"Most AI features do not fail inside the model. They fail at the seam between model output and your...","tags":["ai","python","testing","architecture"],"path":"/codex_1135/four-anti-patterns-that-live-at-the-model-boundary-3cl2","url":"https://dev.to/codex_1135/four-anti-patterns-that-live-at-the-model-boundary-3cl2","score":1.0},{"id":4818618,"title":"From Thread to Task: Modern Concurrency Patterns","description":"While conventional OS threading models offer raw parallel execution, modern programming languages...","tags":["architecture","go","programming","softwareengineering"],"path":"/lorishu/from-thread-to-task-modern-concurrency-patterns-2oi3","url":"https://dev.to/lorishu/from-thread-to-task-modern-concurrency-patterns-2oi3","score":1.0},{"id":4639141,"title":"Under the Hood of FastAPI’s DI Engine: Signature Reflection, Execution Graphs, and Async Exit Stacks","description":"Dependency Injection (DI) in modern web frameworks is often treated as syntactic magic. In FastAPI,...","tags":["python","fastapi","architecture","backend"],"path":"/niraj_matere/under-the-hood-of-fastapis-di-engine-signature-reflection-execution-graphs-and-async-exit-stacks-2f5p","url":"https://dev.to/niraj_matere/under-the-hood-of-fastapis-di-engine-signature-reflection-execution-graphs-and-async-exit-stacks-2f5p","score":1.0}]}
```


---

<sub>28s</sub>

### `devrelay-gateway-get_article_content`

<details>
<summary>Arguments</summary>

```json
{
  "id": 3952946
}
```

</details>

```
{"Ok":"Para 1 — The problem\n  \"Most ML tutorials end at model.fit(). \n   Getting a model into production is a completely \n   different skill. Here's how I built a real async \n   inference microservice.\"\n\nPara 2 — Architecture diagram\n  Paste the ASCII diagram from your ARCHITECTURE.md\n\nPara 3 — The three components\n  FastAPI handles HTTP (why async matters)\n  Celery handles background work (why not just threads)\n  Redis handles both queue and results (why one service)\n\nPara 4 — Key code snippet (predict_async endpoint)\n  Show 15 lines of code — the async endpoint that \n  dispatches to Celery and returns task_id immediately\n\nPara 5 — Testing strategy\n  \"I used in-memory Celery eager mode so tests \n   run without Redis. Here's the conftest pattern.\"\n  Show 10 lines of conftest.py\n\nPara 6 — The result\n  Screenshot of the UI dashboard\n  Screenshot of 47 tests passing\n\nClosing line:\n  \"If you want the full source code with Docker, \n   CI pipeline, Postman collection and deployment \n   guide, I packaged it here: [Gumroad link]\""}
```


---

<sub>30s</sub>

### `devrelay-gateway-get_article_content`

<details>
<summary>Arguments</summary>

```json
{
  "id": 3828372
}
```

</details>

```
{"Ok":"Everyone talks about building ML models. Nobody talks about what happens after.\nYou've trained your model, hit a decent accuracy score, and it works beautifully in your notebook. Then you try to deploy it — and everything falls apart in ways no tutorial prepared you for.\nI've been building and deploying ML systems in production for the past year, and here's what I wish someone had told me earlier.\n\n**1. Your Model is the Easy Part**\nThe model itself is maybe 20% of the work. The other 80% is everything around it — API design, data validation, error handling, and keeping the whole thing alive under real traffic.\n**Lesson:** Treat your deployment stack with the same rigor you treat your model.\n\n**2. Latency Will Surprise You**\nYour model runs in 200ms on your machine. Now add network overhead, cold starts, and concurrent requests — suddenly you're at 2 seconds, and users are complaining.\n**Lesson:** Benchmark early. Use async where possible. Cache aggressively.\n\n**3. Input Data in Production is Messy**\nIn training, your data is clean. In production, users will send you anything — missing fields, wrong types, empty strings. Your model won't fail gracefully.\n**Lesson:** Validate everything at the API boundary before it touches your model. Pydantic with FastAPI makes this effortless.\n\n**4. You Need Logs More Than You Think**\nWhen something breaks at 2 am — and it will — you need to know what input triggered it and what the model returned. Without structured logging, you're debugging blind.\n**Lesson:** Log before you need it, not after something breaks.\n\n**Final Thoughts**\nThe gap between a working notebook and a reliable deployed system is enormous — and most of that gap isn't about ML at all. It's about software engineering fundamentals applied to a non-deterministic system.\nBuild accordingly.\n_What's caught you off guard in production? Drop it in the comments._"}
```


---

<sub>49s</sub>

### `devrelay-gateway-get_comments`

<details>
<summary>Arguments</summary>

```json
{
  "article_id": 3828372,
  "page": 1
}
```

</details>

```
{"Ok":[]}
```


---

<sub>49s</sub>

### `devrelay-gateway-get_comments`

<details>
<summary>Arguments</summary>

```json
{
  "article_id": 3952946,
  "page": 1
}
```

</details>

```
{"Ok":[]}
```


---

<sub>48s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\test_api.py.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\test_api.py (lines 1-70)

<details>
<summary>62 lines</summary>

```
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    source_root = Path(server.__file__).resolve().parent
    invoices = json.loads((source_root / "data" / "invoices.json").read_text(encoding="utf-8"))
    demo_uploads = json.loads((source_root / "data" / "demo_uploads.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(server.repo_api, "ROOT", tmp_path)
    monkeypatch.setattr(server.repo_api, "DEMO_UPLOAD_NUMBERS", {item["invoice_no"] for item in demo_uploads})
    monkeypatch.setattr(server.repo_api, "COMPANIES", [
        {"vkn": "9200000101", "name": "Hazar Tekstil Atölyesi Ltd. Şti.", "sector": "tekstil", "employees": 18, "founded": 2015, "address": "Elazığ", "type": "sme"},
        {"vkn": "9100000011", "name": "Anadolu Market Zinciri A.Ş.", "sector": "perakende", "employees": 4200, "founded": 1998, "address": "Merkez", "type": "buyer"},
    ])
    monkeypatch.setattr(server.repo_api, "COMPANY_BY_VKN", {
        item["vkn"]: item for item in server.repo_api.COMPANIES
    })
    monkeypatch.setattr(server.repo_api, "load_invoices", lambda: invoices)
    monkeypatch.setattr(server.gemma, "extract_invoice", lambda image, name: {
        "invoice_no": "API-TEST-001",
        "issue_date": "2026-10-01",
        "due_date": "2026-12-01",
        "seller_vkn": "9200000101",
        "seller_name": "Hazar Tekstil Atölyesi Ltd. Şti.",
        "buyer_vkn": "9100000011",
        "buyer_name": "Anadolu Market Zinciri A.Ş.",
        "items": [{"description": "kumaş", "unit": "metre", "quantity": 10, "unit_price": 100}],
        "subtotal": 1000,
        "kdv": 200,
        "total": 1200,
        "irsaliye_no": "IRS-1",
        "buyer_approved": True,
    })
    monkeypatch.setattr(server.gemma, "explain_flags", lambda invoice, flags: "İnsan incelemesi gerekir.")
    monkeypatch.setattr(server.gemma, "compare_offers", lambda offers: {"recommendation": "Teklif 1", "reason": "En yüksek net tutar."})
    monkeypatch.setattr(server.gemma, "risk_report", lambda invoice, buyer: {"summary": "Düşük risk."})
    monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
        "expected_days_late": 2.5,
        "late_probability": 0.1,
        "model": "TabPFN",
        "n_train": 10,
        "features": {},
    })
    monkeypatch.setattr(server.gemma, "suspicious_network_report", lambda graph: "Ağ raporu.")
    with TestClient(server.app) as test_client:
        yield test_client


def login(client, role, username):
    response = client.post("/api/login", json={
        "role": role, "username": username, "password": "demo1234",
    })
    assert response.status_code == 200, response.text
    return response.json()["user"]


def test_login_for_each_role(client):
    for role, username in (
        ("kobi", "9200000101"),
```

</details>


---

<sub>48s</sub>

### `view`

**view the file at C:\Users\omres\OneDrive\Desktop\hf26-elazig\requirements.txt.**

C:\Users\omres\OneDrive\Desktop\hf26-elazig\requirements.txt

<details>
<summary>12 lines</summary>

```
networkx>=3.4
pypdfium2>=4.30
pyvis>=0.3.2
requests>=2.32
streamlit>=1.40
fastapi>=0.115
uvicorn>=0.30
python-multipart>=0.0.12
itsdangerous>=2.2
httpx>=0.27
pytest>=8.0
tabpfn>=9.1.0,<10
```

</details>


---

<sub>48s</sub>

### `rg`

**playwright|selenium|beautifulsoup|httpx|pytest**

"playwright|selenium|beautifulsoup|httpx|pytest" (pyproject.toml, requirements.txt, pytest.ini, setup.cfg, package.json, tests)

<details>
<summary>21 matches</summary>

```
requirements.txt:10:httpx>=0.27
requirements.txt:11:pytest>=8.0
tests\test_security.py:61:    first = db.create_upload(user, "VKN-9", "127.0.0.1", "pytest", "invoice.png", bytes_payload)
tests\test_security.py:62:    second = db.create_upload(user, "VKN-9", "127.0.0.1", "pytest", "invoice-copy.png", bytes_payload)
tests\test_gemma.py:4:import pytest
tests\test_gemma.py:82:    with pytest.raises(ValueError, match="görsele dönüştürülemedi"):
tests\test_forecast.py:4:import pytest
tests\test_forecast.py:44:    assert fourth["previous_3_avg_days_late"] == pytest.approx((8 + 0 + 8) / 3)
tests\test_forecast.py:88:    pytest.importorskip("tabpfn", reason="TabPFN is not installed; install requirements.txt to run model tests.")
tests\test_forecast.py:99:    assert result["features"]["previous_3_avg_days_late"] == pytest.approx((0 + 8 + 0) / 3)
tests\test_db.py:7:import pytest
tests\test_db.py:49:        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
tests\test_db.py:52:        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
tests\conftest.py:5:import pytest
tests\conftest.py:10:@pytest.fixture(autouse=True)
tests\test_api.py:5:import pytest
tests\test_api.py:12:@pytest.fixture
tests\test_ai.py:5:import pytest
tests\test_ai.py:12:@pytest.fixture
tests\test_ai.py:176:    assert offers_body["offers"][0]["annual_rate"] == pytest.approx(

(Warning: Some search paths were skipped because they do not exist: pyproject.toml, pytest.ini, setup.cfg, package.json)
```

</details>


---

<sub>1m 0s</sub>

### Copilot

The overflow comes from nesting the payment and forecast cards in a two-column grid inside an already narrow detail-page column. I’ll render those card containers directly in a vertical stack and move TabPFN model fitting into a daemon thread launched by FastAPI lifespan; the test fixture will replace that startup target so tests never load TabPFN.

---

<sub>1m 0s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [x] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [ ] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [ ] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [ ] Run targeted checks and the requested pytest suite\n- [ ] Commit the completed changes without pushing"
}
```

</details>

```
TODO list updated
```


---

<sub>1m 5s</sub>

### `apply_patch`

<details>
<summary>Arguments</summary>

```json
"*** Begin Patch\n*** Update File: web/vadex.js\n@@\n-      </div></div><div id=\"cmp\" style=\"margin-bottom:18px\"></div><div class=\"grid-2\"><div id=\"pay\"></div><div id=\"forecast\"></div></div>`;\n+      </div></div><div id=\"cmp\" style=\"margin-bottom:18px\"></div><div id=\"pay\" style=\"margin-bottom:18px\"></div><div id=\"forecast\" style=\"margin-bottom:18px\"></div>`;\n@@\n-    right = `<div id=\"rr\" style=\"margin-bottom:18px\"></div><div class=\"grid-2\" style=\"margin-bottom:18px\"><div id=\"pay\"></div><div id=\"forecast\"></div></div>\n+    right = `<div id=\"rr\" style=\"margin-bottom:18px\"></div><div id=\"pay\" style=\"margin-bottom:18px\"></div><div id=\"forecast\" style=\"margin-bottom:18px\"></div>\n*** Update File: web/vadex.css\n@@\n-.split { display: grid; grid-template-columns: 1.35fr 1fr; gap: 18px; align-items: start; }\n+.split { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 18px; align-items: start; }\n*** Update File: web/index.html\n@@\n-<link rel=\"stylesheet\" href=\"/vadex.css?v=6\">\n+<link rel=\"stylesheet\" href=\"/vadex.css?v=7\">\n@@\n-<script src=\"/vadex.js?v=6\"></script>\n+<script src=\"/vadex.js?v=7\"></script>\n*** Update File: forecast.py\n@@\n \"\"\"TabPFN payment-delay forecasts from the audited payment history.\"\"\"\n import json\n+import logging\n import math\n import threading\n@@\n _MODELS = None\n _MODELS_LOCK = threading.Lock()\n+logger = logging.getLogger(__name__)\n@@\n def _models():\n@@\n     return _MODELS\n \n \n+def warmup_models():\n+    \"\"\"Load TabPFN in the background; forecasts can retry if initialization fails.\"\"\"\n+    try:\n+        _models()\n+    except Exception:\n+        logger.exception(\"TabPFN warm-up failed; forecasts will retry model initialization.\")\n+\n+\n def forecast_delay(buyer_vkn, amount, due_date):\n*** Update File: server.py\n@@\n import re\n import secrets\n+import threading\n import uuid\n@@\n async def lifespan(application):\n     db.init_db()\n     UPLOADS.mkdir(parents=True, exist_ok=True)\n+    threading.Thread(\n+        target=forecast.warmup_models,\n+        name=\"tabpfn-warmup\",\n+        daemon=True,\n+    ).start()\n     yield\n*** Update File: tests/conftest.py\n@@\n import pytest\n \n import gemma\n+import server\n+\n+\n+@pytest.fixture(autouse=True)\n+def disable_tabpfn_warmup(monkeypatch):\n+    monkeypatch.setattr(server.forecast, \"warmup_models\", lambda: None)\n \n \n @pytest.fixture(autouse=True)\n*** End Patch"
```

</details>

```
Modified 6 file(s): C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.js, C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\vadex.css, C:\Users\omres\OneDrive\Desktop\hf26-elazig\web\index.html, C:\Users\omres\OneDrive\Desktop\hf26-elazig\forecast.py, C:\Users\omres\OneDrive\Desktop\hf26-elazig\server.py, C:\Users\omres\OneDrive\Desktop\hf26-elazig\tests\conftest.py
```


---

<sub>1m 11s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [x] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [x] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [x] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [ ] Run targeted checks and the requested pytest suite\n- [ ] Commit the completed changes without pushing"
}
```

</details>

```
TODO list updated
```


---

<sub>1m 11s</sub>

### `powershell`

**Review changes and check whitespace**

<details>
<summary>Arguments</summary>

```json
{
  "command": "git diff --check; git diff --stat; git diff -- web\\vadex.js web\\vadex.css web\\index.html server.py forecast.py tests\\conftest.py",
  "description": "Review changes and check whitespace"
}
```

</details>

<details>
<summary>129 lines</summary>

```diff
warning: in the working copy of 'web/index.html', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'web/index.html', LF will be replaced by CRLF the next time Git touches it
 forecast.py       | 10 ++++++++++
 logs/gemma.jsonl  |  3 +++
 server.py         |  6 ++++++
 tests/conftest.py |  6 ++++++
 web/index.html    |  4 ++--
 web/vadex.css     |  2 +-
 web/vadex.js      |  4 ++--
 7 files changed, 30 insertions(+), 5 deletions(-)
warning: in the working copy of 'web/index.html', LF will be replaced by CRLF the next time Git touches it
diff --git a/forecast.py b/forecast.py
index 40fdb70..2d70d8b 100644
--- a/forecast.py
+++ b/forecast.py
@@ -1,5 +1,6 @@
 """TabPFN payment-delay forecasts from the audited payment history."""
 import json
+import logging
 import math
 import threading
 from datetime import date
@@ -20,6 +21,7 @@ FEATURE_NAMES = (
 )
 _MODELS = None
 _MODELS_LOCK = threading.Lock()
+logger = logging.getLogger(__name__)
 
 
 def _load_history():
@@ -174,6 +176,14 @@ def _models():
     return _MODELS
 
 
+def warmup_models():
+    """Load TabPFN in the background; forecasts can retry if initialization fails."""
+    try:
+        _models()
+    except Exception:
+        logger.exception("TabPFN warm-up failed; forecasts will retry model initialization.")
+
+
 def forecast_delay(buyer_vkn, amount, due_date):
     """Predict late days and the chance of a payment being over five days late."""
     due_date = date.fromisoformat(str(due_date)[:10])
diff --git a/server.py b/server.py
index e06c88f..a900593 100644
--- a/server.py
+++ b/server.py
@@ -6,6 +6,7 @@ import math
 import os
 import re
 import secrets
+import threading
 import uuid
 from contextlib import asynccontextmanager
 from datetime import date, datetime, timezone
@@ -36,6 +37,11 @@ MAX_UPLOAD_SIZE = 10 * 1024 * 1024
 async def lifespan(application):
     db.init_db()
     UPLOADS.mkdir(parents=True, exist_ok=True)
+    threading.Thread(
+        target=forecast.warmup_models,
+        name="tabpfn-warmup",
+        daemon=True,
+    ).start()
     yield
 
 
diff --git a/tests/conftest.py b/tests/conftest.py
index f607c2e..d3fc3c3 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -5,6 +5,12 @@ Individual tests can still monkeypatch a Gemma function with their own fake; thi
 import pytest
 
 import gemma
+import server
+
+
+@pytest.fixture(autouse=True)
+def disable_tabpfn_warmup(monkeypatch):
+    monkeypatch.setattr(server.forecast, "warmup_models", lambda: None)
 
 
 @pytest.fixture(autouse=True)
diff --git a/web/index.html b/web/index.html
index c99c715..4d4c3c8 100644
--- a/web/index.html
+++ b/web/index.html
@@ -8,7 +8,7 @@
 <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 40 40%27%3E%3Crect width=%2740%27 height=%2740%27 rx=%279%27 fill=%27%2312355b%27/%3E%3Cpath d=%27M9 12l7.7 16.5L24.4 12%27 fill=%27none%27 stroke=%27%23fff%27 stroke-width=%273%27 stroke-linecap=%27round%27/%3E%3Cpath d=%27M26 21l6 7M32 21l-6 7%27 stroke=%27%235fc2c9%27 stroke-width=%272.8%27 stroke-linecap=%27round%27/%3E%3C/svg%3E">
 <link rel="preconnect" href="https://fonts.googleapis.com">
 <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Noto+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
-<link rel="stylesheet" href="/vadex.css?v=6">
+<link rel="stylesheet" href="/vadex.css?v=7">
 </head>
 <body>
 <div class="topband"><div class="wrap">
@@ -29,6 +29,6 @@
 </div></header>
 <div id="app"></div>
 <div id="toast" role="status" aria-live="polite"></div>
-<script src="/vadex.js?v=6"></script>
+<script src="/vadex.js?v=7"></script>
 </body>
 </html>
diff --git a/web/vadex.css b/web/vadex.css
index 712a39b..2f6e283 100644
--- a/web/vadex.css
+++ b/web/vadex.css
@@ -206,7 +206,7 @@ main.page { padding: 28px 34px 64px; min-width: 0; }
 .panel > .ph { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 20px; border-bottom: 1px solid var(--line); }
 .panel > .ph h3 { font-size: 16px; }
 .panel > .pb { padding: 20px; }
-.split { display: grid; grid-template-columns: 1.35fr 1fr; gap: 18px; align-items: start; }
+.split { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 18px; align-items: start; }
 .filters { display: flex; gap: 10px; flex-wrap: wrap; padding: 14px 20px; border-bottom: 1px solid var(--line); background: var(--bg-2); border-radius: 14px 14px 0 0; }
 .filters .f { height: 40px; width: auto; min-width: 150px; flex: 1; }
 table.data { width: 100%; border-collapse: collapse; font-size: 14px; }
diff --git a/web/vadex.js b/web/vadex.js
index 7816417..c309821 100644
--- a/web/vadex.js
+++ b/web/vadex.js
@@ -477,10 +477,10 @@ async function detail(id) {
         ${o.status === "beklemede" ? `<div class="ai-line" id="oc-${o.id}"><span class="skeleton" style="display:inline-block;width:60%;margin:0;vertical-align:middle"></span></div>` : ""}
         ${o.status === "beklemede" && !["finanse_edildi", "reddedildi"].includes(d.status) ? `<div class="acts"><button class="btn primary sm" data-act="accept" data-id="${o.id}">Kabul et</button><button class="btn sm" data-act="reject" data-id="${o.id}">Reddet</button></div>` : ""}</div>`).join("")
         : `<p class="muted" style="margin:0">${d.status === "incelemede" ? "Belge denetim incelemesinde. Onaylandıktan sonra pazara açılacak." : "Henüz teklif gelmedi. Teklif geldiğinde bildirim ve e-posta alacaksınız."}</p>`}
-      </div></div><div id="cmp" style="margin-bottom:18px"></div><div class="grid-2"><div id="pay"></div><div id="forecast"></div></div>`;
+      </div></div><div id="cmp" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>`;
   } else if (role === "finansor") {
     const mine = offers.find(o => o.financier?.id === S.user.id && o.status === "beklemede");
-    right = `<div id="rr" style="margin-bottom:18px"></div><div class="grid-2" style="margin-bottom:18px"><div id="pay"></div><div id="forecast"></div></div>
+    right = `<div id="rr" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>
       <div class="panel"><div class="ph"><h3>${mine ? "Teklifinizi güncelleyin" : "Teklif ver"}</h3><span class="muted small">${offers.filter(o => o.status === "beklemede").length} aktif teklif</span></div><div class="pb">
       ${["teklif_bekliyor", "teklif_var"].includes(d.status) ? `<form id="of"><div class="field"><label class="f" for="na">Ödenecek net tutar (TL)</label><input class="f" id="na" type="number" step="0.01" max="${d.total}" value="${mine ? mine.net_amount : ""}" required></div>
         <div class="muted small" id="calc" style="margin:-6px 0 12px">Nominal ${TL(d.total)}</div><div class="field"><label class="f" for="nt">Not (isteğe bağlı)</label><textarea class="f" id="nt">${esc(mine?.note || "")}</textarea></div>
<shellId: 1 completed with exit code 0>
```

</details>


---

<sub>1m 57s</sub>

### `powershell`

**Run full pytest suite**

<details>
<summary>Arguments</summary>

```json
{
  "command": "& 'C:\\Users\\omres\\OneDrive\\Desktop\\hf26-elazig\\.venv\\Scripts\\python.exe' -m pytest -q",
  "description": "Run full pytest suite",
  "initial_wait": 180,
  "mode": "sync"
}
```

</details>

```
................................                                         [100%]
32 passed in 43.66s
<shellId: 2 completed with exit code 0>
```


---

<sub>2m 13s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [x] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [x] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [x] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [x] Run targeted checks and the requested pytest suite\n- [ ] Commit the completed changes without pushing"
}
```

</details>

```
TODO list updated
```


---

<sub>2m 13s</sub>

### `powershell`

**Check JavaScript syntax and worktree**

<details>
<summary>Arguments</summary>

```json
{
  "command": "node --check web\\vadex.js; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git status --short",
  "description": "Check JavaScript syntax and worktree"
}
```

</details>

<details>
<summary>11 lines</summary>

```
warning: in the working copy of 'web/index.html', LF will be replaced by CRLF the next time Git touches it
 M forecast.py
 M logs/gemma.jsonl
 M server.py
 M tests/conftest.py
 M web/index.html
 M web/vadex.css
 M web/vadex.js
?? logs/agent-writer.log
?? sessions/02-writer.md
<shellId: 3 completed with exit code 0>
```

</details>


---

<sub>2m 13s</sub>

### `rg`

**grid-2.*pay|id="pay"|id="forecast"|\.split \{|@media \(max-width: 980px\)|vadex\.(css|js)\?v=**

"grid-2.*pay|id="pay"|id="forecast"|\.split \{|@media \(max-width: 980px\)|vadex\.(css|js)\?v=" (web\vadex.js, web\vadex.css, web\index.html)

<details>
<summary>7 matches</summary>

```
web\index.html:11:<link rel="stylesheet" href="/vadex.css?v=7">
web\index.html:32:<script src="/vadex.js?v=7"></script>
web\vadex.css:209:.split { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 18px; align-items: start; }
web\vadex.css:303:@media (max-width: 980px) {
web\vadex.js:480:      </div></div><div id="cmp" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>`;
web\vadex.js:483:    right = `<div id="rr" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>
web\vadex.js:490:    right = `<div class="panel"><div class="ph"><h3>Denetim kararı</h3></div><div class="pb">${d.status === "incelemede" ? `<div class="field"><label class="f" for="rs">Gerekçe</label><textarea class="f" id="rs" placeholder="Karar gerekçesi"></textarea></div><div style="display:flex;gap:8px"><button class="btn primary" data-act="review" data-v="approve" data-id="${esc(d.id)}">Onayla, pazara aç</button><button class="btn" data-act="review" data-v="reject" data-id="${esc(d.id)}">Reddet</button></div>` : `<p class="muted" style="margin:0">Belge durumu: ${st(d.status)}</p>`}</div></div><div id="pay"></div>`;
```

</details>


---

<sub>2m 17s</sub>

### `powershell`

**Commit the requested fixes**

<details>
<summary>Arguments</summary>

```json
{
  "command": "git add forecast.py server.py tests\\conftest.py web\\vadex.js web\\vadex.css web\\index.html; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --cached --check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --cached --stat; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git commit -m \"Fix forecast warmup and detail layout\" -m \"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>\"",
  "description": "Commit the requested fixes",
  "initial_wait": 30
}
```

</details>

<details>
<summary>12 lines</summary>

```
warning: in the working copy of 'web/index.html', LF will be replaced by CRLF the next time Git touches it
 forecast.py       | 10 ++++++++++
 server.py         |  6 ++++++
 tests/conftest.py |  6 ++++++
 web/index.html    |  4 ++--
 web/vadex.css     |  2 +-
 web/vadex.js      |  4 ++--
 6 files changed, 27 insertions(+), 5 deletions(-)
error: failed to delete '.git/worktrees/kobi-builder,market-builder': Permission denied
[main cd9043d] Fix forecast warmup and detail layout
 6 files changed, 27 insertions(+), 5 deletions(-)
<shellId: 4 completed with exit code 0>
```

</details>


---

<sub>2m 21s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [x] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [x] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [x] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [x] Run targeted checks and the requested pytest suite\n- [ ] Verify commit and confirm unrelated changes remain uncommitted"
}
```

</details>

```
TODO list updated
```


---

<sub>2m 21s</sub>

### `powershell`

**Verify commit and remaining changes**

<details>
<summary>Arguments</summary>

```json
{
  "command": "git status --short; git show --stat --oneline --summary HEAD",
  "description": "Verify commit and remaining changes"
}
```

</details>

<details>
<summary>12 lines</summary>

```
M logs/gemma.jsonl
?? logs/agent-writer.log
?? sessions/02-writer.md
cd9043d Fix forecast warmup and detail layout
 forecast.py       | 10 ++++++++++
 server.py         |  6 ++++++
 tests/conftest.py |  6 ++++++
 web/index.html    |  4 ++--
 web/vadex.css     |  2 +-
 web/vadex.js      |  4 ++--
 6 files changed, 27 insertions(+), 5 deletions(-)
<shellId: 5 completed with exit code 0>
```

</details>


---

<sub>2m 30s</sub>

### `update_todo`

<details>
<summary>Arguments</summary>

```json
{
  "todos": "- [x] Inspect current worktree, UI detail-card layout, API startup/lifespan, and relevant tests\n- [x] Fix document-detail right-column stacking and responsive overflow; bump asset version\n- [x] Warm TabPFN asynchronously during FastAPI startup without affecting startup or tests\n- [x] Run targeted checks and the requested pytest suite\n- [x] Verify commit and confirm unrelated changes remain uncommitted"
}
```

</details>

```
TODO list updated
```


---

<sub>2m 35s</sub>

### Copilot

Implemented both fixes and committed them as `cd9043d` (`Fix forecast warmup and detail layout`). The payment-history and TabPFN cards now stack with 18px spacing; the split columns can shrink without forcing overflow, and both assets use `?v=7`. TabPFN warm-up runs in a daemon thread during FastAPI lifespan, logs initialization failures without blocking startup, and is stubbed in tests. **Validation:** 32 tests passed; `node --check` and `git diff --check` passed. No push was made.

🌐 **Community Wisdom** — Only one of the two inspected articles was substantive, and neither had comments; it likewise identifies cold-start latency as a production concern: ⚡ [[The Unglamorous Truth About Deploying ML Models in Production](https://dev.to/abdullahramzan1/the-unglamorous-truth-about-deploying-ml-models-in-production-1lpb)] 👤 [@abdullahramzan1](https://dev.to/abdullahramzan1) — Its advice to account for cold starts supports warming the model in the background rather than on the first user request. 🔗 [Read Full Discussion on DEV](https://dev.to/abdullahramzan1/the-unglamorous-truth-about-deploying-ml-models-in-production-1lpb)

The registered Hacktoberfest Hack Day Elazığ event is scheduled through Oct 18 at 06:00 Istanbul time. This fix could make a useful DEV write-up; I can draft one. Unrelated existing changes in `logs/gemma.jsonl`, `logs/agent-writer.log`, and `sessions/02-writer.md` were left untouched.

---

<sub>Generated by [GitHub Copilot CLI](https://github.com/features/copilot/cli)</sub>

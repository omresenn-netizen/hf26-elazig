/* VadeX front end – vanilla JS, talks to server.py (docs/API.md). */
"use strict";

// ---------- helpers ----------
const $ = (s, r = document) => r.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const TL = n => n == null || isNaN(n) ? "–" : new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + " TL";
const TL0 = n => n == null || isNaN(n) ? "–" : new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 }).format(n) + " TL";
const PCT = r => r == null ? "–" : "%" + (r * 100).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
const DATE = d => d ? new Date(d).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" }) : "–";
const DT = d => d ? new Date(d).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" }) : "–";
const short = h => h ? h.slice(0, 10) + "…" + h.slice(-6) : "–";
const app = $("#app");
const toast = m => { const t = $("#toast"); t.textContent = m; t.className = "on"; clearTimeout(toast.t); toast.t = setTimeout(() => t.className = "", 2600); };
const spin = '<span class="spin" aria-hidden="true"></span>';

async function api(path, { method = "GET", body, form } = {}) {
  const opt = { method, credentials: "same-origin", headers: {} };
  if (form) opt.body = form;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch("/api" + path, opt);
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) {
    if (r.status === 401 && S.user) { S.user = null; go("giris"); }
    throw new Error((data && (data.error || data.detail)) || "İşlem tamamlanamadı (" + r.status + ")");
  }
  return data;
}

const STATUS = {
  incelemede: ["İncelemede", "warn"], teklif_bekliyor: ["Teklif bekliyor", "info"], teklif_var: ["Teklif var", "ok"],
  finanse_edildi: ["Finanse edildi", ""], reddedildi: ["Reddedildi", "bad"],
  beklemede: ["Beklemede", "warn"], kabul: ["Kabul edildi", "ok"], red: ["Reddedildi", "bad"], geri_cekildi: ["Geri çekildi", ""],
};
const st = s => { const [l, c] = STATUS[s] || [s, ""]; return `<span class="badge ${c}">${esc(l)}</span>`; };
const riskBadge = d => d.risk_score == null ? '<span class="badge">–</span>'
  : `<span class="badge ${d.risk_score < 30 ? "ok" : d.risk_score < 60 ? "warn" : "bad"}">${esc(d.risk_class || "")} · ${d.risk_score}</span>`;
const icon = {
  up: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 16V4M6 10l6-6 6 6M4 20h16"/></svg>',
  doc: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/></svg>',
  shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  bank: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10l9-6 9 6M5 10v8M10 10v8M14 10v8M19 10v8M3 21h18"/></svg>',
  hash: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 9h14M5 15h14M10 4L8 20M16 4l-2 16"/></svg>',
  chev: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
  bell: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 004 0"/></svg>',
};

// ---------- state + router ----------
const S = { user: null, notes: [], ddOpen: false, upload: null, loginRole: "kobi" };
const go = h => { location.hash = "#/" + h; };
const ROLE_HOME = { kobi: "kobi", finansor: "finansor", denetim: "denetim" };
const MENU = {
  kobi: [["kobi", "Genel bakış"], ["kobi/belgeler", "Belgelerim"], ["kobi/yukle", "Fatura yükle"], ["bildirimler", "Bildirimler"]],
  finansor: [["finansor", "Fatura pazarı"], ["finansor/teklifler", "Tekliflerim"], ["finansor/portfoy", "Portföy"], ["bildirimler", "Bildirimler"]],
  denetim: [["denetim", "İnceleme kuyruğu"], ["denetim/ag", "Fatura ağı analizi"], ["denetim/kayit", "Kayıt defteri"]],
};
const ROLE_NAME = { kobi: "KOBİ hesabı", finansor: "Finansör hesabı", denetim: "Denetim hesabı" };

function nav() {
  $("#nav").innerHTML = S.user
    ? `<a href="#/${ROLE_HOME[S.user.role]}">Panelim</a>
       <span class="bell"><button class="btn ghost sm" data-act="bell" aria-label="Bildirimler">${icon.bell}</button>${unread() ? `<span class="dot">${unread()}</span>` : ""}
       ${S.ddOpen ? `<div class="dd">${S.notes.length ? S.notes.slice(0, 6).map(n => `<div class="it ${n.read ? "" : "unread"}"><b>${esc(n.subject)}</b><small>${DT(n.created_at)}</small></div>`).join("") : '<div class="it muted">Bildirim yok.</div>'}<div class="it"><a href="#/bildirimler">Tümünü gör</a></div></div>` : ""}</span>
       <button class="btn sm" data-act="logout">Çıkış</button>`
    : `<a href="#/#surec">İşlem adımları</a><a href="#/#kontroller">Kontroller</a><a href="#/mevzuat">Mevzuat</a><a class="btn primary" href="#/giris">Giriş yap</a>`;
}
const unread = () => S.notes.filter(n => !n.read).length;

function shell(cur, crumbs, title, sub, body) {
  const menu = MENU[S.user.role].map(([h, l]) => `<a class="${h === cur ? "on" : ""}" href="#/${h}">${esc(l)}${h === "bildirimler" && unread() ? `<span class="count">${unread()}</span>` : ""}</a>`).join("");
  return `<div class="shell"><aside class="side"><div class="who"><b>${esc(S.user.display_name)}</b><small>${ROLE_NAME[S.user.role]}${S.user.company_vkn ? " · VKN " + esc(S.user.company_vkn) : ""}</small></div>${menu}
    <div class="bottom small muted">Oturum IP ve cihaz bilgisiyle kayıt altındadır.</div></aside>
    <main class="page"><div class="crumbs">${crumbs}</div><div class="page-head"><div><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ""}</div><div id="head-actions"></div></div><div id="view">${body}</div></main></div>`;
}

async function render() {
  const r = (location.hash || "#/").slice(2).split("#")[0];
  const p = r.split("/");
  S.ddOpen = false;
  try {
    if (["kobi", "finansor", "denetim", "bildirimler", "belge"].includes(p[0])) {
      if (!S.user) { go("giris"); return; }
      if (p[0] !== "belge" && p[0] !== "bildirimler" && p[0] !== S.user.role) { go(ROLE_HOME[S.user.role]); return; }
      refreshNotes();
    }
    nav();
    const view = ROUTES[r] || (p[0] === "belge" ? () => detail(p.slice(1).join("/")) : home);
    await view();
  } catch (e) {
    app.innerHTML = `<div class="wrap"><div class="panel" style="margin:40px 0"><div class="pb"><b>Bir hata oluştu.</b><p class="muted">${esc(e.message)}</p></div></div></div>`;
  }
  if (location.hash.includes("#surec") || location.hash.includes("#kontroller")) { const id = location.hash.split("#").pop(); document.getElementById(id)?.scrollIntoView(); }
  else scrollTo(0, 0);
}
async function refreshNotes() { try { S.notes = await api("/notifications"); nav(); } catch { /* ignore */ } }

// ---------- public pages ----------
function home() {
  app.innerHTML = `
  <section class="hero"><div class="wrap">
    <div>
      <span class="tag">KOBİ'ler ve lisanslı finansman kuruluşları için</span>
      <h1>Vadeli faturanızı doğrulanmış biçimde finansmana açın.</h1>
      <p class="lead">Yüklediğiniz e-fatura, kurum içinde çalışan açık kaynak bir yapay zekâ modeliyle okunur ve sahte belge kontrollerinden geçer. Faktoring şirketleri ve bankalar doğrulanmış belgeye teklif verir; kabul ettiğiniz tutar vadeyi beklemeden hesabınıza geçer.</p>
      <div class="actions"><a class="btn primary" href="#/giris">KOBİ girişi</a><a class="btn" href="#/giris" data-role="finansor">Finansör girişi</a></div>
    </div>
    <div class="quick"><h3>Hızlı işlemler</h3>
      <a href="#/giris"><span class="ico">${icon.up}</span><span class="t"><b>Fatura yükle</b><small>PNG, JPG veya PDF · en fazla 10 MB</small></span>${icon.chev}</a>
      <a href="#/giris"><span class="ico">${icon.doc}</span><span class="t"><b>Belge durumunu sorgula</b><small>Doğrulama, teklif ve ödeme aşamaları</small></span>${icon.chev}</a>
      <a href="#/giris" data-role="finansor"><span class="ico">${icon.bank}</span><span class="t"><b>Fatura pazarına eriş</b><small>Lisanslı finansman kuruluşları için</small></span>${icon.chev}</a>
      <a href="#/guvenlik"><span class="ico">${icon.hash}</span><span class="t"><b>Kayıt ve bütünlük</b><small>Her belge SHA-256 özetiyle saklanır</small></span>${icon.chev}</a>
    </div>
  </div></section>

  <section class="band" id="surec"><div class="wrap">
    <h2>İşlem adımları</h2><p class="sub">Belgenin yüklenmesinden ödemeye kadar her adım kayıt altına alınır ve panelinizden izlenir.</p>
    <div class="steps">
      <div><span class="n">01</span><h4>Yükleme</h4><p>Fatura yüklenir; dosya özeti (SHA-256), yükleme zamanı ve IP adresi kaydedilir.</p></div>
      <div><span class="n">02</span><h4>Okuma ve doğrulama</h4><p>Gemma 4 faturayı okur. Bilgiler e-Fatura kaydıyla ve alıcı onayıyla karşılaştırılır.</p></div>
      <div><span class="n">03</span><h4>Teklif</h4><p>Risk raporu hazırlanan belge pazara açılır, finansörler teklif verir.</p></div>
      <div><span class="n">04</span><h4>Ödeme</h4><p>Kabul ettiğiniz teklifin tutarı hesabınıza aktarılır, alıcı vadede finansöre öder.</p></div>
    </div>
  </div></section>

  <section class="band alt" id="kontroller"><div class="wrap">
    <h2>Sahte belge kontrolleri</h2><p class="sub">Şüpheli bulunan belge otomatik reddedilmez; denetim ekibinin incelemesine gönderilir.</p>
    <table class="checks"><thead><tr><th>Kontrol</th><th>Ne inceleniyor</th></tr></thead><tbody>
      <tr><td>Çift kullanım</td><td>Aynı belgenin daha önce yüklenip yüklenmediği, dosya ve fatura özetiyle karşılaştırılır.</td></tr>
      <tr><td>Teslimat belgesi</td><td>Mal satışı içeren faturada irsaliye bilgisinin bulunup bulunmadığı.</td></tr>
      <tr><td>Faaliyet uyumu</td><td>Satıcının faaliyet alanı ile faturadaki mal ve hizmetin uyumu.</td></tr>
      <tr><td>Kapasite</td><td>Kesilen fatura tutarlarının işletmenin çalışan sayısıyla orantısı.</td></tr>
      <tr><td>Fatura ağı</td><td>Firmalar arasında dönen fatura zincirleri ve aynı adresi paylaşan yeni kurulmuş şirketler.</td></tr>
      <tr><td>Alıcı onayı</td><td>Faturayı ödeyecek firmanın belgeyi kabul edip etmediği.</td></tr>
    </tbody></table>
  </div></section>

  <section class="band"><div class="wrap">
    <h2>Bilgilendirme</h2><p class="sub">Platformun dayandığı temel düzenlemeler.</p>
    <div class="notice">
      <article><span class="tag">Faktoring</span><h4>6361 sayılı Kanun</h4><p>Alacakları satın alan taraflar, BDDK lisanslı faktoring şirketleri ve bankalardır. Bireysel yatırımcıya açık değildir.</p></article>
      <article><span class="tag">Vergi</span><h4>VUK md. 359</h4><p>Gerçek bir mal veya hizmet satışına dayanmayan belge düzenlemek ve kullanmak suçtur. Şüpheli belgeler ilgili mercilere bildirilebilir.</p></article>
      <article><span class="tag">Kişisel veri</span><h4>6698 sayılı KVKK</h4><p>Fatura verileri platform sunucusunda çalışan model ile işlenir; üçüncü taraf yapay zekâ servislerine gönderilmez.</p></article>
    </div>
  </div></section>
  ${footer()}`;
}

const footer = () => `<footer class="site"><div class="wrap">
  <div><b style="color:#fff;font-size:16px">VadeX</b><p style="margin:8px 0 0;max-width:320px">Vadeli alacakların doğrulanarak lisanslı finansman kuruluşlarına devri için geliştirilmiş platform. Hacktoberfest 2026 Elazığ projesidir.</p></div>
  <div><h5>Platform</h5><a href="#/#surec">İşlem adımları</a><a href="#/#kontroller">Kontroller</a><a href="#/giris">Giriş</a></div>
  <div><h5>Kurumsal</h5><a href="#/guvenlik">Güvenlik</a><a href="#/mevzuat">Mevzuat</a></div>
  <div><h5>Teknoloji</h5><span>Gemma 4 · Ollama · GitHub Copilot</span></div>
  <div class="bottom"><span>© 2026 VadeX · Demo sürümü</span><span>Kişisel Verilerin Korunması · Kullanım Koşulları</span></div>
</div></footer>`;

function staticPage(title, html) {
  app.innerHTML = `<div class="wrap" style="padding:36px 20px 60px;max-width:860px"><div class="crumbs"><a href="#/">Ana sayfa</a> / ${esc(title)}</div><h1 style="font-size:26px;margin-bottom:16px">${esc(title)}</h1>${html}</div>${footer()}`;
}
const guvenlik = () => staticPage("Güvenlik", `
  <div class="panel"><div class="pb"><dl class="kv">
    <dt>Model</dt><dd>Gemma 4, platform sunucusunda Ollama ile çalışır. Belge içeriği dış servislere gönderilmez.</dd>
    <dt>Bütünlük</dt><dd>Her dosyanın SHA-256 özeti saklanır; aynı belge ikinci kez finansmana açılamaz.</dd>
    <dt>Kayıt defteri</dt><dd>Giriş, yükleme, teklif ve kabul işlemleri kullanıcı, zaman, IP ve cihaz bilgisiyle kaydedilir.</dd>
    <dt>Kimlik doğrulama</dt><dd>Parolalar tuzlanmış PBKDF2 özetiyle saklanır; rol bazlı erişim her istekte kontrol edilir.</dd>
    <dt>İnsan denetimi</dt><dd>Yapay zekâ ve kural motoru karar destek aracıdır. Yüksek riskli belgeler denetim ekibine gider.</dd>
  </dl></div></div>`);
const mevzuat = () => staticPage("Mevzuat", `
  <div class="panel"><div class="pb"><dl class="kv">
    <dt>6361 sayılı Kanun</dt><dd>Finansal Kiralama, Faktoring, Finansman ve Tasarruf Finansman Şirketleri Kanunu.</dd>
    <dt>VUK md. 359</dt><dd>Sahte veya muhteviyatı itibarıyla yanıltıcı belge düzenleme ve kullanma.</dd>
    <dt>6698 sayılı KVKK</dt><dd>Kişisel verilerin işlenmesi ve korunması.</dd>
    <dt>e-Fatura</dt><dd>Bu demoda e-Fatura sorgusu simüle edilmektedir.</dd>
  </dl></div></div>`);

// ---------- login ----------
async function login() {
  let demo = {};
  try { demo = await api("/demo-accounts"); } catch { /* optional */ }
  const role = S.loginRole;
  const label = { kobi: "Vergi kimlik numarası", finansor: "Kurum kullanıcı adı", denetim: "Kullanıcı adı" }[role];
  const list = (demo[role] || []).slice(0, 4).map(u => `<code>${esc(u)}</code>`).join(", ");
  app.innerHTML = `<div class="wrap"><div class="auth"><div class="head"><h2>Platform girişi</h2><p class="muted small" style="margin:4px 0 0">Hesap türünüzü seçin.</p>
    <div class="roles">${[["kobi", "KOBİ"], ["finansor", "Finansör"], ["denetim", "Denetim"]].map(([k, l]) => `<button data-act="role" data-v="${k}" class="${k === role ? "on" : ""}">${l}</button>`).join("")}</div></div>
    <form class="body" id="lf"><div class="field"><label class="f" for="u">${label}</label><input class="f" id="u" autocomplete="username" required></div>
    <div class="field"><label class="f" for="pw">Parola</label><input class="f" id="pw" type="password" autocomplete="current-password" required></div>
    <button class="btn primary block" type="submit">Giriş yap</button><div class="err" id="le"></div>
    <div class="hint">Demo hesapları: ${list || "–"}${list ? " · parola <code>demo1234</code>" : ""}</div></form></div></div>${footer()}`;
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

// ---------- KOBİ ----------
async function kobiHome() {
  const [stats, docs] = await Promise.all([api("/stats"), api("/my/documents")]);
  const waiting = docs.filter(d => d.status === "teklif_var");
  app.innerHTML = shell("kobi", "Panel", "Genel bakış", "Belgelerinizin ve tekliflerin güncel durumu.",
    kpis([["Finanse edilen", TL0(stats.financed_total)], ["Teklif bekleyen belge", stats.waiting_count ?? 0], ["Alınan teklif", stats.offer_count ?? 0], ["Ortalama iskonto", stats.avg_discount != null ? PCT(stats.avg_discount) : "–"]]) +
    `<div class="split"><div class="panel"><div class="ph"><h3>Son belgeler</h3><a class="btn sm" href="#/kobi/belgeler">Tümü</a></div>${docTable(docs.slice(0, 6))}</div>
     <div class="panel"><div class="ph"><h3>İşlem bekleyenler</h3></div><div class="pb">${waiting.length ? waiting.map(d => `<div class="offer"><div><b>${esc(d.buyer?.name)}</b><div class="muted small">${esc(d.invoice_no)} · ${d.offer_count} teklif · en iyi ${TL0(d.best_offer)}</div></div><a class="btn primary sm" href="#/belge/${esc(d.id)}">İncele</a></div>`).join("") : '<p class="muted" style="margin:0">Teklif bekleyen işlem yok.</p>'}
     <a class="btn teal block" style="margin-top:14px" href="#/kobi/yukle">Yeni fatura yükle</a></div></div></div>`);
}

async function kobiDocs() {
  const docs = await api("/my/documents");
  const draw = () => {
    const q = ($("#fq")?.value || "").toLowerCase(), s = $("#fs")?.value || "";
    $("#lst").innerHTML = docTable(docs.filter(d => (!q || (d.invoice_no + " " + (d.buyer?.name || "")).toLowerCase().includes(q)) && (!s || d.status === s)));
  };
  app.innerHTML = shell("kobi/belgeler", "Panel / Belgelerim", "Belgelerim", "Yüklediğiniz tüm faturalar.",
    `<div class="panel"><div class="filters"><input class="f" id="fq" placeholder="Belge no veya alıcı ara"><select class="f" id="fs"><option value="">Tüm durumlar</option>${Object.entries(STATUS).slice(0, 5).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join("")}</select><a class="btn primary" href="#/kobi/yukle">Fatura yükle</a></div><div id="lst"></div></div>`);
  $("#fq").oninput = draw; $("#fs").onchange = draw; draw();
}

// upload wizard: 1 Yükle → 2 Okuma → 3 Kontrol → 4 Yayınla
function kobiUpload() {
  const U = S.upload || (S.upload = { step: 1 });
  const wiz = ["Dosya yükleme", "Gemma ile okuma", "Kontrol", "Finansmana açma"].map((l, i) =>
    `<div class="${U.step === i + 1 ? "on" : U.step > i + 1 ? "done" : ""}"><b>0${i + 1}</b>${l}</div>`).join("");
  let body = "";
  if (U.step === 1) body = `<div class="panel"><div class="pb">
      <label class="drop" id="drop"><input type="file" id="file" accept=".png,.jpg,.jpeg,.pdf" hidden>
        <span class="ico" style="margin:0 auto">${icon.up}</span><b>Faturayı sürükleyip bırakın veya seçin</b><span class="muted small">PNG, JPG veya PDF · en fazla 10 MB</span></label>
      <p class="muted small" style="margin:12px 0 0">Dosyanın SHA-256 özeti, yükleme zamanı ve IP adresiniz kayıt defterine işlenir.</p><div class="err" id="ue"></div></div></div>`;
  else {
    const d = U.doc;
    body = `<div class="split"><div>
      <div class="panel"><div class="ph"><h3>Yüklenen dosya</h3>${st(d.status)}</div><div class="pb"><div class="filecard">${U.preview ? `<img src="${U.preview}" alt="">` : `<span class="ico">${icon.doc}</span>`}
        <dl class="kv"><dt>Dosya</dt><dd>${esc(d.file?.name)}</dd><dt>Boyut</dt><dd>${((d.file?.size || 0) / 1024).toFixed(1)} KB</dd><dt>SHA-256</dt><dd class="mono" title="${esc(d.file?.sha256)}">${short(d.file?.sha256)}</dd><dt>Yükleme</dt><dd>${DT(d.file?.uploaded_at)} · ${esc(d.file?.ip_address)}</dd></dl></div></div></div>
      ${U.step >= 2 ? fieldsPanel(U) : ""}
      </div><div>${U.step >= 3 && U.check ? checkPanel(U) : stepHelp(U)}</div></div>`;
  }
  app.innerHTML = shell("kobi/yukle", "Panel / Fatura yükle", "Fatura yükle", "Belgeniz okunur, kontrol edilir ve onayınızla finansmana açılır.", `<div class="wizard">${wiz}</div>${body}`);
  if (U.step === 1) bindDrop();
}
function stepHelp(U) {
  if (U.step === 2 && !U.fields) return `<div class="panel"><div class="ph"><h3>Okuma</h3></div><div class="pb"><p class="muted" style="margin-top:0">Fatura, kurum sunucusunda çalışan Gemma 4 modeliyle okunur. Bilgileri kontrol edip gerekirse düzeltebilirsiniz.</p><button class="btn primary block" data-act="extract">${U.busy ? spin + " Gemma okuyor…" : "Gemma ile oku"}</button><div class="err" id="ue"></div></div></div>`;
  if (U.step === 2) return `<div class="panel"><div class="ph"><h3>Kontrol</h3></div><div class="pb"><p class="muted" style="margin-top:0">Bilgiler e-Fatura kaydı (simülasyon), alıcı onayı ve sahte belge kurallarıyla karşılaştırılır.</p><button class="btn primary block" data-act="check">${U.busy ? spin + " Kontrol ediliyor…" : "Kontrol et"}</button><div class="err" id="ue"></div></div></div>`;
  return "";
}
function fieldsPanel(U) {
  if (!U.fields) return "";
  const f = U.fields, ro = U.step > 2 ? "readonly" : "";
  const inp = (k, l) => `<div class="field"><label class="f">${l}</label><input class="f" data-k="${k}" value="${esc(f[k] ?? "")}" ${ro}></div>`;
  return `<div class="panel"><div class="ph"><h3>Okunan bilgiler</h3><span class="badge info">Gemma 4</span></div><div class="pb">
    <div class="grid-2">${inp("invoice_no", "Fatura no")}${inp("irsaliye_no", "İrsaliye no")}${inp("issue_date", "Düzenleme tarihi")}${inp("due_date", "Vade tarihi")}${inp("seller_name", "Satıcı")}${inp("seller_vkn", "Satıcı VKN")}${inp("buyer_name", "Alıcı")}${inp("buyer_vkn", "Alıcı VKN")}</div>
    <table class="items"><thead><tr><th>Mal / hizmet</th><th>Miktar</th><th>Birim</th><th>Birim fiyat</th></tr></thead><tbody>${(f.items || []).map((it, i) => `<tr><td><input data-i="${i}" data-ik="description" value="${esc(it.description)}" ${ro}></td><td><input data-i="${i}" data-ik="quantity" value="${esc(it.quantity)}" ${ro}></td><td><input data-i="${i}" data-ik="unit" value="${esc(it.unit)}" ${ro}></td><td><input data-i="${i}" data-ik="unit_price" value="${esc(it.unit_price)}" ${ro}></td></tr>`).join("")}</tbody></table>
    <div class="grid-3" style="margin-top:14px">${inp("subtotal", "Ara toplam")}${inp("kdv", "KDV")}${inp("total", "Genel toplam")}</div></div></div>`;
}
function checkPanel(U) {
  const d = U.check.document, cls = d.risk_class || "A";
  return `<div class="panel"><div class="ph"><h3>Kontrol sonucu</h3>${st(d.status)}</div><div class="pb">
    <div class="risk ${cls}"><span class="score">${d.risk_score}</span><div><b>Risk sınıfı ${esc(cls)}</b><div class="muted small">0–29 düşük · 30–59 orta · 60+ yüksek</div></div></div>
    <h4 style="margin:18px 0 10px;font-size:14px">Doğrulama adımları</h4>${timeline(d.steps)}
    ${d.flags?.length ? `<h4 style="margin:6px 0 10px;font-size:14px">Tespit edilen bulgular</h4><ul class="flags">${d.flags.map(fl => `<li class="${d.risk_score >= 60 ? "hi" : ""}"><b>${esc(fl.label)}</b> – ${esc(fl.detail)}</li>`).join("")}</ul>` : '<p class="badge ok">Kural ihlali bulunmadı</p>'}
    <div class="gemma" style="margin-top:12px"><span class="by">Gemma 4 değerlendirmesi</span>${esc(U.check.explanation)}</div>
    ${U.step === 3 ? `<button class="btn teal block" style="margin-top:16px" data-act="publish">${d.risk_score >= 60 ? "Denetim incelemesine gönder" : "Finansmana aç"}</button>` : ""}
    ${U.step === 4 ? `<div class="hint"><b>${d.status === "incelemede" ? "Belge denetim incelemesine gönderildi." : "Belge fatura pazarına açıldı."}</b> Teklif geldiğinde bildirim ve e-posta alacaksınız.</div><div style="display:flex;gap:8px;margin-top:12px"><a class="btn primary" href="#/belge/${esc(d.id)}">Belgeye git</a><button class="btn" data-act="newupload">Yeni fatura</button></div>` : ""}
  </div></div>`;
}
const timeline = steps => `<ol class="tl">${(steps || []).map(s => `<li class="${esc(s.state)}"><span class="dot">${s.state === "done" ? "✓" : s.state === "failed" ? "!" : s.state === "running" ? "…" : ""}</span><div><b>${esc(s.label)}</b><small>${esc(s.detail || "")}</small></div></li>`).join("")}</ol>`;
function bindDrop() {
  const drop = $("#drop"), inp = $("#file");
  const send = async file => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { $("#ue").textContent = "Dosya 10 MB sınırını aşıyor."; return; }
    $("#ue").innerHTML = spin + " Yükleniyor…";
    const form = new FormData(); form.append("file", file);
    try {
      const r = await api("/uploads", { method: "POST", form });
      S.upload = { step: 2, doc: r.document, preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null };
      kobiUpload();
    } catch (e) { $("#ue").textContent = e.message; }
  };
  inp.onchange = () => send(inp.files[0]);
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => send(e.dataTransfer.files[0]));
}
function readFields() {
  const f = S.upload.fields;
  document.querySelectorAll("[data-k]").forEach(i => { f[i.dataset.k] = i.value === "" ? null : i.value; });
  document.querySelectorAll("[data-ik]").forEach(i => { f.items[+i.dataset.i][i.dataset.ik] = i.value; });
  ["subtotal", "kdv", "total"].forEach(k => { if (f[k] != null) f[k] = parseFloat(String(f[k]).replace(/\./g, "").replace(",", ".")) || parseFloat(f[k]); });
  f.items.forEach(it => { it.quantity = parseFloat(it.quantity); it.unit_price = parseFloat(String(it.unit_price).replace(",", ".")); });
  return f;
}

// ---------- detail (all roles) ----------
async function detail(id) {
  const r = await api("/documents/" + encodeURIComponent(id));
  const d = r.document, offers = r.offers || [], role = S.user.role;
  const left = `<div class="panel"><div class="ph"><h3>${esc(d.type || "Fatura")} · ${esc(d.invoice_no)}</h3>${st(d.status)}</div><div class="pb">
      <div class="amount">${TL(d.total)}</div><p class="muted" style="margin:2px 0 16px">Vade ${DATE(d.due_date)} · ${d.days_left ?? "–"} gün · ${riskBadge(d)}</p>
      <dl class="kv"><dt>Satıcı</dt><dd>${esc(d.seller?.name)} <span class="muted">· ${esc(d.seller?.vkn)}</span></dd><dt>Alıcı</dt><dd>${esc(d.buyer?.name)} <span class="muted">· ${esc(d.buyer?.vkn)}</span></dd>
      <dt>Alıcı kredi skoru</dt><dd>${d.buyer?.credit_score ?? "–"} <span class="badge">simülasyon</span></dd><dt>Düzenleme</dt><dd>${DATE(d.issue_date)}</dd><dt>İrsaliye</dt><dd>${esc(d.irsaliye_no || "Yok")}</dd>
      ${d.file ? `<dt>SHA-256</dt><dd class="mono" title="${esc(d.file.sha256)}">${short(d.file.sha256)}</dd><dt>Yükleme</dt><dd>${DT(d.file.uploaded_at)} · ${esc(d.file.ip_address)}</dd>` : ""}</dl>
      <h4 style="margin:20px 0 10px;font-size:14px">Doğrulama adımları</h4>${timeline(d.steps)}
      ${d.flags?.length ? `<h4 style="margin:6px 0 10px;font-size:14px">Bulgular</h4><ul class="flags">${d.flags.map(fl => `<li class="${d.risk_score >= 60 ? "hi" : ""}"><b>${esc(fl.label)}</b> – ${esc(fl.detail)}</li>`).join("")}</ul>` : ""}</div></div>`;
  let right = "";
  if (role === "kobi") {
    right = `<div class="panel"><div class="ph"><h3>Gelen teklifler</h3><span class="muted small">${offers.length} teklif</span></div><div class="pb">
      ${offers.length ? [...offers].sort((a, b) => b.net_amount - a.net_amount).map((o, i) => `<div class="offer"><div><b>${esc(o.financier?.name)}</b> ${i === 0 && o.status === "beklemede" ? '<span class="badge ok">En yüksek</span>' : ""} ${o.status !== "beklemede" ? st(o.status) : ""}<div class="muted small">İskonto ${PCT(o.discount_rate)} · yıllık ${PCT(o.annual_rate)} · ${DT(o.created_at)}</div>${o.note ? `<div class="small">${esc(o.note)}</div>` : ""}</div><div class="net">${TL(o.net_amount)}</div>
        ${o.status === "beklemede" && !["finanse_edildi", "reddedildi"].includes(d.status) ? `<div class="acts"><button class="btn primary sm" data-act="accept" data-id="${o.id}">Kabul et</button><button class="btn sm" data-act="reject" data-id="${o.id}">Reddet</button></div>` : ""}</div>`).join("")
        : `<p class="muted" style="margin:0">${d.status === "incelemede" ? "Belge denetim incelemesinde. Onaylandıktan sonra pazara açılacak." : "Henüz teklif gelmedi. Teklif geldiğinde bildirim ve e-posta alacaksınız."}</p>`}
      ${offers.filter(o => o.status === "beklemede").length > 1 ? `<button class="btn block" style="margin-top:12px" data-act="compare" data-id="${esc(d.id)}">Teklifleri Gemma ile karşılaştır</button><div id="cmp"></div>` : ""}</div></div>`;
  } else if (role === "finansor") {
    const mine = offers.find(o => o.financier?.id === S.user.id && o.status === "beklemede");
    right = `<div class="panel"><div class="ph"><h3>Risk raporu</h3><span class="badge info">Gemma 4</span></div><div class="pb" id="rr">${spin} <span class="muted">Rapor hazırlanıyor…</span></div></div>
      <div class="panel"><div class="ph"><h3>${mine ? "Teklifinizi güncelleyin" : "Teklif ver"}</h3><span class="muted small">${offers.filter(o => o.status === "beklemede").length} aktif teklif</span></div><div class="pb">
      ${["teklif_bekliyor", "teklif_var"].includes(d.status) ? `<form id="of"><div class="field"><label class="f" for="na">Ödenecek net tutar (TL)</label><input class="f" id="na" type="number" step="0.01" max="${d.total}" value="${mine ? mine.net_amount : ""}" required></div>
        <div class="muted small" id="calc" style="margin:-6px 0 12px">Nominal ${TL(d.total)}</div><div class="field"><label class="f" for="nt">Not (isteğe bağlı)</label><textarea class="f" id="nt">${esc(mine?.note || "")}</textarea></div>
        <button class="btn primary block" type="submit">${mine ? "Teklifi güncelle" : "Teklif ver"}</button>${mine ? `<button class="btn block" type="button" style="margin-top:8px" data-act="withdraw" data-id="${mine.id}">Teklifi geri çek</button>` : ""}<div class="err" id="oe"></div></form>`
        : '<p class="muted" style="margin:0">Bu belge teklife kapalı.</p>'}</div></div>`;
  } else {
    right = `<div class="panel"><div class="ph"><h3>Denetim kararı</h3></div><div class="pb">${d.status === "incelemede" ? `<div class="field"><label class="f" for="rs">Gerekçe</label><textarea class="f" id="rs" placeholder="Karar gerekçesi"></textarea></div><div style="display:flex;gap:8px"><button class="btn primary" data-act="review" data-v="approve" data-id="${esc(d.id)}">Onayla, pazara aç</button><button class="btn" data-act="review" data-v="reject" data-id="${esc(d.id)}">Reddet</button></div>` : `<p class="muted" style="margin:0">Belge durumu: ${st(d.status)}</p>`}</div></div>`;
  }
  const back = { kobi: "kobi/belgeler", finansor: "finansor", denetim: "denetim" }[role];
  app.innerHTML = shell(back, `<a href="#/${back}">Geri</a> / ${esc(d.invoice_no)}`, d.invoice_no, esc(d.seller?.name) + " → " + esc(d.buyer?.name), `<div class="split">${left}<div>${right}</div></div>`);
  if (role === "finansor") {
    api(`/documents/${encodeURIComponent(id)}/risk-report`).then(rr => {
      $("#rr").innerHTML = `<div class="gemma"><span class="by">Gemma 4 risk özeti</span>${esc(rr.summary)}</div><dl class="kv" style="margin-top:12px"><dt>Önerilen iskonto</dt><dd>${PCT(rr.suggested_discount_rate)}</dd><dt>Önerilen net tutar</dt><dd>${TL(rr.suggested_net_amount)}</dd></dl>`;
      const na = $("#na"); if (na && !na.value && rr.suggested_net_amount) { na.value = rr.suggested_net_amount.toFixed(2); na.dispatchEvent(new Event("input")); }
    }).catch(e => { $("#rr").innerHTML = `<span class="err">${esc(e.message)}</span>`; });
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
    const qs = new URLSearchParams({ q: $("#mq").value, risk: $("#mr").value, min: $("#mm").value, max_days: $("#md").value, sort: $("#ms").value });
    $("#lst").innerHTML = `<div class="empty">${spin}</div>`;
    const list = await api("/market?" + qs);
    $("#mk").innerHTML = kpis([["Açık belge", list.length], ["Toplam nominal", TL0(list.reduce((a, d) => a + (d.total || 0), 0))], ["Ortalama vade", list.length ? Math.round(list.reduce((a, d) => a + (d.days_left || 0), 0) / list.length) + " gün" : "–"], ["Teklifli belge", list.filter(d => d.offer_count).length]]);
    $("#lst").innerHTML = docTable(list, "market");
  };
  app.innerHTML = shell("finansor", "Panel / Fatura pazarı", "Fatura pazarı", "Doğrulanmış ve finansmana açılmış faturalar. Satırı seçerek risk raporunu görün ve teklif verin.",
    `<div id="mk"></div><div class="panel"><div class="filters"><input class="f" id="mq" placeholder="Firma veya belge no"><select class="f" id="mr"><option value="">Tüm risk sınıfları</option><option value="A">A · düşük</option><option value="B">B · orta</option><option value="C">C · yüksek</option></select><input class="f" id="mm" type="number" placeholder="Min. tutar (TL)"><select class="f" id="md"><option value="">Tüm vadeler</option><option>30</option><option>60</option><option>90</option><option>120</option></select><select class="f" id="ms"><option value="amount">Tutara göre</option><option value="due">Vadeye göre</option></select></div><div id="lst"></div></div>`);
  ["mq", "mm"].forEach(i => $("#" + i).oninput = debounce(draw, 300));
  ["mr", "md", "ms"].forEach(i => $("#" + i).onchange = draw);
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
    `<div class="panel">${docTable(list, "market")}</div>`);
}
async function network() {
  app.innerHTML = shell("denetim/ag", "Denetim / Fatura ağı analizi", "Fatura ağı analizi", "Firmalar arası fatura akışı. Döngüsel zincirler, paravan şirketler ve fatura simsarları kırmızıyla işaretlenir.",
    `<div class="panel net"><div class="ph"><div class="legend"><span><i style="background:#17734a"></i>Temiz</span><span><i style="background:#b3261e"></i>Şüpheli</span><span class="muted">Daire boyutu: kesilen fatura toplamı</span></div><button class="btn sm" data-act="netreport">Gemma ağ raporu</button></div><div id="nr"></div><svg id="g" role="img" aria-label="Fatura ağı grafiği"></svg></div>`);
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
    nodes.map(n => `<g><circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${n.flagged ? "#b3261e" : "#17734a"}" fill-opacity=".85" stroke="#fff" stroke-width="2"><title>${esc(n.name)} · ${esc(n.sector)} · ${esc(TL0(n.total))}</title></circle><text x="${n.x}" y="${n.y + n.r + 13}" text-anchor="middle" font-size="11" fill="#1b2430">${esc((n.name || "").split(" ").slice(0, 2).join(" "))}</text></g>`).join("");
}
async function ledger() {
  const draw = async () => {
    const qs = new URLSearchParams({ company: $("#lc").value, action: $("#la").value, from: $("#lf1").value, to: $("#lt").value });
    $("#csv").href = "/api/audit.csv?" + qs;
    const rows = await api("/audit?" + qs);
    $("#lst").innerHTML = rows.length ? `<div class="tw"><table class="data"><thead><tr><th>Zaman</th><th>Kullanıcı</th><th>Firma</th><th>IP</th><th>İşlem</th><th>Dosya</th><th>SHA-256</th><th>Belge no</th></tr></thead><tbody>${rows.map(r => `<tr><td>${DT(r.at)}</td><td>${esc(r.username)}</td><td>${esc(r.company)}</td><td class="mono">${esc(r.ip_address)}</td><td><span class="badge">${esc(r.action)}</span></td><td>${esc(r.file_name)}</td><td class="mono" title="${esc(r.sha256)}">${short(r.sha256)}</td><td class="mono">${esc(r.invoice_no)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Kayıt yok.</div>';
  };
  app.innerHTML = shell("denetim/kayit", "Denetim / Kayıt defteri", "Kayıt defteri", "Platformdaki tüm işlemler; kullanıcı, zaman, IP ve dosya özetiyle.",
    `<div class="panel"><div class="filters"><input class="f" id="lc" placeholder="Firma VKN"><select class="f" id="la"><option value="">Tüm işlemler</option>${["login", "login_failed", "logout", "upload", "duplicate_upload", "extract", "offer_created", "offer_accepted", "offer_rejected", "transfer_mock"].map(a => `<option>${a}</option>`).join("")}</select><input class="f" id="lf1" type="date"><input class="f" id="lt" type="date"><a class="btn" id="csv" href="/api/audit.csv">CSV indir</a></div><div id="lst"></div></div>`);
  ["lc"].forEach(i => $("#" + i).oninput = debounce(draw, 300));
  ["la", "lf1", "lt"].forEach(i => $("#" + i).onchange = draw);
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
  "": home, giris: login, guvenlik, mevzuat,
  kobi: kobiHome, "kobi/belgeler": kobiDocs, "kobi/yukle": kobiUpload,
  finansor: market, "finansor/teklifler": myOffers, "finansor/portfoy": portfolio,
  denetim: reviewQueue, "denetim/ag": network, "denetim/kayit": ledger,
  bildirimler: notifications,
};

// ---------- events ----------
document.addEventListener("click", async e => {
  const roleLink = e.target.closest("[data-role]");
  if (roleLink) S.loginRole = roleLink.dataset.role;
  const row = e.target.closest("[data-go]"), b = e.target.closest("[data-act]");
  if (row && !b) { go(row.dataset.go); return; }
  if (!b) return;
  const a = b.dataset.act, id = b.dataset.id;
  try {
    if (a === "role") { S.loginRole = b.dataset.v; login(); }
    if (a === "logout") { await api("/logout", { method: "POST" }).catch(() => {}); S.user = null; S.upload = null; go(""); }
    if (a === "bell") { S.ddOpen = !S.ddOpen; nav(); }
    if (a === "newupload") { S.upload = null; kobiUpload(); }
    if (a === "extract") {
      S.upload.busy = true; kobiUpload();
      try { const r = await api(`/documents/${encodeURIComponent(S.upload.doc.id)}/extract`, { method: "POST" }); S.upload.fields = r.fields; S.upload.fields.items ||= []; }
      finally { S.upload.busy = false; } kobiUpload();
    }
    if (a === "check") {
      const fields = readFields(); S.upload.busy = true; kobiUpload();
      try { S.upload.check = await api(`/documents/${encodeURIComponent(S.upload.doc.id)}/check`, { method: "POST", body: { fields } }); S.upload.doc = S.upload.check.document; S.upload.step = 3; }
      finally { S.upload.busy = false; } kobiUpload();
    }
    if (a === "publish") {
      const r = await api(`/documents/${encodeURIComponent(S.upload.doc.id)}/publish`, { method: "POST" });
      S.upload.check.document = r.document || { ...S.upload.check.document, status: r.status }; S.upload.step = 4; kobiUpload();
    }
    if (a === "accept") { const r = await api(`/offers/${id}/accept`, { method: "POST" }); toast("Teklif kabul edildi. " + (r.receipt?.reference ? "Dekont: " + r.receipt.reference : "")); render(); }
    if (a === "reject") { await api(`/offers/${id}/reject`, { method: "POST" }); toast("Teklif reddedildi."); render(); }
    if (a === "withdraw") { await api(`/offers/${id}`, { method: "DELETE" }); toast("Teklif geri çekildi."); render(); }
    if (a === "compare") { $("#cmp").innerHTML = `<p class="muted">${spin} Gemma teklifleri karşılaştırıyor…</p>`; const r = await api(`/documents/${encodeURIComponent(id)}/compare`); $("#cmp").innerHTML = `<div class="gemma" style="margin-top:12px"><span class="by">Gemma 4 önerisi</span><b>${esc(r.recommendation)}</b>\n${esc(r.reason)}</div>`; }
    if (a === "review") { await api(`/documents/${encodeURIComponent(id)}/review`, { method: "POST", body: { decision: b.dataset.v, reason: $("#rs").value } }); toast(b.dataset.v === "approve" ? "Belge pazara açıldı." : "Belge reddedildi."); go("denetim"); }
    if (a === "netreport") { $("#nr").innerHTML = `<div class="pb">${spin} <span class="muted">Gemma şüpheli kümeyi raporluyor…</span></div>`; const r = await api("/network/report", { method: "POST" }); $("#nr").innerHTML = `<div class="pb"><div class="gemma"><span class="by">Gemma 4 ağ raporu</span>${esc(r.report)}</div></div>`; }
  } catch (err) { toast(err.message); const ue = $("#ue"); if (ue) ue.textContent = err.message; }
});
document.addEventListener("click", e => { if (S.ddOpen && !e.target.closest(".bell")) { S.ddOpen = false; nav(); } }, true);
addEventListener("hashchange", render);

(async () => { try { S.user = (await api("/me")).user; } catch { S.user = null; } render(); })();

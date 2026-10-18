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

// query string without empty values (the API rejects "" for numeric filters)
const qsOf = obj => new URLSearchParams(Object.entries(obj).filter(([, v]) => v !== "" && v != null));
const RISK_MAX = { A: 29, B: 59, C: 100 };

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

const caret = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M6 9l6 6 6-6"/></svg>';
const AUD = [
  ["kobi", "KOBİ'yim", "Vadeli faturamı beklemeden nakde çevirmek istiyorum", icon.up],
  ["finansor", "Finansörüm", "Doğrulanmış alacaklara teklif vermek istiyorum", icon.bank],
  ["alici", "Alıcı firmayım", "Tedarikçilerime ödeme yapan taraf benim", icon.doc],
];
const LOGINS = [
  ["kobi", "KOBİ girişi", "VKN ve parola ile", icon.up],
  ["finansor", "Finansör girişi", "Lisanslı kuruluş kullanıcıları", icon.bank],
  ["denetim", "Denetim girişi", "İnceleme ve kayıt defteri", icon.shield],
];
function nav() {
  const open = k => S.menu === k ? "open" : "";
  $("#nav").innerHTML = S.user
    ? `<a href="#/${ROLE_HOME[S.user.role]}">Panelim</a>
       <span class="bell"><button class="btn ghost sm" data-act="bell" aria-label="Bildirimler">${icon.bell}</button>${unread() ? `<span class="dot">${unread()}</span>` : ""}
       ${S.ddOpen ? `<div class="dd">${S.notes.length ? S.notes.slice(0, 6).map(n => `<div class="it ${n.read ? "" : "unread"}"><b>${esc(n.subject)}</b><div class="small">${esc(n.body)}</div><small>${DT(n.created_at)}</small></div>`).join("") : '<div class="it muted">Bildirim yok.</div>'}<div class="it"><a href="#/bildirimler">Tümünü gör</a></div></div>` : ""}</span>
       <button class="btn sm" data-act="logout">Çıkış</button>`
    : `<div class="menu ${open("aud")}"><button data-act="menu" data-v="aud">Kimler için ${caret}</button><div class="drop-list">${AUD.map(([k, t, s, i]) => `<a href="#/kimler/${k}"><span class="ico">${i}</span><span><b>${t}</b><small>${s}</small></span></a>`).join("")}</div></div>
       <a href="#/#surec">Nasıl çalışır</a><a href="#/sahtecilik">Sahte fatura</a><a href="#/mevzuat">Mevzuat</a>
       <div class="menu login ${open("login")}"><button data-act="menu" data-v="login">Giriş ${caret}</button><div class="drop-list">${LOGINS.map(([k, t, s, i]) => `<a href="#/giris/${k}"><span class="ico">${i}</span><span><b>${t}</b><small>${s}</small></span></a>`).join("")}</div></div>`;
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
    S.menu = null; nav();
    const view = ROUTES[r] || (p[0] === "belge" ? () => detail(p.slice(1).join("/"))
      : p[0] === "giris" ? () => login(p[1]) : p[0] === "kimler" ? () => audience(p[1]) : home);
    await view();
  } catch (e) {
    app.innerHTML = `<div class="wrap"><div class="panel" style="margin:40px 0"><div class="pb"><b>Bir hata oluştu.</b><p class="muted">${esc(e.message)}</p></div></div></div>`;
  }
  if (location.hash.includes("#surec") || location.hash.includes("#kontroller")) { const id = location.hash.split("#").pop(); document.getElementById(id)?.scrollIntoView(); }
  else scrollTo(0, 0);
}
async function refreshNotes() { try { S.notes = await api("/notifications"); nav(); } catch { /* ignore */ } }

// ---------- public pages ----------
const ext = '<svg class="ext" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/></svg>';
const FLAG = '<svg class="flag" viewBox="0 0 1200 800" role="img" aria-label="Türk bayrağı"><rect width="1200" height="800" fill="#e30a17"/><circle cx="425" cy="400" r="200" fill="#fff"/><circle cx="475" cy="400" r="160" fill="#e30a17"/><path fill="#fff" d="M583.334 400l180.901 58.779-111.804-153.885v190.212l111.804-153.885z"/></svg>';

const posters = () => `<section class="band" id="sahtecilik-afis"><div class="wrap">
  <div class="campaign-head"><span class="no">#FaturaSahteciliğineHayır</span></div>
  <div class="posters">
    <article class="poster p1"><span class="kicker">Vergi Usul Kanunu md. 359</span><h3>Naylon fatura<br>suçtur.</h3><p>Gerçek bir satış olmadan fatura düzenlemek de, o faturayı gider göstermek de hapis cezası gerektirir. Komisyon teklifi “küçük bir iyilik” değildir.</p><div class="foot"><span class="stamp">3–8 YIL</span><span>hapis cezası öngörülür</span></div></article>
    <article class="poster p2"><span class="kicker">Fatura satın alınmaz, satılmaz</span><h3>“Sende fatura var mı?”<br>sorusuna hayır de.</h3><p>Size komisyon karşılığı fatura kesmeniz teklif edildiyse Vergi İletişim Merkezi'ni arayabilir veya resmî ihbar kanallarını kullanabilirsiniz.</p><div class="foot"><span class="stamp">VİMER 189</span><span>Vergi İletişim Merkezi</span></div></article>
    <article class="poster p3"><span class="kicker">Yasal finansman</span><h3>Gerçek mal,<br>gerçek fatura.</h3><p>Nakit sıkışıklığının çözümü sahte belge değil. Gerçek satışınızın faturasını lisanslı finansman kuruluşlarına devrederek vadeyi beklemeden tahsil edin.</p><div class="foot"><a class="btn sm" style="background:#fff;border-color:#fff;color:#0a5f67" href="#/kimler/kobi">Nasıl yapılır?</a></div></article>
  </div>
</div></section>`;

function home() {
  app.innerHTML = `
  <section class="hero"><div class="wrap">
    <div>
      <span class="pill navy">Fatura finansmanı</span>
      <h1>Vadeli faturanızı<br>güvenle nakde çevirin</h1>
      <p class="lead">Faturanız platform sunucusunda çalışan Gemma 4 modeliyle okunur, sahte belge kontrollerinden geçer ve lisanslı finansman kuruluşlarının teklifine açılır. Kabul ettiğiniz tutar vadeyi beklemeden hesabınıza geçer.</p>
      <div class="actions"><a class="btn primary" href="#/giris/kobi">KOBİ girişi</a><a class="btn" href="#/giris/finansor">Finansör girişi</a></div>
    </div>
    <div class="side-cards">
      <a class="scard" href="#/kimler/kobi"><span class="pill">KOBİ'ler için</span><div class="row"><div><h4>Vadeyi beklemeden tahsilat</h4><p>90 gün vadeli faturanızı bugün finansmana açın, teklifleri karşılaştırın.</p></div>${ext}</div></a>
      <a class="scard" href="#/kimler/finansor"><span class="pill">Finansörler için</span><div class="row"><div><h4>Doğrulanmış alacak pazarı</h4><p>Her belge Gemma 4 risk raporu ve alıcı ödeme geçmişiyle birlikte gelir.</p></div>${ext}</div></a>
      <a class="scard" href="#/sahtecilik"><span class="pill red">Sahte belgeyle mücadele</span><div class="row"><div><h4>Naylon fatura tespiti</h4><p>Döngüsel fatura zincirleri ve fatura simsarları ağ analiziyle işaretlenir.</p></div>${ext}</div></a>
    </div>
  </div></section>

  <section class="band alt"><div class="wrap">
    <h2>Hizmetler</h2><p class="sub">Platformda tarafına göre kullanabileceğiniz başlıca işlemler.</p>
    <div class="services">
      <a class="service" href="#/giris/kobi"><span class="ico">${icon.up}</span><h4>Fatura yükleme</h4><p>PNG, JPG veya PDF faturanızı yükleyin; okuma ve kontrol adımlarını izleyin.</p><span class="go">Başla ${icon.chev}</span></a>
      <a class="service" href="#/giris/kobi"><span class="ico">${icon.doc}</span><h4>Teklif karşılaştırma</h4><p>Gelen teklifleri Gemma 4 yorumlarıyla birlikte net tutar ve yıllık maliyete göre görün.</p><span class="go">Belgelerim ${icon.chev}</span></a>
      <a class="service" href="#/giris/finansor"><span class="ico">${icon.bank}</span><h4>Fatura pazarı</h4><p>Risk sınıfı, vade ve alıcının ödeme geçmişine göre filtreleyip teklif verin.</p><span class="go">Pazara git ${icon.chev}</span></a>
      <a class="service" href="#/guvenlik"><span class="ico">${icon.hash}</span><h4>Kayıt ve bütünlük</h4><p>Her belge SHA-256 özeti, yükleme zamanı ve IP adresiyle kayıt defterinde saklanır.</p><span class="go">Güvenlik ${icon.chev}</span></a>
    </div>
  </div></section>

  <section class="band" id="surec"><div class="wrap">
    <h2>Nasıl çalışır?</h2><p class="sub">Belgenin yüklenmesinden ödemeye kadar her adım panelinizden izlenir.</p>
    <div class="steps">
      <div><h4>Yükleme</h4><p>Fatura yüklenir; dosya özeti, zaman ve IP adresi kaydedilir.</p></div>
      <div><h4>Okuma ve doğrulama</h4><p>Gemma 4 faturayı okur; e-Fatura kaydı, alıcı onayı ve sahte belge kurallarıyla karşılaştırılır.</p></div>
      <div><h4>Teklif</h4><p>Belge pazara açılır; finansörler alıcının ödeme geçmişini görerek teklif verir.</p></div>
      <div><h4>Ödeme</h4><p>Kabul ettiğiniz tutar hesabınıza geçer; alıcı vadede finansöre öder.</p></div>
    </div>
  </div></section>

  <section class="band alt" id="kontroller"><div class="wrap">
    <h2>Sahte belge kontrolleri</h2><p class="sub">Şüpheli bulunan belge otomatik reddedilmez; denetim ekibinin incelemesine gönderilir.</p>
    <table class="checks"><thead><tr><th>Kontrol</th><th>Ne inceleniyor</th></tr></thead><tbody>
      <tr><td>Çift kullanım</td><td>Aynı belgenin daha önce yüklenip yüklenmediği, dosya ve fatura özetiyle karşılaştırılır.</td></tr>
      <tr><td>Teslimat belgesi</td><td>Mal satışı içeren faturada irsaliye bilgisinin bulunup bulunmadığı.</td></tr>
      <tr><td>Faaliyet uyumu</td><td>Satıcının faaliyet alanı ile faturadaki mal ve hizmetin uyumu.</td></tr>
      <tr><td>Kapasite</td><td>Kesilen fatura tutarlarının işletmenin çalışan sayısıyla orantısı.</td></tr>
      <tr><td>Fatura ağı</td><td>Firmalar arasında dönen fatura zincirleri, aynı adresi paylaşan yeni şirketler ve fatura simsarları.</td></tr>
      <tr><td>Alıcı onayı ve ödeme geçmişi</td><td>Faturayı ödeyecek firmanın belgeyi kabul edip etmediği ve geçmiş ödemelerindeki gecikmeler.</td></tr>
    </tbody></table>
  </div></section>

  <section class="band"><div class="wrap">
    <h2>Bilgilendirme</h2><p class="sub">Platformun dayandığı temel düzenlemeler.</p>
    <div class="notice">
      <article><span class="pill">Faktoring</span><h4>6361 sayılı Kanun</h4><p>Alacakları satın alan taraflar BDDK lisanslı faktoring şirketleri ve bankalardır. Bireysel yatırımcıya açık değildir.</p></article>
      <article><span class="pill red">Vergi</span><h4>VUK md. 359</h4><p>Gerçek bir mal veya hizmet satışına dayanmayan belge düzenlemek ve kullanmak suçtur.</p></article>
      <article><span class="pill navy">Kişisel veri</span><h4>6698 sayılı KVKK</h4><p>Fatura verileri platform sunucusundaki model ile işlenir; üçüncü taraf yapay zekâ servislerine gönderilmez.</p></article>
    </div>
  </div></section>
  ${posters()}
  ${footer()}`;
}

const footer = () => `<footer class="site"><div class="wrap">
  <div><b style="color:#fff;font-size:16px;font-family:var(--head)">VadeX</b><p style="margin:8px 0 0;max-width:340px">Vadeli alacakların doğrulanarak lisanslı finansman kuruluşlarına devri için geliştirilmiş özel bir platformdur; bir kamu kurumu değildir. Hacktoberfest 2026 Elazığ projesi.</p></div>
  <div><h5>Kimler için</h5><a href="#/kimler/kobi">KOBİ'ler</a><a href="#/kimler/finansor">Finansörler</a><a href="#/kimler/alici">Alıcı firmalar</a></div>
  <div><h5>Kurumsal</h5><a href="#/guvenlik">Güvenlik</a><a href="#/mevzuat">Mevzuat</a><a href="#/sahtecilik">Sahte faturayla mücadele</a></div>
  <div><h5>Giriş</h5><a href="#/giris/kobi">KOBİ girişi</a><a href="#/giris/finansor">Finansör girişi</a><a href="#/giris/denetim">Denetim girişi</a></div>
  <div class="bottom"><span>© 2026 VadeX · Demo sürümü · Gemma 4 · Ollama · GitHub Copilot</span><span>Kişisel Verilerin Korunması · Kullanım Koşulları</span></div>
</div></footer>`;

function staticPage(title, html, withPosters) {
  app.innerHTML = `<div class="wrap" style="padding:40px 24px 60px;max-width:900px"><div class="crumbs"><a href="#/">Ana sayfa</a> / ${esc(title)}</div><h1 style="font-size:30px;margin-bottom:18px">${esc(title)}</h1>${html}</div>${withPosters ? posters() : ""}${footer()}`;
}
const guvenlik = () => staticPage("Güvenlik", `
  <div class="panel"><div class="pb"><dl class="kv">
    <dt>Model</dt><dd>Gemma 4, platform sunucusunda Ollama ile çalışır. Belge içeriği dış servislere gönderilmez.</dd>
    <dt>Bütünlük</dt><dd>Her dosyanın SHA-256 özeti saklanır; aynı belge ikinci kez finansmana açılamaz.</dd>
    <dt>Kayıt defteri</dt><dd>Giriş, yükleme, teklif ve kabul işlemleri kullanıcı, zaman, IP ve cihaz bilgisiyle kaydedilir; kayıtlar değiştirilemez.</dd>
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
const sahtecilik = () => staticPage("Sahte faturayla mücadele", `
  <p class="muted" style="font-size:16px;margin-top:0">Naylon fatura; gerçekte satılmayan bir mal veya hizmet için düzenlenen faturadır. Faturayı alan taraf bunu gider gösterip vergisini düşürür, düzenleyen taraf komisyon alır. İki taraf da suç işler.</p>
  <div class="panel"><div class="ph"><h3>Örnek: 200.000 TL'lik naylon fatura</h3><span class="pill red">Suç</span></div><div class="pb"><dl class="kv">
    <dt>Faturayı kullanan</dt><dd>200.000 TL'yi gider yazar; kurumlar vergisinden 50.000 TL, KDV'den 40.000 TL olmak üzere yaklaşık 90.000 TL vergi kaçırır.</dd>
    <dt>Faturayı düzenleyen</dt><dd>Örneğin 16.000 TL komisyon alır, ancak kâğıt üzerinde 90.000 TL vergi borcunun altına girer.</dd>
    <dt>Yakalanırsa</dt><dd>Her iki taraf için 3–8 yıl hapis; kaçırılan verginin üç katı vergi ziyaı cezası ve gecikme faizi.</dd>
  </dl><p class="muted small" style="margin:12px 0 0">Oranlar örnek amaçlıdır; kesin hesap için mali müşavirinize danışın.</p></div></div>
  <div class="panel"><div class="ph"><h3>VadeX naylon faturayı nasıl yakalar?</h3></div><div class="pb"><ul style="margin:0;padding-left:18px">
    <li>Alıcı onayı olmayan fatura pazara çıkmaz.</li><li>İrsaliyesiz mal faturası, faaliyetle uyumsuz kalem ve kapasiteyi aşan tutarlar işaretlenir.</li>
    <li>Fatura ağında A → B → C → A döngüleri, aynı adresli yeni şirketler ve onlarca ilgisiz firmaya fatura kesen simsarlar tespit edilir.</li>
    <li>Gemma 4 her bulguyu sade bir dille açıklar; son kararı denetim ekibi verir.</li></ul></div></div>`, true);

// audience pages
const AUDIENCE = {
  kobi: {
    pill: "KOBİ'ler için", title: "Sattınız, teslim ettiniz. Paranız için 90 gün beklemeyin.",
    lead: "Büyük bir firmaya kestiğiniz vadeli faturayı yükleyin; doğrulandıktan sonra lisanslı finansman kuruluşları teklif versin. Kredi başvurusu, ipotek veya kefil gerekmez; risk, faturayı ödeyecek alıcıya göre ölçülür.",
    calc: [["Fatura tutarı (90 gün vade)", "100.000,00 TL"], ["Örnek kırma bedeli (%5,5)", "−5.500,00 TL"], ["Platform hizmet bedeli (%0,5)", "−500,00 TL"], ["Bugün hesabınıza geçen", "94.000,00 TL"]],
    benefits: [["Teminat istenmez", "Değerlendirme alıcı firmanın ödeme gücüne göre yapılır; işletmenizin mülkü teminat gösterilmez."], ["Rekabetçi teklif", "Birden fazla finansör aynı faturaya teklif verir; en yüksek net tutarı siz seçersiniz."], ["Gemma 4 ile yorum", "Her teklifin yıllık maliyeti ve uygunluğu sade bir dille açıklanır."], ["Şeffaf süreç", "Okuma, doğrulama, teklif ve ödeme adımları panelinizde anlık görünür."], ["Yasal ve kayıtlı", "Tüm işlem e-Fatura kaydına dayanır; tefecilik veya kayıt dışı finansmana gerek kalmaz."], ["Veriniz sizde kalır", "Fatura içeriği platform dışındaki yapay zekâ servislerine gönderilmez."]],
    cta: ["kobi", "KOBİ girişi"],
  },
  finansor: {
    pill: "Finansman kuruluşları için", title: "Doğrulanmış alacaklara, risk raporuyla birlikte teklif verin.",
    lead: "Pazardaki her fatura e-Fatura kaydı, alıcı onayı ve sahte belge kontrollerinden geçmiş olarak gelir. Alıcının ödeme geçmişi ve Gemma 4 risk özeti, analiz süresini dakikalara indirir.",
    calc: [["Nominal alacak", "100.000,00 TL"], ["Teklifiniz (bugün ödenen)", "94.500,00 TL"], ["Vade (gün)", "90"], ["Vade sonu brüt getiri", "5.500,00 TL · yıllık ≈ %23,6"]],
    benefits: [["Ön doğrulama", "Çift kullanım, irsaliye, faaliyet uyumu ve fatura ağı kontrolleri tamamlanmış belgeler."], ["Alıcı ödeme geçmişi", "Alıcının son 18 aydaki ödeme davranışı ve gecikme eğilimi tek ekranda."], ["Gemma 4 risk özeti", "Her belge için önerilen iskonto ve gerekçesi; karar sizde kalır."], ["Filtreli pazar", "Risk sınıfı, tutar, vade ve sektöre göre listeleme."], ["Kayıt defteri", "Teklif ve kabul işlemleri değiştirilemez şekilde kayıt altında."], ["Veri yerelliği", "Model platform sunucusunda çalışır; müşteri verisi dışarı çıkmaz."]],
    cta: ["finansor", "Finansör girişi"],
  },
  alici: {
    pill: "Alıcı firmalar için", title: "Tedarikçinizi ayakta tutun, nakdiniz kasanızda kalsın.",
    lead: "Faturayı ödeyecek taraf sizsiniz. Tedarikçileriniz faturalarını finansmana açarak vadeyi beklemeden nakde ulaşır; siz ödemeyi aynı vadede yaparsınız. Üretim zinciriniz nakit sıkışıklığı yüzünden durmaz.",
    calc: [["Tedarikçi faturası", "100.000,00 TL"], ["Sizin ödeme tarihiniz", "Değişmez (vade sonu)"], ["Tedarikçinin bugün aldığı", "≈ 94.000,00 TL"], ["Sizin ek maliyetiniz", "0 TL"]],
    benefits: [["Kesintisiz tedarik", "Tedarikçileriniz hammadde ve maaş ödemelerini aksatmadan üretime devam eder."], ["Vade gücü", "Tedarikçiniz nakde erken ulaştığı için vade görüşmelerinde esneklik kazanırsınız."], ["Tek onay", "Faturayı e-Fatura üzerinden onaylamanız yeterli; ödeme yönlendirmesi platformda görünür."], ["Ödeme itibarı", "Zamanında ödeme geçmişiniz, tedarikçilerinizin daha iyi teklif almasını sağlar."], ["Sahte belgeye karşı", "Adınıza düzenlenmiş ancak onaylamadığınız faturalar pazara çıkmaz."], ["Raporlama", "Hangi tedarikçinizin hangi faturayı finansmana açtığını izleyin."]],
    cta: ["giris/kobi", "Tedarikçilerinizi davet edin"],
  },
};
function audience(kind) {
  const a = AUDIENCE[kind] || AUDIENCE.kobi;
  app.innerHTML = `<section class="aud-hero"><div class="wrap"><div>
      <div class="tabs-aud">${AUD.map(([k, t]) => `<a class="pill ${k === kind ? "navy" : ""}" href="#/kimler/${k}">${t}</a>`).join("")}</div>
      <h1>${esc(a.title)}</h1><p>${esc(a.lead)}</p>
      <div class="actions" style="display:flex;gap:12px;flex-wrap:wrap"><a class="btn primary" href="#/${a.cta[0].includes("/") ? a.cta[0] : "giris/" + a.cta[0]}">${esc(a.cta[1])}</a><a class="btn" href="#/#surec">Nasıl çalışır?</a></div></div>
    <div class="calc"><h4>Örnek hesap</h4>${a.calc.map(([l, v], i) => `<div class="line ${i === a.calc.length - 1 ? "total" : ""}"><span>${esc(l)}</span><b>${esc(v)}</b></div>`).join("")}<p class="muted small" style="margin:10px 0 0">Oranlar örnek amaçlıdır; gerçek oran piyasa faizine ve alıcının riskine göre belirlenir.</p></div>
  </div></section>
  <section class="band"><div class="wrap"><h2>Avantajlar</h2><p class="sub">${esc(a.pill)} VadeX'in sağladıkları.</p>
    <div class="benefits">${a.benefits.map(([t, p], i) => `<div class="benefit"><span class="ico">${[icon.shield, icon.bank, icon.doc, icon.up, icon.hash, icon.shield][i]}</span><h4>${esc(t)}</h4><p>${esc(p)}</p></div>`).join("")}</div></div></section>
  ${posters()}${footer()}`;
}

// ---------- login ----------
async function login(roleFromUrl) {
  if (roleFromUrl) S.loginRole = roleFromUrl;
  let demo = [];
  try { demo = await api("/demo-accounts"); } catch { /* optional */ }
  const role = S.loginRole;
  const label = { kobi: "Vergi kimlik numarası", finansor: "Kurum kullanıcı adı", denetim: "Kullanıcı adı" }[role];
  const accounts = (Array.isArray(demo) ? demo.find(d => d.role === role)?.accounts : demo[role]) || [];
  const list = accounts.slice(0, 4).map(u => { const n = typeof u === "string" ? u : u.username; return `<code data-act="fill" data-v="${esc(n)}" title="${esc(u.display_name || "")}">${esc(n)}</code>`; }).join(" ");
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
// an upload the user cancelled, and an upload that was never read/checked properly (shown as a draft)
const isCancelled = d => (d.flags || []).some(f => f.code === "user_cancelled");
const isDraft = d => !isCancelled(d) && d.status === "incelemede" && (d.risk_score == null || !d.invoice_no || String(d.invoice_no).length < 6);
const draftRow = d => `<tr><td><span class="badge warn">Taslak</span> <span class="small">${esc(d.file?.name || d.id)}</span></td><td class="muted">–</td><td class="num muted">–</td><td class="muted">–</td><td class="muted">–</td><td class="muted small">Okuma veya kontrol tamamlanmadı</td>
  <td class="num"><button class="btn sm" data-act="resume" data-id="${esc(d.id)}">Devam et</button> <button class="btn sm ghost" data-act="cancelupload" data-id="${esc(d.id)}">Sil</button></td></tr>`;
function docTable(list, mode) {
  if (!list.length) return '<div class="empty">Kayıt bulunamadı.</div>';
  const fin = mode === "market";
  return `<div class="tw"><table class="data"><thead><tr><th>Belge no</th><th>${fin ? "Satıcı (KOBİ)" : "Alıcı"}</th>${fin ? "<th>Alıcı</th>" : ""}<th class="num">Tutar</th><th>Vade</th><th>Risk</th>${fin ? '<th class="num">Kredi skoru</th><th class="num">En iyi teklif</th>' : "<th>Durum</th>"}<th class="num">Teklif</th></tr></thead><tbody>
  ${list.map(d => !fin && isDraft(d) ? draftRow(d) : `<tr class="go" data-go="belge/${esc(d.id)}"><td class="mono">${esc(d.invoice_no)}</td><td>${esc(fin ? d.seller?.name : d.buyer?.name)}</td>${fin ? `<td>${esc(d.buyer?.name)}</td>` : ""}<td class="num"><b>${TL0(d.total)}</b></td><td>${DATE(d.due_date)} <span class="muted small">${d.days_left != null ? d.days_left + " gün" : ""}</span></td><td>${riskBadge(d)}</td>${fin ? `<td class="num">${d.buyer?.credit_score ?? "–"}</td><td class="num">${d.best_offer ? TL0(d.best_offer) : "–"}</td>` : `<td>${st(d.status)}</td>`}<td class="num">${d.offer_count ?? 0}</td></tr>`).join("")}
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
  const [stats, all] = await Promise.all([api("/stats"), api("/my/documents")]);
  const docs = all.filter(d => !isCancelled(d));
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
    // cancelled uploads only appear when the user filters for rejected documents
    $("#lst").innerHTML = docTable(docs.filter(d => (s === "reddedildi" || !isCancelled(d))
      && (!q || ((d.invoice_no || "") + " " + (d.buyer?.name || "") + " " + (d.file?.name || "")).toLowerCase().includes(q)) && (!s || d.status === s)));
  };
  app.innerHTML = shell("kobi/belgeler", "Panel / Belgelerim", "Belgelerim", "Yüklediğiniz tüm faturalar.",
    `<div class="panel"><div class="filters"><input class="f" id="fq" placeholder="Belge no veya alıcı ara"><select class="f" id="fs"><option value="">Tüm durumlar</option>${Object.entries(STATUS).slice(0, 5).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join("")}</select><a class="btn primary" href="#/kobi/yukle">Fatura yükle</a></div><div id="lst"></div></div>`);
  $("#fq").oninput = draw; $("#fs").onchange = draw; takeSearch("#fq"); draw();
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
const cancelBtn = id => `<button class="btn block" style="margin-top:10px" data-act="cancelupload" data-id="${esc(id)}">Vazgeç ve yüklemeyi sil</button>`;
function stepHelp(U) {
  if (U.step === 2 && U.notInvoice) return `<div class="panel"><div class="ph"><h3>Okuma</h3><span class="badge bad">Fatura bulunamadı</span></div><div class="pb">
    <div class="ai-line" style="margin-bottom:14px">${esc(U.notInvoice)}</div>
    <button class="btn red block" data-act="cancelupload" data-id="${esc(U.doc.id)}">Yüklemeyi sil</button>
    <button class="btn block" style="margin-top:10px" data-act="manual">Bilgileri elle doldur</button></div></div>`;
  if (U.step === 2 && !U.fields) return `<div class="panel"><div class="ph"><h3>Okuma</h3></div><div class="pb"><p class="muted" style="margin-top:0">Fatura, kurum sunucusunda çalışan Gemma 4 modeliyle okunur. Bilgileri kontrol edip gerekirse düzeltebilirsiniz.</p><button class="btn primary block" data-act="extract">${U.busy ? spin + " Gemma okuyor…" : "Gemma ile oku"}</button>${cancelBtn(U.doc.id)}<div class="err" id="ue"></div></div></div>`;
  if (U.step === 2) return `<div class="panel"><div class="ph"><h3>Kontrol</h3></div><div class="pb"><p class="muted" style="margin-top:0">Bilgiler e-Fatura kaydı (simülasyon), alıcı onayı ve sahte belge kurallarıyla karşılaştırılır.</p><button class="btn primary block" data-act="check">${U.busy ? spin + " Kontrol ediliyor…" : "Kontrol et"}</button>${cancelBtn(U.doc.id)}<div class="err" id="ue"></div></div></div>`;
  return "";
}
function fieldsPanel(U) {
  if (!U.fields) return "";
  const f = U.fields, ro = U.step > 2 ? "readonly" : "";
  const inp = (k, l) => `<div class="field"><label class="f">${l}</label><input class="f" data-k="${k}" value="${esc(f[k] ?? "")}" ${ro}></div>`;
  return `<div class="panel"><div class="ph"><h3>Okunan bilgiler</h3><span class="badge info">Gemma 4</span></div><div class="pb">
    ${(f.corrections || []).map(c => `<div class="ai-line" style="margin-bottom:10px">${esc(c.field === "buyer_vkn" ? "Alıcı" : "Satıcı")} VKN'si <span class="mono">${esc(c.read)}</span> okundu, kayıtlarla eşleştirilip <b class="mono">${esc(c.corrected)}</b> olarak düzeltildi. Lütfen kontrol edin.</div>`).join("")}
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
    <div class="gemma" style="margin-top:12px"><span class="by">Gemma 4 değerlendirmesi</span>${md(U.check.explanation)}</div>
    ${U.step === 3 ? `<button class="btn teal block" style="margin-top:16px" data-act="publish">${d.risk_score >= 60 ? "Denetim incelemesine gönder" : "Finansmana aç"}</button>${cancelBtn(d.id)}` : ""}
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
      ${d.flags?.length ? `<h4 style="margin:6px 0 10px;font-size:14px">Bulgular</h4><ul class="flags">${d.flags.map(fl => `<li class="${d.risk_score >= 60 ? "hi" : ""}"><b>${esc(fl.label)}</b> – ${esc(fl.detail)}</li>`).join("")}</ul>` : ""}</div></div>
      <div id="ins" style="margin-bottom:18px"></div>`;
  let right = "";
  if (role === "kobi") {
    right = `<div class="panel"><div class="ph"><h3>Gelen teklifler</h3><span class="muted small">${offers.length} teklif</span></div><div class="pb">
      ${offers.length ? [...offers].sort((a, b) => b.net_amount - a.net_amount).map((o, i) => `<div class="offer"><div><b>${esc(o.financier?.name)}</b> ${i === 0 && o.status === "beklemede" ? '<span class="badge ok">En yüksek</span>' : ""} ${o.status !== "beklemede" ? st(o.status) : ""}<div class="muted small">İskonto ${PCT(o.discount_rate)} · yıllık ${PCT(o.annual_rate)} · ${DT(o.created_at)}</div>${o.note ? `<div class="small">${esc(o.note)}</div>` : ""}</div><div class="net">${TL(o.net_amount)}</div>
        ${o.status === "beklemede" ? `<div class="ai-line" id="oc-${o.id}"><span class="skeleton" style="display:inline-block;width:60%;margin:0;vertical-align:middle"></span></div>` : ""}
        ${o.status === "beklemede" && !["finanse_edildi", "reddedildi"].includes(d.status) ? `<div class="acts"><button class="btn primary sm" data-act="accept" data-id="${o.id}">Kabul et</button><button class="btn sm" data-act="reject" data-id="${o.id}">Reddet</button></div>` : ""}</div>`).join("")
        : `<p class="muted" style="margin:0">${d.status === "incelemede" ? "Belge denetim incelemesinde. Onaylandıktan sonra pazara açılacak." : "Henüz teklif gelmedi. Teklif geldiğinde bildirim ve e-posta alacaksınız."}</p>`}
      </div></div><div id="cmp" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>`;
  } else if (role === "finansor") {
    const mine = offers.find(o => o.financier?.id === S.user.id && o.status === "beklemede");
    right = `<div id="rr" style="margin-bottom:18px"></div><div id="pay" style="margin-bottom:18px"></div><div id="forecast" style="margin-bottom:18px"></div>
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
  "": home, giris: () => login(), guvenlik, mevzuat, sahtecilik,
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
    if (a === "role") { go("giris/" + b.dataset.v); }
    if (a === "menu") { S.menu = S.menu === b.dataset.v ? null : b.dataset.v; nav(); }
    if (a === "fill") { $("#u").value = b.dataset.v; $("#pw").value = "demo1234"; $("#pw").focus(); }
    if (a === "logout") { await api("/logout", { method: "POST" }).catch(() => {}); S.user = null; S.upload = null; go(""); }
    if (a === "bell") { S.ddOpen = !S.ddOpen; nav(); }
    if (a === "newupload") { S.upload = null; kobiUpload(); }
    if (a === "extract") {
      S.upload.busy = true; kobiUpload();
      try {
        const r = await api(`/documents/${encodeURIComponent(S.upload.doc.id)}/extract`, { method: "POST" });
        if (r.not_invoice) { S.upload.notInvoice = r.message; S.upload.fields = null; }
        else { S.upload.notInvoice = null; S.upload.fields = r.fields; S.upload.fields.items ||= []; }
      } finally { S.upload.busy = false; } kobiUpload();
    }
    if (a === "manual") {
      S.upload.notInvoice = null;
      S.upload.fields = { invoice_no: "", issue_date: "", due_date: "", seller_vkn: S.user.company_vkn, seller_name: S.user.display_name,
        buyer_vkn: "", buyer_name: "", irsaliye_no: "", subtotal: "", kdv: "", total: "", items: [{ description: "", quantity: "", unit: "", unit_price: "" }] };
      kobiUpload();
    }
    if (a === "cancelupload") {
      if (!confirm("Bu yükleme silinecek. Emin misiniz?")) return;
      await api(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
      toast("Yükleme silindi. Aynı dosyayı yeniden yükleyebilirsiniz.");
      if (S.upload?.doc?.id === id) S.upload = null;
      if ((location.hash || "").includes("kobi/yukle")) kobiUpload(); else render();
    }
    if (a === "resume") {
      const r = await api(`/documents/${encodeURIComponent(id)}`);
      S.upload = { step: 2, doc: r.document };
      go("kobi/yukle");
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
document.addEventListener("click", e => {
  if (S.ddOpen && !e.target.closest(".bell")) { S.ddOpen = false; nav(); }
  if (S.menu && !e.target.closest(".menu")) { S.menu = null; nav(); }
}, true);
addEventListener("hashchange", render);
// header search: searches the list that belongs to the signed-in role
document.querySelector(".search").addEventListener("submit", e => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (!q) return;
  if (!S.user) { toast("Arama yapmak için giriş yapın."); go("giris"); return; }
  S.searchQ = q;
  const target = { kobi: "kobi/belgeler", finansor: "finansor", denetim: "denetim/kayit" }[S.user.role];
  if ((location.hash || "").slice(2) === target) render(); else go(target);
});
function takeSearch(inputSel) {
  if (!S.searchQ) return;
  const el = $(inputSel); if (el) el.value = S.searchQ;
  S.searchQ = null;
}

// live updates: a financier's offer shows up on the KOBİ screen without a reload
setInterval(async () => {
  if (!S.user || document.hidden) return;
  const before = unread();
  await refreshNotes();
  if (unread() > before) {
    toast(S.notes[0]?.subject || "Yeni bildirim");
    const r = (location.hash || "").slice(2);
    if (r.startsWith("belge/") || r === "kobi" || r === "kobi/belgeler") render();
  }
}, 10000);

(async () => { try { S.user = (await api("/me")).user; } catch { S.user = null; } render(); })();

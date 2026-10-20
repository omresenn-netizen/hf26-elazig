import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "file:///C:/Users/omres/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const OUT = path.resolve("presentation-output/VadeX_Juri_Sunumu_TR.pptx");
const BUILD = path.resolve(".presentation-build");
const W = 1280, H = 720;
const C = { navy: "#0B1728", navy2: "#14263B", cream: "#F5F2E9", white: "#FFFFFF", ink: "#152638", muted: "#647384", teal: "#55D6C2", tealDark: "#087E78", amber: "#F2A65A", red: "#C75146", line: "#D7DED9", pale: "#E6F3EF" };
const FONT = "Segoe UI";
const pres = Presentation.create({ slideSize: { width: W, height: H } });
const cleanInvoice = new Uint8Array(await fs.readFile(path.resolve("samples/01_gercek_icecek.png")));
const suspiciousInvoice = new Uint8Array(await fs.readFile(path.resolve("samples/04_naylon_danismanlik.png")));

function shape(slide, geometry, x, y, w, h, fill="none", lineFill="none", lineWidth=0, name) {
  return slide.shapes.add({ geometry, name, position: { left:x, top:y, width:w, height:h }, fill,
    line: { style: "solid", fill: lineFill, width: lineWidth } });
}
function txt(slide, value, x,y,w,h,size,color=C.ink,opts={}) {
  const s=shape(slide,"textbox",x,y,w,h,"none","none",0,opts.name);
  s.text=value;
  s.text.style={fontSize:size,typeface:FONT,color,bold:!!opts.bold,alignment:opts.align||"left",verticalAlignment:opts.valign||"top",wrap:"square",autoFit:"shrinkText",insets:0,lineSpacing:1.08};
  return s;
}
function line(slide,x,y,w,h,color=C.line) { shape(slide,"rect",x,y,w,h,color,"none",0); }
function title(slide,kicker,heading,dark=false) {
  txt(slide,kicker.toUpperCase(),72,46,1120,24,15,dark?C.teal:C.tealDark,{bold:true});
  txt(slide,heading,72,82,1136,66,42,dark?C.white:C.ink,{bold:true});
}
function notes(slide, text) { slide.speakerNotes.text=text; slide.speakerNotes.setVisible(true); }
function footer(slide,num,dark=false) {
  txt(slide,"VADEX  /  HACKTOB3V FEST",72,679,600,18,12,dark?"#9EADBA":C.muted,{bold:true});
  txt(slide,String(num).padStart(2,"0"),1160,679,48,18,12,dark?"#9EADBA":C.muted,{align:"right",bold:true});
}

// 1 — Cover
{
  const s=pres.slides.add(); s.background.fill=C.navy;
  shape(s,"rect",0,0,12,H,C.teal,"none",0);
  txt(s,"VADEX",72,72,500,34,18,C.teal,{bold:true});
  txt(s,"Fatura finansmanında\ngüven, faturayı\nanlamakla başlar",72,148,670,236,55,C.white,{bold:true});
  txt(s,"Yerel Gemma 4 ile fatura çıkarımı ve\naçıklanabilir risk incelemesi",74,410,650,84,27,"#D4E0E7");
  txt(s,"Ömer Esen  ·  Onur  |  Hacktoberfest Hack Day Elazığ",74,601,720,28,17,"#AAB8C5");
  s.images.add({blob:cleanInvoice,contentType:"image/png",alt:"VadeX demosunda kullanılan sentetik örnek e-fatura",fit:"contain",crop:{left:0,top:0,right:0,bottom:0.48},position:{left:795,top:82,width:405,height:536}});
  footer(s,1,true);
  notes(s,"0:00–0:15. Açılış: VadeX, fatura finansmanı öncesinde faturadaki bilgileri ve risk işaretlerini görünür kılar. Gösterdiğimiz fatura sentetik demo verisidir; gerçek bir müşteri belgesi değildir.\n\nKaynak: proje README.md ve samples/01_gercek_icecek.png.");
}

// 2 — Problem
{
  const s=pres.slides.add(); s.background.fill=C.cream; title(s,"Problem","Finansman öncesi faturaya güvenmek gerekir");
  txt(s,"“Bir fatura lazım.\n200 bin.”",76,190,570,190,50,C.ink,{bold:true});
  line(s,76,418,92,6,C.amber);
  txt(s,"Bu talep, gerçek bir satış veya hizmet olmadan fatura üretme isteğiydi.",76,454,535,78,23,C.muted);
  txt(s,"KOBİ nakde ihtiyaç duyar. Finansör ise parayı göndermeden önce belgenin tutarlılığını ve tarafların riskini anlamak ister.",700,202,480,156,28,C.ink,{bold:true});
  txt(s,"VadeX, bu ilk incelemeyi hızlandırmak için geliştirildi.",700,413,465,82,22,C.tealDark,{bold:true});
  txt(s,"Son karar insanda kalır.",700,526,465,46,26,C.ink,{bold:true});
  footer(s,2);
  notes(s,"0:15–0:40. Projenin çıkış noktasını tek cümlelik gerçek bir taleple anlatın. Vergi kaybı veya ceza hesabına girmeden, gerçek mal/hizmet bulunmayan fatura talebinin finansman güvenini nasıl zedelediğine odaklanın.\n\nKaynak: README.md içindeki proje motivasyonu.");
}

// 3 — Workflow
{
  const s=pres.slides.add(); s.background.fill=C.white; title(s,"Ürün akışı","Belgeden incelemeye, tek bir izlenebilir akış");
  const y=244, xs=[90,382,674,966], labels=["Fatura yüklenir","Gemma 4\nalanları çıkarır","Kurallar risk\nişaretlerini üretir","İnsan inceler;\nfinansör karar verir"], subs=["Görsel veya PDF","Yerel Ollama\nçalışma zamanı","Mükerrer · irsaliye\nsektör · kapasite","Otomatik kabul\nveya ret yok"];
  for(let i=0;i<4;i++){
    shape(s,"ellipse",xs[i],y,72,72,i===3?C.navy:C.pale,"none",0,`step-${i+1}`);
    txt(s,String(i+1),xs[i],y+16,72,36,27,i===3?C.white:C.tealDark,{bold:true,align:"center",valign:"middle"});
    txt(s,labels[i],xs[i]-20,y+100,220,72,25,C.ink,{bold:true,align:"center"});
    txt(s,subs[i],xs[i]-18,y+194,216,60,17,C.muted,{align:"center"});
    if(i<3) shape(s,"rightArrow",xs[i]+106,y+22,150,28,C.teal,"none",0,`flow-${i+1}`);
  }
  line(s,72,587,1136,1,C.line);
  txt(s,"Fatura verisi yerel modelle işlenir. Risk sinyali kararın yerini almaz.",72,613,1136,34,22,C.tealDark,{bold:true,align:"center"});
  footer(s,3);
  notes(s,"0:40–1:10. Diyagramı soldan sağa anlatın. Gemma alan çıkarımı ve açıklama için kullanılır. Fraud kuralları belirli sinyalleri üretir. Şüpheli belge otomatik reddedilmez; insan incelemesine kalır. GİB sorgusu, banka transferi ve kredi servisi bu demoda mock'tur.\n\nKaynak: server.py, gemma.py, fraud.py, README.md.");
}

// 4 — Demo evidence
{
  const s=pres.slides.add(); s.background.fill=C.cream; title(s,"Demo","Belge aynı; risk sinyalleri farklı");
  s.images.add({blob:suspiciousInvoice,contentType:"image/png",alt:"VadeX için üretilmiş sentetik danışmanlık faturası örneği",fit:"contain",crop:{left:0,top:0,right:0,bottom:0.55},position:{left:74,top:174,width:484,height:420}});
  txt(s,"Örnek vaka",650,188,480,28,16,C.tealDark,{bold:true});
  txt(s,"Danışmanlık hizmeti\n300.000 TL",650,228,520,106,39,C.ink,{bold:true});
  line(s,650,368,86,5,C.amber);
  txt(s,"Belirsiz hizmet tanımı, satıcı geçmişiyle birlikte incelemeyi tetikler.",650,405,500,92,24,C.ink);
  txt(s,"Sistem ‘sahte’ hükmü vermez. İnceleme kuyruğuna yönlendirir.",650,532,500,56,20,C.red,{bold:true});
  txt(s,"Sentetik demo faturası",74,609,480,24,15,C.muted);
  footer(s,4);
  notes(s,"1:10–1:40. Canlı demoda önce temiz faturayı KOBİ rolünde yükleyin. Ardından bu örneğe geçip risk işaretlerini ve açıklamayı gösterin. Gerekirse denetim panelindeki ağ görünümünü açın. Bu slayttaki görsel sentetik demo faturasıdır; gerçek belge değildir. Buradaki açıklama, örnek dosyanın tanımıyla sınırlıdır; canlı skor/çıktıyı ekranda doğrulayın.\n\nKaynak: samples/04_naylon_danismanlik.png, docs/PITCH.md.");
}

// 5 — AI + evidence
{
  const s=pres.slides.add(); s.background.fill=C.navy; title(s,"Yerel AI + tahmin","AI yardımcıdır; karar verici değildir",true);
  txt(s,"TabPFN",76,192,250,36,20,C.teal,{bold:true});
  txt(s,"4,36 gün",76,245,410,80,54,C.white,{bold:true});
  txt(s,"gecikme tahmininde MAE",78,328,430,32,19,"#B7C5CF");
  txt(s,"%78,05",76,414,410,80,54,C.white,{bold:true});
  txt(s,"5 günden fazla gecikme sınıflandırma doğruluğu",78,498,470,54,19,"#B7C5CF");
  line(s,614,190,2,392,"#34485C");
  txt(s,"201",672,204,160,54,34,C.teal,{bold:true});
  txt(s,"kurgusal ödeme kaydı",672,256,405,36,20,C.white);
  txt(s,"41",672,331,160,54,34,C.teal,{bold:true});
  txt(s,"zamansal holdout test satırı",672,383,445,36,20,C.white);
  txt(s,"TabPFN gecikmeyi tahmin eder.\nGemma sonucu Türkçe açıklar.\nİnsan incelemesi devam eder.",672,465,500,124,24,"#D5E0E7");
  txt(s,"Bu ölçüm sentetik demo verisindendir; kredi performansı iddiası değildir.",76,618,1090,30,17,C.amber,{bold:true});
  footer(s,5,true);
  notes(s,"1:40–2:10. TabPFN ölçümünü anlatırken veri setinin 201 kurgusal ödeme satırından oluştuğunu ve holdout'un 41 satır olduğunu mutlaka belirtin. Bu değerler gerçek müşterilerde performans veya kredi kararı başarısı olarak sunulmamalı.\n\nKaynak: docs/FORECAST.md ve README.md.");
}

// 6 — Category fit
{
  const s=pres.slides.add(); s.background.fill=C.white; title(s,"Hack Day kategori uyumu","Üç kategori için somut proje kanıtı");
  const rows=[
    ["01","Best Use of Gemma 4","Fatura görselinden alan çıkarımı ve Türkçe risk açıklaması; Gemma 4 yerelde Ollama üzerinden çalışır."],
    ["02","Best Open-Source AI Project","Açık ağırlıklı Gemma ürünün temel akışında; repo public ve MIT lisanslı."],
    ["03","Best Use of GitHub Copilot","Copilot ajan oturumları ve geliştirme iş akışları repo içinde belgeli; CI GitHub Actions üzerinde."],
  ];
  const tops=[188,336,484];
  for(let i=0;i<3;i++){
    const y=tops[i]; txt(s,rows[i][0],76,y+3,56,36,20,C.tealDark,{bold:true});
    txt(s,rows[i][1],154,y,410,44,25,C.ink,{bold:true});
    txt(s,rows[i][2],596,y,590,76,20,C.muted);
    if(i<2) line(s,154,y+116,1032,1,C.line);
  }
  txt(s,"Adaylık uyumu; resmî kategori kaydı, organizatörün teslim yöntemiyle ayrıca doğrulanmalı.",76,626,1110,28,16,C.red,{bold:true});
  footer(s,6);
  notes(s,"2:10–2:35. Kategorileri Hacktoberfest Hack Day Elazığ x HacktoB3V Fest sayfasındaki adlarıyla söyleyin. Bu slayt kategori uyumunu ve repo kanıtını özetler; proje tesliminin yapıldığını iddia etmez. Etkinlik sayfasında MLH submission_url görünmediği için organizatörün yöntemini ayrıca teyit edin.\n\nKaynaklar: https://events.mlh.com/events/15182-hacktoberfest-hack-day-elazig-x-hacktob3v-fest ; https://github.com/omresenn-netizen/hf26-elazig ; LICENSE ; sessions/.");
}

// 7 — close / live demo plan
{
  const s=pres.slides.add(); s.background.fill=C.cream; title(s,"Canlı demo","Fatura yerelde okunur. Karar insanda kalır.");
  txt(s,"Gösterim sırası",76,196,360,34,20,C.tealDark,{bold:true});
  txt(s,"1  Temiz faturayı yükle ve çıkarılan alanları göster\n\n2  Şüpheli örnekte risk işaretlerini aç\n\n3  Finansör / denetim ekranında insan incelemesini göster",76,247,620,260,24,C.ink);
  line(s,758,194,2,372,C.line);
  txt(s,"Demo sınırları",810,196,355,34,20,C.tealDark,{bold:true});
  txt(s,"GİB, kredi skoru, banka transferi ve e-imza mock'tur.\n\nGemma risk kararı vermez.\n\nFaturalar sentetik örneklerdir.",810,247,370,250,22,C.muted);
  shape(s,"rect",76,566,1128,70,C.navy,"none",0);
  txt(s,"VadeX",102,581,170,40,29,C.teal,{bold:true});
  txt(s,"Fatura finansmanında daha hızlı ve açıklanabilir ilk inceleme",296,583,860,36,23,C.white,{bold:true});
  footer(s,7);
  notes(s,"2:35–3:00. Kapanış cümlesi: ‘VadeX finansman kararını otomatikleştirmiyor; finansörün ve denetçinin faturayı daha hızlı, açıklanabilir bulgularla incelemesine yardım ediyor.’ Sorular için hazır olun. Demo öncesi Ollama/Gemma, 8600 uygulama adresi, demo hesabı ve örnek görselleri kontrol edin. Upload → cancel → re-upload ve non-invoice warning akışlarını sunumdan önce tarayıcıda deneyin.\n\nKaynak: README.md, docs/PITCH.md, docs/DEPLOY.md.");
}

await fs.mkdir(BUILD,{recursive:true});
await fs.mkdir(path.dirname(OUT),{recursive:true});
for (const [i,s] of pres.slides.items.entries()) {
  const png=await pres.export({slide:s,format:"png",scale:1});
  await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,"0")}.png`),new Uint8Array(await png.arrayBuffer()));
}
const montage=await pres.export({format:"png",montage:true,scale:0.4});
await fs.writeFile(path.join(BUILD,"montage.png"),new Uint8Array(await montage.arrayBuffer()));
const candidate=path.join(BUILD,"candidate.pptx");
await (await PresentationFile.exportPptx(pres)).save(candidate);
console.log(JSON.stringify({candidate,output:OUT,slides:pres.slides.items.length},null,2));





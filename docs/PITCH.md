# VadeX - 3 Dakikalık Jüri Pitchesi ve Canlı Demo Scripti

## 1) Hedef ve akış

Bu sunum yaklaşık 3 dakika sürer. Yapı:

- 0:00–0:25: Sorun ve nedeni anlatılır
- 0:25–0:55: VadeX çözümü ve kimin ödüyor?
- 0:55–1:30: Gemma 4 ve anti-fraud akışı
- 1:30–2:10: Demo ekranları ve hareketler
- 2:10–2:50: Jüri soruları / kısa cevaplar
- 2:50–3:00: Son söz

## 2) Kim ne konuşacak?

- Sunucu 1 (giriş ve problem): "Sorunu anlatır."
- Sunucu 2 (teknik akış): "Gemma, risk, işlem akışı ve güveni açıklar."
- Sunucu 3 (demo): "Ekranları ve örnek dosyaları çalıştırır."

## 3) Demo hesapları ve rol dağılımı

- KOBİ: `9200000505`
- Finansör: `anadolu_faktoring`
- Denetim: `denetim`
- Broker / şüpheli işlem tarafı: `9300000904`

Tüm hesapların şifresi: `demo1234`

## 4) Canlı demo adımları

### A. Temiz belge gösterimi

- Rol: KOBİ
- Kullanıcı: `9200000505`
- Dosya: `samples/01_gercek_icecek.png`
- Beklenen sonuç: temiz/normal fatura, düşük risk, teklif akışı garanti gibi görünür
- Demo cümlesi: "Bu faturada veri çıkarımı düzgün, sektör ve buyer ilişkisi tutarlı. Yüksek risk değil; insan kararına bırakılıyor."

### B. Şüpheli belge gösterimi

- Rol: KOBİ
- Kullanıcı: `9200000505`
- Dosya: `samples/04_naylon_danismanlik.png`
- Beklenen sonuç: risk ~90, açıklama: belirsiz hizmet tanımı, kapasite sapması, eksik irsaliye / sahtecilik sinyali
- Durum: `incelemede` review queue
- Demo cümlesi: "Bu dosyada risk yüksek; bir finansör bunu hemen kabul etmez, denetim kuyruğuna gider. Gemma sadece yardımcı olur; karar insanın elinde kalır."

### C. Finasör paneli

- Rol: `anadolu_faktoring`
- Hedef: risk raporu görseli, uygun iskonto ve net tutar
- Açıklama: "Faturanın risk değeri ve alıcı profili üzerinden önerilen indirim otomatik hesaplanıyor; son karar yine insan tarafından veriliyor."

### D. Denetim paneli

- Rol: `denetim`
- Hedef: ağ grafı ve şüpheli cluster
- Açıklama: "Aynı şirket/seller ilişkisi içinde döngü, shell-company, ve gereksiz "danışmanlık" kalemleri görülüyor. Bu da tek bir belgeyi değil, networki incelerken fark ediliyor."

## 5) Gemma bekleme süreleri ve ne söylenecek?

Gemma 4'ün görsel okuma ve risk çıktısı bir kaç saniye sürebilir. O sırada şöyle bir arka plan cümlesi söylenebilir:

- "Gemma görseli okuyor, faturadaki tutar, VKN, satıcı ve alıcı bilgisini ayıklıyor. Sonra etiketsiz risk bayraklarını, sektör uyumsuzluğunu ve kapasite anomalisini tek tek kontrol ediyor."
- "Bu adım bizim insan kararına güvenen sistemimizin en kritik kısmı: model sadece öneri çıkarıyor, nihai karar yine insanın elinde."

Bekleme sırasında ekranın temiz olan ve şüpheli olan örnekler arasında geçiş yapılabilir. Bu, sunumun akışını bozmadan "sistem çalışıyor" hissi verir.

## 6) Uygulama konuşma metni (örnek)

### Giriş

"Bugün burada, ticari faturanın sahte olup olmadığını bir insanın karar vermeden önce hızlıca anlamaya çalışan bir sistem gösteriyoruz. Bu işin temel sorunu, KOBİ'lerin nakit akışına ihtiyaç duyması ve büyük şirketlerin ödemesini 60–120 gün beklemesidir."

### Sorun / çözüm

"VadeX, satıcıya nakit pompalayan ve risk kontrolü yapan bir finansman desteği sunar. Yalnızca 'işlem başarılı' değil, 'bu fatura güvenilir mi?' sorusunu sorar."

### Gemma

"Gemma 4 görüntüden fatura bilgilerini çıkarır, VKN'i doğrular ve risk bayraklarını Türkçe açıklar. Ama asla otomatik red etmez. Uzak bulut yerine yerelde çalışır; verisi dışarı çıkmaz."

### Demo

"Şimdi ilk örneği açıyorum: 01_gercek_icecek.png. Bu fatura temiz ve makul risk taşıyor. Ardından 04_naylon_danismanlik.png dosyasını açıyorum; burada kapasite, belirsiz hizmet açıklaması ve düzensiz işlem sinyalleri belirgin. Bu dosya incelemede kalıyor."

### Son cümle

"Yani sistem, finansman kararını insanın gözüyle birlikte veriyor; Gemma ise sadece güveni artıran bir yardımcı. Bu, güvenli ve anlaşılır bir AI finansman akışı."

## 7) Olası jüri soruları ve kısa cevaplar

### Soru 1: "Neden bulut yerine yerel model kullandınız?"
Cevap: "Faturalar finansal veri içerir. Yerel model, gizliliği korur, verinin dışarı çıkmasını azaltır ve maliyetin fatura başına daha öngörülebilir olmasını sağlar."

### Soru 2: "Gemma neden tek başına karar vermiyor?"
Cevap: "Çünkü finansal riskte insan denetimi şart. Model yalnızca öneri üretir; onay, ret ve güvenli ödeme kararı insan tarafından verilir."

### Soru 3: "Sahte faturayı nasıl tespit ediyorsunuz?"
Cevap: "Tek bir işaret değil, 5–7 risk kuralı birlikte değerlendirilir: VKN uyumsuzluğu, kapasite outlier, belirsiz hizmet açıklaması, eksik irsaliye, sektör uyumsuzluğu ve ağ döngüsü."

### Soru 4: "Bu sistem gerçek bir bankada kullanılabilir mi?"
Cevap: "Bu demo bir finansman karar destek aracı; üretime geçerken gerçek GİB, kredi verisi ve banka entegrasyonlarıyla daha katı iş akışı ve denetim katmanı eklenir."

### Soru 5: "Neden bu işin yeniden yatırım değeri var?"
Cevap: "KOBİ'ler nakit sıkışıyor, finansörler ise güvenli ve ölçeklenebilir bir pipeline istiyor. VadeX, her iki taraf için de aynı anda değer üretiyor: hızlı nakit ve daha güvenli kredi akışı."

## 8) Son notlar

- Demo ekranı büyüklüğü ve sade görünümü korunur.
- Şüpheli belge her zaman onaylanmadan önce inceleme listesine düşer.
- Risk raporu ve grafikler, sunumun ana kanıtı olmalıdır.
- "Gemma yardımcı, insan karar verici" cümlesi sunumun merkezindeki mesajdır.

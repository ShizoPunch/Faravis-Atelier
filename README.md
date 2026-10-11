# Faravis Atelier — Instagram Stüdyosu

Ürün fotoğraflarını markaya uygun Instagram gönderilerine dönüştüren araç.

**Ne yapar:** arka planı yapay zekâyla (BiRefNet) kaldırır → markanın sahnelerinden birine yerleştirir →
gerçekçi temas + düşen gölge ekler → logo ve başlık basar → Instagram ölçüsünde JPG verir.

## Kullanım

```bash
pip install -r requirements.txt

# Fotoğrafları gelen/ klasörüne koyun
python studio/studio.py gelen/urun.jpg                      # kum sahnesi, 4:5 (1080×1350)
python studio/studio.py gelen/urun.jpg --all                # 8 sahnenin hepsi + karşılaştırma panosu
python studio/studio.py gelen/urun.jpg --scene kemer \
    --title "Toprağın Sessizliği" --subtitle "El yapımı seramik"
python studio/studio.py gelen/*.jpg --scene golge --format story
```

Çıktılar `output/` klasörüne düşer.

| Seçenek | Değerler |
|---|---|
| `--scene` | Yandan çekim: `kum` · `keten` · `mermer` · `pudra` · `adacayi` · `golge` · `kemer` · `gece`<br>Üstten çekim (flat-lay): `zeytin` · `lacivert` · `beton` · `kadife` · `kil` · `traverten` · `serme` · `isik` |
| `--format` | `portrait` 1080×1350 (varsayılan) · `square` 1080×1080 · `story` 1080×1920 |
| `--title`, `--subtitle` | Alt kısma serif başlık + harf aralıklı alt başlık |
| `--no-logo` | FARAVIS ATELIER logosunu kaldırır |
| `--scale` | Ürün boyutu çarpanı (ör. `0.85`) |
| `--rotate` | Eğik çekilmiş ürünü düzeltir, derece cinsinden (ör. `-7`) |

## Sahneler: hangi ürüne hangisi?

| Sahne | His | En iyi olduğu ürünler |
|---|---|---|
| **kum** | Sıcak, sade stüdyo | Her şey; ana katalog |
| **keten** | Doğal, el emeği | Tekstil, örgü, ahşap, doğal malzeme |
| **mermer** | Temiz, lüks | Takı, parfüm, seramik, kozmetik |
| **pudra** | Yumuşak, feminen | Aksesuar, çanta, takı |
| **adacayi** | Taze, doğal | Seramik, bitki/ev ürünleri, krem tonlu ürünler |
| **golge** | Güneşli pencere ışığı; 2024–26'nın en güçlü trendi | Öne çıkarılacak ürünler, lansmanlar |
| **kemer** | Editoryal, butik vitrini | Kahraman ürün, kampanya |
| **gece** | Koyu, dramatik | Açık renkli, parlak ya da altın detaylı ürünler |

**Üstten (flat-lay) çekilmiş fotoğraflar** için ayrı sahneler var. Bunlarda ürün yüzeyin üzerinde yatar ve gölge sağ-alta düşer:

| Sahne | His | En iyi olduğu ürünler |
|---|---|---|
| **zeytin** | Derin zeytin yeşili | Açık ahşap + altın detay. **Altın askılarda en güçlüsü** |
| **lacivert** | Derin lacivert, terzi dili | Krom/gümüş detaylı ürünler. **Krom askılarda en güçlüsü** |
| **beton** | Sıcak gri sıva, sade | Krom/gümüş, minimal ürünler |
| **kadife** | Koyu espresso | Altın/pirinç detaylar, lüks algı |
| **kil** | Terrakota, sıcak | Açık tonlu ürünler, yaz koleksiyonu |
| **traverten** · **serme** · **isik** | Açık taş / keten / pencere ışığı | Koyu renkli ürünler (açık ürünlerde kontrast düşer) |

## Marka kiti

`brand/brand.json`: renk paleti, fontlar (Cormorant Garamond + Montserrat, OFL lisanslı) ve logo.
Logo: `brand/logo.png` (şeffaf zemin) ve `brand/logo.svg` (vektör). Stüdyo, `logo.png` varsa onu sahnenin yazı rengine boyayıp
**sol üst köşeye** basar; dosya yoksa yazıyla oluşturulan logoya döner (`wordmark.position`).

## Fotoğraf çekim ipuçları (sonucu en çok bunlar belirler)

1. **Gün ışığı, doğrudan güneş değil.** Pencere kenarı, bulutlu gün ya da tül perde arkası.
2. **Sade ve ürünle zıt renkli bir zemin.** Açık ürün için koyu, koyu ürün için açık zemin
   kullanın. Böylece dekupe kusursuz olur.
3. **Ürünün kenarları kadraj dışına taşmasın.** Etrafta boşluk bırakın.
4. **Göz hizasından ya da hafif üstten** çekin. Sahnelerin perspektifi buna göre ayarlı.
5. En yüksek çözünürlükte gönderin (WhatsApp sıkıştırması yerine dosya olarak).

## KDV Hesap Defteri (`kdv/`)

Telefonda ve bilgisayarda çalışan KDV hesaplayıcı ve proforma aracı.
Fatura düzenleyicileri gibi tek tablo: her satır bir ürün (ad, adet, birim fiyat, KDV oranı), satırın altında KDV hariç ve KDV tutarı,
sağda ara toplam, oranlara göre KDV ve genel toplam.

- **Fiyatlar KDV hariç / KDV dahil:** tablonun üstünde tek ayar; değiştirince fiyatlar çevrilir, toplam aynı kalır.
- **Logo uygulaması:** her satırda "Lazer kazıma" ya da "Metal plaka" seçilir; adet fiyatları tablonun altındaki alana bir kez girilir.
  Ürünle aynı adet ve KDV oranıyla hesaplanır, proformada ürünün altında ayrı satır olarak görünür.
- **Proforma PDF:** logolu A4; satıcı (ad soyad dahil) ve alıcı blokları, ödeme ve teslim şekli, banka bilgileri (hesap sahibi, banka, IBAN — hesap sahibi boşsa satıcının ad soyadı yazılır),
  tutar yazıyla, "resmi fatura yerine geçmez" notu ve imza alanı. Maliyet ve kâr proformada yer almaz.
  - Telefonda **Gönder:** paylaşım menüsü açılır (WhatsApp, Mail, Dosyalara Kaydet…).
  - Bilgisayarda **PDF kaydet:** Chrome / Edge kayıt yerini sorar; diğer tarayıcılar İndirilenler'e kaydeder.
- **Proformalar** (⋯ menüsü): kaydedilen / gönderilen her proforma listelenir; durum (Taslak, Gönderildi, Onaylandı,
  Reddedildi, Ödendi), bekleyen ve onaylanan toplamlar; eskisini açma ya da kopyasından yeni proforma.
- **Müşteriler:** proformadaki müşteri adı yazılırken önceki müşteriler önerilir, seçince iletişim / adres / vergi bilgisi dolar.
- **Ön ödeme ve termin:** ön ödeme yüzdesi proformaya "Ön ödeme / Kalan" olarak, termin (iş günü) hafta sonları atlanarak tarihe çevrilir.
- **Renk ve kanca:** her satırda askı rengi (Naturel, Beyaz, Ceviz, Siyah ya da "Özel renk…" ile elle yazılan renk) ve kanca
  (Standart Gold, Standart Gümüş, Gold Lama, Siyah Lama, Gümüş Lama); proformada ürün adının altında.
- **Ürün listesi ve kademeli fiyat:** `kdv/katalog.json` ikas ürün Excel'inden üretilir (80 ürün). ikas'taki adet paketleri
  (12, 25, 50, 100, 250, 500) adet başı fiyata ve kademelere dönüşür; adet yazınca uygun kademe fiyatı kendiliğinden gelir.
  Yeni Excel uygulamadan da yüklenebilir: ⋯ → Ürün listesi → Excel / CSV yükle.
- **Ürün görselleri:** ikas Excel'indeki ilk görsel; tabloda, ürün listesinde, önerilerde ve (isteğe bağlı) proformada.
  Görseller doğrudan ikas'ın görsel sunucusundan (cdn.myikas.com) yüklenir; erişilemezse ürün adının baş harfi gösterilir,
  PDF'e eklenemeyen görseller için proforma ekranında not çıkar.
- **Kâr hesabı**, özeti kopyalama, Excel'e (CSV) aktarma, **yedek al / yedekten yükle** (tüm veriler tek JSON dosyasında;
  telefon ile bilgisayar arasında taşımak için de kullanılır). Veriler cihazda saklanır.

Hesap, faturadaki gibi satır bazında kuruşa yuvarlanır; toplamlar satırların toplamıdır.

### Telefonda ve bilgisayarda açmak

Uygulama GitHub Pages'ten yayınlanır (bir kez: GitHub → Settings → Pages → *Deploy from a branch* → dal ve `/ (root)` → Save).
Adres: `https://shizopunch.github.io/Faravis-Atelier/kdv/`

- **iPhone:** adresi Safari'de açın → Paylaş → **Ana Ekrana Ekle**. Uygulama gibi açılır, internetsiz de çalışır.
- **Bilgisayar:** Chrome ya da Edge'de açın → adres çubuğundaki **Yükle** simgesi. Masaüstü uygulaması gibi açılır.

Listeler, ürün listesi ve firma bilgileri her cihazın kendi tarayıcısında saklanır (cihazlar arası eşitlenmez).

### Siteden ürün listesini çekmek

```bash
python kdv/katalog_cek.py            # faravisatelier.com → kdv/katalog.json
```

Sitenin `sitemap.xml` dosyasındaki ürün sayfalarını gezer; ad, stok kodu, varyant ve KDV dahil fiyatı okur.
Uygulama açılışta `katalog.json` dosyasını otomatik yükler ("faravisatelier.com listesini yükle" ile de yenilenir).
Maliyetler sitede olmadığı için Katalog ekranında bir kez girilir; liste yeniden yüklense de korunur.

## Ar-Ge yol haritası

- [x] Otomatik dekupe (ISNet), ana ürün dışındaki parçaları temizleme
- [x] 8 prosedürel sahne, temas + düşen gölge, pencere ışığının ürüne de düşmesi
- [x] 4:5 / kare / story formatları, karşılaştırma panosu
- [x] Flat-lay (üstten çekim) sahneleri, eğim düzeltme, sol üstte ® logo
- [ ] Ürün rengine göre **otomatik sahne önerisi** (renk uyumu analizi)
- [ ] **Carousel şablonları**: kapak → detay → ölçü/malzeme → fiyat/CTA
- [ ] Feed ızgarası önizlemesi (9'lu profil görünümü, ton dengesi)
- [ ] Gerçek doku fotoğrafları (traverten, keten, ahşap) ile sahne kütüphanesi
- [ ] Yansıma (mermer zeminde), ürün üstüne sahne ışığı uyumu (color match)
- [ ] Yapay zekâ ile üretilmiş bağlamsal sahneler (ürün bir masada, rafta, elde)

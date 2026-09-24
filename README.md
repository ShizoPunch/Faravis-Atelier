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
| `--scene` | Yandan çekim: `kum` · `keten` · `mermer` · `pudra` · `adacayi` · `golge` · `kemer` · `gece`<br>Üstten çekim (flat-lay): `zeytin` · `kadife` · `kil` · `traverten` · `serme` · `isik` |
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
| **zeytin** | Derin zeytin yeşili | Açık ahşap + altın (askılar). **Şu an en güçlü sahne** |
| **kadife** | Koyu espresso | Altın/pirinç detaylar, lüks algı |
| **kil** | Terrakota, sıcak | Açık tonlu ürünler, yaz koleksiyonu |
| **traverten** · **serme** · **isik** | Açık taş / keten / pencere ışığı | Koyu renkli ürünler (açık ürünlerde kontrast düşer) |

## Marka kiti

`brand/brand.json`: renk paleti, fontlar (Cormorant Garamond + Montserrat, OFL lisanslı) ve logo.
Logo varsayılan olarak **sol üst köşede, ® tescil işaretiyle** basılır (`wordmark.position`, `wordmark.symbol`).
Logo dosyanız varsa `brand/` klasörüne eklenir, yazı logosunun yerine o kullanılır.

## Fotoğraf çekim ipuçları (sonucu en çok bunlar belirler)

1. **Gün ışığı, doğrudan güneş değil.** Pencere kenarı, bulutlu gün ya da tül perde arkası.
2. **Sade ve ürünle zıt renkli bir zemin.** Açık ürün için koyu, koyu ürün için açık zemin
   kullanın. Böylece dekupe kusursuz olur.
3. **Ürünün kenarları kadraj dışına taşmasın.** Etrafta boşluk bırakın.
4. **Göz hizasından ya da hafif üstten** çekin. Sahnelerin perspektifi buna göre ayarlı.
5. En yüksek çözünürlükte gönderin (WhatsApp sıkıştırması yerine dosya olarak).

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

# Faravis Atelier — Instagram Stüdyosu

Ürün fotoğraflarını markaya uygun Instagram gönderilerine dönüştüren araç.

**Ne yapar:** arka planı yapay zekâyla kaldırır → markanın sahnelerinden birine yerleştirir →
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
| `--scene` | `kum` · `keten` · `mermer` · `pudra` · `adacayi` · `golge` · `kemer` · `gece` |
| `--format` | `portrait` 1080×1350 (varsayılan) · `square` 1080×1080 · `story` 1080×1920 |
| `--title`, `--subtitle` | Alt kısma serif başlık + harf aralıklı alt başlık |
| `--no-logo` | FARAVIS ATELIER logosunu kaldırır |
| `--scale` | Ürün boyutu çarpanı (ör. `0.85`) |

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

## Marka kiti

`brand/brand.json`: renk paleti ve fontlar (Cormorant Garamond + Montserrat, OFL lisanslı).
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
- [ ] Ürün rengine göre **otomatik sahne önerisi** (renk uyumu analizi)
- [ ] **Carousel şablonları**: kapak → detay → ölçü/malzeme → fiyat/CTA
- [ ] Feed ızgarası önizlemesi (9'lu profil görünümü, ton dengesi)
- [ ] Gerçek doku fotoğrafları (traverten, keten, ahşap) ile sahne kütüphanesi
- [ ] Yansıma (mermer zeminde), ürün üstüne sahne ışığı uyumu (color match)
- [ ] Yapay zekâ ile üretilmiş bağlamsal sahneler (ürün bir masada, rafta, elde)

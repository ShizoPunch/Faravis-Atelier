# tvarsiv_ kurgu masası

TV kliplerini dikey Reels'e çevirir: kanca yazısı, kelime kelime vurgulu altyazı, zoom/sarsıntı/donma,
kendi ürettiğimiz ses efektleri ve isteğe bağlı kendi sesin (yorum/seslendirme).

## Akış

1. **İndir:** Linkteki videonun yalnızca gereken kısmını indir (dosya küçük kalır):
   ```bash
   yt-dlp -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]" \
          --download-sections "*1:20-2:05" -o "tvarsiv/gelen/%(id)s.%(ext)s" "LINK"
   ```
2. **Yükle:** Dosyayı `tvarsiv/gelen/` klasörüne koy ve gönder (git push ya da GitHub'da
   *Add file → Upload files*, web'de dosya başına 25 MB sınırı var).
3. **İncele** (Claude yapar): `python tvarsiv/incele.py` → `yazilar/<ad>.json` (kelime zamanlı metin) ve
   `yazilar/<ad>_kareler.jpg` (2 saniyede bir kare).
4. **Planla** (Claude yapar): `planlar/<ad>.json` yazılır: kesimler, kanca, efektler.
5. **Bas:** `python tvarsiv/montaj.py tvarsiv/planlar/<ad>.json` → `cikti/<ad>.mp4` + `_kapak.jpg`.
   Hızlı deneme için `--onizleme` (540×960).

İlk çalıştırmada ses-yazı modeli (Whisper large-v3-turbo, ~560 MB) GitHub'dan kendiliğinden iner (`kurulum.sh`).
İnternet gerekmez, her şey makinede çalışır.

## Plan dosyası

```json
{
  "kaynak": "gelen/klip.mp4",
  "parcalar": [{"bas": 12.0, "son": 31.5}, {"bas": 40.2, "son": 52.0}],
  "duzen": "meme",
  "pencere": 1.5,
  "kanca": "Yarışmacı *birinci soruda* annesini aradı 😂",
  "duzelt": {"Yarışmancı": "Yarışmacı"},
  "metin": {"3": "Bu daha birinci soru ama"},
  "olaylar": [
    {"t": 14.2, "tip": "zoom", "olcek": 1.5, "sure": 1.2, "merkez": [0.62, 0.4]},
    {"t": 14.2, "tip": "ses", "ad": "boom", "seviye": 0.8},
    {"t": 20.0, "tip": "dondur", "sure": 1.2},
    {"t": 20.0, "tip": "yazi", "metin": "*Riske* girmiyor 💀", "sure": 1.2},
    {"t": 12.0, "tip": "ses", "dosya": "gelen/benim_yorumum.m4a"}
  ],
  "ilerleme": true,
  "kapak_t": 20.0
}
```

Tüm `t` değerleri **kaynak videonun saniyesidir** (yazılardaki zamanlar). Kesimler ve dondurmalar otomatik hesaplanır.
Birden fazla kaynaktan derleme için parçalara `"kaynak"` yazılır; o parçadaki olaylara da aynı `"kaynak"` eklenir.

| Alan | Anlamı |
|---|---|
| `duzen` | `meme`: koyu zemin, üstte kanca, ortada video · `bulanik`: arkada bulanık video · `kirp`: tam ekran 9:16 kırpma (`kirp_x` ile yatay odak, 0–1) |
| `pencere` | Video penceresinin en/boy oranı (`meme`/`bulanik`). 1.78 = tam 16:9, 1.3 = yüzler daha büyük |
| `kanca` | Üstteki yazı. `*kelime*` sarı vurgulanır. `kanca_stil: "beyaz"` → klasik beyaz panel, siyah yazı |
| `kanca_sure` | Kanca kaç saniye görünsün (boşsa sonuna kadar) |
| `altyazi` | `false` ise altyazı yok. `altyazi_kelime` (varsayılan 3), `altyazi_boyut` (80), `buyuk_harf` (true) |
| `duzelt` / `metin` | Ses-yazı hatalarını düzeltme: tek kelime değişimi / parça numarasıyla tüm cümle |
| `imza` | Sağ alttaki filigran (varsayılan `@tvarsiv_`, `""` ile kapatılır) |
| `ilerleme` | Videonun altında sarı ilerleme çubuğu |
| `ses_seviyesi` | Orijinal sesin çarpanı (varsayılan 1.0). Çıkış her zaman −14 LUFS'a normalize edilir |

**Olay tipleri**

| `tip` | Alanlar | Etki |
|---|---|---|
| `zoom` | `olcek`, `sure`, `merkez` [x, y] (0–1), `gecis`: `ani` / `yumusak` | Yüze ya da tepkiye yaklaşma |
| `sarsinti` | `sure`, `guc` (px) | Kamera sarsıntısı |
| `dondur` | `sure` | Kareyi dondurur, flaş + yavaş içe kayma; videoya süre ekler |
| `flas` | | Beyaz flaş |
| `yazi` / `emoji` | `metin`, `sure`, `konum`: `ust`/`orta`/`alt`, `boyut` | Zıplayarak beliren büyük yazı / emoji |
| `ses` | `ad` (efekt) **ya da** `dosya` (kendi ses kaydın), `seviye`, `kaydir`, `kis`, `kis_oran` | Ses ekler; o sırada orijinal ses kısılır |
| `bip` | `sure` | Sansür bip'i (orijinal ses susturulur) |

**Efektler** (`sfx/`, `sfx_uret.py` ile sıfırdan sentezlendi, telif yok):
`boom` · `whoosh` · `ding` · `pop` · `tik` · `riser` · `scratch` · `dramatik` · `huzunlu` · `glitch` · `kamera` · `bip` · `kalp`

## Özgünlük notu

Instagram, başkasının videosunu yalnızca filigran, çerçeve ya da altyazı ekleyerek yeniden yüklemeyi özgün saymıyor.
Aynalama, hızlandırma gibi hileler de işe yaramıyor. Erişimi asıl geri getiren şey **anlamlı katkı**:
kendi sesinle yorum ya da tepki, birkaç klibi bir temada birleştiren derlemeler ("Haftanın en komik 3 yarışmacısı"),
kendi esprin olan kanca ve yazılar. Bu araç bunların hepsini destekliyor; en etkilisi `"tip": "ses", "dosya": ...` ile
telefonla kaydedilmiş 3-5 saniyelik bir giriş yorumu.

Yine de içerik kanalın malı: hak sahibi sesi kapatabilir ya da videoyu kaldırtabilir.

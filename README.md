# meteo — Open-Meteo Python istemcisi & Flask web uygulaması

Open-Meteo'nun tüm ücretsiz API'lerine tek paketten erişim. Bölge adını
yazarsın, gerisini halleder: koordinatı çözümler, anlık/saatlik/günlük
tahmini, geçmiş ölçümleri, iklim modelini, deniz/dalga, taşkın, hava
kalitesi ve rakım verisini getirir. Anahtar gerektirmez.

İki yüzü var:
* **Python kütüphanesi** (`meteo` paketi) — programatik erişim
* **Flask web uygulaması** (`app.py`) — tarayıcı arayüzü + JSON API

## Kurulum

```bash
pip install -r requirements.txt   # requests + Flask
```

Geliştirme/test için:

```bash
pip install pytest
```

## Web uygulaması (Flask)

```bash
flask --app app run --debug --port 5001   # http://127.0.0.1:5001
# veya:
python app.py
```

Tarayıcıda aç: bölge adını yaz, "Getir" de. Otomatik tamamlama çalışır.
İstersen haritadan konum da seçebilirsin — haritaya tıkla, yer adı OSM
Nominatim ile bulunur ve koordinat forma dolar.

Sayfa anlık hava, günlük/saatlik tahmin, hava kalitesi, deniz, taşkın ve
rakımı tek yerde gösterir; konumu bir haritada işaretler; en altta ham JSON.

### JSON API

| Yöntem | Yol | Parametre |
| --- | --- | --- |
| GET | `/api/places` | `name`, `count?`, `language?`, `country?` |
| GET | `/api/reverse` | `lat`, `lon`, `zoom?`, `language?` — koordinat→yer adı (OSM Nominatim) |
| GET | `/api/geocode` | `name`, `language?`, `country?` |
| GET | `/api/weather` | `place` veya `lat`+`lon`, `days?`, `past_days?`, `sections?` |
| GET | `/api/historical` | `place`/`lat`+`lon`, `start`, `end`, `hourly?` |
| GET | `/api/raw` | `kind`, + herhangi bir alt-API parametresi |
| POST | `/api/compare` | `points:[{name,lat,lon}, ...]` (≥2) — çok nokta karşılaştırma |
| POST | `/api/analyze` | `lat`, `lon` — hava kalitesi uzaysal gradyan analizi |
| POST | `/api/scan` | `bbox:{north,south,east,west}`, `source`, `variable`, `grid?` — alan tarama |

`sections` virgülle ayrılmış liste: `forecast,air_quality,marine,flood,elevation`
(boş bırakılırsa `all`).

Örnekler:

```bash
curl 'http://127.0.0.1:5001/api/weather?place=İstanbul&days=3'
curl 'http://127.0.0.1:5001/api/historical?place=İzmir&start=2025-01-01&end=2025-01-31'
curl 'http://127.0.0.1:5001/api/raw?kind=forecast&latitude=41.01&longitude=28.95&current=true'
curl -X POST http://127.0.0.1:5001/api/scan \
  -H 'Content-Type: application/json' \
  -d '{"bbox":{"north":36,"south":34.8,"east":34.6,"west":32.8},"source":"aq_cams_europe","variable":"pm2_5","grid":8}'
```

### Alan tarama — veri kaynakları (`/scan`)

Tarama modunda **değişken birinci seçimdir**: açılır listede TÜM değişkenler
(partiküller PM2.5/PM10, ozon, NO₂/SO₂/CO/NH₃, çöl tozu, AQ indeksleri ve UV
indeksi dahil) hava kalitesi grubu en üstte görünür. Bir değişken seçilince
kaynak listesi otomatik olarak o değişkeni gerçekten ölçen kaynaklarla
sınırlandırılır (ölçmeyenler gri/devre dışı); seçili kaynak uyumsuzsa en ince
uyumlu kaynağa geçilir. Böylece partiküller/UV "yok" sanılmaz — onları üreten
CAMS hava kalitesi modeli seçili kaynağa otomatik gelir.

Kaynak kartında modelin ne olduğu, çözünürlüğü ve "veri bu kadarlık alanın
ortalamasıdır" notu görünür. Izgara yoğunluğu üst sınırı **dinamik** belirlenir:
hücre, kaynağın doğal çözünürlüğünden ince olmaz (interpole örneklemeyi/gerçek
olmayan veriyi önler).

> **Not:** Partikül/UV/AQ değişkenleri yalnızca CAMS hava kalitesi modelinde
> vardır (`aq_cams_europe` ~10 km, `aq_cams_global` ~40 km) — hava *tahmin*
> modelleri (ICON/GFS/ECMWF) kirletici üretmez. Bu yüzden PM/UV seçildiğinde
> kaynak otomatik olarak CAMS'e döner.

Çalışan (anahtarsız) kaynaklar — iki aile:

**Open-Meteo modelleri** (her kaynak kartında "Veri yolu: Open-Meteo"):

| Kaynak | Model | Çözünürlük | Değişkenler |
| --- | --- | --- | --- |
| `forecast_best` | seamless (otomatik) | ~9–25 km | tahmin |
| `forecast_icon_eu` | DWD ICON-EU | ~6 km | tahmin |
| `forecast_icon_global` | DWD ICON | ~13 km | tahmin |
| `forecast_gfs` | NOAA GFS | ~13 km | tahmin |
| `forecast_ecmwf` | ECMWF IFS | ~25 km | tahmin |
| `aq_cams_europe` | CAMS Avrupa | ~10 km | kirletici/AQ |
| `aq_cams_global` | CAMS küresel | ~40 km | kirletici/AQ |
| `elevation` | Copernicus DEM | ~30 m (gerçek arazi) | yükseklik |

**Diğer anahtarsız kaynaklar** (web aramasıyla bulundu, Open-Meteo dışı):

| Kaynak | Sağlayıcı | Çözünürlük | Mod | Not |
| --- | --- | --- | --- | --- |
| `opentopo_srtm30m` | OpenTopoData (SRTM v3) | ~30 m (gerçek arazi) | sayısal ızgara | 1 istek/sn, 1000/gün |
| `opentopo_srtm90m` | OpenTopoData (SRTM v3) | ~90 m (gerçek arazi) | sayısal ızgara | 1 istek/sn, 1000/gün |
| `rainviewer` | RainViewer (kamu radarı) | ~1–2 km (gerçek yağış) | radar tile katmanı | `/api/rainviewer` |
| `weatherapi_forecast` | weather-api.site | ~9–25 km tahmin | sayısal ızgara | keyless, anlık + tahmin |
| `weatherapi_aq` | weather-api.site | ~20 km AQ tahmini | sayısal ızgara | PM/AQ/UV keyless |
| `eris_current` | Eris (OpenWeatherMap proxy) | ~9–25 km | sayısal ızgara | yalnızca anlık hava |
| `wttrin_current` | wttr.in (JSON) | ~9–25 km | sayısal ızgara | `?format=j1`, keyless |

**İklim / enerji (anahtarsız, günlük ortalama)**:

| Kaynak | Sağlayıcı | Çözünürlük | Değişkenler |
| --- | --- | --- | --- |
| `nasa_power_daily` | NASA POWER | ~56 km reanalysis | günlük ort/max sıcaklık, yağış, güneş radyasyonu, yüzey toprak nemi |

> NASA POWER verileri **dün veya daha gerideki günün ortalamasıdır**; anlık değil,
> ~0.5° reanalysis ızgarasındır. Uygulama son 30 günde geriye doğru ilk dolu
> değeri otomatik seçer.

Hücreler Open-Meteo'nun virgülle ayrılmış çoklu koordinat desteğiyle **batch**
çekilir (tek istekte 100 nokta) → ince ızgaralar saniyeler içinde. DEM gibi
ince kaynaklar 64×64'e kadar çıkar; kaba modeller küçük alanlarda otomatik
az hücreyle sınırlanır. OpenTopoData kamu API'si 1 istek/sn ile sınırlı olduğu
için batch'leri **sıralı** çeker (ince ızgarada yavaştır). RainViewer radar
kaynağı sayısal ızgara vermez; haritada gerçek zamanlı yağış radarı **tile
katmanı** olarak gösterilir (geçmiş frame'ler + nowcast; `/api/rainviewer`).

`openaq` / `tropomi` / `radar` / `cernsio_aqi` alternatif kaynakları katalogda
**bilgi amaçlı** görünür (gerçek/ince veri sunarlar ama anahtar/entegrasyon
veya şehir bazlı sorgu nedeniyle lat/lon taramasına uymaz); tarama için
seçilemezler. Web aramasında bulunan ama mimariye uymayan diğer anahtarsız
kaynaklar: **EEA Air Quality** (anahtarsız ama Parquet dosya indirme — nokta
sorgu değil), **NOAA/NWS api.weather.gov** (anahtarsız ama yalnız ABD).

## Komut satırı

```bash
# Varsayılan: anlık + günlük tahmin
python -m meteo "İstanbul"

# Hepsini al (forecast + air quality + marine + flood + elevation)
python -m meteo "İstanbul" --all --pretty

# Geçmiş ölçümler
python -m meteo "İzmir" --historical 2025-01-01 2025-01-31

# İklim modeli projeksiyonu
python -m meteo "İzmir" --climate 2025-01-01 2030-12-31

# Deniz + hava kalitesi + rakım
python -m meteo "Bodrum" --marine --air-quality --elevation

# Doğrudan koordinat
python -m meteo --lat 41.01 --lon 28.95 --current --hourly --daily

# Bölge araması (enlem/boylam listesi)
python -m meteo --search "Ankara"

# Sonucu dosyaya yaz
python -m meteo "İstanbul" --all --pretty --save istanbul.json
```

### Seçenekler

| Seçenek | Açıklama |
| --- | --- |
| `--all` | Eldeki tüm API'leri çağır |
| `--forecast` `--current` `--hourly` `--daily` | Tahmin grupları |
| `--historical BAŞ BİT` | Geçmiş ölçümler (archive) |
| `--historical-forecast BAŞ BİT` | Geçmişe dönük tahmin |
| `--climate BAŞ BİT` | İklim modeli (CMIP6) |
| `--marine` | Deniz/dalga tahmini |
| `--flood` | Nehir debisi / taşkın |
| `--air-quality` | PM, ozon, NO2, AQI ... |
| `--elevation` | Rakım |
| `--search` | Bölge adı → eşleşme listesi |
| `--lat` `--lon` | Doğrudan koordinat |
| `--timezone` `--language` `--country` | Saat dilimi / dil / ülke kodu |
| `--forecast-days` `--past-days` `--marine-days` `--flood-days` `--aq-days` | Aralık |
| `--pretty` `--save DOSYA` | Çıktı biçimi |

## Python API

```python
from meteo import OpenMeteo

m = OpenMeteo()

# Bölge adı → koordinat
yer = m.geocode("İstanbul")
print(yer.name, yer.latitude, yer.longitude, yer.country)

# Anlık + günlük tahmin
fc = m.forecast(yer, current=True, daily=True, forecast_days=7)
print(fc["current"]["temperature_2m"], "°C")

# Saatlik tüm değişkenler
fc = m.forecast(yer, hourly=True)

# Geçmiş ölçümler
g = m.historical(yer, start_date="2024-01-01", end_date="2024-12-31")
print(g["daily"]["time"])

# Hava kalitesi
aq = m.air_quality(yer, current=True)
print(aq["current"]["pm2_5"], "µg/m³")

# Deniz / taşkın / rakım
print(m.marine(yer, hourly=True))
print(m.flood(yer, daily=True))
print(m.elevation(yer))

# Hepsini tek seferde
all_data = m.all(yer)
```

### İleri düzey: doğrudan ham istek

```python
# İstenen alt API'ye herhangi bir parametre geçir
data = m.fetch_raw("forecast", {
    "latitude": 41.01, "longitude": 28.95,
    "hourly": "temperature_2m,precipitation",
    "models": "icon_seamless",   # opsiyonel model
})
```

## Kapsanan API'ler

| API | Metot | Uç nokta |
| --- | --- | --- |
| Geocoding | `geocode`, `geocode_search`, `geocode_location` | geocoding-api |
| Forecast | `forecast` | api.open-meteo.com/v1/forecast |
| Historical | `historical` | archive-api |
| Historical Forecast | `historical_forecast` | historical-forecast-api |
| Climate | `climate` | climate-api |
| Flood | `flood` | flood-api |
| Marine | `marine` | marine-api |
| Air Quality | `air_quality` | air-quality-api |
| Elevation | `elevation` | api.open-meteo.com/v1/elevation |

Open-Meteo'un desteklediği tüm değişkenler parametre olarak
geçirilebilir; `True` kısayolu yaygın değişkenlerin tamamını ister.

## Hata yönetimi

`OpenMeteoError` / `APIError` Exception'ları fırlatılır: HTTP hataları,
API `error` alanları, geçici (429/5xx) durumlar otomatik olarak katlanmalı
beklemeyle yeniden denenir (`retries`, `backoff` parametreleri).

## Notlar

* Anahtar yok; Open-Meteo ticari olmayan kullanım için ücretsizdir.
* Adil kullanım için önbellek/limit politikaları Open-Meteo tarafındandır;
  yüksek hacimli kullanımda kendi önbelleğini ekle.
* `python -m meteo --help` tüm seçenekleri listeler.
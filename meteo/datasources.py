"""Veri kaynağı kataloğu — tarama modunda kullanıcının seçebileceği veri
kaynakları (modeller) hakkında dürüst meta-veri.

"integrated" kaynakların hepsi **Open-Meteo üzerinden anahtarsız** çalışır.
Bunlar iki ailededir:

  * Hava tahmini modelleri (Open-Meteo `models=` parametresiyle seçilir):
    icon_eu (~6 km) gibi daha ince, ecmwf_ifs04 (~40 km) gibi daha kaba
    modeller gerçek alternatif olarak sunulur.
  * CAMS hava kalitesi modelleri: cams_europe (~10 km) ve cams_global (~40 km).
  * Yükseklik (DEM ~30 m) — gerçek arazi, ince ızgarada anlamlı.

"external" kaynaklar (OpenAQ / Sentinel-5P / radar) gerçek/ince veri sunar ama
**anahtar/entegrasyon** gerektirir; katalogda bilgi amaçlı dururlar, tarama için
seçilemezler.

Her kaynak:
  - section      : Open-Meteo uç bölümü ("forecast" | "air_quality" | "elevation")
  - model        : `models=` parametresi değeri (None = varsayılan/best_match)
  - min_cell_deg : kaynağın doğal çözünürlüğü (enlem derecesi). Izgara bu
                   değerden ince olursa Open-Meteo interpolasyon yapar (gerçek
                   yeni ölçüm değil). Dinamik en yüksek ızgara bununla hesaplanır.
  - diğer alanlar : bilgilendirme kartı için (provider, measures, resolution,
                   cell_area, coverage, update_freq, caveat)
"""

from __future__ import annotations

from typing import Dict, List

# Bölüm → o bölümün tarayabildiği değişken anahtarları
# (app.SCAN_VARIABLES ile aynı anahtarlar kullanılır).
SECTION_VARS: Dict[str, List[str]] = {
    "forecast": [
        "temperature_2m", "apparent_temperature", "relative_humidity_2m",
        "precipitation", "wind_speed_10m", "pressure_msl", "cloud_cover",
    ],
    "air_quality": [
        "sulphur_dioxide", "nitrogen_dioxide", "pm2_5", "pm10", "ozone",
        "carbon_monoxide", "ammonia", "dust", "us_aqi", "european_aqi", "uv_index",
    ],
    "elevation": ["elevation"],
    "climate": [
        "daily_mean_temperature_2m", "daily_max_temperature_2m",
        "daily_precipitation", "surface_shortwave_radiation",
        "soil_moisture_surface",
    ],
}


def _row(provider, kind_label, measures, resolution, cell_area,
          coverage, update_freq, caveat, kind="model", status="integrated",
          backend="openmeteo", via="Open-Meteo", mode="grid", dataset=None):
    return {
        "provider": provider, "kind": kind, "kind_label": kind_label,
        "measures": measures, "resolution": resolution, "cell_area": cell_area,
        "coverage": coverage, "update_freq": update_freq, "status": status,
        "caveat": caveat, "backend": backend, "via": via, "mode": mode,
        "dataset": dataset,
    }


DATA_SOURCES: Dict[str, dict] = {
    # ----- Hava tahmini modelleri (anahtarsız, Open-Meteo üzerinden) -----
    "forecast_best": {
        "id": "forecast_best",
        "label": "Hava tahmini — en iyi eşleşme",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.08,  # ~9 km (seamless, bölgeye göre en ince modeli seçer)
        **_row(
            provider="Open-Meteo seamless (konuma göre en iyi modeli otomatik seçer)",
            kind_label="Atmosfer modeli (otomatik)",
            measures="Sıcaklık, hissedilen sıcaklık, nem, yağış, rüzgâr, basınç, bulutluluk — anlık tahmin.",
            resolution="~9–25 km ızgara (bölgeye göre değişir)",
            cell_area="Her değer yaklaşık 9–25 km'lik bir ızgara hücresini temsil eder; nokta ölçümü değil, model ortalamasıdır.",
            coverage="Küresel, kara + deniz",
            update_freq="Saatlik, kısa vade",
            caveat="Yerel mikro-iklim (dere yatağı, yamaç, kentsel ısı adası) çözülemez.",
        ),
    },
    "forecast_icon_eu": {
        "id": "forecast_icon_eu",
        "label": "DWD ICON-EU (~6 km)",
        "section": "forecast", "model": "icon_eu",
        "min_cell_deg": 0.054,  # ~6 km
        **_row(
            provider="DWD ICON-EU (Almanya Hava Durumu) — Open-Meteo üzerinden",
            kind_label="Atmosfer modeli (Avrupa)",
            measures="Aynı tahmin değişkenleri, daha ince Avrupa ızgarası.",
            resolution="~6 km ızgara (Avrupa)",
            cell_area="Her değer ~6 km'lik bir ızgara hücresinin ortalamasıdır; seamless'ten ince, daha yerel gradyanlar.",
            coverage="Avrupa (Kıbrıs dahil)",
            update_freq="Saatlik",
            caveat="Avrupa dışı alanlarda veri olmaz; yine de nokta ölçümü değil model ortalamasıdır.",
        ),
    },
    "forecast_icon_global": {
        "id": "forecast_icon_global",
        "label": "DWD ICON küresel (~13 km)",
        "section": "forecast", "model": "icon_global",
        "min_cell_deg": 0.117,  # ~13 km
        **_row(
            provider="DWD ICON küresel — Open-Meteo üzerinden",
            kind_label="Atmosfer modeli (küresel)",
            measures="Aynı tahmin değişkenleri, küresel ızgara.",
            resolution="~13 km ızgara",
            cell_area="Her değer ~13 km'lik bir ızgara hücresinin ortalamasıdır.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="ICON-EU'dan kaba; küresel tutarlılık için.",
        ),
    },
    "forecast_gfs": {
        "id": "forecast_gfs",
        "label": "NOAA GFS (~13 km)",
        "section": "forecast", "model": "gfs_global",
        "min_cell_deg": 0.117,  # ~13 km
        **_row(
            provider="NOAA GFS (ABD) — Open-Meteo üzerinden",
            kind_label="Atmosfer modeli (küresel)",
            measures="Aynı tahmin değişkenleri, NOAA küresel modeli.",
            resolution="~13 km ızgara",
            cell_area="Her değer ~13 km'lik bir ızgara hücresinin ortalamasıdır.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="ICON ile karşılaştırma için bağımsız bir model; farklı tahmin verebilir.",
        ),
    },
    "forecast_ecmwf": {
        "id": "forecast_ecmwf",
        "label": "ECMWF IFS (~25 km)",
        "section": "forecast", "model": "ecmwf_ifs025",
        "min_cell_deg": 0.225,  # ~25 km
        **_row(
            provider="ECMWF IFS — Open-Meteo üzerinden",
            kind_label="Atmosfer modeli (küresel, kaba)",
            measures="Aynı tahmin değişkenleri, ECMWF küresel ızgarası.",
            resolution="~25 km ızgara",
            cell_area="Her değer ~25 km'lik bir ızgara hücresinin ortalamasıdır; yerel detay zayıf.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="Kaba ama genellikle istikrarlı; bağımsız karşılaştırma kaynağı.",
        ),
    },

    # MET Norway — bağımsız anahtarsız tahmin kaynağı (Open-Meteo dışı).
    "metno_forecast": {
        "id": "metno_forecast",
        "label": "MET Norway (yr.no) tahmini",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.045,  # ~5 km tahmini
        "variables": [
            "temperature_2m", "relative_humidity_2m", "precipitation",
            "wind_speed_10m", "pressure_msl", "cloud_cover",
        ],
        **_row(
            provider="MET Norway / Norwegian Meteorological Institute (api.met.no)",
            kind_label="Atmosfer modeli (kuzey/deniz ağırlıklı)",
            backend="metno", via="MET Norway", mode="grid",
            measures="Sıcaklık, nem, yağış (1 saatlik), rüzgâr hızı, basınç, bulutluluk.",
            resolution="~5–10 km ızgarası (varies by region)",
            cell_area="Her değer MET Norway modelinin ızgara hücresi ortalamasıdır; Open-Meteo'dan bağımsız bir model.",
            coverage="Küresel (okyanus/kuzey enlemlerinde daha iyi)",
            update_freq="Saatlik",
            caveat="Kullanıcı-Agent gerekir (met.no politikası). UV/hissedilen sıcaklık vermez; rüzgâr m/s'den km/h çevrilir.",
        ),
    },

    # 7Timer! — NOAA GFS tabanlı anahtarsız tahmin.
    "seventimer_forecast": {
        "id": "seventimer_forecast",
        "label": "7Timer! (GFS tabanlı)",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.09,  # ~10 km
        "variables": [
            "temperature_2m", "relative_humidity_2m", "precipitation",
            "wind_speed_10m", "cloud_cover",
        ],
        **_row(
            provider="7Timer! (www.7timer.info)",
            kind_label="NOAA GFS tabanlı tahmin",
            backend="seventimer", via="7Timer!", mode="grid",
            measures="Sıcaklık, nem, yağış, rüzgâr hızı, bulutluluk.",
            resolution="~10–20 km ızgara",
            cell_area="Her değer 7Timer'ın GFS tabanlı ızgara hücresi ortalamasıdır; Open-Meteo GFS'inden bağımsız bir kaynak.",
            coverage="Küresel",
            update_freq="6 saatte bir (GFS init)",
            caveat="Basınç, hissedilen sıcaklık ve UV vermez. Rüzgâr yönü metin (N/SW) döner, hızı m/s'den km/h çevrilir. Yağış miktarı kategorik/integer olabilir.",
        ),
    },

    # ----- Hava kalitesi modelleri (anahtarsız, CAMS üzerinden) -----
    "aq_cams_europe": {
        "id": "aq_cams_europe",
        "label": "CAMS Avrupa (~10 km)",
        "section": "air_quality", "model": "cams_europe",
        "min_cell_deg": 0.09,  # ~10 km
        **_row(
            provider="CAMS Avrupa bölgesel modeli — Open-Meteo üzerinden",
            kind_label="Atmosfer kimyası modeli (Avrupa)",
            measures="SO₂, NO₂, PM2.5, PM10, ozon, CO, NH₃, toz, AQ indeksleri, UV — yüzey konsantrasyonu.",
            resolution="~10 km ızgara (Avrupa)",
            cell_area="Her değer ~10 km'lik bir ızgara hücresinin ortalamasıdır; küresel CAMS'ten ince.",
            coverage="Avrupa (Kıbrıs dahil)",
            update_freq="Saatlik",
            caveat="Yine tek baca/trafik gibi nokta kaynakları yer seviyesinde çözülemez; CO uzun ömürlü olduğu için yerel farklar görünmez.",
        ),
    },
    "aq_cams_global": {
        "id": "aq_cams_global",
        "label": "CAMS küresel (~40 km)",
        "section": "air_quality", "model": "cams_global",
        "min_cell_deg": 0.36,  # ~40 km
        **_row(
            provider="CAMS küresel modeli — Open-Meteo üzerinden",
            kind_label="Atmosfer kimyası modeli (küresel, kaba)",
            measures="Aynı kirleticiler, küresel kaba ızgara.",
            resolution="~40 km ızgara",
            cell_area="Her değer ~40 km'lik bir ızgara hücresinin ortalamasıdır; yerel detay çok zayıf.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="Çok kaba; yalnızca bölgesel arka plan için anlamlı.",
        ),
    },

    # ----- Yükseklik (gerçek arazi, anahtarsız) -----
    "elevation": {
        "id": "elevation",
        "label": "Yükseklik (DEM ~30 m)",
        "section": "elevation", "model": None,
        "min_cell_deg": 0.0003,  # ~30 m
        **_row(
            provider="Copernicus DEM / SRTM — Open-Meteo üzerinden",
            kind_label="Sayısal yükseklik modeli (gerçek arazi)",
            kind="dem",
            measures="Yer yüzeyi yüksekliği (metre).",
            resolution="~30 m (küresel), bazı bölgelerde ~10–25 m",
            cell_area="Yaklaşık 30 m'lik hücre — neredeyse noktasal ve GERÇEK arazi verisi, model değil. Bu yüzden ince ızgarada bile anlamlıdır; uygulama burada en yüksek ızgarayı otomatik önerir.",
            coverage="Küresel kara",
            update_freq="Statik (arazi değişmez)",
            caveat="Gerçek ölçümdür; ızgarayı model sınırıyla değil arazi detayıyla sınırlar.",
        ),
    },

    # ----- Diğer anahtarsız kaynaklar (Open-Meteo dışı, web aramasıyla bulundu) -----

    # OpenTopoData — anahtarsız SRTM yükseklik API'si (Open-Meteo dışı, gerçek arazi).
    # Kamu API'si: 100 nokta/istek, 1 istek/sn, 1000 istek/gün. -60..60 enlem kapsar.
    "opentopo_srtm30m": {
        "id": "opentopo_srtm30m",
        "label": "Yükseklik — OpenTopoData SRTM 30m",
        "section": "elevation", "model": None,
        "min_cell_deg": 0.0003,  # ~30 m
        **_row(
            provider="OpenTopoData (SRTM v3) — opentopodata.org",
            kind_label="Sayısal yükseklik modeli (gerçek arazi, SRTM)",
            kind="dem",
            backend="opentopodata", via="OpenTopoData", dataset="srtm30m",
            measures="Yer yüzeyi yüksekliği (metre) — SRTM 1 arc-saniye.",
            resolution="~30 m",
            cell_area="~30 m'lik SRTM hücresi — GERÇEK arazi, model değil. Open-Meteo DEM'den bağımsız bir kaynak; sonuçlar küçük farklar gösterebilir.",
            coverage="−60°…60° enlem (Kıbrıs dahil), kara",
            update_freq="Statik (SRTM v3)",
            caveat="Kamu API'si sınırı: 1 istek/sn, 1000/gün → ince ızgarada yavaştır (batch'ler sıralı çekilir). Deniz/nokta dışı yerde null.",
        ),
    },
    "opentopo_srtm90m": {
        "id": "opentopo_srtm90m",
        "label": "Yükseklik — OpenTopoData SRTM 90m",
        "section": "elevation", "model": None,
        "min_cell_deg": 0.0008,  # ~90 m
        **_row(
            provider="OpenTopoData (SRTM v3) — opentopodata.org",
            kind_label="Sayısal yükseklik modeli (gerçek arazi, SRTM)",
            kind="dem",
            backend="opentopodata", via="OpenTopoData", dataset="srtm90m",
            measures="Yer yüzeyi yüksekliği (metre) — SRTM 3 arc-saniye.",
            resolution="~90 m",
            cell_area="~90 m'lik SRTM hücresi — GERÇEK arazi, model değil. 30m'den kaba ama daha hızlı.",
            coverage="−60°…60° enlem (Kıbrıs dahil), kara",
            update_freq="Statik (SRTM v3)",
            caveat="Kamu API'si sınırı: 1 istek/sn, 1000/gün. 30m'den az detay ama istek sayısı düşer.",
        ),
    },

    # RainViewer — anahtarsız küresel hava radarı (gerçek yağış gözlemi). Tile-overlay
    # modu: sayısal hücre değil, harita üstünde radar kompozit katmanı. Son 2 saat + nowcast.
    "rainviewer": {
        "id": "rainviewer",
        "label": "Yağış radarı — RainViewer",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="RainViewer — rainviewer.com (kamu radar API)",
            kind_label="Radar gözlemi (gerçek, gerçek zamanlı)",
            kind="satellite",
            backend="rainviewer", via="RainViewer", mode="radar", status="integrated",
            measures="Yağış reflektivitesi — gerçek radar kompoziti, tahmin değil.",
            resolution="~1–2 km (radar kapsama alanında)",
            cell_area="Radar tile'ları görsel katmandır; sayısal hücre/ızgara vermez. Her tile radar kapsamasındaki alanın gerçek yansımasını gösterir.",
            coverage="Küresel (radar istasyonu olan bölgeler)",
            update_freq="10 dk (son ~2 saat geçmiş + nowcast)",
            caveat="Tile tabanlı görsel; sayısal tarama/maske üretmez. Radar olmayan bölgeler boş. Anahtarsız, kişisel/ eğitim kullanımı.",
        ),
    },

    # ----- Web aramasıyla bulunan yeni anahtarsız public API kaynakları -----
    # weather-api.site — keyless hava tahmini / anlık hava JSON API'si.
    "weatherapi_forecast": {
        "id": "weatherapi_forecast",
        "label": "weather-api.site (anlık tahmin)",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.09,  # ~10 km; gerçek çözünürlüğü belirsiz, güvenli tavan
        **_row(
            provider="weather-api.site",
            kind_label="Anahtarsız hava tahmin API'si",
            backend="weatherapi", via="weather-api.site", mode="grid",
            measures="Sıcaklık, hissedilen sıcaklık, nem, yağış, rüzgâr, basınç, bulutluluk, UV.",
            resolution="~9–25 km tahmin ızgarası (tahmini)",
            cell_area="Her değer tahmin modelinin ızgara hücresi ortalamasıdır; nokta ölçümü değil.",
            coverage="Küresel",
            update_freq="Saatlik tahmin, anlık mevcut",
            caveat="Ücretsiz public API; rate limit açıklanmamış. Aşırı kullanımda kısıtlanabilir.",
        ),
    },
    "weatherapi_aq": {
        "id": "weatherapi_aq",
        "label": "weather-api.site (hava kalitesi)",
        "section": "air_quality", "model": None,
        "min_cell_deg": 0.18,  # ~20 km; model tabanlı AQ tahmini
        **_row(
            provider="weather-api.site",
            kind_label="Anahtarsız hava kalitesi API'si",
            backend="weatherapi", via="weather-api.site", mode="grid",
            measures="PM2.5, PM10, NO₂, SO₂, CO, ozon, ABD AQI.",
            resolution="~20 km tahmini AQ ızgarası",
            cell_area="Her değer model tabanlı hava kalitesi tahmininin ızgara ortalamasıdır; istasyon ölçümü değil.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="AQ değerleri model tahminidir; yerel sensör ölçümlerinden farklı olabilir. Rate limit açıklanmamış.",
        ),
    },

    # Eris — keyless anlık hava API'si (OpenWeatherMap üzerinden açık proxy).
    "eris_current": {
        "id": "eris_current",
        "label": "Eris (anlık hava)",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.09,
        **_row(
            provider="Eris (weather-api.madadipouya.com)",
            kind_label="Anahtarsız anlık hava API'si",
            backend="eris", via="Eris", mode="grid",
            measures="Sıcaklık, nem, basınç, rüzgâr, hava durumu açıklaması.",
            resolution="~9–25 km (OpenWeatherMap istasyon/model karışımı)",
            cell_area="Her değer istasyon/veri kaynağı karışımının nokta yaklaşıklamasıdır; yerel istasyon olmayan yerlerde model değeri olabilir.",
            coverage="Küresel",
            update_freq="Anlık/10 dk",
            caveat="Public instance 'no limits' diyor ama bağımsız proxydir; üretimde kendi kendine host edilebilir. Sadece anlık veri, tahmin/forecast yok.",
        ),
    },

    # wttr.in — terminal dostu, JSON çıkışlı keyless hava API'si.
    "wttrin_current": {
        "id": "wttrin_current",
        "label": "wttr.in (anlık hava)",
        "section": "forecast", "model": None,
        "min_cell_deg": 0.09,
        **_row(
            provider="wttr.in (WorldWeatherOnline verisi)",
            kind_label="Anahtarsız anlık hava API'si",
            backend="wttrin", via="wttr.in", mode="grid",
            measures="Sıcaklık, nem, basınç, rüzgâr, görünürlük, UV.",
            resolution="~9–25 km (WorldWeatherOnline ızgara)",
            cell_area="Her değer WorldWeatherOnline ızgara/istasyon karışımının nokta yaklaşıklamasıdır.",
            coverage="Küresel",
            update_freq="Saatlik",
            caveat="?format=j1 JSON endpoint'i gayri resmi/desteklenmez sayılabilir; ana site metin/ANSI odaklıdır. Aşırı kullanımda IP engeli olabilir.",
        ),
    },

    # CERNS.IO — keyless şehir bazlı hava kalitesi API'si. API dokümanında
    # /locate (lat/lon → slug) ucu gösteriliyordu ancak canlı testte 404 dönüyor;
    # sadece bilinen şehir slug'larıyla çalışıyor. Bu yüzden lat/lon taramasına
    # uymadığı için external (bilgi) olarak bırakılıyor.
    "cernsio_aqi": {
        "id": "cernsio_aqi",
        "label": "CERNS.IO (şehir AQI) — bilgi",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="CERNS.IO",
            kind_label="Anahtarsız şehir bazlı hava kalitesi API'si",
            status="external", backend=None, via="CERNS.IO",
            measures="PM2.5, PM10, ABD AQI, UV indeksi.",
            resolution="Şehir merkezi (~33.000 şehir)",
            cell_area="Her değer seçilen şehrin istasyon/model karışımı ortalamasıdır; ızgara tarama yapmaz.",
            coverage="33.000+ şehir, 108+ ülke",
            update_freq="~30 dk",
            caveat="Şehir slug'ıyla çalışır; lat/lon'dan otomatik şehir bulma (/locate) canlıda 404. Entegrasyon için şehir adı/arama arayüzü gerekir. Rate limit 60 istek/dk/IP.",
        ),
    },

    # NASA POWER — keyless günlük iklim/enerji verisi (dün ortalaması).
    "nasa_power_daily": {
        "id": "nasa_power_daily",
        "label": "NASA POWER (günlük iklim/enerji)",
        "section": "climate", "model": None,
        "min_cell_deg": 0.05,  # ~5.6 km (0.5° reanalysis ~56 km aslında; güvenli tavan)
        **_row(
            provider="NASA POWER (NASA Langley Research Center)",
            kind_label="Anahtarsız günlük iklim/enerji verisi",
            backend="nasa_power", via="NASA POWER", mode="grid",
            measures="Günlük ortalama sıcaklık, günlük maksimum sıcaklık, günlük toplam yağış, güneş radyasyonu (kısa dalga), yüzey toprak nemi.",
            resolution="0.5° reanalysis (~56 km); güneş radyasyonu gibi parametreler daha kaba",
            cell_area="Her değer ~56 km'lik bir reanalysis ızgara hücresinin günlük ortalamasıdır; anlık değil, dünün ortalamasıdır.",
            coverage="Küresel (kara/deniz), 1981–dün",
            update_freq="Günlük (bir gecikmeli)",
            caveat="Veri dünün ortalamasıdır; anlık/bugün tahmini değildir. Reanalysis ızgarası kabaca 0.5° (~56 km); yerel detay çok düşük.",
        ),
    },

    # ----- Görsel / nokta overlay kaynaklar (sayısal ızgara değil) -----
    # USGS Deprem API — küresel, keyless GeoJSON; haritada daire marker olarak
    # gösterilir, çizme/alan seçme ZORUNLU değil.
    "usgs_earthquakes": {
        "id": "usgs_earthquakes",
        "label": "USGS Depremler (son 1 saat)",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="USGS Earthquake Hazards Program",
            kind_label="Gerçek deprem gözlemleri (nokta)",
            kind="station", status="integrated", backend="usgs", via="USGS", mode="points",
            measures="Büyüklük (magnitude), derinlik, zaman, konum.",
            resolution="Noktasal (epicenter)",
            cell_area="Her nokta bir depremin merkez üssünü gösterir; ızgara ortalaması değil, gerçek gözlem.",
            coverage="Küresel",
            update_freq="Dakikalık",
            caveat="Yalnızca algılanan depremler; çok küçük/derin/okyanus ortası olaylar eksik olabilir. Alan tarama yapmaz; haritada nokta marker gösterir.",
        ),
    },

    # EUMETSAT Meteosat 0° full disk uydu görüntüsü — keyless JPG; haritada
    # image overlay olarak gösterilir, çizme/alan seçme ZORUNLU değil.
    "eumetsat_meteosat": {
        "id": "eumetsat_meteosat",
        "label": "EUMETSAT Meteosat uydu görüntüsü",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="EUMETSAT (Meteosat Second Generation, 0° full disk)",
            kind_label="Gerçek uydu görüntüsü (image overlay)",
            kind="satellite", status="integrated", backend="eumetsat", via="EUMETSAT", mode="image",
            measures="Doğal renk RGB (gündüz) / IR 10.8 µm (gece).",
            resolution="Full disk (~3 km piksel, 3712×3712 yerine web için düşük çözünürlü)",
            cell_area="Tam diskin bir kısmı — Kıbrıs ve Akdeniz görünür. Görsel overlay; sayısal tarama/ızgara değil.",
            coverage="Afrika/Avrupa/Ortadoğu (Meteosat 0° full disk)",
            update_freq="~15–60 dk (ürüne göre)",
            caveat="EUMETSAT 'latest image' URL'leri doğrudan erişime açık ama aşırı poll yapılmamalı (~30 dk). Görüntü küresel projeksiyondadır, haritaya image overlay olarak yerleştirilir.",
        ),
    },

    # ----- Alternatif kaynaklar (bilgi amaçlı, anahtar/entegrasyon gerekir) -----
    "openaq": {
        "id": "openaq",
        "label": "OpenAQ — yer istasyonları",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="OpenAQ (devlet çevre ajansı istasyonlarını toplar)",
            kind_label="Gerçek sensör istasyonu",
            kind="station", status="external", backend=None, via="OpenAQ",
            measures="PM2.5, PM10, NO₂, SO₂, CO, O₃ — gerçek saatlik ölçüm.",
            resolution="Noktasal (istasyon yeri)",
            cell_area="Tek bir sensörün bulunduğu noktanın ölçümüdür; ızgara ortalaması değil, GERÇEK ölçümdür — ama yalnızca istasyon olan yerde.",
            coverage="İstasyon bulunan bölgeler (Kıbrıs'ta seyrek/boş olabilir)",
            update_freq="Saatlik",
            caveat="Sürekli ızgara vermez; istasyon olmayan alan boş kalır. OpenAQ v3 API anahtarı ister.",
        ),
    },
    "tropomi": {
        "id": "tropomi",
        "label": "Sentinel-5P TROPOMI — uydu",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="Copernicus Sentinel-5P",
            kind_label="Uydu kolon ölçümü",
            kind="satellite", status="external", backend=None, via="Sentinel-5P",
            measures="NO₂, SO₂, CO, aerosol — atmosfer kolonu (toplam dikey miktar).",
            resolution="~3.5×5.5 km",
            cell_area="Her piksel ~3.5–5.5 km'lik bir alanın kolon ortalamasıdır; YÜZEY konsantrasyonu değil, WHO limitleriyle doğrudan karşılaştırılamaz.",
            coverage="Küresel, günde ~1 geçiş",
            update_freq="Günlük",
            caveat="Çok ince uzamsal maske verir ama kolon≠yüzey; bulutlu günlerde veri olmaz. Copernicus hesabı/anahtarı gerekir.",
        ),
    },
    "radar": {
        "id": "radar",
        "label": "Hava radarı — yağış",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="NOAA MRMS / ulusal radarlar",
            kind_label="Radar gözlemi (gerçek)",
            kind="station", status="external", backend=None, via="NOAA MRMS",
            measures="Yağış miktarı (QPE) — gerçek ölçüm, tahmin değil.",
            resolution="~1 km, 2–5 dk",
            cell_area="Her hücre ~1 km'lik alanın gerçek radar ölçümüdür; model değil. Yalnızca yağış için.",
            coverage="Radar kapsama alanı (ABD/Eu geneli)",
            update_freq="2–5 dk",
            caveat="Yalnızca yağış; diğer değişkenler yok. Kaynak verisi ayrıştırma (grib/geojson) gerekir.",
        ),
    },

    # Ek dışarıda bırakılan public API kaynaklar (mimari/region/auth uymadığı
    # için bilgi amaçlı; tarama için seçilemez).
    "noaa_goes": {
        "id": "noaa_goes",
        "label": "NOAA GOES uydu görüntüsü — bilgi",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="NOAA/NESDIS GOES-East/West",
            kind_label="Gerçek uydu görüntüsü (bilgi)",
            kind="satellite", status="external", backend=None, via="NOAA GOES",
            measures="Doğal renk, infrared, su buharı bantları.",
            resolution="~0.5–2 km (banta göre)",
            cell_area="GOES 'ne' sektörü Atlantik/ABD doğu kıyısını kapsar; Kıbrıs'ı göstermez. Full Disk küresel ama çok kaba (~10 km).",
            coverage="GOES-East/West görüş alanı (Amerika/Atlantik/Pasifik)",
            update_freq="10–15 dk",
            caveat="Kıbrıs/Akdeniz için EUMETSAT Meteosat entegre edildi; NOAA GOES bilgi amaçlıdır. Doğrudan image URL sector bazlıdır.",
        ),
    },
    "blitzortung_lightning": {
        "id": "blitzortung_lightning",
        "label": "Blitzortung yıldırım — bilgi",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="Blitzortung.org / LightningMaps.org",
            kind_label="Gerçek yıldırım gözlemi (bilgi)",
            kind="station", status="external", backend=None, via="Blitzortung",
            measures="Yıldırım düşme zamanı, konum, polarite, akım.",
            resolution="Noktasal (~km çözünürlük)",
            cell_area="Her nokta bir yıldırım düşmesini gösterir; gerçek gözlem.",
            coverage="Detektör ağı olan bölgeler (Avrupa/Akdeniz kapsamlı)",
            update_freq="Gerçek zamanlı (sn düzeyinde)",
            caveat="Keyless açık HTTP/GeoJSON endpoint yok; protected HTTP veya websocket gerektirir. Ticari kullanım yasak. Entegrasyon için participant hesabı veya kendi websocket-GeoJSON proxy'si gerekir.",
        ),
    },
    "windy_embed": {
        "id": "windy_embed",
        "label": "Windy embed — bilgi",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="Windy.com",
            kind_label="Harita embed / interaktif hava haritası (bilgi)",
            kind="satellite", status="external", backend=None, via="Windy",
            measures="Rüzgâr, sıcaklık, dalga, yağış, bulut katmanları.",
            resolution="Model/uydu karışımı",
            cell_area="Windy interaktif haritası; doğrudan veri değil, görsel.",
            coverage="Küresel",
            update_freq="Model güncellemelerine göre",
            caveat="Embed/iFrame kullanımı Windy politikasına tabi; doğrudan entegrasyon için resmi API anahtarı veya embed izni gerekir. Bilgi amaçlı harici bağlantı.",
        ),
    },
    "sunrise_sunset": {
        "id": "sunrise_sunset",
        "label": "Sunrise-Sunset.org — bilgi",
        "section": None, "model": None, "min_cell_deg": None,
        **_row(
            provider="Sunrise-Sunset.org",
            kind_label="Güneş doğuş/batış ve alacakaranlık (bilgi)",
            kind="station", status="external", backend=None, via="Sunrise-Sunset.org",
            measures="Güneş doğuş/batış, öğle, gece yarım, sivil/askeri/astronomik alacakaranlık, golden hour.",
            resolution="Noktasal (lat/lon)",
            cell_area="Seçilen noktanın günlük güneş hesaplaması.",
            coverage="Küresel",
            update_freq="Günlük",
            caveat="Open-Meteo zaten sunrise/sunset veriyor; bu kaynak ek twilight/golden hour detayı sunar. Tek nokta sorgusu; ızgara tarama yapmaz.",
        ),
    },
}


def get(source_id: str) -> dict | None:
    """Bir kaynağın meta-verisini döndürür, yoksa None."""
    return DATA_SOURCES.get(source_id)


def variables_for(source_id: str) -> List[str]:
    """Bir kaynağin tarayabildiği değişken anahtarlarını döndürür.
    Kaynak tanımında açıkça `variables` listesi varsa onu döndürür; yoksa
    bölümün değişkenlerini döndürür. External kaynaklar için boş.
    Böylece aynı bölümdeki farklı backend'ler (örn. MET Norway, 7Timer)
    yalnızca sundukları değişkenleri gösterebilir."""
    src = DATA_SOURCES.get(source_id)
    if not src:
        return []
    explicit = src.get("variables")
    if explicit is not None:
        return list(explicit)
    if not src.get("section"):
        return []
    return SECTION_VARS.get(src["section"], [])


def integrated_sources() -> List[dict]:
    """Çalışan (status=integrated) kaynakların listesi."""
    return [s for s in DATA_SOURCES.values() if s["status"] == "integrated"]


def external_sources() -> List[dict]:
    """Alternatif (status=external) kaynakların listesi."""
    return [s for s in DATA_SOURCES.values() if s["status"] == "external"]
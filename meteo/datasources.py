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
}


def get(source_id: str) -> dict | None:
    """Bir kaynağın meta-verisini döndürür, yoksa None."""
    return DATA_SOURCES.get(source_id)


def variables_for(source_id: str) -> List[str]:
    """Bir kaynağin tarayabildiği değişken anahtarlarını döndürür
    (external kaynaklar için boş)."""
    src = DATA_SOURCES.get(source_id)
    if not src or not src.get("section"):
        return []
    return SECTION_VARS.get(src["section"], [])


def integrated_sources() -> List[dict]:
    """Çalışan (status=integrated) kaynakların listesi."""
    return [s for s in DATA_SOURCES.values() if s["status"] == "integrated"]


def external_sources() -> List[dict]:
    """Alternatif (status=external) kaynakların listesi."""
    return [s for s in DATA_SOURCES.values() if s["status"] == "external"]
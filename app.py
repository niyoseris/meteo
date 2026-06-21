"""meteo — Flask web uygulaması.

HTML arayüz ve JSON API üzerinden Open-Meteo verilerine erişim.

Çalıştırma::

    flask --app app run --debug --port 5001   # geliştirme
    # veya:
    python app.py                             # dahili sunucu, 5001 portunda

Rotalar
-------
  GET /                       Ana sayfa (arama formu)
  GET /weather                HTML sonuç sayfası (?place= veya ?lat=&lon=)
  GET /api/places             Bölge arama (JSON) — ?name=...
  GET /api/geocode            En iyi eşleşme (JSON) — ?name=...
  GET /api/weather            Tüm/seçili veriler (JSON) — ?place=&days=&sections=
  GET /api/historical         Geçmiş ölçümler (JSON) — ?place=&start=&end=
  GET /api/raw                Doğrudan alt API passthrough — ?kind=&...
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import Flask, abort, jsonify, render_template, request

from meteo import OpenMeteo, OpenMeteoError, APIError, Location, codes, air_quality_ref, interpret
from meteo.weather import CURRENT_VARS, AIR_QUALITY_VARS
from meteo import metrics_ref
from meteo import datasources

app = Flask(__name__)


@app.template_filter("dt")
def _dt_filter(value):
    """ISO zamanı okunabilir TR biçimine çevirir.

    "2026-06-20T13:15" -> "20.06.2026 13:15"
    "2026-06-20T13:15:00" -> "20.06.2026 13:15"
    zaten kısa veya boşsa olduğu gibi döner.
    """
    if not value:
        return ""
    s = str(value)
    if "T" in s:
        date, _, timepart = s.partition("T")
        timepart = timepart.split("+")[0].split(".")[0]
        # saniyeyi at (HH:MM:SS -> HH:MM)
        if len(timepart) >= 5:
            timepart = timepart[:5]
        return f"{date.split('-')[2]}.{date.split('-')[1]}.{date.split('-')[0]} {timepart}"
    return s

# Tüm isteklerde paylaşılan tek client (session yeniden kullanımı).
_meteo = OpenMeteo()

# OSM Nominatim için ayrı oturum — kullanım politikası gerçek bir User-Agent
# ister. Lütfen kendi e-postanızı ekleyin; yerel geliştirme için yeterli.
_NOMINATIM = requests.Session()
_NOMINATIM.headers.update({
    "User-Agent": "meteo/0.1.0 (openstreetmap-lookup; local-dev)",
    "Accept-Language": "tr",
})


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _resolve_place_or_coords() -> Tuple[Optional[Location], Optional[str]]:
    """Sorgu argümanlarından konum çözer.

    Dönüş: (Location, hata_mesajı). Hata varsa Location None olur.
    """
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is not None and lon is not None:
        return (
            Location(
                latitude=lat,
                longitude=lon,
                name=request.args.get("name", "") or f"({lat}, {lon})",
                timezone=request.args.get("timezone", "auto"),
            ),
            None,
        )

    place = request.args.get("place", "").strip()
    if not place:
        return None, "Bir bölge adı veya enlem/boylam (lat, lon) gerekli."
    try:
        loc = _meteo.geocode_location(
            place,
            timezone=request.args.get("timezone", "auto"),
            language=request.args.get("language", "tr"),
            country_codes=request.args.get("country"),
        )
    except OpenMeteoError as exc:
        return None, str(exc)
    return loc, None


def _api_error(message: str, status: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _sections() -> List[str]:
    raw = request.args.get("sections")
    if not raw:
        return ["all"]
    return [s.strip() for s in raw.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# HTML sayfalar
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/weather")
def weather_page():
    loc, err = _resolve_place_or_coords()
    if err or loc is None:
        return render_template("weather.html", error=err or "Bilinmeyen hata", location=None)

    days = request.args.get("days", default=7, type=int)
    try:
        data = _meteo.all(
            loc,
            forecast_days=days,
            past_days=0,
            air_quality_days=days,
            marine_days=days,
            flood_days=30,
        )
    except OpenMeteoError as exc:
        return render_template("weather.html", error=str(exc), location=None)

    # Hava kodu açıklamalarını zenginleştir.
    _enrich(data)
    # Hava kalitesi için açıklamalı + referans kıyaslamalı tablo.
    aq_metrics = []
    aq = data.get("air_quality")
    if isinstance(aq, dict) and "error" not in aq and "current" in aq:
        aq_metrics = air_quality_ref.build_table(aq["current"])
    return render_template(
        "weather.html",
        location=loc,
        data=data,
        codes=codes,
        aq_metrics=aq_metrics,
        days=days,
        error=None,
    )


@app.route("/compare")
def compare_page():
    """Karşılaştırma modu — haritada birden fazla nokta seç, yan yana karşılaştır."""
    return render_template("compare.html")


@app.route("/scan")
def scan_page():
    """Alan tarama modu — bir alanı dikdörtgenle seç, bir değişkeni ızgara
    noktalarıyla tara, sonucu haritada renk maskesi olarak göster.

    Kullanıcı önce bir veri kaynağı/modeli seçer; kaynak bilgilendirme kartında
    modelin ne olduğunu, çözünürlüğünü ve "veri bu kadarlık alanın
    ortalamasıdır" notunu görür. Değişken listesi kaynağa göre filtrelenir,
    ızgara yoğunluğu üst sınırı kaynak + alana göre dinamik belirlenir.
    """
    var_by_key = {v["key"]: v for v in SCAN_VARIABLES}
    sources = []
    for meta in datasources.DATA_SOURCES.values():
        var_keys = datasources.variables_for(meta["id"])
        sources.append({
            "id": meta["id"],
            "label": meta["label"],
            "section": meta.get("section"),
            "model": meta.get("model"),
            "min_cell_deg": meta.get("min_cell_deg"),
            "backend": meta.get("backend", "openmeteo"),
            "via": meta.get("via", "Open-Meteo"),
            "mode": meta.get("mode", "grid"),
            "provider": meta["provider"],
            "kind_label": meta["kind_label"],
            "measures": meta["measures"],
            "resolution": meta["resolution"],
            "cell_area": meta["cell_area"],
            "coverage": meta["coverage"],
            "update_freq": meta["update_freq"],
            "status": meta["status"],
            "caveat": meta["caveat"],
            "variables": [{"key": k, "label": var_by_key[k]["label"], "unit": var_by_key[k]["unit"]}
                           for k in var_keys if k in var_by_key],
        })
    return render_template("scan.html", sources=sources, variables=SCAN_VARIABLES,
                           default_source="forecast_best", default_variable="temperature_2m")


# ---------------------------------------------------------------------------
# Alan tarama (scan) yardımcıları
# ---------------------------------------------------------------------------
# Taranabilir değişkenler: (anahtar, etiket, bölüm, birim)
SCAN_VARIABLES: List[dict] = [
    {"key": "sulphur_dioxide", "label": "SO₂ (kükürt dioksit)", "section": "air_quality", "unit": "µg/m³"},
    {"key": "nitrogen_dioxide", "label": "NO₂ (azot dioksit)", "section": "air_quality", "unit": "µg/m³"},
    {"key": "pm2_5", "label": "PM2.5", "section": "air_quality", "unit": "µg/m³"},
    {"key": "pm10", "label": "PM10", "section": "air_quality", "unit": "µg/m³"},
    {"key": "ozone", "label": "Ozon (O₃)", "section": "air_quality", "unit": "µg/m³"},
    {"key": "carbon_monoxide", "label": "CO (karbon monoksit)", "section": "air_quality", "unit": "µg/m³"},
    {"key": "ammonia", "label": "NH₃ (amonyak)", "section": "air_quality", "unit": "µg/m³"},
    {"key": "dust", "label": "Çöl tozu", "section": "air_quality", "unit": "µg/m³"},
    {"key": "us_aqi", "label": "ABD AQI", "section": "air_quality", "unit": ""},
    {"key": "european_aqi", "label": "AB AQI", "section": "air_quality", "unit": ""},
    {"key": "uv_index", "label": "UV indeksi", "section": "air_quality", "unit": ""},
    {"key": "temperature_2m", "label": "Sıcaklık", "section": "forecast", "unit": "°C"},
    {"key": "apparent_temperature", "label": "Hissedilen sıcaklık", "section": "forecast", "unit": "°C"},
    {"key": "relative_humidity_2m", "label": "Nem", "section": "forecast", "unit": "%"},
    {"key": "precipitation", "label": "Yağış", "section": "forecast", "unit": "mm"},
    {"key": "wind_speed_10m", "label": "Rüzgâr hızı", "section": "forecast", "unit": "km/s"},
    {"key": "pressure_msl", "label": "Basınç", "section": "forecast", "unit": "hPa"},
    {"key": "cloud_cover", "label": "Bulutluluk", "section": "forecast", "unit": "%"},
    {"key": "elevation", "label": "Yükseklik (DEM)", "section": "elevation", "unit": "m"},
    {"key": "daily_mean_temperature_2m", "label": "Günlük ortalama sıcaklık", "section": "climate", "unit": "°C"},
    {"key": "daily_max_temperature_2m", "label": "Günlük maksimum sıcaklık", "section": "climate", "unit": "°C"},
    {"key": "daily_precipitation", "label": "Günlük toplam yağış", "section": "climate", "unit": "mm"},
    {"key": "surface_shortwave_radiation", "label": "Yüzey güneş radyasyonu", "section": "climate", "unit": "kWh/m²"},
    {"key": "soil_moisture_surface", "label": "Yüzey toprak nemi", "section": "climate", "unit": "m³/m³"},
]


def _scan_grid(north, south, east, west, rows):
    """Bbox içinde ızgara noktaları (lat, lon) üretir — hücreler yaklaşık
    kare olacak şekilde sütun sayısını boylam/enlem oranına göre ayarlar.

    rows, mutlak tavanlarla (SCAN_MAX_ROWS / SCAN_MAX_CELLS) kırpılır. Kaynağın
    doğal çözünürlüğüne göre dürüstleştirme (interpole örnekleme sınırı)
    çağırıcıda _max_rows_for() ile yapılır; bu fonksiyon yalnızca geometri üretir.
    """
    lat_span = north - south
    lon_span = east - west
    if lat_span <= 0 or lon_span <= 0:
        raise ValueError("Geçersiz alan: kuzey>güney ve doğu>batı olmalı")
    rows = max(2, min(SCAN_MAX_ROWS, int(rows)))
    midlat = (north + south) / 2
    cols = max(1, round(rows * lon_span / lat_span * math.cos(math.radians(midlat))))
    cols = min(2 * rows, cols)
    if rows * cols > SCAN_MAX_CELLS:  # çok büyük ızgarada sütunu küçült
        cols = max(1, SCAN_MAX_CELLS // rows)
    lats = [south + i * lat_span / (rows - 1) for i in range(rows)] if rows > 1 \
        else [(north + south) / 2]
    lons = [west + j * lon_span / (cols - 1) for j in range(cols)] if cols > 1 \
        else [(west + east) / 2]
    cells = [(la, lo) for la in lats for lo in lons]
    cell_h = (lat_span / (rows - 1)) if rows > 1 else lat_span or 0.01
    cell_w = (lon_span / (cols - 1)) if cols > 1 else lon_span or 0.01
    return cells, rows, cols, cell_h, cell_w


# Izgara tavanları — batch çekim sayesinde ince ızgaralar ucuz, ama DOM/ağır
# yanıttan kaçınmak için mutlak sınırlar.
SCAN_MAX_ROWS = 64          # en fazla satır (enlem)
SCAN_MAX_CELLS = 4096        # en fazla toplam hücre
SCAN_BATCH = 100            # tek istekte birleştirilecek nokta sayısı


def _max_rows_for(lat_span: float, min_cell_deg: float | None) -> int:
    """Kaynağın doğal çözünürlüğüne (min_cell_deg) göre dürüst en yüksek satır
    sayısı. Hücre enlem boyu min_cell_deg'den ince olmaz → interpole örneklemeyi
    (gerçek olmayan veri) önler. DEM gibi ince kaynaklar SCAN_MAX_ROWS'a kadar
    çıkar; kaba modeller küçük alanlarda az hücreyle sınırlanır."""
    if not min_cell_deg or min_cell_deg <= 0:
        return SCAN_MAX_ROWS
    if lat_span <= 0:
        return 2
    natural = int(lat_span / min_cell_deg) + 1
    return max(2, min(SCAN_MAX_ROWS, natural))


def _fetch_cells(src, variable, points):
    """Izgara noktalarını kaynağın backend'ine göre çeker. points:
    [(lat, lon), ...] → aynı sıralı değer listesi (hata durumunda None).

    Backend'ler:
      openmeteo     — Open-Meteo (forecast/air_quality/elevation), virgülle
                      çoklu koordinat, paralel batch.
      opentopodata  — OpenTopoData SRTM, boruyla ayrılmış locations, SIRALI
                      (kamu limiti 1 istek/sn).
    RainViewer (mode radar) sayısal tarama vermez; burada işlenmez."""
    backend = (src or {}).get("backend", "openmeteo")
    if backend == "opentopodata":
        return _fetch_opentopodata(src.get("dataset"), points)
    if backend == "weatherapi":
        return _fetch_weatherapi(src.get("section"), variable, points)
    if backend == "eris":
        return _fetch_eris(variable, points)
    if backend == "wttrin":
        return _fetch_wttrin(variable, points)
    if backend == "nasa_power":
        return _fetch_nasa_power(variable, points)
    return _fetch_openmeteo(src.get("section"), src.get("model"), variable, points)


def _fetch_opentopodata(dataset, points):
    """OpenTopoData kamu API'si — 100 nokta/istek, 1 istek/sn → batch'ler
    sıralı çekilir. locations=lat,lon|lat,lon|... Yanıt results[].elevation
    giriş sırasıyla hizalı."""
    import time
    if not dataset:
        return [None] * len(points)
    out: List[Optional[float]] = [None] * len(points)
    batches = [list(range(i, min(i + 100, len(points))))
               for i in range(0, len(points), 100)]
    url = f"https://api.opentopodata.org/v1/{dataset}"
    last = 0.0
    for idx in batches:
        # 1 istek/sn kamu sınırına uy: önceki çağrıdan bu yana >= 1.1 sn geçsin.
        wait = 1.1 - (time.monotonic() - last)
        if wait > 0 and last:
            time.sleep(wait)
        last = time.monotonic()
        locs = "|".join(f"{round(points[j][0], 4)},{round(points[j][1], 4)}" for j in idx)
        try:
            r = requests.get(url, params={"locations": locs, "interpolation": "cubic"},
                             timeout=30)
            r.raise_for_status()
            results = (r.json() or {}).get("results") or []
            for k, j in enumerate(idx):
                if k < len(results) and results[k] is not None:
                    out[j] = results[k].get("elevation")
        except Exception:
            pass  # bu batch None
    return out


def _fetch_openmeteo(section, model, variable, points):
    """Open-Meteo virgülle çoklu koordinat — forecast/air_quality → dizi,
    elevation → tek nesne + elevation dizisi. Paralel batch (8 iş parçacığı)."""
    out: List[Optional[float]] = [None] * len(points)

    def handle(idx_slice, data):
        if section == "elevation":
            vals = data.get("elevation") if isinstance(data, dict) else None
            if vals:
                for k, j in enumerate(idx_slice):
                    if k < len(vals):
                        out[j] = vals[k]
            return
        if isinstance(data, list):
            for k, j in enumerate(idx_slice):
                if k < len(data):
                    cur = data[k].get("current", {}) if isinstance(data[k], dict) else {}
                    out[j] = cur.get(variable)
        elif isinstance(data, dict):
            j = idx_slice[0]
            out[j] = data.get("current", {}).get(variable)

    def fetch_batch(batch_idx):
        pts = [points[j] for j in batch_idx]
        lats = ",".join(str(round(la, 4)) for la, _ in pts)
        lons = ",".join(str(round(lo, 4)) for _, lo in pts)
        params = {"latitude": lats, "longitude": lons}
        if section == "elevation":
            kind = "elevation"
        else:
            kind = section
            params["current"] = variable
            params["timezone"] = "auto"
            if model:
                params["models"] = model
        try:
            data = _meteo.fetch_raw(kind, params)
            handle(batch_idx, data)
        except Exception:
            pass  # bu batch'in hücreleri None kalır

    batches = [list(range(i, min(i + SCAN_BATCH, len(points))))
               for i in range(0, len(points), SCAN_BATCH)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(fetch_batch, batches))
    return out


def _fetch_cell(src, variable, lat, lon):
    """Tek nokta yardımcı (karşılaştırma modu gibi tekil kullanımlar için)."""
    vals = _fetch_cells(src, variable, [(lat, lon)])
    return vals[0] if vals else None


# ---------------------------------------------------------------------------
# Yeni anahtarsız public API backend'leri (web aramasıyla bulundu)
# ---------------------------------------------------------------------------

def _fetch_weatherapi(section, variable, points):
    """weather-api.site — forecast (/weather) veya air-quality (/air-quality).
    Basit lat/lon JSON; bilinmeyen rate limit → 4 paralel işçi ile ılımlı."""
    out: List[Optional[float]] = [None] * len(points)
    endpoint = "air-quality" if section == "air_quality" else "weather"
    field_map = {
        "forecast": {
            "temperature_2m": "temperature",
            "apparent_temperature": "feels_like",
            "relative_humidity_2m": "humidity",
            "precipitation": "precipitation",
            "wind_speed_10m": "wind_speed",
            "pressure_msl": "pressure",
            "cloud_cover": "cloud_cover",
            "uv_index": "uv_index",
        },
        "air_quality": {
            "pm2_5": "pm2_5",
            "pm10": "pm10",
            "nitrogen_dioxide": "nitrogen_dioxide",
            "ozone": "ozone",
            "sulphur_dioxide": "sulphur_dioxide",
            "carbon_monoxide": "carbon_monoxide",
            "us_aqi": "us_aqi",
        },
    }.get(section, {})
    field = field_map.get(variable)
    if not field:
        return out

    def fetch_one(i):
        lat, lon = points[i]
        try:
            r = requests.get(
                f"https://weather-api.site/{endpoint}",
                params={"lat": round(lat, 4), "lon": round(lon, 4)},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json() or {}
            val = data.get("current", {}).get(field)
            if val is not None:
                out[i] = float(val)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(fetch_one, range(len(points))))
    return out


def _fetch_eris(variable, points):
    """Eris — anlık hava; OpenWeatherMap proxy."""
    out: List[Optional[float]] = [None] * len(points)
    field_map = {
        "temperature_2m": ("main", "temp"),
        "relative_humidity_2m": ("main", "humidity"),
        "pressure_msl": ("main", "pressure"),
        "wind_speed_10m": ("wind", "speed"),
    }
    mapping = field_map.get(variable)
    if not mapping:
        return out
    sec, key = mapping

    def fetch_one(i):
        lat, lon = points[i]
        try:
            r = requests.get(
                "https://weather-api.madadipouya.com/v1/weather/current",
                params={"lat": round(lat, 4), "lon": round(lon, 4)},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json() or {}
            val = data.get(sec, {}).get(key)
            if val is not None:
                out[i] = float(val)
                # Eris/OpenWeatherMap rüzgârı m/s döner; bizim etiket km/s (aslında
                # km/h) için çarp. Düzeltme: etiket birimi ileride km/h olmalı.
                if variable == "wind_speed_10m":
                    out[i] = out[i] * 3.6
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(fetch_one, range(len(points))))
    return out


def _fetch_wttrin(variable, points):
    """wttr.in — JSON modu (?format=j1). Değerler genelde string; güvenli parse."""
    out: List[Optional[float]] = [None] * len(points)
    field_map = {
        "temperature_2m": "temp_C",
        "relative_humidity_2m": "humidity",
        "pressure_msl": "pressure",
        "wind_speed_10m": "windspeedKmph",
        "uv_index": "uvIndex",
    }
    field = field_map.get(variable)
    if not field:
        return out

    def _float(x):
        try:
            return float(x) if x not in (None, "", "-") else None
        except Exception:
            return None

    def fetch_one(i):
        lat, lon = points[i]
        try:
            r = requests.get(
                f"https://wttr.in/{round(lat, 4)},{round(lon, 4)}",
                params={"format": "j1"},
                timeout=15,
                headers={"User-Agent": "meteo/0.1.0 (github.com/niyoseris/meteo)"},
            )
            r.raise_for_status()
            data = r.json() or {}
            cc = data.get("current_condition") or [{}]
            val = cc[0].get(field)
            out[i] = _float(val)
        except Exception:
            pass

    # wttr.in daha duyarlı; 2 işçi ile yavaş git.
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(fetch_one, range(len(points))))
    return out


def _fetch_nasa_power(variable, points):
    """NASA POWER — günlük reanalysis. Son mevcut günü döndürür (genelde 1–30 gün
    geride). Her nokta için ayrı istek; 4 paralel işçi."""
    out: List[Optional[float]] = [None] * len(points)
    param_map = {
        "daily_mean_temperature_2m": "T2M",
        "daily_max_temperature_2m": "T2M_MAX",
        "daily_precipitation": "PRECTOT",
        "surface_shortwave_radiation": "ALLSKY_SFC_SW_DWN",
        "soil_moisture_surface": "GWETTOP",
    }
    param = param_map.get(variable)
    if not param:
        return out

    from datetime import datetime, timedelta, timezone
    # Reanalysis gecikmeli yayınlanır; son 30 günde geriye doğru ilk dolu değeri al.
    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=30)

    def fetch_one(i):
        lat, lon = points[i]
        try:
            r = requests.get(
                "https://power.larc.nasa.gov/api/temporal/daily/point",
                params={
                    "parameters": param,
                    "community": "RE",
                    "longitude": round(lon, 4),
                    "latitude": round(lat, 4),
                    "start": start.strftime("%Y%m%d"),
                    "end": end.strftime("%Y%m%d"),
                    "format": "JSON",
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json() or {}
            param_block = data.get("properties", {}).get("parameter", {})
            # API bazen istenen anahtarı takma adla döner (örn. PRECTOT → PRECTOTCORR).
            series = param_block.get(param) or param_block.get(param + "CORR")
            if not series:
                return
            # Son mevcut tarihi (null/-999 değil) al.
            for date_key in sorted(series.keys(), reverse=True):
                val = series[date_key]
                if val is not None and val != -999.0:
                    out[i] = float(val)
                    return
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(fetch_one, range(len(points))))
    return out


# ---------------------------------------------------------------------------
# Karşılaştırma yardımcıları
# ---------------------------------------------------------------------------
# Her nokta için çekilecek metrikler: (anahtar, etiket, birim, tür, aq_anahtarı)
# aq_anahtarı verilirse değer air_quality_ref ile derecelendirilir (renk için).
COMPARE_METRICS: List[dict] = [
    {"key": "weather_code", "label": "Durum", "unit": "", "kind": "text"},
    {"key": "temperature_2m", "label": "Sıcaklık", "unit": "°C", "kind": "num"},
    {"key": "apparent_temperature", "label": "Hissedilen", "unit": "°C", "kind": "num"},
    {"key": "relative_humidity_2m", "label": "Nem", "unit": "%", "kind": "num"},
    {"key": "precipitation", "label": "Yağış", "unit": "mm", "kind": "num"},
    {"key": "wind_speed_10m", "label": "Rüzgâr", "unit": "km/s", "kind": "num"},
    {"key": "wind_direction_10m", "label": "Rüzgâr yönü", "unit": "°", "kind": "num"},
    {"key": "pressure_msl", "label": "Basınç", "unit": "hPa", "kind": "num"},
    {"key": "cloud_cover", "label": "Bulut", "unit": "%", "kind": "num"},
    {"key": "pm2_5", "label": "PM2.5", "unit": "µg/m³", "kind": "num", "aq": "pm2_5"},
    {"key": "pm10", "label": "PM10", "unit": "µg/m³", "kind": "num", "aq": "pm10"},
    {"key": "ozone", "label": "Ozon", "unit": "µg/m³", "kind": "num", "aq": "ozone"},
    {"key": "nitrogen_dioxide", "label": "NO₂", "unit": "µg/m³", "kind": "num", "aq": "nitrogen_dioxide"},
    {"key": "sulphur_dioxide", "label": "SO₂", "unit": "µg/m³", "kind": "num", "aq": "sulphur_dioxide"},
    {"key": "carbon_monoxide", "label": "CO", "unit": "µg/m³", "kind": "num", "aq": "carbon_monoxide"},
    {"key": "us_aqi", "label": "ABD AQI", "unit": "", "kind": "num", "aq": "us_aqi"},
    {"key": "european_aqi", "label": "AB AQI", "unit": "", "kind": "num", "aq": "european_aqi"},
    {"key": "elevation", "label": "Rakım", "unit": "m", "kind": "num"},
]


def _point_metrics(lat: float, lon: float) -> dict:
    """Bir nokta için anlık hava + hava kalitesi + rakım topla (tek sözlük)."""
    out: Dict[str, Any] = {}
    # --- hava durumu (anlık) ---
    try:
        fc = _meteo.fetch_raw("forecast", {
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "current": CURRENT_VARS, "timezone": "auto",
        })
        c = fc.get("current", {})
        wc = c.get("weather_code")
        out["weather_code"] = (
            f"{codes.emoji(wc)} {codes.label(wc)}" if wc is not None else None
        )
        for k in ("temperature_2m", "apparent_temperature", "relative_humidity_2m",
                  "precipitation", "wind_speed_10m", "wind_direction_10m",
                  "pressure_msl", "cloud_cover"):
            out[k] = c.get(k)
    except OpenMeteoError:
        pass

    # --- hava kalitesi (anlık) ---
    try:
        aq = _meteo.fetch_raw("air_quality", {
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "current": AIR_QUALITY_VARS, "timezone": "auto",
        })
        qc = aq.get("current", {})
        for k in ("pm2_5", "pm10", "ozone", "nitrogen_dioxide", "sulphur_dioxide",
                  "carbon_monoxide", "us_aqi", "european_aqi"):
            out[k] = qc.get(k)
    except OpenMeteoError:
        pass

    # --- rakım ---
    try:
        el = _meteo.fetch_raw("elevation", {
            "latitude": round(lat, 4), "longitude": round(lon, 4),
        })
        ev = el.get("elevation")
        out["elevation"] = ev[0] if isinstance(ev, list) and ev else None
    except OpenMeteoError:
        pass
    return out


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
@app.route("/api/places")
def api_places():
    name = request.args.get("name", "").strip()
    if not name:
        return _api_error("name parametresi gerekli")
    try:
        results = _meteo.geocode_search(
            name,
            language=request.args.get("language", "tr"),
            count=request.args.get("count", default=10, type=int),
            country_codes=request.args.get("country"),
        )
    except OpenMeteoError as exc:
        return _api_error(str(exc), 502)
    return jsonify(
        [
            {
                "name": r.name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "country": r.country,
                "country_code": r.country_code,
                "admin1": r.admin1,
                "population": r.population,
                "elevation": r.elevation,
                "timezone": r.timezone,
            }
            for r in results
        ]
    )


@app.route("/api/geocode")
def api_geocode():
    name = request.args.get("name", "").strip()
    if not name:
        return _api_error("name parametresi gerekli")
    try:
        r = _meteo.geocode(
            name,
            language=request.args.get("language", "tr"),
            country_codes=request.args.get("country"),
        )
    except OpenMeteoError as exc:
        return _api_error(str(exc), 404)
    return jsonify(
        {
            "name": r.name,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "country": r.country,
            "country_code": r.country_code,
            "admin1": r.admin1,
            "population": r.population,
            "elevation": r.elevation,
            "timezone": r.timezone,
        }
    )


@app.route("/api/weather")
def api_weather():
    loc, err = _resolve_place_or_coords()
    if err or loc is None:
        return _api_error(err or "Konum çözülemedi")

    days = request.args.get("days", default=7, type=int)
    past = request.args.get("past_days", default=0, type=int)
    sections = _sections()

    try:
        if sections == ["all"]:
            data = _meteo.all(
                loc,
                forecast_days=days,
                past_days=past,
                air_quality_days=days,
                marine_days=days,
                flood_days=30,
            )
        else:
            data = {"_location": _loc_dict(loc)}
            for s in sections:
                if s == "forecast":
                    data["forecast"] = _meteo.forecast(
                        loc, current=True, hourly=True, daily=True,
                        forecast_days=days, past_days=past,
                    )
                elif s == "air_quality":
                    data["air_quality"] = _meteo.air_quality(
                        loc, current=True, hourly=True, forecast_days=days, past_days=past,
                    )
                elif s == "marine":
                    data["marine"] = _meteo.marine(
                        loc, hourly=True, forecast_days=days, past_days=past,
                    )
                elif s == "flood":
                    data["flood"] = _meteo.flood(loc, daily=True, forecast_days=30)
                elif s == "elevation":
                    data["elevation"] = _meteo.elevation(loc)
                else:
                    return _api_error(f"Bilinmeyen bölüm: {s}")
    except OpenMeteoError as exc:
        return _api_error(str(exc), 502)

    return jsonify(data)


@app.route("/api/historical")
def api_historical():
    loc, err = _resolve_place_or_coords()
    if err or loc is None:
        return _api_error(err or "Konum çözülemedi")

    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return _api_error("start ve end (YYYY-MM-DD) gerekli")

    hourly = request.args.get("hourly", "false").lower() in ("1", "true", "yes", "on")
    try:
        data = _meteo.historical(
            loc, start_date=start, end_date=end, daily=True, hourly=hourly,
        )
    except OpenMeteoError as exc:
        return _api_error(str(exc), 502)
    return jsonify(data)


@app.route("/api/compare", methods=["POST"])
def api_compare():
    """Birden fazla noktanın anlık verilerini yan yana karşılaştırır.

    Gövde (JSON): {"points": [{"name","lat","lon"}, ...], "days": 1}
    Dönüş: {"points":[...], "rows":[{"label","unit","kind","values":[...],
    "ratings":[...|""]}, ...]}
    """
    body = request.get_json(silent=True) or {}
    points = body.get("points")
    if not points or not isinstance(points, list):
        return _api_error("points listesi (en az 2 nokta) gerekli")
    if len(points) < 2:
        return _api_error("Karşılaştırma için en az 2 nokta gerekli")
    if len(points) > 8:
        return _api_error("En fazla 8 nokta karşılaştırılabilir")

    point_meta = []
    metrics_per_point: List[dict] = []
    for p in points:
        try:
            lat = float(p.get("lat"))
            lon = float(p.get("lon"))
        except (TypeError, ValueError):
            return _api_error("Her nokta için lat ve lon gerekli", 400)
        name = (p.get("name") or "").strip() or f"({lat:.3f}, {lon:.3f})"
        point_meta.append({"name": name, "lat": round(lat, 4), "lon": round(lon, 4)})
        metrics_per_point.append(_point_metrics(lat, lon))

    rows: List[dict] = []
    for spec in COMPARE_METRICS:
        values = [m.get(spec["key"]) for m in metrics_per_point]
        info = metrics_ref.info(spec["key"])
        row = {
            "key": spec["key"], "label": spec["label"],
            "unit": spec["unit"], "kind": spec["kind"], "values": values,
            "what": info["what"], "ref": info["ref"],
        }
        if spec.get("aq"):
            row["ratings"] = [
                (air_quality_ref.rate(spec["aq"], v)[1] if v is not None else None)
                for v in values
            ]
        rows.append(row)

    return jsonify({"points": point_meta, "rows": rows})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Bir alanı ızgara noktalarıyla tarar, her hücrenin değerini döndürür.

    Gövde (JSON): {"bbox":{...}, "source":"aq_cams_europe",
                   "variable":"sulphur_dioxide", "grid":10}

    Kaynak seçimi modeli belirler (forecast icon_eu, cams_europe vb.).
    Izgara üst sınırı kaynağın doğal çözünürlüğüne göre dürüstleştirilir:
    hücre, kaynağın min_cell_deg'inden ince olmaz (interpole örneklemeyi önler).
    DEM gibi ince kaynaklar SCAN_MAX_ROWS'a kadar çıkar.

    Dönüş: {variable,label,unit,section,source,bbox,rows,cols,min,max,
            cell_h,cell_w,max_grid,cells:[{lat,lon,value}, ...]}
    """
    body = request.get_json(silent=True) or {}
    bbox = body.get("bbox")
    variable = body.get("variable")
    source_id = body.get("source")
    if not bbox or not variable or not source_id:
        return _api_error("bbox, source ve variable gerekli")

    src = datasources.get(source_id)
    if not src:
        return _api_error(f"Bilinmeyen kaynak: {source_id}")
    if src["status"] != "integrated":
        return _api_error(f"Bu kaynak tarama için kullanılamaz: {src['label']}")
    if src.get("mode") == "radar":
        return _api_error(f"{src['label']} sayısal tarama vermez (radar görsel katmanı) — "
                          "doğrudan harita üstünde gösterilir.")

    if variable not in datasources.variables_for(source_id):
        return _api_error(f"{src['label']} bu değişkeni ölçmüyor: {variable}")

    spec = next((s for s in SCAN_VARIABLES if s["key"] == variable), None)
    if not spec:  # teorik olarak yukarıdaki kontrol kapsar
        return _api_error(f"Bilinmeyen değişken: {variable}")

    try:
        north = float(bbox.get("north")); south = float(bbox.get("south"))
        east = float(bbox.get("east")); west = float(bbox.get("west"))
    except (TypeError, ValueError):
        return _api_error("bbox {north,south,east,west} sayısal olmalı")

    # Dinamik dürüst üst sınır: hücre kaynağın çözünürlüğünden ince olmasın.
    max_grid = _max_rows_for(north - south, src.get("min_cell_deg"))
    grid = body.get("grid", 10)
    try:
        rows_req = int(grid)
    except (TypeError, ValueError):
        rows_req = 10
    rows_req = max(2, min(max_grid, rows_req))

    try:
        cells, rows, cols, cell_h, cell_w = _scan_grid(north, south, east, west, rows_req)
    except ValueError as exc:
        return _api_error(str(exc), 400)

    # Batch çekim — kaynağın backend'ine (Open-Meteo / OpenTopoData) göre.
    values = _fetch_cells(src, variable, cells)

    valid = [v for v in values if v is not None]
    vmin = min(valid) if valid else 0.0
    vmax = max(valid) if valid else 1.0
    if vmax == vmin:
        vmax = vmin + 1e-9  # bölme sıfıra düşmesin

    return jsonify({
        "variable": variable, "label": spec["label"], "unit": spec["unit"],
        "section": src["section"],
        "source": src,
        "bbox": {"north": north, "south": south, "east": east, "west": west},
        "rows": rows, "cols": cols, "min": vmin, "max": vmax,
        "cell_h": cell_h, "cell_w": cell_w, "max_grid": max_grid,
        "cells": [{"lat": cells[i][0], "lon": cells[i][1], "value": values[i]}
                  for i in range(len(cells))],
    })


@app.route("/api/rainviewer")
def api_rainviewer():
    """RainViewer kamu radar API'si (anahtarsız) — weather-maps.json'u sunucuda
    çekip tile URL şablonu + geçmiş/nowcast frame'lerini döndürür. CORS/endpoint
    kararlılığı için istemciye değil sunucuya bırakıldı.

    Dönüş: {host, tile_url, frames:[{time,path,nowcast?}], coverage_url?}
    Tile şablonu: {host}{path}/{size}/{z}/{x}/{y}/{color}/{options}.png
    """
    try:
        r = requests.get("https://api.rainviewer.com/public/weather-maps.json",
                         timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as exc:
        return _api_error(f"RainViewer verisi alınamadı: {exc}")
    host = d.get("host", "https://tilecache.rainviewer.com")
    radar = d.get("radar") or {}
    past = radar.get("past") or []
    nowcast = radar.get("nowcast") or []
    frames = [{"time": f.get("time"), "path": f.get("path"), "nowcast": False}
              for f in past] + \
             [{"time": f.get("time"), "path": f.get("path"), "nowcast": True}
              for f in nowcast]
    coverage = radar.get("coverage")
    return jsonify({
        "host": host,
        "frames": frames,
        "coverage_url": f"{host}{coverage}/256/{{z}}/{{x}}/{{y}}/0/0_0.png" if coverage else None,
        "attribution": "RainViewer",
    })


@app.route("/api/analyze")
def api_analyze():
    """Bir nokta için hava kalitesi yorumu (arka plan vs yerel sinyal).

    Merkezin anlık değerlerini alır, ~model çözünürlüğü kadar uzaktaki
    4 komşu noktayla karşılaştırır (uzaysal gradyan testi) ve her
    kirletici için "bölgesel arka plan mı / yerel sinyal mi" kararı +
    Türkçe özet döndürür.
    """
    loc, err = _resolve_place_or_coords()
    if err or loc is None:
        return _api_error(err or "Konum çözülemedi")
    offset = request.args.get("offset", default=0.3, type=float)
    try:
        result = interpret.interpret_aq(_meteo, loc, offset_deg=offset)
    except OpenMeteoError as exc:
        return _api_error(str(exc), 502)
    return jsonify(result)


@app.route("/api/air_quality_ref")
def api_aq_ref():
    """Kirleticilerin açıklaması, birimi, referans değerleri ve bantları (JSON)."""
    out = []
    for key in air_quality_ref.ORDER:
        e = air_quality_ref.POLLUTANTS[key]
        out.append({
            "key": key,
            "label": e["label"],
            "unit": e["unit"],
            "what": e["what"],
            "ref": e["ref"],
            "bands": [
                {"limit": lim, "rating": label, "rating_class": cls}
                for lim, label, cls in e["bands"]
            ],
        })
    return jsonify(out)


@app.route("/api/reverse")
def api_reverse():
    """Koordinat → tıklanan NOKTANIN bilgisi (OSM Nominatim).

    Yüksek zoom (18 = bina/sokak seviyesi) ile en spesifik sonucu alır;
    `name` olarak en yerel (sokak/mahalle) adı seçilir, üst bağlam
    `display_name`/`context` içinde ayrıca verilir.
    """
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return _api_error("lat ve lon gerekli")
    zoom = request.args.get("zoom", default=18, type=int)
    try:
        resp = _NOMINATIM.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": zoom,
                    "accept-language": request.args.get("language", "tr")},
            timeout=15,
        )
        if resp.status_code >= 400:
            return _api_error(f"Nominatim HTTP {resp.status_code}", 502)
        data = resp.json()
    except requests.RequestException as exc:
        return _api_error(f"Nominatim isteği başarısız: {exc}", 502)
    except ValueError as exc:
        return _api_error(f"Nominatim JSON çözülemedi: {exc}", 502)

    addr = data.get("address", {}) or {}
    # En spesifikten en genele — tıklanan noktanın kendisini seç.
    name = (
        addr.get("road")
        or addr.get("pedestrian")
        or addr.get("neighbourhood")
        or addr.get("suburb")
        or addr.get("quarter")
        or addr.get("city_district")
        or addr.get("hamlet")
        or addr.get("village")
        or addr.get("town")
        or addr.get("city")
        or addr.get("municipality")
        or data.get("name")
        or f"({lat}, {lon})"
    )
    # Üst bağlam (mahalle/bucağın bağlı olduğu yer) — ayrı alanda.
    context_parts = [
        p for p in (
            addr.get("suburb") or addr.get("city_district"),
            addr.get("city") or addr.get("town") or addr.get("village"),
            addr.get("state"),
            addr.get("country"),
        ) if p
    ]
    context = ", ".join(context_parts)
    return jsonify({
        "name": name,
        "display_name": data.get("display_name", ""),
        "context": context,
        "country": addr.get("country", ""),
        "country_code": (addr.get("country_code") or "").upper(),
        "state": addr.get("state", ""),
        "county": addr.get("county", ""),
        "category": data.get("category", ""),
        "type": data.get("type", ""),
        "latitude": float(data.get("lat", lat)),
        "longitude": float(data.get("lon", lon)),
        "raw": addr,
    })


@app.route("/api/raw")
def api_raw():
    """Doğrudan alt API passthrough. ?kind=forecast&latitude=...&..."""
    kind = request.args.get("kind")
    if not kind:
        return _api_error("kind parametresi gerekli")
    # Tüm sorgu argümanlarını (kind hariç) parametre olarak topla.
    params = {k: v for k, v in request.args.items() if k != "kind"}
    # sayısal görünenleri dönüştürmeye çalışma — API dizge de kabul eder.
    try:
        data = _meteo.fetch_raw(kind, params)
    except OpenMeteoError as exc:
        return _api_error(str(exc), 502)
    return jsonify(data)


# ---------------------------------------------------------------------------
# Zenginleştirme: weather_code -> açıklama
# ---------------------------------------------------------------------------
def _enrich(data: dict) -> None:
    """`data` içindeki weather_code alanlarının yanına okunabilir açıklama
    ekler (HTML görünümü için)."""
    for section in ("forecast",):
        sec = data.get(section)
        if not isinstance(sec, dict) or "error" in sec:
            continue
        for grp in ("current", "daily", "hourly"):
            obj = sec.get(grp)
            if not isinstance(obj, dict):
                continue
            if grp == "current" and "weather_code" in obj:
                obj["weather_code_label"] = codes.label(obj["weather_code"])
                obj["weather_code_emoji"] = codes.emoji(obj["weather_code"])
            elif grp in ("daily", "hourly"):
                codes_list = obj.get("weather_code")
                if isinstance(codes_list, list):
                    obj["weather_code_labels"] = [codes.label(c) for c in codes_list]
                    obj["weather_code_emojis"] = [codes.emoji(c) for c in codes_list]


def _loc_dict(loc: Location) -> dict:
    return {
        "name": loc.name,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "country": loc.country,
        "timezone": loc.timezone,
    }


# ---------------------------------------------------------------------------
# Hata işleyiciler
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return _api_error("Bulunamadı", 404)
    return render_template("index.html"), 404


@app.errorhandler(APIError)
def handle_api_error(exc: APIError):
    if request.path.startswith("/api/"):
        return _api_error(str(exc), exc.status or 502)
    return render_template("weather.html", error=str(exc), location=None), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
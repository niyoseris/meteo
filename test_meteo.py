"""Canlı API'ye dokunmayan birim testler: URL/parametre üretimi, hata
yolları, geocoding ayrıştırması, CLI çözümleyici.

Çalıştır: pytest -q   (veya: python -m pytest -q)
"""

import json
from unittest.mock import MagicMock

import pytest

import meteo
from meteo.client import OpenMeteo, OpenMeteoError, APIError, Location, BASE_URLS
from meteo.types import GeocodingResult
from meteo import air_quality_ref, codes
from meteo import cli


# ---------------------------------------------------------------------------
# Parametre üretimi
# ---------------------------------------------------------------------------
def test_loc_params_from_location():
    p = OpenMeteo._loc_params(Location(41.01234, 28.95678, name="İstanbul"))
    assert p == {"latitude": 41.0123, "longitude": 28.9568}


def test_loc_params_from_tuple():
    p = OpenMeteo._loc_params((41.0, 28.9))
    assert p["latitude"] == 41.0 and p["longitude"] == 28.9


def test_base_urls_cover_all_apis():
    for k in [
        "forecast", "historical", "historical_forecast", "climate",
        "flood", "marine", "air_quality", "elevation", "geocoding",
    ]:
        assert k in BASE_URLS and BASE_URLS[k].startswith("https://")


# ---------------------------------------------------------------------------
# Geocoding ayrıştırması
# ---------------------------------------------------------------------------
def test_geocoding_result_to_location():
    g = GeocodingResult(
        name="Ankara", latitude=39.92, longitude=32.85, country="Türkiye",
        elevation=850.0,
    )
    loc = g.to_location()
    assert loc.latitude == 39.92 and loc.name == "Ankara" and loc.elevation == 850.0
    assert loc.timezone == "auto"


def test_parse_geocoding_raw():
    raw = {
        "name": "İzmir", "latitude": 38.42, "longitude": 27.14,
        "country": "Türkiye", "country_code": "TR", "admin1": "İzmir",
        "population": 3000000, "elevation": 30,
    }
    g = OpenMeteo._parse_geocoding(raw)  # type: ignore[attr-defined]
    assert g.name == "İzmir" and g.country_code == "TR" and g.population == 3000000


# ---------------------------------------------------------------------------
# forecast parametre üretimi (mock'lu _request)
# ---------------------------------------------------------------------------
def _make_client(captured):
    m = OpenMeteo(session=MagicMock())

    def fake_request(kind, params):
        captured.clear()
        captured["kind"] = kind
        captured.update(params)
        return {}

    m._request = fake_request
    return m


def test_forecast_true_means_all_variables():
    cap = {}
    m = _make_client(cap)
    m.forecast((41.0, 28.9), current=True, hourly=True, daily=True, forecast_days=3)
    assert cap["kind"] == "forecast"
    assert "temperature_2m" in cap["current"]
    assert "temperature_2m" in cap["hourly"]
    assert "temperature_2m_max" in cap["daily"]
    assert cap["forecast_days"] == 3
    assert cap["latitude"] == 41.0 and cap["longitude"] == 28.9


def test_forecast_custom_vars_string():
    cap = {}
    m = _make_client(cap)
    m.forecast((41.0, 28.9), hourly="temperature_2m,precipitation")
    assert cap["hourly"] == "temperature_2m,precipitation"
    assert "current" not in cap and "daily" not in cap


def test_fetch_raw_unknown_kind():
    m = OpenMeteo(session=MagicMock())
    with pytest.raises(OpenMeteoError):
        m.fetch_raw("nonsense", {})


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------
def test_to_json_dataclass():
    m = OpenMeteo(session=MagicMock())
    s = m.to_json(Location(41.0, 28.9, name="x"))
    data = json.loads(s)
    assert data["latitude"] == 41.0 and data["name"] == "x"


# ---------------------------------------------------------------------------
# CLI çözümleyici
# ---------------------------------------------------------------------------
def test_cli_resolve_by_place(monkeypatch):
    m = OpenMeteo(session=MagicMock())
    m._request = lambda kind, params: {"results": [
        {"name": "İstanbul", "latitude": 41.0, "longitude": 28.9, "country": "TR"}
    ]}
    ns = cli.build_parser().parse_args(["İstanbul", "--current", "--daily"])
    loc = cli._resolve_location(ns, m)
    assert isinstance(loc, Location) and loc.latitude == 41.0


def test_cli_resolve_by_coords():
    ns = cli.build_parser().parse_args(["--lat", "41.01", "--lon", "28.95"])
    m = OpenMeteo(session=MagicMock())
    loc = cli._resolve_location(ns, m)
    assert loc.latitude == 41.01 and loc.longitude == 28.95
    assert not ns.place  # place opsiyonel


def test_cli_requires_location():
    ns = cli.build_parser().parse_args(["--current"])
    m = OpenMeteo(session=MagicMock())
    with pytest.raises(SystemExit):
        cli._resolve_location(ns, m)

# ---------------------------------------------------------------------------
# Hava kalitesi referansı
# ---------------------------------------------------------------------------
def test_rate_bands():
    assert air_quality_ref.rate("pm2_5", 10) == ("İyi", "good")
    assert air_quality_ref.rate("pm2_5", 20) == ("Orta", "moderate")
    assert air_quality_ref.rate("pm2_5", 60) == ("Çok kötü", "verypoor")
    assert air_quality_ref.rate("pm2_5", None) is None
    assert air_quality_ref.rate("bilinmeyen", 5) is None


def test_uv_index_bands():
    assert air_quality_ref.rate("uv_index", 1)[0] == "Düşük"
    assert air_quality_ref.rate("uv_index", 4)[0] == "Orta"
    assert air_quality_ref.rate("uv_index", 12)[0] == "Aşırı"


def test_build_table_orders_and_skips_missing():
    current = {"pm2_5": 6.7, "pm10": 20.0, "us_aqi": 34, "nope": 99}
    rows = air_quality_ref.build_table(current)
    keys = [r["key"] for r in rows]
    # genel indeksler önce gelmeli
    assert keys[0] == "us_aqi"
    assert "nope" not in keys
    pm25 = next(r for r in rows if r["key"] == "pm2_5")
    assert pm25["rating"] == "İyi" and pm25["rating_class"] == "good"
    assert pm25["what"] and pm25["ref"]


def test_metric_info_handles_none():
    info = air_quality_ref.metric_info("ozone", None)
    assert info["ok"] is False and info["rating"] is None


# ---------------------------------------------------------------------------
# Yorumlama motoru
# ---------------------------------------------------------------------------
def _stub_aq_client(center_vals, neighbor_vals):
    """center_vals/neighbor_vals: {var: value}. Komşu değerleri 4 noktaya yayar."""
    from meteo.client import OpenMeteo
    from unittest.mock import MagicMock
    m = OpenMeteo(session=MagicMock())
    seq = [center_vals] + [neighbor_vals] * 4
    def fake(kind, params):
        fake.calls = getattr(fake, "calls", 0)
        v = seq[fake.calls] if fake.calls < len(seq) else seq[-1]
        fake.calls += 1
        return {"current": dict(v)}
    m.fetch_raw = fake
    return m


def test_probe_uniform_when_identical():
    m = _stub_aq_client(
        {"carbon_monoxide": 106.0, "nitrogen_dioxide": 1.0},
        {"carbon_monoxide": 106.0, "nitrogen_dioxide": 1.0},
    )
    from meteo import interpret
    p = interpret.spatial_probe(m, (35.0, 34.0), ["carbon_monoxide", "nitrogen_dioxide"])
    assert p["carbon_monoxide"]["verdict"] == "uniform"
    assert p["carbon_monoxide"]["cv"] < 0.06


def test_probe_local_high_when_center_outlier():
    m = _stub_aq_client(
        {"nitrogen_dioxide": 60.0, "carbon_monoxide": 106.0},
        {"nitrogen_dioxide": 1.0, "carbon_monoxide": 106.0},
    )
    from meteo import interpret
    p = interpret.spatial_probe(m, (41.0, 28.9), ["nitrogen_dioxide", "carbon_monoxide"])
    assert p["nitrogen_dioxide"]["verdict"] == "local_high"
    assert p["carbon_monoxide"]["verdict"] == "uniform"


def test_interpret_summary_mentions_background():
    m = _stub_aq_client(
        {"carbon_monoxide": 106.0, "nitrogen_dioxide": 1.0, "pm2_5": 8.0},
        {"carbon_monoxide": 106.0, "nitrogen_dioxide": 1.0, "pm2_5": 8.0},
    )
    from meteo import interpret
    r = interpret.interpret_aq(m, (35.69, 34.57))
    assert "arka plan" in r["summary"]
    co = next(x for x in r["rows"] if x["key"] == "carbon_monoxide")
    assert co["verdict"] == "uniform" and co["in_background"] is True
    assert r["source"]["provider"]  # kaynak meta-verisi dolu


def test_source_note_known():
    from meteo import interpret
    assert interpret.source_note("air_quality")["resolution"]
    assert interpret.source_note("nope") is None


# ---------------------------------------------------------------------------
# Karşılaştırma modu
# ---------------------------------------------------------------------------
def test_compare_requires_two_points():
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/compare", json={"points": [{"lat": 41.0, "lon": 28.9}]})
    assert r.status_code == 400
    assert "en az 2" in r.get_json()["error"]


def test_compare_builds_rows(monkeypatch):
    import app as appmod

    calls = {"n": 0}
    def fake_fetch(kind, params):
        calls["n"] += 1
        if kind == "forecast":
            return {"current": {"weather_code": 1, "temperature_2m": 24.0,
                "apparent_temperature": 23.0, "relative_humidity_2m": 50,
                "precipitation": 0.0, "wind_speed_10m": 10, "wind_direction_10m": 180,
                "pressure_msl": 1010, "cloud_cover": 30}}
        if kind == "air_quality":
            return {"current": {"pm2_5": 6.0, "pm10": 20.0, "ozone": 90.0,
                "nitrogen_dioxide": 1.0, "sulphur_dioxide": 0.5,
                "carbon_monoxide": 100.0, "us_aqi": 30, "european_aqi": 20}}
        if kind == "elevation":
            return {"elevation": [50.0]}
        return {}
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)

    c = appmod.app.test_client()
    r = c.post("/api/compare", json={"points": [
        {"name": "A", "lat": 41.0, "lon": 28.9},
        {"name": "B", "lat": 35.7, "lon": 34.6},
    ]})
    assert r.status_code == 200
    data = r.get_json()
    assert [p["name"] for p in data["points"]] == ["A", "B"]
    keys = [row["key"] for row in data["rows"]]
    assert "temperature_2m" in keys and "pm2_5" in keys and "elevation" in keys
    temp = next(row for row in data["rows"] if row["key"] == "temperature_2m")
    assert temp["values"] == [24.0, 24.0]
    pm = next(row for row in data["rows"] if row["key"] == "pm2_5")
    assert pm["ratings"] == ["good", "good"]


def test_point_metrics_missing_section_tolerant(monkeypatch):
    import app as appmod
    def fake_fetch(kind, params):
        if kind == "forecast":
            raise appmod.OpenMeteoError("boom")  # hava başarısız
        if kind == "air_quality":
            return {"current": {"pm2_5": 7.0, "us_aqi": 40}}
        if kind == "elevation":
            return {"elevation": [12.0]}
        return {}
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    m = appmod._point_metrics(41.0, 28.9)
    assert m.get("temperature_2m") is None      # forecast patladı -> None
    assert m["pm2_5"] == 7.0 and m["elevation"] == 12.0


# ---------------------------------------------------------------------------
# Metrik açıklama sözlüğü
# ---------------------------------------------------------------------------
def test_metrics_ref_weather():
    from meteo import metrics_ref
    i = metrics_ref.info("temperature_2m")
    assert i["what"] and "metre" in i["what"]   # ASCII çapa; Türkçe 'ı' kırılganlığından kaçınır


def test_metrics_ref_aq_falls_back_to_aq_ref():
    from meteo import metrics_ref
    i = metrics_ref.info("pm2_5")
    assert "WHO" in i["ref"] and i["what"]


def test_metrics_ref_unknown():
    from meteo import metrics_ref
    i = metrics_ref.info("bilinmeyen")
    assert i == {"what": "", "ref": ""}


def test_compare_rows_include_what_ref(monkeypatch):
    import app as appmod
    def fake_fetch(kind, params):
        if kind == "forecast":
            return {"current": {"weather_code": 1, "temperature_2m": 20.0,
                "apparent_temperature": 19.0, "relative_humidity_2m": 50,
                "precipitation": 0.0, "wind_speed_10m": 5, "wind_direction_10m": 90,
                "pressure_msl": 1013, "cloud_cover": 10}}
        if kind == "air_quality":
            return {"current": {"pm2_5": 5.0, "pm10": 10.0, "ozone": 80.0,
                "nitrogen_dioxide": 1.0, "sulphur_dioxide": 0.5,
                "carbon_monoxide": 100.0, "us_aqi": 30, "european_aqi": 20}}
        if kind == "elevation":
            return {"elevation": [100.0]}
        return {}
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    c = appmod.app.test_client()
    r = c.post("/api/compare", json={"points": [
        {"name": "A", "lat": 1, "lon": 2}, {"name": "B", "lat": 3, "lon": 4}]})
    data = r.get_json()
    temp = next(row for row in data["rows"] if row["key"] == "temperature_2m")
    assert temp["what"] and "metre" in temp["what"]
    pm = next(row for row in data["rows"] if row["key"] == "pm2_5")
    assert "WHO" in pm["ref"]


# ---------------------------------------------------------------------------
# Alan tarama (scan)
# ---------------------------------------------------------------------------
def test_scan_grid_shape():
    import app as appmod
    cells, rows, cols, ch, cw = appmod._scan_grid(40.0, 38.0, 30.0, 28.0, 8)
    assert rows == 8
    assert cols >= 1
    assert len(cells) == rows * cols
    assert ch > 0 and cw > 0


def test_scan_grid_invalid_raises():
    import app as appmod
    import pytest
    with pytest.raises(ValueError):
        appmod._scan_grid(38.0, 40.0, 30.0, 28.0, 8)  # north<south


def test_scan_requires_source():
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "variable": "sulphur_dioxide", "grid": 4})
    assert r.status_code == 400
    assert "source" in r.get_json()["error"]


def test_scan_unknown_source():
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "bilinmeyen", "variable": "pm2_5", "grid": 4})
    assert r.status_code == 400
    assert "Bilinmeyen kaynak" in r.get_json()["error"]


def test_scan_external_source_blocked():
    """external kaynaklar tarama için kullanılamaz."""
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "openaq", "variable": "pm2_5", "grid": 4})
    assert r.status_code == 400
    assert "kullanılamaz" in r.get_json()["error"]


def test_scan_variable_not_in_source():
    """bir kaynak kendi bölümünün değişkenlerini ölçer; forecast'te pm2_5 olmaz."""
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "forecast_best", "variable": "pm2_5", "grid": 4})
    assert r.status_code == 400
    assert "ölçmüyor" in r.get_json()["error"]


def _batch_count(params):
    lat = str(params.get("latitude", ""))
    return len(lat.split(",")) if lat else 1


def test_scan_endpoint(monkeypatch):
    import app as appmod
    # batch: çoklu noktada artan değer döndür → min/max renk skalası testi
    counter = {"n": 0}
    def fake_fetch(section, params):
        n = _batch_count(params)
        arr = []
        for _ in range(n):
            counter["n"] += 1
            arr.append({"current": {"sulphur_dioxide": float(counter["n"])}})
        return arr if n > 1 else arr[0]
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "aq_cams_europe", "variable": "sulphur_dioxide", "grid": 4})
    assert r.status_code == 200
    data = r.get_json()
    assert data["variable"] == "sulphur_dioxide"
    assert len(data["cells"]) == data["rows"] * data["cols"]
    assert data["min"] < data["max"]
    assert all("lat" in cell and "lon" in cell and "value" in cell for cell in data["cells"])
    assert data["source"]["resolution"]      # kaynak meta-verisi
    assert data["source"]["cell_area"]        # "veri neyi temsil eder" notu
    assert data["max_grid"] >= 2              # dinamik üst sınır dönüyor


def test_scan_model_param_passed(monkeypatch):
    """icon_eu seçilince fetch_raw'a models=icon_eu geçmeli."""
    import app as appmod
    seen = {}
    def fake_fetch(section, params):
        seen["section"] = section
        seen["models"] = params.get("models")
        n = _batch_count(params)
        arr = [{"current": {"temperature_2m": 20.0}} for _ in range(n)]
        return arr if n > 1 else arr[0]
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "forecast_icon_eu", "variable": "temperature_2m", "grid": 4})
    assert r.status_code == 200
    assert seen["section"] == "forecast" and seen["models"] == "icon_eu"


def test_scan_elevation_endpoint(monkeypatch):
    """Yükseklik (DEM) taraması — elevation uç noktası 'elevation' listesi döndürür."""
    import app as appmod
    def fake_fetch(section, params):
        assert section == "elevation"
        n = _batch_count(params)
        return {"elevation": [100.0] * n}
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "elevation", "variable": "elevation", "grid": 4})
    assert r.status_code == 200
    data = r.get_json()
    assert data["variable"] == "elevation"
    assert data["unit"] == "m"
    assert data["source"]["cell_area"]


def test_max_rows_for_honesty():
    """Dinamik üst sınır: kaba modelde az, ince kaynakta (DEM) tavana çıkar."""
    import app as appmod
    from meteo import datasources
    # cams_global ~40km, 1° alan → ~3 hücre
    assert appmod._max_rows_for(1.0, datasources.get("aq_cams_global")["min_cell_deg"]) <= 4
    # cams_europe ~10km, 5° alan → ~56 hücre (64 tavanı altında)
    assert 50 <= appmod._max_rows_for(5.0, datasources.get("aq_cams_europe")["min_cell_deg"]) <= 64
    # DEM ~30m, 1° alan → 64 tavanına çıkar (çok ince)
    assert appmod._max_rows_for(1.0, datasources.get("elevation")["min_cell_deg"]) == 64


def test_scan_clamps_oversampling(monkeypatch):
    """Çok ince grid istense bile dürüst üst sınır clamp'ler (interpole örneklemeyi önler)."""
    import app as appmod
    calls = {"n": 0}
    def fake_fetch(section, params):
        n = _batch_count(params); calls["n"] += n
        arr = [{"current": {"pm2_5": 5.0}} for _ in range(n)]
        return arr if n > 1 else arr[0]
    monkeypatch.setattr(appmod._meteo, "fetch_raw", fake_fetch)
    c = appmod.app.test_client()
    # cams_global ~40km, 1° alan → max ~3; grid=99 istense bile ~3 satır.
    r = c.post("/api/scan", json={"bbox": {"north": 40, "south": 39, "east": 30, "west": 29},
                                  "source": "aq_cams_global", "variable": "pm2_5", "grid": 99})
    data = r.get_json()
    assert r.status_code == 200
    assert data["rows"] <= 4   # çok ince istek dürüstçe kısıtlandı
    assert data["max_grid"] <= 4


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_scan_opentopodata_backend(monkeypatch):
    """OpenTopoData (anahtarsız, Open-Meteo dışı) backend'i — requests.get ile."""
    import app as appmod
    captured = {}
    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        locs = params["locations"].split("|")
        results = [{"dataset": "srtm30m", "elevation": 100.0 + i, "location": {"lat": 0, "lng": 0}}
                   for i in range(len(locs))]
        return _FakeResp({"status": "OK", "results": results})
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.5, "east": 34.0, "west": 33.5},
                                  "source": "opentopo_srtm30m", "variable": "elevation", "grid": 4})
    assert r.status_code == 200
    data = r.get_json()
    assert data["variable"] == "elevation"
    assert "opentopodata.org" in captured["url"]
    assert all(cell["value"] is not None for cell in data["cells"])
    assert data["source"]["via"] == "OpenTopoData"
    assert data["source"]["backend"] == "opentopodata"


def test_scan_weatherapi_forecast_backend(monkeypatch):
    """weather-api.site forecast backend'i requests.get ile."""
    import app as appmod
    captured = {}
    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["url"] = url
        assert "weather-api.site" in url
        return _FakeResp({
            "latitude": params["lat"], "longitude": params["lon"],
            "current": {"temperature": 22.5, "humidity": 55, "wind_speed": 10,
                        "pressure": 1012, "cloud_cover": 20, "uv_index": 5.0,
                        "precipitation": 0.0, "feels_like": 23.0},
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "weatherapi_forecast", "variable": "temperature_2m", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["variable"] == "temperature_2m"
    assert data["source"]["backend"] == "weatherapi"
    assert data["source"]["via"] == "weather-api.site"
    assert all(cell["value"] == 22.5 for cell in data["cells"])


def test_scan_weatherapi_aq_backend(monkeypatch):
    """weather-api.site air-quality backend'i PM2.5 ile."""
    import app as appmod
    def fake_get(url, params=None, timeout=None, **kwargs):
        assert "air-quality" in url
        return _FakeResp({
            "latitude": params["lat"], "longitude": params["lon"],
            "current": {"pm2_5": 12.3, "pm10": 18.0, "us_aqi": 42,
                        "nitrogen_dioxide": 8, "ozone": 35, "sulphur_dioxide": 2, "carbon_monoxide": 0.3},
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "weatherapi_aq", "variable": "pm2_5", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["section"] == "air_quality"
    assert all(cell["value"] == 12.3 for cell in data["cells"])


def test_scan_eris_backend(monkeypatch):
    """Eris anlık hava backend'i — OpenWeatherMap proxy."""
    import app as appmod
    captured = {}
    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["url"] = url
        return _FakeResp({
            "main": {"temp": 20.0, "humidity": 60, "pressure": 1015},
            "wind": {"speed": 3.0},
            "weather": [{"main": "Clear"}],
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "eris_current", "variable": "wind_speed_10m", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["backend"] == "eris"
    # Eris rüzgâr m/s döner, km/h çevrimi uygulanır: 3.0 * 3.6 = 10.8
    assert all(abs(cell["value"] - 10.8) < 0.01 for cell in data["cells"])


def test_scan_wttrin_backend(monkeypatch):
    """wttr.in JSON backend'i — değerler string; parse testi."""
    import app as appmod
    def fake_get(url, params=None, timeout=None, **kwargs):
        assert "wttr.in" in url
        assert params.get("format") == "j1"
        return _FakeResp({
            "current_condition": [{
                "temp_C": "24", "humidity": "45", "pressure": "1011",
                "windspeedKmph": "12", "uvIndex": "6",
            }],
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "wttrin_current", "variable": "temperature_2m", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["backend"] == "wttrin"
    assert all(cell["value"] == 24.0 for cell in data["cells"])


def test_scan_nasa_power_backend(monkeypatch):
    """NASA POWER günlük iklim backend'i — dün ortalaması."""
    import app as appmod
    captured = {}
    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["param"] = params.get("parameters")
        return _FakeResp({
            "type": "Feature",
            "properties": {
                "parameter": {
                    "ALLSKY_SFC_SW_DWN": {"20230101": 2.5, "20230102": 3.1},
                },
            },
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "nasa_power_daily", "variable": "surface_shortwave_radiation", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["backend"] == "nasa_power"
    assert data["source"]["section"] == "climate"
    assert captured["param"] == "ALLSKY_SFC_SW_DWN"
    assert all(cell["value"] == 3.1 for cell in data["cells"])


def test_usgs_earthquakes_endpoint(monkeypatch):
    """/api/earthquakes USGS GeoJSON proxy'si — bbox + minmag + hours ile."""
    import app as appmod
    captured = {}
    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["params"] = params
        return _FakeResp({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [33.4, 35.2, 10.0]},
                 "properties": {"mag": 4.2, "place": "Test deprem", "time": 1750436335000, "url": "http://example.com"}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [33.5, 35.3, 60.0]},
                 "properties": {"mag": 3.1, "place": "Test deprem 2", "time": 1750436336000, "url": "http://example.com"}},
            ],
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.get("/api/earthquakes?minlat=34&maxlat=36.5&minlon=32&maxlon=35.5&minmag=2&hours=24")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 2
    assert data["features"][0]["properties"]["mag"] == 4.2
    assert data["features"][0]["geometry"]["coordinates"][2] == 10.0  # depth
    assert captured["params"]["format"] == "geojson"
    assert captured["params"]["minmagnitude"] == 2.0


def test_scan_metno_backend(monkeypatch):
    """MET Norway backend'i — locationforecast/2.0/compact."""
    import app as appmod
    def fake_get(url, params=None, timeout=None, **kwargs):
        assert "api.met.no" in url
        return _FakeResp({
            "properties": {
                "timeseries": [{
                    "time": "2026-06-21T15:00:00Z",
                    "data": {
                        "instant": {"details": {
                            "air_temperature": 28.5, "relative_humidity": 55.0,
                            "wind_speed": 4.0, "air_pressure_at_sea_level": 1012.0,
                            "cloud_area_fraction": 25.0,
                        }},
                        "next_1_hours": {"details": {"precipitation_amount": 1.2}},
                    },
                }],
            },
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "metno_forecast", "variable": "temperature_2m", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["backend"] == "metno"
    assert all(cell["value"] == 28.5 for cell in data["cells"])
    # rüzgâr m/s → km/h
    r2 = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                    "source": "metno_forecast", "variable": "wind_speed_10m", "grid": 3})
    assert all(abs(cell["value"] - 14.4) < 0.01 for cell in r2.get_json()["cells"])


def test_satellite_endpoint():
    """/api/satellite EUMETSAT URL döndürür; harici HTTP çağrısı yapmaz."""
    import app as appmod
    c = appmod.app.test_client()
    r = c.get("/api/satellite?product=ir108")
    assert r.status_code == 200
    data = r.get_json()
    assert data["url"].startswith("https://eumetview.eumetsat.int/static-images/latestImages/")
    assert "IR108" in data["url"]
    assert data["attribution"] == "EUMETSAT"
    assert data["bounds"] == [[-78.0, -78.0], [78.0, 78.0]]
    assert "full disk" in data["coverage"].lower()
    assert "çizme" in data["note"].lower() or "alan" in data["note"].lower()


def test_scan_seventimer_backend(monkeypatch):
    """7Timer! backend'i — GFS tabanlı JSON tahmin."""
    import app as appmod
    def fake_get(url, params=None, timeout=None, **kwargs):
        assert "7timer" in url
        return _FakeResp({
            "product": "civil", "init": "2026062106",
            "dataseries": [{
                "timepoint": 3, "temp2m": 27, "rh2m": "35%", "prec_amount": 2,
                "cloudcover": 3, "wind10m": {"direction": "N", "speed": 2},
            }],
        })
    monkeypatch.setattr(appmod.requests, "get", fake_get)
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                  "source": "seventimer_forecast", "variable": "temperature_2m", "grid": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"]["backend"] == "seventimer"
    assert all(cell["value"] == 27.0 for cell in data["cells"])
    # bulut 3/9 oktal → %
    r2 = c.post("/api/scan", json={"bbox": {"north": 36.0, "south": 35.9, "east": 34.0, "west": 33.9},
                                    "source": "seventimer_forecast", "variable": "cloud_cover", "grid": 3})
    assert all(abs(cell["value"] - 33.33) < 0.01 for cell in r2.get_json()["cells"])


def test_scan_radar_mode_rejected():
    """RainViewer radar modu /api/scan'dan sayısal tarama vermez."""
    import app as appmod
    c = appmod.app.test_client()
    r = c.post("/api/scan", json={"bbox": {"north": 36, "south": 35, "east": 34, "west": 33},
                                  "source": "rainviewer", "variable": "precipitation", "grid": 4})
    assert r.status_code == 400
    assert "radar" in r.get_json()["error"].lower()


def test_rainviewer_endpoint(monkeypatch):
    """/api/rainviewer — weather-maps.json'u çekip frame listesi döndürür."""
    import app as appmod
    payload = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [{"time": 1782028800, "path": "/v2/radar/aaa"},
                     {"time": 1782029400, "path": "/v2/radar/bbb"}],
            "nowcast": [{"time": 1782030000, "path": "/v2/radar/ccc"}],
        },
    }
    monkeypatch.setattr(appmod.requests, "get", lambda *a, **k: _FakeResp(payload))
    c = appmod.app.test_client()
    r = c.get("/api/rainviewer")
    assert r.status_code == 200
    data = r.get_json()
    assert data["host"].startswith("https://")
    assert len(data["frames"]) == 3
    assert data["frames"][0]["nowcast"] is False
    assert data["frames"][-1]["nowcast"] is True
    assert data["frames"][0]["path"] == "/v2/radar/aaa"


def test_datasources_catalog():
    from meteo import datasources
    # integrated Open-Meteo kaynakları: model + dürüst notu + çözünürlük + değişken
    for sid in ["forecast_best", "forecast_icon_eu", "aq_cams_europe", "elevation"]:
        s = datasources.get(sid)
        assert s and s["status"] == "integrated"
        assert s["cell_area"] and s["min_cell_deg"]
        assert s["backend"] == "openmeteo" and s["via"] == "Open-Meteo"
        assert datasources.variables_for(sid)
    # Open-Meteo DIŞI anahtarsız kaynaklar (web aramasıyla bulundu)
    assert datasources.get("opentopo_srtm30m")["backend"] == "opentopodata"
    assert datasources.get("opentopo_srtm30m")["via"] == "OpenTopoData"
    assert datasources.get("opentopo_srtm90m")["dataset"] == "srtm90m"
    assert datasources.get("rainviewer")["mode"] == "radar"
    assert datasources.get("rainviewer")["backend"] == "rainviewer"
    # Web aramasıyla bulunan yeni anahtarsız kaynaklar
    for sid in ["weatherapi_forecast", "weatherapi_aq", "eris_current", "wttrin_current", "nasa_power_daily"]:
        s = datasources.get(sid)
        assert s and s["status"] == "integrated" and s["backend"] and s["via"]
        assert datasources.variables_for(sid)
    assert datasources.get("nasa_power_daily")["section"] == "climate"
    # CERNS.IO lat/lon locate ucu çalışmadığı için external bilgi kaynağı
    assert datasources.get("cernsio_aqi")["status"] == "external"
    # external kaynakların taranabilir değişkeni yok
    for sid in ["openaq", "tropomi", "radar"]:
        assert datasources.get(sid)["status"] == "external"
        assert datasources.variables_for(sid) == []
    # her Open-Meteo modeli bir bölümüne bağlı
    assert datasources.get("forecast_icon_eu")["section"] == "forecast"
    assert datasources.get("aq_cams_global")["section"] == "air_quality"
    # scan sayfası kaynak kataloğunu + provenance'ı şablona aktarır
    import app as appmod
    c = appmod.app.test_client()
    r = c.get("/scan")
    assert r.status_code == 200
    assert b"Veri kayna" in r.data
    assert b"Veri neyi temsil eder" in r.data or b"source-info" in r.data
    assert b"Open-Meteo modelleri" in r.data          # optgroup provenance
    assert b"Di\xcc\x87\xc4\x9fer anahtars\xc4\xb1z" in r.data or b"anahtars" in r.data
    assert b"RainViewer" in r.data or b"rainviewer" in r.data
    assert b"OpenTopoData" in r.data or b"opentopo" in r.data


def test_scan_page_variable_catalog_covers_particles_uv():
    """Tarama sayfası TÜM değişken katalogunu (partikül/UV/AQI dahil) aktarır
    ve varsayılan değişken PM2.5'tir — yani partiküller 'kayboldu' sanılmaz."""
    import app as appmod, json
    c = appmod.app.test_client()
    r = c.get("/scan")
    assert r.status_code == 200
    body = r.data.decode()
    m = body.split("window.SCAN_VARIABLES = ", 1)[1].split(";</script>", 1)[0]
    catalog = json.loads(m)
    keys = {v["key"] for v in catalog}
    # partikül/UV/AQI katalogda her zaman var (kaynağa göre gizlenmez)
    for k in ["pm2_5", "pm10", "uv_index", "us_aqi", "european_aqi",
              "nitrogen_dioxide", "ozone"]:
        assert k in keys, f"{k} katalogda yok"
    # hava kalitesi değişkenleri en üstte (en az bir AQ değişkeni forecast'ten önce)
    first_section = catalog[0]["section"]
    assert first_section == "air_quality"
    # iklim/enerji değişkenleri de katalogda (NASA POWER)
    for k in ["surface_shortwave_radiation", "soil_moisture_surface", "daily_mean_temperature_2m"]:
        assert k in keys, f"{k} katalogda yok"
    # varsayılan değişken nötr bir tahmin değişkenidir (Sıcaklık) — böylece
    # açılışta tahmin modelleri (DWD ICON/GFS/ECMWF) seçilebilir kalır; PM2.5
    # seçilince kaynak otomatik CAMS'e döner (JS applyVariable ile).
    assert '"temperature_2m"' in body.split("SCAN_DEFAULTS")[1][:80]

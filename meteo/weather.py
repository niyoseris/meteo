"""Hava/weather API'leri — forecast, historical, climate, flood, marine,
air-quality, elevation.

Bu modül `WeatherMixin` tanımlar; `OpenMeteo` bu mixin'i miras alır. Her
metot, ilgili alt uç noktaya parametreleri iletir ve ham JSON döndürür.
"all" parametreleri API'nin tüm yaygın değişkenlerini istemek için
kısayol olarak kullanılır; ileri düzey kullanıcılar bireysel değişken
listelerini kendileri de verebilir.
"""

from __future__ import annotations

from typing import Iterable, Optional, TYPE_CHECKING, Union

from .types import Location, GeocodingResult

if TYPE_CHECKING:  # çalışma zamanında değil — döngüsel import yok
    from .client import OpenMeteo


# ---------------------------------------------------------------------------
# Yaygın değişken setleri. Open-Meteo çok sayıda değişken destekler; burada
# "tümünü al" deneyimi için kapsamlı listeler tutuyoruz.
# ---------------------------------------------------------------------------
CURRENT_VARS = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "is_day",
        "precipitation",
        "rain",
        "showers",
        "snowfall",
        "weather_code",
        "cloud_cover",
        "pressure_msl",
        "surface_pressure",
        "wind_speed_10m",
        "wind_direction_10m",
        "wind_gusts_10m",
    ]
)

HOURLY_VARS = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "precipitation_probability",
        "precipitation",
        "rain",
        "showers",
        "snowfall",
        "snow_depth",
        "weather_code",
        "pressure_msl",
        "surface_pressure",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "visibility",
        "evapotranspiration",
        "et0_fao_evapotranspiration",
        "vapour_pressure_deficit",
        "wind_speed_10m",
        "wind_speed_80m",
        "wind_direction_10m",
        "wind_direction_80m",
        "wind_gusts_10m",
        "temperature_80m",
        "soil_temperature_0cm",
        "soil_temperature_6cm",
        "soil_temperature_18cm",
        "soil_temperature_54cm",
        "soil_moisture_0_to_1cm",
        "soil_moisture_1_to_3cm",
        "soil_moisture_3_to_9cm",
        "soil_moisture_9_to_27cm",
        "uv_index",
        "uv_index_clear_sky",
        "is_day",
        "sunshine_duration",
        "shortwave_radiation",
        "direct_radiation",
        "diffuse_radiation",
    ]
)

DAILY_VARS = ",".join(
    [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "sunrise",
        "sunset",
        "daylight_duration",
        "sunshine_duration",
        "uv_index_max",
        "precipitation_sum",
        "rain_sum",
        "showers_sum",
        "snowfall_sum",
        "precipitation_hours",
        "precipitation_probability_max",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
        "et0_fao_evapotranspiration",
    ]
)

MARINE_VARS = ",".join(
    [
        "wave_height",
        "wave_direction",
        "wave_period",
        "wind_wave_height",
        "wind_wave_direction",
        "wind_wave_period",
        "swell_wave_height",
        "swell_wave_direction",
        "swell_wave_period",
    ]
)

AIR_QUALITY_VARS = ",".join(
    [
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "ammonia",
        "dust",
        "uv_index",
        "european_aqi",
        "us_aqi",
    ]
)

CLIMATE_VARS = ",".join(
    [
        "temperature_2m_max",
        "temperature_2m_min",
        "temperature_2m_mean",
        "precipitation_sum",
        "rain_sum",
        "snowfall_sum",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
        "shortwave_radiation_sum",
        "et0_fao_evapotranspiration_sum",
    ]
)

FLOOD_VARS = "river_discharge"


# ---------------------------------------------------------------------------
# Konum yardımcıları
# ---------------------------------------------------------------------------
def _loc(loc: Union[Location, GeocodingResult, tuple]) -> dict:
    if isinstance(loc, (Location, GeocodingResult)):
        return {"latitude": round(loc.latitude, 4), "longitude": round(loc.longitude, 4)}
    lat, lon = loc
    return {"latitude": round(lat, 4), "longitude": round(lon, 4)}


def _tz(loc: Union[Location, GeocodingResult, tuple, None], default: str = "auto") -> str:
    if isinstance(loc, Location):
        return loc.timezone or default
    return default


class WeatherMixin:
    """`OpenMeteo`'ya hava/weather API'lerini ekler (mixin)."""

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------
    def forecast(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        current: Union[bool, str, Iterable[str]] = False,
        hourly: Union[bool, str, Iterable[str]] = False,
        daily: Union[bool, str, Iterable[str]] = False,
        timezone: Optional[str] = None,
        forecast_days: int = 7,
        past_days: int = 0,
        forecast_hours: Optional[int] = None,
        past_hours: Optional[int] = None,
        cell_selection: str = "land",
        extra: Optional[dict] = None,
    ) -> dict:
        """Anlık / saatlik / günlük tahmin.

        `current`, `hourly`, `daily` için:
          * `True`  — o grubun tüm değişkenleri istenir,
          * `False` — istenmez,
          * `str` veya yineleme — bireysel değişken listesi.
        """
        params = _loc(location)
        params["timezone"] = timezone or _tz(location)
        params["forecast_days"] = forecast_days
        if past_days:
            params["past_days"] = past_days
        if forecast_hours is not None:
            params["forecast_hours"] = forecast_hours
        if past_hours is not None:
            params["past_hours"] = past_hours
        params["cell_selection"] = cell_selection

        for key, val, default in (
            ("current", current, CURRENT_VARS),
            ("hourly", hourly, HOURLY_VARS),
            ("daily", daily, DAILY_VARS),
        ):
            if val is True:
                params[key] = default
            elif isinstance(val, str):
                params[key] = val
            elif val:  # yineleme
                params[key] = ",".join(val)

        if extra:
            params.update(extra)
        return self._request("forecast", params)

    # ------------------------------------------------------------------
    # Historical (archive)
    # ------------------------------------------------------------------
    def historical(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        start_date: str,
        end_date: str,
        daily: Union[bool, str, Iterable[str]] = True,
        hourly: Union[bool, str, Iterable[str]] = False,
        timezone: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Geçmiş ölçümler (archive API). Tarihler ISO biçiminde (YYYY-MM-DD)."""
        params = _loc(location)
        params["start_date"] = start_date
        params["end_date"] = end_date
        params["timezone"] = timezone or _tz(location)

        if daily is True:
            params["daily"] = DAILY_VARS
        elif isinstance(daily, str):
            params["daily"] = daily
        elif daily:
            params["daily"] = ",".join(daily)

        if hourly is True:
            params["hourly"] = HOURLY_VARS
        elif isinstance(hourly, str):
            params["hourly"] = hourly
        elif hourly:
            params["hourly"] = ",".join(hourly)

        if extra:
            params.update(extra)
        return self._request("historical", params)

    # ------------------------------------------------------------------
    # Historical forecast (retro-tahmin)
    # ------------------------------------------------------------------
    def historical_forecast(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        start_date: str,
        end_date: str,
        current: Union[bool, str, Iterable[str]] = False,
        hourly: Union[bool, str, Iterable[str]] = False,
        daily: Union[bool, str, Iterable[str]] = True,
        timezone: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Geçmişe dönük tahmin verisi (model yeniden-analizleri)."""
        params = _loc(location)
        params.update({"start_date": start_date, "end_date": end_date})
        params["timezone"] = timezone or _tz(location)

        for key, val, default in (
            ("daily", daily, DAILY_VARS),
            ("hourly", hourly, HOURLY_VARS),
        ):
            if val is True:
                params[key] = default
            elif isinstance(val, str):
                params[key] = val
            elif val:
                params[key] = ",".join(val)

        if current is True:
            params["current"] = CURRENT_VARS
        elif isinstance(current, str):
            params["current"] = current
        elif current:
            params["current"] = ",".join(current)

        if extra:
            params.update(extra)
        return self._request("historical_forecast", params)

    # ------------------------------------------------------------------
    # Climate
    # ------------------------------------------------------------------
    def climate(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        start_date: str,
        end_date: str,
        daily: Union[bool, str, Iterable[str]] = True,
        timezone: Optional[str] = None,
        models: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """İklim modeli projeksiyonu (CMIP6)."""
        params = _loc(location)
        params.update({"start_date": start_date, "end_date": end_date})
        params["timezone"] = timezone or _tz(location)
        if daily is True:
            params["daily"] = CLIMATE_VARS
        elif isinstance(daily, str):
            params["daily"] = daily
        elif daily:
            params["daily"] = ",".join(daily)
        if models:
            params["models"] = models
        if extra:
            params.update(extra)
        return self._request("climate", params)

    # ------------------------------------------------------------------
    # Flood
    # ------------------------------------------------------------------
    def flood(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        daily: Union[bool, str, Iterable[str]] = True,
        past_days: int = 0,
        forecast_days: int = 90,
        timezone: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Nehir debisi / taşkın tahmini."""
        params = _loc(location)
        params["timezone"] = timezone or _tz(location)
        params["past_days"] = past_days
        params["forecast_days"] = forecast_days
        if daily is True:
            params["daily"] = FLOOD_VARS
        elif isinstance(daily, str):
            params["daily"] = daily
        elif daily:
            params["daily"] = ",".join(daily)
        if extra:
            params.update(extra)
        return self._request("flood", params)

    # ------------------------------------------------------------------
    # Marine
    # ------------------------------------------------------------------
    def marine(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        current: Union[bool, str, Iterable[str]] = False,
        hourly: Union[bool, str, Iterable[str]] = True,
        daily: Union[bool, str, Iterable[str]] = False,
        forecast_days: int = 7,
        past_days: int = 0,
        timezone: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Deniz / dalga tahmini. Sahil/deniz noktaları için anlamlıdır."""
        params = _loc(location)
        params["timezone"] = timezone or _tz(location)
        params["forecast_days"] = forecast_days
        if past_days:
            params["past_days"] = past_days

        for key, val, default in (
            ("current", current, MARINE_VARS),
            ("hourly", hourly, MARINE_VARS),
            ("daily", daily, "wave_height_max,wave_direction_dominant"),
        ):
            if val is True:
                params[key] = default
            elif isinstance(val, str):
                params[key] = val
            elif val:
                params[key] = ",".join(val)

        if extra:
            params.update(extra)
        return self._request("marine", params)

    # ------------------------------------------------------------------
    # Air quality
    # ------------------------------------------------------------------
    def air_quality(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        current: Union[bool, str, Iterable[str]] = False,
        hourly: Union[bool, str, Iterable[str]] = False,
        timezone: Optional[str] = None,
        forecast_days: int = 5,
        past_days: int = 0,
        extra: Optional[dict] = None,
    ) -> dict:
        """Hava kalitesi (PM, ozon, NO2, AQI ...)."""
        params = _loc(location)
        params["timezone"] = timezone or _tz(location)
        params["forecast_days"] = forecast_days
        if past_days:
            params["past_days"] = past_days

        for key, val in (("current", current), ("hourly", hourly)):
            if val is True:
                params[key] = AIR_QUALITY_VARS
            elif isinstance(val, str):
                params[key] = val
            elif val:
                params[key] = ",".join(val)

        if extra:
            params.update(extra)
        return self._request("air_quality", params)

    # ------------------------------------------------------------------
    # Elevation
    # ------------------------------------------------------------------
    def elevation(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
    ) -> dict:
        """Bir noktanın rakımını döndürür (metre)."""
        params = _loc(location)
        # elevation API latitude/longitude listelerini de destekler; tek
        # nokta için normal değerler yeterli.
        return self._request("elevation", params)

    # ------------------------------------------------------------------
    # "Hepsini al" kısayolu
    # ------------------------------------------------------------------
    def all(
        self: OpenMeteo,
        location: Union[Location, GeocodingResult, tuple],
        *,
        forecast_days: int = 7,
        past_days: int = 0,
        air_quality_days: int = 5,
        marine_days: int = 7,
        flood_days: int = 30,
    ) -> dict:
        """Bir bölge için eldeki tüm API'leri çağırıp tek sözlükte toplar.

        Hata alan alt istekler söz konusu bölümde `{"error": "..."}` olarak
        döner; böylece tek bir API'nin başarısızlığı diğerlerini bozmaz.
        """
        out: dict = {"location": _loc(location)}
        tz = _tz(location)

        def safe(name: str, fn) -> dict:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 — kasıtlı geniş yakalama
                return {"error": f"{type(exc).__name__}: {exc}"}

        out["forecast"] = safe(
            "forecast",
            lambda: self.forecast(
                location,
                current=True,
                hourly=True,
                daily=True,
                forecast_days=forecast_days,
                past_days=past_days,
                timezone=tz,
            ),
        )
        out["air_quality"] = safe(
            "air_quality",
            lambda: self.air_quality(
                location,
                current=True,
                hourly=True,
                forecast_days=air_quality_days,
                past_days=past_days,
                timezone=tz,
            ),
        )
        out["marine"] = safe(
            "marine",
            lambda: self.marine(
                location,
                hourly=True,
                forecast_days=marine_days,
                past_days=past_days,
                timezone=tz,
            ),
        )
        out["flood"] = safe(
            "flood",
            lambda: self.flood(location, daily=True, forecast_days=flood_days, timezone=tz),
        )
        out["elevation"] = safe("elevation", lambda: self.elevation(location))
        return out
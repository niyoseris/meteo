"""Temel HTTP client ve API giriş noktası.

`OpenMeteo` sınıfı tüm alt API'leri tek çatı altında toplar. Alt metotlar
(`forecast`, `historical`, ...) uygun alt uç noktaya istek atar ve dönen
JSON'u ham biçimde döndürür — bu sayede "tüm verilere" erişim korunur.
"""

from __future__ import annotations

import json
import time
from typing import Any, Iterable, Mapping, Optional, TYPE_CHECKING, Union

import requests

from .types import Location, GeocodingResult

if TYPE_CHECKING:  # yalnızca tip denetimi için — çalışma zamanında değil
    pass


class OpenMeteoError(Exception):
    """Open-Meteo istekleriyle ilgili genel hata."""


class APIError(OpenMeteoError):
    """API'den gelen hata (HTTP 4xx/5xx veya `error` alanı)."""

    def __init__(self, message: str, status: int = 0, url: str = ""):
        super().__init__(message)
        self.status = status
        self.url = url


# Alt uç noktaların temel adresleri.
BASE_URLS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "historical": "https://archive-api.open-meteo.com/v1/archive",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "climate": "https://climate-api.open-meteo.com/v1/climate",
    "flood": "https://flood-api.open-meteo.com/v1/flood",
    "marine": "https://marine-api.open-meteo.com/v1/marine",
    "air_quality": "https://air-quality-api.open-meteo.com/v1/air-quality",
    "elevation": "https://api.open-meteo.com/v1/elevation",
    "geocoding": "https://geocoding-api.open-meteo.com/v1/search",
}

# Nazik bir "kim yapıyor" başlığı. Open-Meteo anahtarsız çalışır, bu yüzden
# kimlik doğrulama yoktur; sadece kullanım takibi için.
_USER_AGENT = "meteo/0.1.0 (python-requests)"


class _BaseClient:
    """HTTP katmanı — mixin'lerin ortak kullandığı düşük seviye istek."""

    def __init__(
        self,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.8,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        )

    # ------------------------------------------------------------------
    # Düşük seviye istek
    # ------------------------------------------------------------------
    def _request(
        self,
        kind: str,
        params: Mapping[str, Any],
        *,
        url: Optional[str] = None,
    ) -> dict:
        target = url or BASE_URLS[kind]
        last_err: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(target, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last_err = exc
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
                raise APIError(f"İstek başarısız: {exc}", url=target) from exc

            # 5xx ve 429'da yeniden dene.
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                last_err = APIError(
                    f"Geçici hata {resp.status_code}", status=resp.status_code, url=target
                )
                time.sleep(self.backoff * (2 ** attempt))
                continue

            if resp.status_code >= 400:
                raise APIError(
                    f"HTTP {resp.status_code}: {resp.text[:300]}",
                    status=resp.status_code,
                    url=resp.url,
                )

            try:
                data = resp.json()
            except ValueError as exc:
                raise APIError(f"JSON çözülemedi: {exc}", url=resp.url) from exc

            if isinstance(data, dict) and data.get("error"):
                reason = data.get("reason") or data.get("error")
                raise APIError(f"API hatası: {reason}", url=resp.url)

            return data

        raise last_err if last_err else APIError("Bilinmeyen hata", url=target)

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    @staticmethod
    def _loc_params(
        loc: Union[Location, GeocodingResult, tuple]
    ) -> dict:
        if isinstance(loc, (Location, GeocodingResult)):
            lat, lon = loc.latitude, loc.longitude
        else:
            lat, lon = loc
        return {"latitude": round(lat, 4), "longitude": round(lon, 4)}

    def fetch_raw(self, kind: str, params: Mapping[str, Any]) -> dict:
        """İstenen alt API'ye (`kind`) ham istek at.

        `kind` :data:`BASE_URLS` anahtarlarından biri olmalı. İleri düzey
        kullanıcılar için doğrudan erişim; normal kullanımda sarmalayıcı
        metotları tercih edin.
        """
        if kind not in BASE_URLS:
            raise OpenMeteoError(f"Bilinmeyen API türü: {kind!r}")
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request(kind, clean)

    def to_json(self, data: Any, *, indent: int = 2) -> str:
        """Sonucu insancıl JSON metnine çevirir (dataclass-aware)."""
        return json.dumps(
            data, ensure_ascii=False, indent=indent, default=lambda o: o.__dict__
        )


# Mixin'leri gecikmeli ithal et — döngüsel import yok: geocoding/weather
# yalnızca `types` ve (TYPE_CHECKING altında) bu sınıfı referans eder.
from .geocoding import GeocodingMixin  # noqa: E402
from .weather import WeatherMixin  # noqa: E402


class OpenMeteo(GeocodingMixin, WeatherMixin, _BaseClient):
    """Open-Meteo API'leri için tek giriş noktası.

    GeocodingMixin (bölge adı → koordinat) ve WeatherMixin (forecast,
    historical, climate, flood, marine, air-quality, elevation) yeteneklerini
    miras alır.

    Parametreler
    ------------
    timeout:
        Tek istek için saniye cinsinden zaman aşımı.
    retries:
        Başarısız isteklerin tekrar deneme sayısı.
    backoff:
        Tekrar denemeler arası başlangıç bekleme (saniye); katlanarak artar.
    session:
        Dışarıdan verilmiş `requests.Session` (testler için yararlı).
    """
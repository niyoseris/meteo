"""Geocoding API — bölge adından koordinat çözümleme.

Open-Meteo'nun ücretsiz geocoding servisi şehir/yer adından enlem-boylam
döndürür. Bir arama birden çok eşleşme döndürebilir; varsayılan olarak en
popüler (ilk) sonuç seçilir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from .types import GeocodingResult, Location
from .client import OpenMeteoError

if TYPE_CHECKING:  # çalışma zamanında değil — döngüsel import yok
    from .client import OpenMeteo


class GeocodingMixin:
    """`OpenMeteo`'ya geocoding yetenekleri ekler (mixin olarak)."""

    def geocode_search(
        self: "OpenMeteo",
        name: str,
        *,
        language: str = "tr",
        count: int = 10,
        country_codes: Optional[str] = None,
    ) -> List[GeocodingResult]:
        """`name` için eşleşmeleri listeler.

        Parametreler
        ------------
        language:
            Sonuç metinlerinin dili (ör. "tr", "en").
        count:
            Dönecek azami sonuç sayısı.
        country_codes:
            ISO 3166-1 alpha-2 kodları (virgülle, örn. "TR,DE") ile
            aramayı ülkeyle sınırlandırma.
        """
        if not name or not name.strip():
            raise OpenMeteoError("Bölge adı boş olamaz.")

        params = {
            "name": name.strip(),
            "count": count,
            "language": language,
            "format": "json",
        }
        if country_codes:
            params["countryCode"] = country_codes

        data = self._request("geocoding", params)
        results = data.get("results") or []
        return [self._parse_geocoding(r) for r in results]

    @staticmethod
    def _parse_geocoding(raw: dict) -> GeocodingResult:
        return GeocodingResult(
            name=raw.get("name", ""),
            latitude=raw.get("latitude"),
            longitude=raw.get("longitude"),
            country=raw.get("country", ""),
            country_code=raw.get("country_code", ""),
            admin1=raw.get("admin1", ""),
            admin2=raw.get("admin2", ""),
            timezone=raw.get("timezone", ""),
            population=raw.get("population"),
            elevation=raw.get("elevation"),
            feature_code=raw.get("feature_code", ""),
            raw=raw,
        )

    def geocode(
        self: "OpenMeteo",
        name: str,
        *,
        language: str = "tr",
        country_codes: Optional[str] = None,
    ) -> GeocodingResult:
        """`name` için en iyi (ilk) eşleşmeyi döndürür; yoksa hata."""
        results = self.geocode_search(
            name, language=language, count=1, country_codes=country_codes
        )
        if not results:
            raise OpenMeteoError(f"Bölge bulunamadı: {name!r}")
        return results[0]

    def geocode_location(
        self: "OpenMeteo",
        name: str,
        *,
        language: str = "tr",
        timezone: str = "auto",
        country_codes: Optional[str] = None,
    ) -> Location:
        return self.geocode(
            name, language=language, country_codes=country_codes
        ).to_location(timezone=timezone)
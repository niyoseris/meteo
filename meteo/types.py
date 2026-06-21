"""Ortak veri tipleri — döngüsel import olmaması için ayrı modülde.

Bu modül `client`/`geocoding`/`weather` modüllerinin hepsinden bağımsız
ithal edilebilir; başka modüle bağımlılığı yoktur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    """Bir noktanın coğrafi konumu."""

    latitude: float
    longitude: float
    name: str = ""
    country: str = ""
    admin1: str = ""
    timezone: str = "auto"
    elevation: Optional[float] = None

    def __str__(self) -> str:
        parts = [self.name or f"({self.latitude}, {self.longitude})"]
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class GeocodingResult:
    """Geocoding API arama sonucu."""

    name: str
    latitude: float
    longitude: float
    country: str = ""
    country_code: str = ""
    admin1: str = ""
    admin2: str = ""
    timezone: str = ""
    population: Optional[int] = None
    elevation: Optional[float] = None
    feature_code: str = ""
    raw: dict = field(default_factory=dict)

    def to_location(self, timezone: str = "auto") -> Location:
        return Location(
            latitude=self.latitude,
            longitude=self.longitude,
            name=self.name,
            country=self.country,
            admin1=self.admin1,
            timezone=timezone,
            elevation=self.elevation,
        )
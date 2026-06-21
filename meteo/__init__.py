"""meteo — Open-Meteo verilerine tek paketten erişim.

Tek paket, tüm Open-Meteo API'leri:
  * Geocoding      — bölge adı → koordinat
  * Forecast       — anlık, saatlik, günlük tahmin
  * Historical      — geçmiş ölçümler (archive)
  * Climate        — iklim modeli verisi
  * Flood          — taşkın tahmini
  * Marine         — deniz/dalga verisi
  * Air Quality    — hava kalitesi
  * Elevation      — rakım

Örnek::

    from meteo import OpenMeteo
    m = OpenMeteo()
    yer = m.geocode("İstanbul")
    veri = m.forecast(yer, current=True)
"""

from .client import OpenMeteo, OpenMeteoError, APIError, Location
from .geocoding import GeocodingResult
from . import codes
from . import air_quality_ref
from . import metrics_ref
from . import interpret

__all__ = [
    "OpenMeteo",
    "OpenMeteoError",
    "APIError",
    "Location",
    "GeocodingResult",
    "codes",
    "air_quality_ref",
    "metrics_ref",
    "interpret",
]
__version__ = "0.1.0"
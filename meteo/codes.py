"""WMO hava durumu kodları (weather_code) → Türkçe açıklama ve emoji.

Open-Meteo `weather_code` alanı WMO yorum kodlarına karşılık gelir.
Burada okunabilir karşılıklar sağlanır.
"""

from __future__ import annotations

from typing import Dict, Tuple

# kod -> (emoji, Türkçe açıklama)
_WMO: Dict[int, Tuple[str, str]] = {
    0: ("☀️", "Açık"),
    1: ("🌤️", "Az bulutlu"),
    2: ("⛅", "Parçalı bulutlu"),
    3: ("☁️", "Kapalı"),
    45: ("🌫️", "Sisli"),
    48: ("🌫️", "Kırağılı sis"),
    51: ("🌦️", "Hafif çiseleme"),
    53: ("🌦️", "Çiseleme"),
    55: ("🌧️", "Yoğun çiseleme"),
    56: ("🌧️", "Dondurucu hafif çiseleme"),
    57: ("🌧️", "Dondurucu yoğun çiseleme"),
    61: ("🌧️", "Hafif yağmur"),
    63: ("🌧️", "Yağmur"),
    65: ("🌧️", "Şiddetli yağmur"),
    66: ("🌧️", "Dondurucu hafif yağmur"),
    67: ("🌧️", "Dondurucu şiddetli yağmur"),
    71: ("🌨️", "Hafif kar"),
    73: ("🌨️", "Kar"),
    75: ("❄️", "Şiddetli kar"),
    77: ("🌨️", "Kar taneleri"),
    80: ("🌦️", "Hafif sağanak"),
    81: ("🌧️", "Sağanak"),
    82: ("⛈️", "Şiddetli sağanak"),
    85: ("🌨️", "Hafif kar sağanağı"),
    86: ("❄️", "Şiddetli kar sağanağı"),
    95: ("⛈️", "Gök gürültülü fırtına"),
    96: ("⛈️", "Dolu ile hafif fırtına"),
    99: ("⛈️", "Dolu ile şiddetli fırtına"),
}


def describe(code: int) -> Tuple[str, str]:
    """`code` için (emoji, açıklama) döndürür; bilinmeyen için (?)."""
    return _WMO.get(int(code), ("❔", f"Kod {code}"))


def label(code: int) -> str:
    """Yalnızca Türkçe açıklama."""
    return describe(code)[1]


def emoji(code: int) -> str:
    """Yalnızca emoji."""
    return describe(code)[0]


def all_codes() -> Dict[int, Tuple[str, str]]:
    """Tüm kod tablosunu döndürür (debug/gösterim için)."""
    return dict(_WMO)
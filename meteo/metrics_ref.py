"""Metrik açıklama sözlüğü — "bu nedir" ve "kabul edilen referans".

Hava durumu metrikleri burada tanımlı; hava kalitesi metrikleri
`air_quality_ref.POLLUTANTS`'tan gelir. `info(key)` ikisini birleştirir.
"""

from __future__ import annotations

from typing import Optional

from . import air_quality_ref

WEATHER_METRICS = {
    "weather_code": {
        "what": "WMO hava durumu kodu; anlık gökyüzü ve yağış durumunu özetler.",
        "ref": "0=açık · 1-3=az/parçalı/kapalı bulut · 51-67=yağmur · 71-77=kar · 80-82=sağanak · 95-99=fırtına",
    },
    "temperature_2m": {
        "what": "2 metre yükseklikte hava sıcaklığı.",
        "ref": "İnsan konforu ~20-24 °C",
    },
    "apparent_temperature": {
        "what": "Hissedilen sıcaklık; rüzgâr, nem ve güneş etkisiyle bedenin algıladığı sıcaklık.",
        "ref": "Gerçek sıcaklıktan ± birkaç derece sapabilir",
    },
    "relative_humidity_2m": {
        "what": "2 m'de bağıl nem; havanın taşıyabileceği maksimum nemin yüzdesi.",
        "ref": "40-60% kapalı alan için konforlu",
    },
    "precipitation": {
        "what": "Son saatteki toplam yağış (sıvı eşdeğer; yağmur+kar birleşik).",
        "ref": "<0.5 mm hafif · 0.5-4 mm orta · >4 mm şiddetli",
    },
    "wind_speed_10m": {
        "what": "10 m yükseklikte rüzgâr hızı (km/s).",
        "ref": "<15 km/s hafif · 15-25 orta · 25-40 güçlü · >40 fırtınalı",
    },
    "wind_direction_10m": {
        "what": "Rüzgârın estiği yön (°). 0=K, 90=D, 180=G, 270=B.",
        "ref": "—",
    },
    "pressure_msl": {
        "what": "Deniz seviyesine indirgenmiş atmosfer basıncı (hPa).",
        "ref": "~1013 hPa standart · <1000 alçak (bozucu) · >1020 yüksek",
    },
    "cloud_cover": {
        "what": "Gökyüzünün bulutla kaplı oranı (%).",
        "ref": "0=açık · 0-25 az · 25-75 parçalı · 75-100 kapalı",
    },
    "elevation": {
        "what": "Noktanın denizden yüksekliği (m).",
        "ref": "—",
    },
    "us_aqi": {  # indeks de burada açıklanabilir (AQ ref ile aynı)
        "what": "ABD hava kalitesi indeksi (0-500); tüm kirleticilerin birleşik sağlık etkisi.",
        "ref": "0-50 iyi · 51-100 orta · 101-150 hassas · 151-200 sağlıksız · 201-300 çok sağlıksız · 301+ tehlikeli",
    },
    "european_aqi": {
        "what": "Avrupa hava kalitesi indeksi (0-100); günlük toplam hava kalitesi etkisi.",
        "ref": "0-20 iyi · 21-40 makul · 41-60 orta · 61-80 kötü · 81-100 çok kötü",
    },
}


def info(key: str) -> dict:
    """Bir metrik için {what, ref} döndürür. AQ ise air_quality_ref'ten, hava ise buradan."""
    if key in WEATHER_METRICS:
        e = WEATHER_METRICS[key]
        return {"what": e["what"], "ref": e["ref"]}
    aq = air_quality_ref.POLLUTANTS.get(key)
    if aq:
        return {"what": aq["what"], "ref": aq["ref"]}
    return {"what": "", "ref": ""}
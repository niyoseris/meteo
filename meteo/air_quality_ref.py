"""Hava kalitesi kirleticileri için referans veriler.

Her kirletici için:
  * `label`  — okunabilir ad
  * `unit`   — birim
  * `what`   — "bu nedir" açıklaması (Türkçe)
  * `ref`    — kabul edilen/ortalam referans değer (WHO, EU, AQI bantları)
  * `bands`  — (üst_sınır, derece_etiketi, css_sınıfı) listesi (artan sırada)

`rate(key, value)` fonksiyonu bir değeri uygun banda yerleştirir ve
(derece_etiketi, css_sınıfı) döndürür. Bantlar WHO 2021 hava kalitesi
kılavuzları ile AB/ABD AQI sınıflandırmalarına dayanır.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# css_sınıfı -> (etiket renk için) — şablon/CSS ile uyumlu.
# good / moderate / poor / verypoor

POLLUTANTS: Dict[str, dict] = {
    # --- Genel indeksler (önce gösterilir) ---
    "us_aqi": {
        "label": "ABD AQI",
        "unit": "indeks",
        "what": "ABD hava kalitesi indeksi (0–500); tüm kirleticilerin birleşik sağlık etkisini tek sayıda özetler.",
        "ref": "0-50 iyi · 51-100 orta · 101-150 hassaslar için sağlıksız · 151-200 sağlıksız · 201-300 çok sağlıksız · 301+ tehlikeli",
        "bands": [
            (50, "İyi", "good"),
            (100, "Orta", "moderate"),
            (150, "Hassaslar için sağlıksız", "poor"),
            (200, "Sağlıksız", "poor"),
            (300, "Çok sağlıksız", "verypoor"),
            (10_000, "Tehlikeli", "verypoor"),
        ],
    },
    "european_aqi": {
        "label": "AB AQI",
        "unit": "indeks",
        "what": "Avrupa hava kalitesi indeksi (0–100); günlük toplam hava kalitesi etkisini özetler.",
        "ref": "0-20 iyi · 21-40 makul · 41-60 orta · 61-80 kötü · 81-100 çok kötü",
        "bands": [
            (20, "İyi", "good"),
            (40, "Makul", "moderate"),
            (60, "Orta", "moderate"),
            (80, "Kötü", "poor"),
            (100, "Çok kötü", "verypoor"),
            (10_000, "Aşırı kötü", "verypoor"),
        ],
    },
    # --- Partiküller ---
    "pm2_5": {
        "label": "PM2.5",
        "unit": "µg/m³",
        "what": "Çapı 2.5 mikrometreden küçük ince partikül madde; akciğere derin sızar, kardiyovasküler ve solunum riskini artırır.",
        "ref": "WHO 24 saat ortalaması: 15 µg/m³ (yıllık: 5)",
        "bands": [
            (15, "İyi", "good"),
            (35, "Orta", "moderate"),
            (55, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    "pm10": {
        "label": "PM10",
        "unit": "µg/m³",
        "what": "Çapı 10 mikrometreden küçük partikül madde; toz, polen ve trafik kaynaklı; solunum yollarını tahriş eder.",
        "ref": "WHO 24 saat ortalaması: 45 µg/m³ (yıllık: 15)",
        "bands": [
            (45, "İyi", "good"),
            (75, "Orta", "moderate"),
            (100, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    "dust": {
        "label": "Çöl tozu (PM10)",
        "unit": "µg/m³",
        "what": "Sahra/çöl kaynaklı uzun menzilli toz taşınımı; PM10 eşdeğeri partikül.",
        "ref": "PM10 eşdeğer · WHO 24 saat: 45 µg/m³",
        "bands": [
            (50, "İyi", "good"),
            (100, "Orta", "moderate"),
            (200, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    # --- Gazlar ---
    "ozone": {
        "label": "Ozon (O₃)",
        "unit": "µg/m³",
        "what": "Yüzeye yakın ozon; sıcak ve güneşli havada NOx ve VOC'lerden oluşur, solunum sistemine zarar verir.",
        "ref": "WHO 8 saat ortalaması: 100 µg/m³",
        "bands": [
            (100, "İyi", "good"),
            (140, "Orta", "moderate"),
            (180, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    "nitrogen_dioxide": {
        "label": "Azot dioksit (NO₂)",
        "unit": "µg/m³",
        "what": "Trafik ve yakma kaynaklı NO₂; solunum yolu iltihabına yol açar.",
        "ref": "WHO 24 saat ortalaması: 25 µg/m³ (yıllık: 10)",
        "bands": [
            (25, "İyi", "good"),
            (50, "Orta", "moderate"),
            (100, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    "sulphur_dioxide": {
        "label": "Kükürt dioksit (SO₂)",
        "unit": "µg/m³",
        "what": "Kömür ve yakıt yanması kaynaklı SO₂; astımı tetikler, asit yağmuruna neden olur.",
        "ref": "WHO 24 saat ortalaması: 40 µg/m³",
        "bands": [
            (40, "İyi", "good"),
            (80, "Orta", "moderate"),
            (125, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    "carbon_monoxide": {
        "label": "Karbon monoksit (CO)",
        "unit": "µg/m³",
        "what": "Renksiz, kokusuz yanma gazı; kanda oksijen taşınmasını engeller.",
        "ref": "WHO 24 saat ortalaması: 4000 µg/m³ (4 mg/m³)",
        "bands": [
            (1000, "İyi", "good"),
            (4000, "Orta", "moderate"),
            (10000, "Kötü", "poor"),
            (1_000_000, "Çok kötü", "verypoor"),
        ],
    },
    "ammonia": {
        "label": "Amonyak (NH₃)",
        "unit": "µg/m³",
        "what": "Tarım ve hayvancılık kaynaklı NH₃; atmosferde partikül oluşumuna katkıda bulunur.",
        "ref": "Yaygın WHO sınırı yok · kırsalda tipik <10 µg/m³",
        "bands": [
            (100, "İyi", "good"),
            (200, "Orta", "moderate"),
            (500, "Kötü", "poor"),
            (10_000, "Çok kötü", "verypoor"),
        ],
    },
    # --- Diğer ---
    "uv_index": {
        "label": "UV indeksi",
        "unit": "indeks",
        "what": "Güneşin ultraviyole radyasyon şiddeti; cilt hasarı ve güneş yanma riskini gösterir.",
        "ref": "0-2 düşük · 3-5 orta · 6-7 yüksek · 8-10 çok yüksek · 11+ aşırı",
        "bands": [
            (2, "Düşük", "good"),
            (5, "Orta", "moderate"),
            (7, "Yüksek", "poor"),
            (10, "Çok yüksek", "verypoor"),
            (10_000, "Aşırı", "verypoor"),
        ],
    },
}

# Görüntüleme sırası — önce genel indeksler, sonra partiküller, sonra gazlar.
ORDER: List[str] = [
    "us_aqi", "european_aqi",
    "pm2_5", "pm10", "dust",
    "ozone", "nitrogen_dioxide", "sulphur_dioxide",
    "carbon_monoxide", "ammonia", "uv_index",
]


def rate(key: str, value) -> Optional[Tuple[str, str]]:
    """`value` için (derece_etiketi, css_sınıfı) döndürür.

    Değer None ise veya kirletici bilinmiyorsa None döner.
    """
    entry = POLLUTANTS.get(key)
    if not entry or value is None:
        return None
    for limit, label, cls in entry["bands"]:
        if value <= limit:
            return label, cls
    # Tüm bantların üstündeyse en kötü bant.
    return entry["bands"][-1][1], entry["bands"][-1][2]


def metric_info(key: str, value) -> Optional[dict]:
    """Tek bir kirletici için tam görüntüleme bilgisi hazırlar.

    Dönüş: {key, label, value, unit, what, ref, rating, rating_class, ok}
    `ok` False ise değer yok (None) demektir — şablon boş gösterebilir.
    """
    entry = POLLUTANTS.get(key)
    if not entry:
        return None
    info = {
        "key": key,
        "label": entry["label"],
        "value": value,
        "unit": entry["unit"],
        "what": entry["what"],
        "ref": entry["ref"],
        "rating": None,
        "rating_class": None,
        "ok": value is not None,
    }
    r = rate(key, value)
    if r:
        info["rating"], info["rating_class"] = r
    return info


def build_table(current: dict) -> List[dict]:
    """`air_quality.current` sözlüğünden sıralı görüntüleme listesi üretir.

    Yalnızca `current` içinde bulunan ve referans tablosunda tanımlı
    kirleticileri ORDER sırasıyla döndürür.
    """
    if not isinstance(current, dict):
        return []
    rows = []
    for key in ORDER:
        if key in current:
            info = metric_info(key, current.get(key))
            if info:
                rows.append(info)
    return rows
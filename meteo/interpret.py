"""Veri yorumlama motoru — "bu değer gerçek yerel sinyal mi, model arka planı mı?"

İki temel mekanizma:

1) **Uzaysal gradyan testi (spatial probe)**: Bir noktanın değerini, aynı
   andaki ~model çözünürlüğü kadar uzaktaki 4 komşu noktayla (K/G/D/B)
   karşılaştırır. Merkez komşulardan ayırt edilemiyorsa değer **bölgesel
   arka plan / ızgara ortalamasıdır** (yerel kaynak sinyali yok). Merkez
   belirgin bir aykırılıksa **yerel kaynak sinyali olabilir**. Bu, tek bir
   bacayı/trafiği çözümleyemeyen kaba atmosfer modellerinde hangi
   kirleticilerin "gerçek" okunabileceğini, hangilerinin arka plan olduğunu
   otomatik belirler — CO özel durumu değil, tüm kirleticiler için geçerli.

2) **Bağlam ve kaynak meta-verisi**: Her kirletici için tipik arka plan
   aralığı, "yerel sinyal neyi işaret eder" ve her API'nin veri kaynağı /
   çözünürlük notu.

Sonuç, hem yapısal (JSON) hem de Türkçe özet olarak alınabilir.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Optional, Tuple, Union

from .client import OpenMeteo, Location, GeocodingResult

# ---------------------------------------------------------------------------
# Veri kaynağı meta-verisi
# ---------------------------------------------------------------------------
SOURCES: Dict[str, dict] = {
    "forecast": {
        "provider": "Çeşitli ulusal hava durumu modelleri (ICON, GFS, MeteoFrance …)",
        "resolution": "~10–25 km ızgara",
        "caveat": "Model tahmini; nokta ölçümü değil. Yerel mikro-iklim çözülemez.",
    },
    "air_quality": {
        "provider": "CAMS (Copernicus Atmosfer İzleme Servisi) atmosfer modeli",
        "resolution": "~10–40 km ızgara (küresel ~40 km, Avrupa ~10 km)",
        "caveat": "Izgara hücre ortalamasıdır, yer seviyesi nokta ölçümü değildir. "
                  "Tek baca/trafik gibi nokta kaynakları yer seviyesinde çözülemez.",
    },
    "marine": {
        "provider": "Meteo France wave modeli",
        "resolution": "Bölgesel deniz ızgarası",
        "caveat": "Kara içi noktalarda veri olmaz; sahile yakın noktalarda yaklaşık.",
    },
    "flood": {
        "provider": "GloFAS (Global Flood Awareness System)",
        "resolution": "~10 km ızgara, nehir ağı boyunca",
        "caveat": "Büyük nehir havzaları için; küçük dereler çözülemez.",
    },
    "elevation": {
        "provider": "Copernicus DEM / SRTM",
        "resolution": "~30 m",
        "caveat": "Yüksek çözünürlüklü topoğrafya — noktasal olarak güvenilir.",
    },
    "historical": {
        "provider": "ERA5 reanaliz + istasyon enterpolasyonu",
        "resolution": "~25 km ızgara",
        "caveat": "Geçmiş reanaliz; yerel değil bölgesel ortalamaya yatkın.",
    },
}

# ---------------------------------------------------------------------------
# Kirletici bağlamı: tipik arka plan + yerel kaynak imzası
# ---------------------------------------------------------------------------
# arka_plan: (alt, üst) µg/m³ — temiz/arka plan sitede beklenen değer.
# kaynak: bir YEREL sinyal bu kirleticide görülürse neyi işaret eder.
AQ_CONTEXT: Dict[str, dict] = {
    "pm2_5": {
        "label": "PM2.5", "unit": "µg/m³",
        "arka_plan": (3, 15),
        "kaynak": "Trafik, sanayi, ısınma, yangın — yerel kentsel imza verir.",
    },
    "pm10": {
        "label": "PM10", "unit": "µg/m³",
        "arka_plan": (5, 25),
        "kaynak": "Yol/ınşaat tozu, çöl tozu — PM2.5'ten daha yerel/kabalıksız.",
    },
    "ozone": {
        "label": "Ozon (O₃)", "unit": "µg/m³",
        "arka_plan": (60, 100),
        "kaynak": "Sıcak+güneşli havada NOx/VOC'den oluşur; genelde bölgesel, "
                  "yerel nokta kaynağı zayıf.",
    },
    "nitrogen_dioxide": {
        "label": "Azot dioksit (NO₂)", "unit": "µg/m³",
        "arka_plan": (0.5, 6),
        "kaynak": "TRAFİK ve yakma — en iyi yerel kentsel/trafik göstergesi.",
    },
    "sulphur_dioxide": {
        "label": "Kükürt dioksit (SO₂)", "unit": "µg/m³",
        "arka_plan": (0.3, 4),
        "kaynak": "Kömür/yakıt sanayi, gemiler, termik santral — yerel sinyal "
                  "verebilen endüstriyel gösterge.",
    },
    "carbon_monoxide": {
        "label": "Karbon monoksit (CO)", "unit": "µg/m³",
        "arka_plan": (80, 200),
        "kaynak": "Trafik yerel CO verir; termik santral CO'su yer seviyesinde "
                  "zayıftır (verimli yanma + baca yukarıda dağılır). CO uzun "
                  "ömürlü olduğundan çoğunlukla bölgesel arka plandır.",
    },
    "ammonia": {
        "label": "Amonyak (NH₃)", "unit": "µg/m³",
        "arka_plan": (1, 12),
        "kaynak": "Tarım/hayvancılık — yoğun tarım bölgelerinde yerel sinyal.",
    },
    "dust": {
        "label": "Çöl tozu", "unit": "µg/m³",
        "arka_plan": (0, 20),
        "kaynak": "Çöl tozu taşınımı — bölgesel/epizodik, yerel nokta kaynağı değil.",
    },
}

# Uzaysal proba dahil edilecek kirleticiler (indeksler hariç).
PROBE_VARS: List[str] = [
    "pm2_5", "pm10", "ozone", "nitrogen_dioxide",
    "sulphur_dioxide", "carbon_monoxide", "ammonia", "dust",
]


# ---------------------------------------------------------------------------
# Uzaysal gradyan testi
# ---------------------------------------------------------------------------
def spatial_probe(
    client: OpenMeteo,
    location: Union[Location, GeocodingResult, Tuple[float, float]],
    variables: Optional[List[str]] = None,
    *,
    offset_deg: float = 0.3,
) -> Dict[str, dict]:
    """Merkez + 4 komşu (K/G/D/B) noktayı sorgular, değişken başına
    uzaysal dağılım istatistiği ve bir **verdict** üretir.

    Dönüş: {variable: {center, neighbors, mean, std, cv, center_dev, verdict, note}}
    """
    variables = variables or PROBE_VARS
    if isinstance(location, (Location, GeocodingResult)):
        lat0, lon0 = location.latitude, location.longitude
    else:
        lat0, lon0 = location

    offsets = [
        (lat0, lon0),                       # merkez
        (lat0 + offset_deg, lon0),          # kuzey
        (lat0 - offset_deg, lon0),          # güney
        (lat0, lon0 + offset_deg),          # doğu
        (lat0, lon0 - offset_deg),          # batı
    ]
    var_str = ",".join(variables)

    samples: Dict[str, List[float]] = {v: [] for v in variables}
    for (la, lo) in offsets:
        try:
            d = client.fetch_raw(
                "air_quality",
                {"latitude": round(la, 4), "longitude": round(lo, 4),
                 "current": var_str, "timezone": "auto"},
            )
            cur = d.get("current", {})
        except Exception:
            cur = {}
        for v in variables:
            val = cur.get(v)
            samples[v].append(val)

    result: Dict[str, dict] = {}
    for v in variables:
        vals = samples[v]
        center = vals[0]
        neighbors = vals[1:]
        # None'ları temizle (bazı kirleticiler bazı modellerde olmayabilir).
        nb = [x for x in neighbors if x is not None]
        if center is None or len(nb) < 2:
            result[v] = {"verdict": "no_data", "note": "Veri yok."}
            continue

        mean_n = statistics.fmean(nb)
        std_n = statistics.pstdev(nb) if len(nb) > 1 else 0.0
        cv = (std_n / mean_n) if mean_n else 0.0
        center_dev = (abs(center - mean_n) / std_n) if std_n else (
            0.0 if abs(center - mean_n) < 1e-6 else 99.0
        )

        if cv < 0.06 and center_dev < 1.5:
            verdict, note = "uniform", (
                "Komşu noktalarla neredeyse aynı → bölgesel arka plan / "
                "ızgara ortalaması. Yerel nokta kaynak sinyali yok."
            )
        elif center_dev > 2.5 and center > mean_n:
            verdict, note = "local_high", (
                "Merkez komşulardan belirgin yüksek → yerel kaynak sinyali olabilir."
            )
        elif center_dev > 2.5 and center < mean_n:
            verdict, note = "local_low", (
                "Merkez komşulardan belirgin düşük → yerel bir düşüş/nokta etkisi."
            )
        else:
            verdict, note = "gradient", (
                "Bölgesel gradyan var; yerel sinyal zayıf/belirsiz."
            )

        result[v] = {
            "center": center, "neighbors": neighbors,
            "mean": round(mean_n, 3), "std": round(std_n, 3),
            "cv": round(cv, 4), "center_dev": round(center_dev, 3),
            "verdict": verdict, "note": note,
        }
    return result


# ---------------------------------------------------------------------------
# Yorum derleme
# ---------------------------------------------------------------------------
def interpret_aq(
    client: OpenMeteo,
    location: Union[Location, GeocodingResult, Tuple[float, float]],
    *,
    current: Optional[dict] = None,
    variables: Optional[List[str]] = None,
    offset_deg: float = 0.3,
) -> dict:
    """Bir nokta için hava kalitesi yorumu üretir.

    1) Merkezin anlık değerlerini alır (current verilmezse sorgular).
    2) Uzaysal probu çalıştırır.
    3) Kirletici bağlamıyla her değişken için arka plan karşılaştırması ve
       yerel kaynak yorumu ekler.
    4) Genel bir Türkçe özet üretir.
    """
    variables = variables or PROBE_VARS
    if isinstance(location, (Location, GeocodingResult)):
        lat0, lon0 = location.latitude, location.longitude
    else:
        lat0, lon0 = location

    if current is None:
        d = client.fetch_raw(
            "air_quality",
            {"latitude": round(lat0, 4), "longitude": round(lon0, 4),
             "current": ",".join(variables), "timezone": "auto"},
        )
        current = d.get("current", {})

    probe = spatial_probe(client, (lat0, lon0), variables, offset_deg=offset_deg)

    rows: List[dict] = []
    for v in variables:
        ctx = AQ_CONTEXT.get(v, {})
        val = current.get(v)
        p = probe.get(v, {})
        lo, hi = ctx.get("arka_plan", (None, None))
        in_background = None
        if val is not None and lo is not None:
            in_background = lo <= val <= hi
        rows.append({
            "key": v,
            "label": ctx.get("label", v),
            "unit": ctx.get("unit", ""),
            "value": val,
            "arka_plan": [lo, hi],
            "in_background": in_background,
            "kaynak": ctx.get("kaynak", ""),
            "verdict": p.get("verdict"),
            "verdict_note": p.get("note", ""),
            "stats": {k: p.get(k) for k in ("mean", "std", "cv", "center_dev")},
        })

    summary = _summarize(rows)
    return {
        "location": {"latitude": lat0, "longitude": lon0},
        "source": SOURCES["air_quality"],
        "offset_deg": offset_deg,
        "rows": rows,
        "summary": summary,
    }


def _summarize(rows: List[dict]) -> str:
    """Genel Türkçe özet cümlesi(leri)."""
    have = [r for r in rows if r["value"] is not None and r["verdict"] != "no_data"]
    if not have:
        return "Yorum için yeterli veri bulunamadı."
    uniform = [r for r in have if r["verdict"] == "uniform"]
    local = [r for r in have if r["verdict"] in ("local_high", "local_low")]

    parts: List[str] = []
    parts.append(
        f"{len(have)} kirletici analiz edildi, {len(uniform)} tanesi komşu "
        f"noktalarla neredeyle aynı (bölgesel arka plan)."
    )
    if local:
        labels = ", ".join(r["label"] for r in local)
        parts.append(
            f"Yerel sinyal olabilecek kirleticiler: {labels}. "
            "Bunlar gerçek bir nokta kaynağını (trafik/sanayi/…) yansıtıyor olabilir."
        )
    else:
        parts.append(
            "Hiçbir kirleticide belirgin yerel nokta sinyali yok — değerler "
            "bölgesel arka plan/ızgara ortalamasıyla uyumlu. Tek baca veya "
            "trafik gibi nokta kaynakları bu modelin çözünürlüğünde görülmez."
        )
    # arka plan dışı (yüksek) ama yine de uniform olanlar için not.
    high_bg = [r for r in uniform if r["in_background"] is False and r["value"] is not None]
    if high_bg:
        labels = ", ".join(r["label"] for r in high_bg)
        parts.append(
            f"Arka plan aralığının dışında olanlar: {labels}. "
            "Bölgesel/sezonsal bir yükselme olabilir; yerel kaynak değil bölgesel etki."
        )
    return " ".join(parts)


def source_note(kind: str) -> Optional[dict]:
    """Bir API türü için veri kaynağı notunu döndürür."""
    return SOURCES.get(kind)
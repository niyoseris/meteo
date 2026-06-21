"""Komut satırı arayüzü.

Kullanım örnekleri::

    # Anlık + günlük tahmin (varsayılan)
    python -m meteo "İstanbul"

    # Hepsini al (forecast + air quality + marine + flood + elevation)
    python -m meteo "İstanbul" --all

    # Geçmiş veri
    python -m meteo "İzmir" --historical 2025-01-01 2025-01-31

    # Doğrudan koordinat
    python -m meteo --lat 41.01 --lon 28.95 --forecast --hourly --daily

    # Bölge araması (enlem/boylam listesi)
    python -m meteo --search "Ankara"

Çıktı JSON olarak basılır; --pretty ile girintili, --save ile dosyaya yazılır.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from .client import OpenMeteo, OpenMeteoError, APIError, Location
from .types import GeocodingResult


def _resolve_location(args: argparse.Namespace, m: OpenMeteo):
    """Argümanlardan bir konum çözümler (Location veya demet)."""
    if args.lat is not None and args.lon is not None:
        return Location(
            latitude=args.lat,
            longitude=args.lon,
            name=args.name or "",
            timezone=args.timezone or "auto",
        )
    if not args.place:
        raise SystemExit("Hata: bir bölge adı veya --lat/--lon verilmeli.")
    return m.geocode_location(args.place, timezone=args.timezone or "auto")


def _dump(data: Any, args: argparse.Namespace) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Yazıldı: {args.save}", file=sys.stderr)
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="meteo",
        description="Open-Meteo verilerine erişim — istediğin bölgenin tüm verileri.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("place", nargs="?", help="Bölge adı (ör. 'İstanbul', 'Berlin, DE')")
    p.add_argument("--lat", type=float, help="Doğrudan enlem")
    p.add_argument("--lon", type=float, help="Doğrudan boylam")
    p.add_argument("--name", help="--lat/--lon için etiket")
    p.add_argument("--timezone", default=None, help="Saat dilimi (varsayılan: auto)")
    p.add_argument("--language", default="tr", help="Geocoding dili (varsayılan: tr)")
    p.add_argument("--country", default=None, help="Geocoding ülke kodu (ör. TR)")

    g = p.add_argument_group("Veri seçimi (en az biri gerekir)")
    g.add_argument("--all", action="store_true", help="Eldeki tüm API'leri çağır")
    g.add_argument("--forecast", action="store_true", help="Tahmin (anlık/saatlik/günlük)")
    g.add_argument("--current", action="store_true", help="Tahmin içinde anlık değerler")
    g.add_argument("--hourly", action="store_true", help="Tahmin içinde saatlik değerler")
    g.add_argument("--daily", action="store_true", help="Tahmin içinde günlük değerler")
    g.add_argument("--historical", nargs=2, metavar=("BASLANGIC", "BITIS"), help="Geçmiş ölçümler (YYYY-MM-DD)")
    g.add_argument("--historical-forecast", nargs=2, metavar=("BASLANGIC", "BITIS"))
    g.add_argument("--climate", nargs=2, metavar=("BASLANGIC", "BITIS"), help="İklim modeli verisi")
    g.add_argument("--marine", action="store_true", help="Deniz/dalga tahmini")
    g.add_argument("--flood", action="store_true", help="Taşkın/nehir debisi")
    g.add_argument("--air-quality", dest="air_quality", action="store_true", help="Hava kalitesi")
    g.add_argument("--elevation", action="store_true", help="Rakım")
    g.add_argument("--search", action="store_true", help="Bölge araması (koordinat listesi)")

    p.add_argument("--forecast-days", type=int, default=7)
    p.add_argument("--past-days", type=int, default=0)
    p.add_argument("--marine-days", type=int, default=7)
    p.add_argument("--flood-days", type=int, default=30)
    p.add_argument("--aq-days", dest="aq_days", type=int, default=5)
    p.add_argument("--hourly-vars", help="Saatlik değişkenleri geçersiz kıl (virgülle)")
    p.add_argument("--daily-vars", help="Günlük değişkenleri geçersiz kıl (virgülle)")

    p.add_argument("--pretty", action="store_true", help="Girintili JSON")
    p.add_argument("--save", help="Sonucu dosyaya yaz")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--retries", type=int, default=3)
    return p


def run(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    m = OpenMeteo(timeout=args.timeout, retries=args.retries)

    # 1) Arama modu: sadece listele, çık.
    if args.search:
        if not args.place:
            raise SystemExit("Hata: --search için bir bölge adı verilmeli.")
        results = m.geocode_search(
            args.place, language=args.language, country_codes=args.country
        )
        _dump(
            [
                {
                    "name": r.name,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "country": r.country,
                    "admin1": r.admin1,
                    "population": r.population,
                    "elevation": r.elevation,
                    "timezone": r.timezone,
                }
                for r in results
            ],
            args,
        )
        return 0

    loc = _resolve_location(args, m)
    tz = loc.timezone if isinstance(loc, Location) else (args.timezone or "auto")

    # --all hepsini bir arada getirir.
    if args.all:
        data = m.all(
            loc,
            forecast_days=args.forecast_days,
            past_days=args.past_days,
            air_quality_days=args.aq_days,
            marine_days=args.marine_days,
            flood_days=args.flood_days,
        )
        if isinstance(loc, Location):
            data["location"] = {
                "name": loc.name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "country": loc.country,
                "timezone": tz,
            }
        _dump(data, args)
        return 0

    # Tek/seçili API'ler.
    out: dict = {}

    if args.forecast or args.current or args.hourly or args.daily:
        out["forecast"] = m.forecast(
            loc,
            current=args.current or False,
            hourly=(args.hourly_vars or True) if args.hourly else False,
            daily=(args.daily_vars or True) if args.daily else False,
            forecast_days=args.forecast_days,
            past_days=args.past_days,
            timezone=tz,
        )

    if args.historical:
        start, end = args.historical
        out["historical"] = m.historical(
            loc, start_date=start, end_date=end, daily=True, hourly=args.hourly, timezone=tz
        )

    if args.historical_forecast:
        start, end = args.historical_forecast
        out["historical_forecast"] = m.historical_forecast(
            loc, start_date=start, end_date=end, daily=True, timezone=tz
        )

    if args.climate:
        start, end = args.climate
        out["climate"] = m.climate(loc, start_date=start, end_date=end, timezone=tz)

    if args.marine:
        out["marine"] = m.marine(
            loc, hourly=True, forecast_days=args.marine_days, past_days=args.past_days, timezone=tz
        )

    if args.flood:
        out["flood"] = m.flood(loc, daily=True, forecast_days=args.flood_days, timezone=tz)

    if args.air_quality:
        out["air_quality"] = m.air_quality(
            loc, current=True, hourly=True, forecast_days=args.aq_days, past_days=args.past_days, timezone=tz
        )

    if args.elevation:
        out["elevation"] = m.elevation(loc)

    if not out:
        # Veri seçilmediyse varsayılan: anlık + günlük tahmin.
        out["forecast"] = m.forecast(
            loc, current=True, daily=True, forecast_days=args.forecast_days, timezone=tz
        )

    if isinstance(loc, Location):
        out["_location"] = {
            "name": loc.name,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "country": loc.country,
            "timezone": tz,
        }

    _dump(out, args)
    return 0


def main() -> int:
    try:
        return run()
    except (OpenMeteoError, APIError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
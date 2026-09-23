#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 v1.8 CHALLENGER — GLOBAL EVENT INTELLIGENCE COLLECTOR
============================================================

Objetivo:
- Crear un dataset point-in-time de noticias + contexto de mercado/macro.
- Cada ejecución APPENDEA; nunca reescribe observaciones antiguas.
- Las noticias guardan hora de publicación cuando está disponible y,
  sobre todo, la hora exacta en que fueron observadas por nuestro sistema.
- Este dataset NO modifica v1.7-FROZEN.

Fuentes sin API key:
- Google News RSS search
- Yahoo Finance (mercado)
- FRED (macro)

No usa sentimiento "mágico": guarda features reproducibles y un score léxico
simple como punto de partida. El Challenger posterior decidirá si aportan edge.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "\nFalta yfinance.\nEjecuta:\n  py -m pip install yfinance\n"
    )

OUT = Path("mfp3_event_intelligence")
RAW_EVENTS = OUT / "events_raw.jsonl"
DAILY_FEATURES = OUT / "daily_event_features.csv"
MARKET_CONTEXT = OUT / "market_context.csv"
SEEN_IDS = OUT / "seen_event_ids.txt"

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# Query intentionally broad; we'll tag later.
QUERIES = {
    "QQQ": [
        'Nasdaq OR technology stocks OR semiconductors OR artificial intelligence',
        'Federal Reserve OR US inflation OR US jobs OR Treasury yields',
    ],
    "ECH": [
        'Chile economy OR Chile central bank OR Chile peso OR Chile inflation',
        'Chile copper OR Chile lithium OR Chile mining',
    ],
    "CPER": [
        'copper price OR copper demand OR copper supply OR LME copper',
        'China copper OR China manufacturing OR copper mine disruption',
        'Chile Peru Congo copper mine OR copper strike',
    ],
    "GLOBAL": [
        'geopolitical risk markets OR sanctions commodities OR tariffs markets',
        'China stimulus OR China PMI OR China property market',
    ],
}

TICKERS = [
    "QQQ", "ECH", "CPER", "SPY", "EEM", "FXI",
    "HG=F", "GC=F", "^VIX", "TLT", "UUP", "CLP=X"
]

FRED = {
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "FEDFUNDS": "DFF",
    "WTI": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
}

POSITIVE_WORDS = {
    "surge", "rise", "rally", "gain", "growth", "strong", "beat",
    "stimulus", "cut", "easing", "recovery", "record", "upgrade",
    "expansion", "rebound", "support", "deal", "ceasefire",
}
NEGATIVE_WORDS = {
    "fall", "drop", "slump", "crash", "weak", "miss", "war",
    "sanction", "tariff", "strike", "shutdown", "inflation", "hike",
    "recession", "default", "downgrade", "disruption", "shortage",
    "attack", "conflict", "risk",
}
HIGH_IMPACT_WORDS = {
    "federal reserve", "central bank", "inflation", "jobs", "payroll",
    "cpi", "pmi", "tariff", "sanction", "war", "strike", "mine",
    "china", "stimulus", "interest rate", "copper", "treasury",
}

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def fetch_url(url: str, timeout=20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; MFP3Research/1.0; "
                "+paper-trading-research)"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def google_news_rss(query: str, max_items=50) -> List[dict]:
    q = urllib.parse.quote(query)
    url = (
        "https://news.google.com/rss/search?"
        f"q={q}&hl=en-US&gl=US&ceid=US:en"
    )

    try:
        xml = fetch_url(url)
        root = ET.fromstring(xml)
    except Exception as e:
        print("  RSS error:", query, e)
        return []

    out = []
    for item in root.findall(".//item")[:max_items]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or ""
        source_node = item.find("source")
        source = source_node.text if source_node is not None else ""

        try:
            published = parsedate_to_datetime(pub).astimezone(
                timezone.utc
            ).isoformat(timespec="seconds")
        except Exception:
            published = None

        out.append({
            "title": html.unescape(title).strip(),
            "url": link.strip(),
            "source": (source or "").strip(),
            "published_at_utc": published,
        })

    return out

def clean_words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z]+", text.lower())

def lexical_scores(title: str) -> dict:
    words = clean_words(title)
    pos = sum(w in POSITIVE_WORDS for w in words)
    neg = sum(w in NEGATIVE_WORDS for w in words)

    lower = title.lower()
    impact = sum(term in lower for term in HIGH_IMPACT_WORDS)

    sentiment = (pos - neg) / max(1, pos + neg)
    return {
        "lexical_sentiment": float(sentiment),
        "positive_hits": int(pos),
        "negative_hits": int(neg),
        "impact_keyword_hits": int(impact),
    }

def event_id(title: str, source: str, published: str | None) -> str:
    s = f"{title}|{source}|{published}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_seen() -> set:
    if not SEEN_IDS.exists():
        return set()
    return set(
        x.strip()
        for x in SEEN_IDS.read_text(encoding="utf-8").splitlines()
        if x.strip()
    )

def append_seen(ids: List[str]):
    if not ids:
        return
    with SEEN_IDS.open("a", encoding="utf-8") as f:
        for x in ids:
            f.write(x + "\n")

def append_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def collect_news() -> List[dict]:
    seen = load_seen()
    new_ids = []
    events = []

    retrieved = now_utc()

    for tag, queries in QUERIES.items():
        for query in queries:
            print(f"Noticias [{tag}]: {query}")
            items = google_news_rss(query)

            for item in items:
                eid = event_id(
                    item["title"],
                    item["source"],
                    item["published_at_utc"],
                )
                if eid in seen:
                    continue

                score = lexical_scores(item["title"])
                event = {
                    "event_id": eid,
                    "retrieved_at_utc": retrieved,
                    "published_at_utc": item["published_at_utc"],
                    "asset_tag": tag,
                    "query": query,
                    **item,
                    **score,
                }
                append_jsonl(RAW_EVENTS, event)
                events.append(event)
                new_ids.append(eid)

    append_seen(new_ids)
    return events

def latest_yahoo_context() -> dict:
    raw = yf.download(
        TICKERS,
        period="90d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    row = {"recorded_at_utc": now_utc()}

    for t in TICKERS:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                l0 = raw.columns.get_level_values(0)
                l1 = raw.columns.get_level_values(1)
                if t in l0:
                    d = raw[t]
                elif t in l1:
                    d = raw.xs(t, axis=1, level=1)
                else:
                    continue
            else:
                d = raw

            close = pd.to_numeric(
                d["Close"], errors="coerce"
            ).dropna()

            if close.empty:
                continue

            safe = (
                t.replace("^", "")
                .replace("=", "_")
                .replace("-", "_")
                .lower()
            )

            row[f"{safe}_close"] = float(close.iloc[-1])
            for n in [1, 5, 20, 60]:
                if len(close) > n:
                    row[f"{safe}_ret_{n}"] = float(
                        close.iloc[-1] / close.iloc[-1-n] - 1
                    )

            if len(close) >= 20:
                r = close.pct_change().dropna().tail(20)
                row[f"{safe}_vol20"] = float(
                    r.std() * np.sqrt(252)
                )

        except Exception as e:
            print("  Yahoo context error", t, e)

    return row

def latest_fred_context() -> dict:
    row = {}

    for name, sid in FRED.items():
        try:
            df = pd.read_csv(FRED_URL.format(sid=sid))
            vcol = df.columns[1]
            vals = pd.to_numeric(
                df[vcol], errors="coerce"
            ).dropna()

            if vals.empty:
                continue

            row[f"fred_{name.lower()}"] = float(vals.iloc[-1])

            if len(vals) > 5:
                row[f"fred_{name.lower()}_chg5"] = float(
                    vals.iloc[-1] - vals.iloc[-6]
                )
            if len(vals) > 20:
                row[f"fred_{name.lower()}_chg20"] = float(
                    vals.iloc[-1] - vals.iloc[-21]
                )

        except Exception as e:
            print("  FRED error", name, e)

    if (
        "fred_us10y" in row
        and "fred_us2y" in row
    ):
        row["fred_curve_10y_2y"] = (
            row["fred_us10y"] - row["fred_us2y"]
        )

    return row

def append_csv_dynamic(path: Path, row: dict):
    """
    CSV simple. Si aparecen columnas nuevas en el futuro,
    se reconstruye preservando observaciones anteriores.
    """
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat(
            [old, pd.DataFrame([row])],
            ignore_index=True,
            sort=False,
        )
    else:
        new = pd.DataFrame([row])

    new.to_csv(path, index=False, encoding="utf-8-sig")

def daily_event_features(events: List[dict]) -> dict:
    row = {"recorded_at_utc": now_utc()}

    tags = list(QUERIES.keys())

    for tag in tags:
        z = [e for e in events if e["asset_tag"] == tag]

        row[f"{tag.lower()}_new_event_count"] = len(z)

        if z:
            row[f"{tag.lower()}_sentiment_mean"] = float(
                np.mean([e["lexical_sentiment"] for e in z])
            )
            row[f"{tag.lower()}_impact_hits"] = int(
                sum(e["impact_keyword_hits"] for e in z)
            )
            row[f"{tag.lower()}_negative_event_share"] = float(
                np.mean([
                    e["lexical_sentiment"] < 0
                    for e in z
                ])
            )
        else:
            row[f"{tag.lower()}_sentiment_mean"] = 0.0
            row[f"{tag.lower()}_impact_hits"] = 0
            row[f"{tag.lower()}_negative_event_share"] = 0.0

    return row

def main():
    OUT.mkdir(exist_ok=True)

    print("\n" + "=" * 82)
    print("MFP-3 v1.8 — GLOBAL EVENT INTELLIGENCE COLLECTOR")
    print("=" * 82)

    events = collect_news()
    print(f"\nEventos nuevos guardados: {len(events)}")

    market = latest_yahoo_context()
    macro = latest_fred_context()
    context = {**market, **macro}

    append_csv_dynamic(MARKET_CONTEXT, context)

    features = daily_event_features(events)
    append_csv_dynamic(DAILY_FEATURES, features)

    print("\nContexto de mercado guardado.")
    print("Noticias raw :", RAW_EVENTS.resolve())
    print("Features     :", DAILY_FEATURES.resolve())
    print("Mercado/macro:", MARKET_CONTEXT.resolve())
    print(
        "\nEste collector NO modifica v1.7-FROZEN. "
        "Sólo alimenta al Challenger."
    )

if __name__ == "__main__":
    main()

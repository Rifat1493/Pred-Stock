from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ALL_STOCK_DATA_PATH = DATA_DIR / "all_stock_data.csv"
TICKER_INFO_PATH = DATA_DIR / "tsx_tickers_extracted.csv"
FILTERED_TICKERS_PATH = DATA_DIR / "filtered_tickers.csv"
DIVIDEND_DATA_PATH = DATA_DIR / "dividend_data.csv"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def load_all_stock_data() -> pd.DataFrame:
	df = pd.read_csv(ALL_STOCK_DATA_PATH)
	if "Date" not in df.columns:
		raise ValueError("all_stock_data.csv must contain a Date column")

	df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
	df = df.dropna(subset=["Date"]).sort_values("Date")
	df = df.set_index("Date")
	return df


def load_dividend_data() -> pd.DataFrame:
	if not DIVIDEND_DATA_PATH.exists():
		return pd.DataFrame()

	data = pd.read_csv(DIVIDEND_DATA_PATH)
	if data.empty:
		return data

	ticker_col = None
	for col in data.columns:
		if col.strip().lower() in {"ticker", "symbol"}:
			ticker_col = col
			break

	if ticker_col is None:
		return pd.DataFrame()

	data[ticker_col] = data[ticker_col].astype(str).str.strip().str.upper()
	return data


def _extract_close(data: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
	if data.empty:
		return pd.DataFrame()

	is_multi = isinstance(data.columns, pd.MultiIndex)
	frames = {}
	for ticker in tickers:
		if is_multi:
			if ticker not in data.columns.get_level_values(0):
				continue
			if not data[ticker]["Close"].isna().all():
				frames[ticker] = data[ticker]["Close"]
			elif not data[ticker]["Adj Close"].isna().all():
				frames[ticker] = data[ticker]["Adj Close"]
		else:
			if not data["Close"].isna().all():
				frames[ticker] = data["Close"]
			elif not data["Adj Close"].isna().all():
				frames[ticker] = data["Adj Close"]

	return pd.concat(frames, axis=1) if frames else pd.DataFrame()


def get_ranked_stock_data(
	tickers: List[str],
	period_days: int = 2,
	day_period_years: int = 10,
	threshold: float = 5.0,
	top_k: int = 15,
) -> Tuple[pd.DataFrame, List[str]]:
	if not tickers:
		return pd.DataFrame(), []

	minute_data = yf.download(
		tickers,
		period=f"{period_days}d",
		interval="1m",
		progress=False,
		group_by="ticker",
		auto_adjust=False,
	)

	if minute_data.empty:
		return pd.DataFrame(), []

	range_scores = {}
	is_multi = isinstance(minute_data.columns, pd.MultiIndex)
	for ticker in tickers:
		if is_multi:
			if ticker not in minute_data.columns.get_level_values(0):
				continue
			if not minute_data[ticker]["Close"].isna().all():
				close_prices = minute_data[ticker]["Close"]
			elif not minute_data[ticker]["Adj Close"].isna().all():
				close_prices = minute_data[ticker]["Adj Close"]
			else:
				continue
		else:
			if not minute_data["Close"].isna().all():
				close_prices = minute_data["Close"]
			elif not minute_data["Adj Close"].isna().all():
				close_prices = minute_data["Adj Close"]
			else:
				continue

		clean = close_prices.dropna()
		if clean.empty:
			continue

		price_range = clean.max() - clean.min()
		if price_range > threshold:
			range_scores[ticker] = price_range

	if not range_scores:
		return pd.DataFrame(), []

	ranked = sorted(range_scores.items(), key=lambda x: x[1], reverse=True)
	ranked_tickers = [ticker for ticker, _ in ranked[:top_k]]

	day_data = yf.download(
		ranked_tickers,
		# period=f"{day_period_years}y",
		period="6mo",
		interval="1d",
		progress=False,
		group_by="ticker",
		auto_adjust=False,
	)

	if day_data.empty:
		return pd.DataFrame(), ranked_tickers

	day_df = _extract_close(day_data, ranked_tickers)
	return day_df, ranked_tickers


def load_industry_map() -> Dict[str, str]:
	if not TICKER_INFO_PATH.exists():
		return {}

	info = pd.read_csv(TICKER_INFO_PATH)
	ticker_col = None
	sector_col = None
	for col in info.columns:
		if col.strip().lower() in {"ticker", "symbol"}:
			ticker_col = col
		if col.strip().lower() in {"sector", "industry"}:
			sector_col = col

	if ticker_col is None or sector_col is None:
		return {}

	info[ticker_col] = info[ticker_col].astype(str).str.strip()
	info[sector_col] = info[sector_col].astype(str).str.strip()

	industry_map = {
		ticker: sector[:5]
		for ticker, sector in zip(info[ticker_col], info[sector_col])
		if ticker and sector and sector.lower() != "nan"
	}
	return industry_map


def build_ticker_groups(df: pd.DataFrame, group_size: int = 10) -> List[List[str]]:
	price_max = df.max(axis=0, skipna=True)
	price_max = price_max.dropna()
	sorted_tickers = price_max.sort_values().index.tolist()

	groups = [
		sorted_tickers[i : i + group_size]
		for i in range(0, len(sorted_tickers), group_size)
	]
	return groups


def update_all_stock_data() -> Tuple[bool, str]:
	if not ALL_STOCK_DATA_PATH.exists():
		return False, "all_stock_data.csv not found."

	existing = pd.read_csv(ALL_STOCK_DATA_PATH)
	if "Date" not in existing.columns:
		return False, "all_stock_data.csv must contain a Date column."

	existing["Date"] = pd.to_datetime(existing["Date"], errors="coerce")
	existing = existing.dropna(subset=["Date"])
	existing = existing.sort_values("Date")

	tickers = [col for col in existing.columns if col != "Date"]
	if not tickers:
		return False, "No tickers found in all_stock_data.csv."

	last_date = existing["Date"].max()
	start_date = (last_date + pd.Timedelta(days=1)).date()

	data = yf.download(
		tickers,
		start=start_date,
		progress=False,
		group_by="ticker",
		auto_adjust=False,
	)

	if data.empty:
		return False, "No new data available from Yahoo Finance."

	if isinstance(data.columns, pd.MultiIndex):
		if ("Adj Close" in data.columns.get_level_values(1)):
			latest = data.xs("Adj Close", level=1, axis=1)
		elif ("Close" in data.columns.get_level_values(1)):
			latest = data.xs("Close", level=1, axis=1)
		else:
			return False, "Price columns not found in Yahoo Finance response."
	else:
		return False, "Unexpected Yahoo Finance data format."

	latest = latest.reset_index().rename(columns={"index": "Date"})
	latest = latest.rename(columns={"Date": "Date"})
	if "Date" not in latest.columns:
		latest = latest.rename(columns={latest.columns[0]: "Date"})

	combined = pd.concat([existing, latest], ignore_index=True)
	combined = combined.drop_duplicates(subset=["Date"]).sort_values("Date")

	combined.to_csv(ALL_STOCK_DATA_PATH, index=False)
	return True, "all_stock_data.csv updated."


def load_filtered_tickers() -> List[str]:
	if not FILTERED_TICKERS_PATH.exists():
		return []

	data = pd.read_csv(FILTERED_TICKERS_PATH)
	if data.empty:
		return []

	col = None
	for name in data.columns:
		if name.strip().lower() in {"ticker", "symbol"}:
			col = name
			break

	if col is None:
		return []

	tickers = (
		data[col]
		.astype(str)
		.str.strip()
		.replace("", pd.NA)
		.dropna()
		.unique()
		.tolist()
	)
	return tickers


def add_filtered_ticker(ticker: str) -> Tuple[bool, str, List[str]]:
	clean = ticker.strip().upper()
	if not clean:
		return False, "Ticker cannot be empty.", load_filtered_tickers()

	existing = load_filtered_tickers()
	if clean in existing:
		return False, f"{clean} is already in the watchlist.", existing

	updated = existing + [clean]
	data = pd.DataFrame({"Ticker": updated})
	data.to_csv(FILTERED_TICKERS_PATH, index=False)
	return True, f"Added {clean}.", updated


def remove_filtered_ticker(ticker: str) -> Tuple[bool, str, List[str]]:
	clean = ticker.strip().upper()
	if not clean:
		return False, "Ticker cannot be empty.", load_filtered_tickers()

	existing = load_filtered_tickers()
	if clean not in existing:
		return False, f"{clean} is not in the watchlist.", existing

	updated = [item for item in existing if item != clean]
	data = pd.DataFrame({"Ticker": updated})
	data.to_csv(FILTERED_TICKERS_PATH, index=False)
	return True, f"Removed {clean}.", updated


def normalize_tsx_ticker(ticker: str) -> str:
	"""Normalize a Toronto exchange ticker to Yahoo-style SYMBOL.TO / SYMBOL.V."""
	clean = ticker.strip().upper().replace(" ", "")
	if not clean:
		return ""

	if clean.endswith(".TRT"):
		return f"{clean[:-4]}.TO"
	if clean.endswith(".TRV"):
		return f"{clean[:-4]}.V"
	if clean.endswith((".TO", ".V")):
		return clean
	return f"{clean}.TO"


def to_alpha_vantage_symbol(ticker: str) -> str:
	"""Convert Yahoo-style TSX/TSXV ticker to Alpha Vantage price API suffix (.TRT/.TRV)."""
	clean = normalize_tsx_ticker(ticker)
	if clean.endswith(".TO"):
		return f"{clean[:-3]}.TRT"
	if clean.endswith(".V"):
		return f"{clean[:-2]}.TRV"
	return clean


def to_news_sentiment_ticker(ticker: str) -> str:
	"""
	NEWS_SENTIMENT only allows alphanumeric, colon, underscore, and hyphen (no dots).
	Use the base symbol; convert internal dots (e.g. AW.UN) to hyphens.
	"""
	clean = normalize_tsx_ticker(ticker)
	if clean.endswith(".TO"):
		base = clean[:-3]
	elif clean.endswith(".V"):
		base = clean[:-2]
	else:
		base = clean
	return base.replace(".", "-")


def get_alpha_vantage_api_key(explicit_key: Optional[str] = None) -> str:
	if explicit_key and explicit_key.strip():
		return explicit_key.strip()
	return (
		os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
		or os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
	)


def _news_ticker_aliases(av_symbol: str) -> set[str]:
	symbol = av_symbol.upper()
	return {
		symbol,
		symbol.replace("-", "."),
		symbol.replace("-", "_"),
		f"{symbol}.TRT",
		f"{symbol}.TRV",
		f"{symbol}-TRT",
		f"{symbol}_TRT",
	}


def _parse_news_article(article: Dict[str, Any], av_symbol: str) -> Dict[str, Any]:
	ticker_score = None
	ticker_label = None
	relevance = None
	aliases = _news_ticker_aliases(av_symbol)
	for item in article.get("ticker_sentiment") or []:
		item_ticker = str(item.get("ticker", "")).upper()
		if item_ticker not in aliases and not item_ticker.startswith(av_symbol.upper()):
			continue
		try:
			ticker_score = float(item.get("ticker_sentiment_score"))
		except (TypeError, ValueError):
			ticker_score = None
		ticker_label = item.get("ticker_sentiment_label")
		try:
			relevance = float(item.get("relevance_score"))
		except (TypeError, ValueError):
			relevance = None
		break

	overall_score = None
	try:
		overall_score = float(article.get("overall_sentiment_score"))
	except (TypeError, ValueError):
		overall_score = None

	return {
		"title": article.get("title") or "",
		"url": article.get("url") or "",
		"source": article.get("source") or "",
		"published": article.get("time_published") or "",
		"summary": article.get("summary") or "",
		"overall_sentiment_score": overall_score,
		"overall_sentiment_label": article.get("overall_sentiment_label"),
		"ticker_sentiment_score": ticker_score,
		"ticker_sentiment_label": ticker_label,
		"relevance_score": relevance,
	}


def _aggregate_ticker_sentiment(articles: List[Dict[str, Any]]) -> Tuple[Optional[float], str]:
	"""Average ticker-level scores from news articles (same NEWS_SENTIMENT response)."""
	weighted_sum = 0.0
	weight_total = 0.0
	plain_scores: List[float] = []

	for article in articles:
		score = article.get("ticker_sentiment_score")
		if score is None:
			score = article.get("overall_sentiment_score")
		if score is None:
			continue

		plain_scores.append(float(score))
		relevance = article.get("relevance_score")
		weight = float(relevance) if relevance is not None else 1.0
		weighted_sum += float(score) * weight
		weight_total += weight

	if weight_total > 0:
		avg = weighted_sum / weight_total
	elif plain_scores:
		avg = sum(plain_scores) / len(plain_scores)
	else:
		return None, "No Sentiment Data"

	if avg <= -0.35:
		label = "Bearish"
	elif avg <= -0.15:
		label = "Somewhat-Bearish"
	elif avg < 0.15:
		label = "Neutral"
	elif avg < 0.35:
		label = "Somewhat-Bullish"
	else:
		label = "Bullish"
	return avg, label


def fetch_ticker_news_sentiment(
	ticker: str,
	api_key: str,
	limit: int = 5,
) -> Dict[str, Any]:
	"""
	One Alpha Vantage NEWS_SENTIMENT call per ticker.
	Returns up to `limit` articles plus an aggregated ticker sentiment.
	"""
	display_ticker = normalize_tsx_ticker(ticker)
	av_symbol = to_news_sentiment_ticker(display_ticker)
	params = {
		"function": "NEWS_SENTIMENT",
		"tickers": av_symbol,
		"limit": str(limit),
		"sort": "LATEST",
		"apikey": api_key,
	}

	response = requests.get(ALPHA_VANTAGE_URL, params=params, timeout=30)
	response.raise_for_status()
	payload = response.json()

	if not isinstance(payload, dict):
		raise ValueError(f"Unexpected response for {display_ticker}.")

	if "Note" in payload:
		raise ValueError(payload["Note"])
	if "Information" in payload:
		raise ValueError(payload["Information"])
	if "Error Message" in payload:
		raise ValueError(payload["Error Message"])

	feed = payload.get("feed") or []
	articles = [_parse_news_article(item, av_symbol) for item in feed[:limit]]
	sentiment_score, sentiment_label = _aggregate_ticker_sentiment(articles)

	return {
		"ticker": display_ticker,
		"av_symbol": av_symbol,
		"sentiment_score": sentiment_score,
		"sentiment_label": sentiment_label,
		"articles": articles,
		"error": None,
	}


def fetch_watchlist_news_sentiment(
	tickers: List[str],
	api_key: str,
	limit: int = 5,
	pause_seconds: float = 0.8,
) -> Dict[str, Dict[str, Any]]:
	"""Fetch news/sentiment for each ticker. Results are meant to be cached in memory."""
	results: Dict[str, Dict[str, Any]] = {}
	normalized = [normalize_tsx_ticker(t) for t in tickers if normalize_tsx_ticker(t)]

	for index, ticker in enumerate(normalized):
		try:
			results[ticker] = fetch_ticker_news_sentiment(ticker, api_key=api_key, limit=limit)
		except Exception as exc:  # noqa: BLE001 - surface API/network errors in UI
			results[ticker] = {
				"ticker": ticker,
				"av_symbol": to_news_sentiment_ticker(ticker),
				"sentiment_score": None,
				"sentiment_label": "Error",
				"articles": [],
				"error": str(exc),
			}

		if index < len(normalized) - 1 and pause_seconds > 0:
			time.sleep(pause_seconds)

	return results

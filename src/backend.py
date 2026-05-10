from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import yfinance as yf


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ALL_STOCK_DATA_PATH = DATA_DIR / "all_stock_data.csv"
TICKER_INFO_PATH = DATA_DIR / "tsx_tickers_extracted.csv"
FILTERED_TICKERS_PATH = DATA_DIR / "filtered_tickers.csv"
DIVIDEND_DATA_PATH = DATA_DIR / "dividend_data.csv"


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

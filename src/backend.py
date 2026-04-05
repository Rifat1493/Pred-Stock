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


def load_all_stock_data() -> pd.DataFrame:
	df = pd.read_csv(ALL_STOCK_DATA_PATH)
	if "Date" not in df.columns:
		raise ValueError("all_stock_data.csv must contain a Date column")

	df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
	df = df.dropna(subset=["Date"]).sort_values("Date")
	df = df.set_index("Date")
	return df


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

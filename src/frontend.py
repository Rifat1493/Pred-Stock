from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src import backend


@st.cache_data(show_spinner=False)
def _load_data():
	dividend_df = backend.load_dividend_data()
	industry_map = backend.load_industry_map()

	if dividend_df.empty:
		return pd.DataFrame(), dividend_df, industry_map, [], []

	ticker_col = None
	for col in dividend_df.columns:
		if col.strip().lower() in {"ticker", "symbol"}:
			ticker_col = col
			break

	if ticker_col is None:
		return pd.DataFrame(), dividend_df, industry_map, [], []

	dividend_tickers = (
		dividend_df[ticker_col]
		.astype(str)
		.str.strip()
		.str.upper()
		.dropna()
		.tolist()
	)

	day_df, ranked_tickers = backend.get_ranked_stock_data(dividend_tickers)
	groups = backend.build_ticker_groups(day_df, group_size=10) if not day_df.empty else []
	return day_df, dividend_df, industry_map, groups, ranked_tickers


def _format_labels(tickers, industry_map):
	labels = {}
	for ticker in tickers:
		base = ticker.split(".")[0]
		industry = industry_map.get(base, "").strip()
		short = industry[:5] if industry else ""
		labels[ticker] = f"{ticker} ({short})" if short else ticker
	return labels


def _render_exploration():
	st.markdown("### Exploration")

	if "page_index" not in st.session_state:
		st.session_state.page_index = 0

	day_df, _, industry_map, groups, _ = _load_data()
	if day_df.empty or not groups:
		st.info("No tickers available to plot.")
		return

	total_pages = len(groups)
	page_index = min(st.session_state.page_index, total_pages - 1)
	st.session_state.page_index = page_index

	col_prev, col_page, col_next = st.columns([1, 2, 1])
	with col_prev:
		if st.button("Prev", disabled=page_index == 0):
			st.session_state.page_index -= 1
	with col_page:
		st.markdown(f"Page {page_index + 1} of {total_pages}")
	with col_next:
		if st.button("Next", disabled=page_index >= total_pages - 1):
			st.session_state.page_index += 1

	tickers = groups[st.session_state.page_index]
	labels = _format_labels(tickers, industry_map)

	plot_df = day_df[tickers].copy()
	plot_df = plot_df.rename(columns=labels)
	plot_df.index.name = "Date"
	plot_df = plot_df.reset_index()
	long_df = plot_df.melt(id_vars="Date", var_name="Ticker", value_name="Price")

	fig = px.line(
		long_df,
		x="Date",
		y="Price",
		color="Ticker",
		title="Prices by Ticker (10 per page)",
	)
	fig.update_traces(visible="legendonly")
	fig.update_layout(legend_title_text="Ticker (Industry)")

	chart_container = st.container(height=620)
	with chart_container:
		st.plotly_chart(fig, use_container_width=True)


def _render_dividends():
	st.markdown("### Dividends")
	_, dividend_df, _, _, ranked_tickers = _load_data()
	if dividend_df.empty or not ranked_tickers:
		st.info("No dividend data available to show.")
		return

	ticker_col = None
	for col in dividend_df.columns:
		if col.strip().lower() in {"ticker", "symbol"}:
			ticker_col = col
			break

	if ticker_col is None:
		st.info("Dividend data is missing a ticker column.")
		return

	filtered = dividend_df[
		dividend_df[ticker_col].astype(str).str.upper().isin(set(ranked_tickers))
	].copy()
	st.dataframe(filtered, use_container_width=True)


def render_app() -> None:
    st.set_page_config(page_title="TSX Stocks", layout="wide")

    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #1e1e2e;
            border: 1px solid #3a3a5c;
            border-radius: 8px;
            padding: 6px 20px;
            color: #aaaacc;
        }
        .stTabs [aria-selected="true"] {
            background-color: #4f46e5 !important;
            border-color: #4f46e5 !important;
            color: white !important;
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }
        .stTabs [data-baseweb="tab-border"] {
            display: none;
        }
        </style>
    """, unsafe_allow_html=True)

    tabs = st.tabs(
        [
            "Exploration",
            "Dividends",
            "Financial Conditions",
            "Sentiment",
            "Correlation",
        ]
    )

    with tabs[0]:
        _render_exploration()
    with tabs[1]:
        _render_dividends()

    for tab in tabs[2:]:
        with tab:
            st.write("")

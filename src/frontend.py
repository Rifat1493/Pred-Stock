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


def _init_sentiment_state() -> None:
	if "sentiment_tickers" not in st.session_state:
		st.session_state.sentiment_tickers = []
	if "sentiment_results" not in st.session_state:
		st.session_state.sentiment_results = {}
	if "sentiment_last_fetched" not in st.session_state:
		st.session_state.sentiment_last_fetched = None


def _format_published(value: str) -> str:
	if not value or len(value) < 8:
		return value or ""
	# Alpha Vantage: YYYYMMDDTHHMMSS
	date_part = value[:8]
	time_part = value[9:15] if "T" in value and len(value) >= 15 else ""
	formatted = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
	if time_part:
		formatted += f" {time_part[:2]}:{time_part[2:4]}"
	return formatted


def _render_sentiment() -> None:
	st.markdown("### Sentiment")
	st.caption(
		"TSX watchlist (.TO). News and sentiment come from one Alpha Vantage "
		"NEWS_SENTIMENT call per ticker and stay cached until you click Search."
	)
	_init_sentiment_state()

	api_key = backend.get_alpha_vantage_api_key()
	try:
		if hasattr(st, "secrets") and "ALPHAVANTAGE_API_KEY" in st.secrets:
			api_key = api_key or str(st.secrets["ALPHAVANTAGE_API_KEY"]).strip()
	except Exception:
		pass

	with st.expander("API key", expanded=not bool(api_key)):
		entered_key = st.text_input(
			"Alpha Vantage API key",
			type="password",
			value="",
			placeholder="Set ALPHAVANTAGE_API_KEY or paste here",
			key="sentiment_api_key_input",
			help="Used only for NEWS_SENTIMENT. Prefer env var / Streamlit secrets.",
		)
		if entered_key.strip():
			api_key = entered_key.strip()

	st.markdown("#### Watchlist")
	add_col, remove_col = st.columns(2)
	with add_col:
		new_ticker = st.text_input(
			"Add ticker",
			placeholder="e.g. CNR or CNR.TO",
			key="sentiment_add_ticker",
		)
		if st.button("Add", key="sentiment_add_btn"):
			normalized = backend.normalize_tsx_ticker(new_ticker)
			if not normalized:
				st.warning("Enter a ticker.")
			elif normalized in st.session_state.sentiment_tickers:
				st.warning(f"{normalized} is already in the watchlist.")
			else:
				st.session_state.sentiment_tickers.append(normalized)
				st.success(f"Added {normalized}.")

	with remove_col:
		if st.session_state.sentiment_tickers:
			to_remove = st.selectbox(
				"Remove ticker",
				options=st.session_state.sentiment_tickers,
				key="sentiment_remove_select",
			)
			if st.button("Delete", key="sentiment_remove_btn"):
				st.session_state.sentiment_tickers = [
					t for t in st.session_state.sentiment_tickers if t != to_remove
				]
				st.success(f"Removed {to_remove}.")
		else:
			st.info("No tickers yet. Add a TSX symbol above.")

	if st.session_state.sentiment_tickers:
		st.write(", ".join(st.session_state.sentiment_tickers))

	btn_col, apply_col, status_col = st.columns([1, 1, 3])
	with btn_col:
		search_clicked = st.button(
			"Search",
			type="primary",
			key="sentiment_search_btn",
			disabled=not st.session_state.sentiment_tickers,
		)
	with apply_col:
		apply_clicked = st.button(
			"Apply",
			key="sentiment_apply_btn",
			disabled=not st.session_state.sentiment_tickers,
		)
	with status_col:
		if st.session_state.sentiment_last_fetched:
			st.caption(f"Cached results from {st.session_state.sentiment_last_fetched}")
		else:
			st.caption("No cached results yet. Click Search or Apply to load news.")

	if search_clicked or apply_clicked:
		if not api_key:
			st.error("Alpha Vantage API key is required.")
		else:
			with st.spinner("Fetching news & sentiment (one API call per ticker)..."):
				st.session_state.sentiment_results = backend.fetch_watchlist_news_sentiment(
					st.session_state.sentiment_tickers,
					api_key=api_key,
					limit=5,
				)
				st.session_state.sentiment_last_fetched = pd.Timestamp.now().strftime(
					"%Y-%m-%d %H:%M:%S"
				)

	results = st.session_state.sentiment_results
	if not results:
		return

	st.markdown("#### Results")
	for ticker in st.session_state.sentiment_tickers:
		payload = results.get(ticker)
		if payload is None:
			st.warning(f"{ticker}: no cached result — click Search or Apply to load.")
			continue

		score = payload.get("sentiment_score")
		label = payload.get("sentiment_label") or "—"
		score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
		st.markdown(f"**{ticker}** — sentiment: {label} ({score_text})")

		if payload.get("error"):
			st.error(payload["error"])
			continue

		articles = payload.get("articles") or []
		if not articles:
			st.info("No news articles returned.")
			continue

		rows = []
		for article in articles:
			rows.append(
				{
					"Published": _format_published(article.get("published", "")),
					"Title": article.get("title", ""),
					"Source": article.get("source", ""),
					"Ticker sentiment": article.get("ticker_sentiment_label")
					or article.get("overall_sentiment_label")
					or "—",
					"Score": article.get("ticker_sentiment_score")
					if article.get("ticker_sentiment_score") is not None
					else article.get("overall_sentiment_score"),
					"URL": article.get("url", ""),
				}
			)
		st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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
    with tabs[2]:
        st.write("")
    with tabs[3]:
        _render_sentiment()
    with tabs[4]:
        st.write("")

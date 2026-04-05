from __future__ import annotations

import streamlit as st
import plotly.express as px

from src import backend


@st.cache_data(show_spinner=False)
def _load_data():
	df = backend.load_all_stock_data()
	industry_map = backend.load_industry_map()
	groups = backend.build_ticker_groups(df, group_size=10)
	return df, industry_map, groups


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

	update_clicked = st.button("Update Data")
	if update_clicked:
		with st.spinner("Updating all_stock_data.csv..."):
			ok, message = backend.update_all_stock_data()
		if ok:
			st.cache_data.clear()
			st.success(message)
		else:
			st.warning(message)

	df, industry_map, groups = _load_data()
	if not groups:
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

	plot_df = df[tickers].copy()
	plot_df = plot_df.rename(columns=labels)
	long_df = plot_df.reset_index().melt(
		id_vars="Date", var_name="Ticker", value_name="Price"
	)

	fig = px.line(
		long_df,
		x="Date",
		y="Price",
		color="Ticker",
		title="Prices by Ticker (10 per page)",
	)
	fig.update_layout(legend_title_text="Ticker (Industry)")

	chart_container = st.container(height=620)
	with chart_container:
		st.plotly_chart(fig, use_container_width=True)


def _render_dividends():
	st.markdown("### Dividends")
	st.markdown("**Watchlist**")
	st.markdown(
		"""
		<style>
		button[title="Remove from watchlist"] {
			position: relative !important;
			width: 100% !important;
			min-height: 44px !important;
			padding: 10px 28px 10px 14px !important;
			border-radius: 999px !important;
			background: #1e1e2e !important;
			border: 1px solid #3a3a5c !important;
			color: #f4f4ff !important;
			font-weight: 600 !important;
			text-align: left !important;
		}
		button[title="Remove from watchlist"]::after {
			content: "×";
			position: absolute;
			top: 6px;
			right: 8px;
			width: 18px;
			height: 18px;
			border-radius: 999px;
			background: #0f111a;
			border: 1px solid #3a3a5c;
			color: #f4f4ff;
			font-size: 12px;
			line-height: 16px;
			text-align: center;
		}
		button[title="Remove from watchlist"]:hover {
			background: #4f46e5 !important;
			border-color: #4f46e5 !important;
		}
		button[title="Remove from watchlist"]:hover::after {
			background: #1e1e2e;
			border-color: #1e1e2e;
		}
		</style>
		""",
		unsafe_allow_html=True,
	)

	watchlist = backend.load_filtered_tickers()
	if not watchlist:
		st.write("None")
	else:
		per_row = 5
		for start in range(0, len(watchlist), per_row):
			row = watchlist[start : start + per_row]
			cols = st.columns(per_row)
			for col, ticker in zip(cols, row):
				with col:
					if st.button(ticker, key=f"remove_{ticker}", help="Remove from watchlist"):
						ok, message, _ = backend.remove_filtered_ticker(ticker)
						if ok:
							st.success(message)
						else:
							st.warning(message)
						st.rerun()

	st.markdown("---")
	new_ticker = st.text_input("Add ticker", placeholder="e.g., CNR.TO")
	if st.button("Add to watchlist"):
		ok, message, _ = backend.add_filtered_ticker(new_ticker)
		if ok:
			st.success(message)
			st.rerun()
		else:
			st.warning(message)


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

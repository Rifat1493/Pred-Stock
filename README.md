# TSX Stocks Streamlit App

This app downloads up to 15 years of daily prices from Yahoo Finance for Canadian tickers (TSX/TSXV), filters out extreme-price tickers, and plots 10 tickers per page (always keeping CNR.TO if present).

## Setup

```powershell
cd "d:\Office\2024\Kroger\stock"
py -m pip install -r requirements.txt
```

## Run on local network (same Wi‑Fi)

```powershell
# Option A: rely on config (.streamlit/config.toml)
streamlit run app.py

# Option B: explicit flags
streamlit run src/app.py --server.address 0.0.0.0 --server.port 8501
```

Find your PC's IP:
```powershell
ipconfig | findstr IPv4
```
Then open from any device on the same Wi‑Fi:
```
http://<your-ip>:8501
```

## Data sources
- Default tickers read from `../data/tsx_tickers_extracted.csv` (column `Ticker` or `Symbol`). The app maps `:TSX` → `.TO` and `:TSXV` → `.V` automatically.
- Wide CSV: `stock/dataset/tsx_adj_close_15y_wide.csv`
- Tidy CSV: `stock/dataset/tsx_adj_close_15y_tidy.csv`

## Notes
- Pagination shows 10 tickers per page (configurable), always including `CNR.TO` if present.
- Tickers with any price > 1000 are dropped (threshold configurable).
- Results are cached; change inputs to refresh.


page 1 exploration - dowanload all (all_data.csv), check_pattern from all_data.csv (top_comp_names.csv), download_shortlisted(top_comp_data.csv)

page 2 - dividend declration - future date 

page 3 - financial conditions - user input (ticker list) watch list
page 4 - Sentiment  --- user input (ticker list) watchlist
page 5 - correlation - with gold, dollar, crude oil (single ticker), seasonality



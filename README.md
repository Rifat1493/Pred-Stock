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

## Knowledge Base
abx up, oil down, gold up
tri up, bitcoin up, ray down




## Draft

page 1 exploration - dowanload all (all_data.csv), check_pattern from all_data.csv (top_comp_names.csv), download_shortlisted(top_comp_data.csv)

page 2 - dividend declration - future date 

page 3 - financial conditions - user input (ticker list) watch list
page 4 - Sentiment  --- user input (ticker list) watchlist
page 5 - correlation - with gold, dollar, crude oil (single ticker), seasonality


stock identification:

upward trend, 8 to 200 price
dividend.

correlation with dollar, oil, gold, other stock, individual and sector.
inter sector, intra sector, 

real estate stock or ETF
predefined pool of stocks()

buy: (first 30 min) from pool of stocks
correlated something got lowered
4 dollar loss in a single day


reliable power, AI infrastructure, productivity, automation, AI, memory


CEG,VRT, BE, micron, NVDA AMD TSMC ASML ARM CADENCE ANET palantir
oracle msft google tesla meta amazon sofi robinhood renewable energy


Buy/sell:
CNQ.TO, L.TO, ARX.TO, ABX.TO, NOA.TO
from the follow tickers (CNR.TO, ABX.TO)
Generate a per-company report based on the following questions. Assign a score from 1–5 and provide a brief reason for each. Focus only on very recent news (last 2–3 days from the current date). If no relevant news exists within this timeframe, use the most recent available update and clearly mention that it is not from the last 2–3 days. please do not hallucinate answer based on trusted resources.

i) Is there any negative/positive news currently going on about the company like increasing or decreasing the earnings or dividends.
ii) Is there any negative/positive news about the management of the company (like chnages in management who had a good or bad track record, scandal by any c suit memeber)
iii) Is there any positive or negative news by its competitor(like new innovation by competitor or downngrade of the competitor)
iv) any news on stopping any war which is related to the sector of the company or breakout like covid 
v) merger and acuisition





** valuation report by any company
https://site.financialmodelingprep.com/developer/docs/quickstart

PEG ≈ 1 → Fairly valued
PEG < 1 → Potentially undervalued (growth is strong relative to price)
PEG > 1 → Potentially overvalued

β = 1 → Stock moves roughly in line with the market
β > 1 → Stock is more volatile than the market
Example: β = 1.5 → if the market goes up 10%, the stock might go up ~15%
β < 1 → Stock is less volatile than the market
Example: β = 0.5 → market up 10%, stock might go up ~5%
β < 0 → Stock moves opposite the market (rare)
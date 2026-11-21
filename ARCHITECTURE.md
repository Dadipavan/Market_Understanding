# Architecture

Rule-based (no AI/ML) market analysis for learning. Every verdict is a sum of explicit rules, each with points and a plain-language reason.

```
USER (browser)
  Home -> Stock Investing | Trading | Screener | IPO | Mutual Funds | Gold & Crypto | Bonds | Options (F&O) | Paper Portfolio | Learn
        |
UI LAYER (Streamlit)      Home.py, pages/, ui/common.py, ui/charts.py
  charts, scores, verdicts, "why" tables, glossary hints, data-quality panel, DEMO toggle
        |
ENGINE LAYER (pure Python, deterministic, unit-tested)
  indicators/technical.py   SMA, EMA, RSI, MACD, ATR, Bollinger, support/resistance
  scoring/technical.py      0-100 technical score (reasons, coverage)
  scoring/fundamental.py    0-100 fundamental score (quality, growth, balance sheet, valuation, ownership)
  rules/advisor.py          investing_report (60% fundamental / 40% technical), trading_setup (entry, ATR stop, targets, size)
  risk/sizing.py, costs.py  position size, STT/brokerage/GST/stamp/DP charges, STCG/LTCG
  backtest/engine.py        long-only, next-bar execution, costs, vs buy-and-hold
  portfolio/ledger.py       paper trades, avg-cost P&L, journal; lives in the user's session, exported as JSON
  ipo/scoring.py            IPO rules on a table you maintain (ipo/ipos_sample.csv)
  funds/amfi.py, analytics  AMFI NAV list, NAV history, CAGR, drawdown, SIP/XIRR, fund score
  derivatives/options.py    Black-Scholes, Greeks, implied vol, strategy payoffs (educational, no live chain)
  bonds/calc.py             price <-> YTM, duration, after-tax yield
  learn/glossary.py         plain-language terms
        |
DATA LAYER
  markets/india.py          NSE adapter: tickers, INR, NIFTY 50 (add markets as siblings)
  datasources/service.py    fetch -> validate -> cross-check -> timestamp  => PriceResult
  datasources/yahoo.py      yfinance prices (free, unofficial)
  datasources/nse.py        NSE bhavcopy (official end-of-day, used as the 2nd source)
  datasources/universe.py   all NSE equities (EQUITY_L.csv), NIFTY 50 fallback
  datasources/fundamentals  yfinance fundamentals normalised to one dict (None = unavailable)
  core/validation.py        OHLC sanity checks, two-source price match
  core/cache.py             on-disk TTL cache
  core/demo.py              deterministic SYNTHETIC data for offline demo/tests
        |
EXTERNAL: Yahoo Finance | NSE archives | AMFI NAVAll.txt | mfapi.in | (later: Screener.in, broker API)
```

## Request flow: "Analyse RELIANCE"

```
page -> get_prices("RELIANCE", "1y")
   demo?  -> core.demo (synthetic, labelled)
   else   -> yahoo.fetch_history (cached 15 min)
          -> validate_ohlcv  (positive, high>=low, no >40% jump, recent, ordered)
          -> NSE bhavcopy close vs Yahoo close within 1%  (skipped for indices/gold/crypto/.BO)
          => PriceResult{df, checks[], as_of, sources}
page -> get_fundamentals -> investing_report(df, info, verified)
          technical_analysis + fundamental_analysis -> weighted score -> verdict + reasons + risks
          missing data = "unavailable" (excluded and reported via coverage), never silently zero
          failed checks => verdict prefixed "UNVERIFIED DATA"
page renders: verdict, why-table, entry zone / invalidation, chart, data-quality panel
```

## Design rules
- One-way dependencies: UI -> engine -> data. Swapping a data source touches only `datasources/`.
- Common contract (`core/base.py`): `Analysis{score, verdict, reasons[], risks[]}`; each `Reason` carries points, max points and `available`.
- Backtests act on the *next* bar (no look-ahead) and charge costs.
- No server-side user data: paper portfolios are session state, exported/imported as JSON.
- No order execution anywhere.

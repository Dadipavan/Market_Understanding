"""Plain-language glossary used across the app: term -> (category, meaning, how to use it)."""

GLOSSARY: dict[str, tuple[str, str, str]] = {
    "Stock / share": ("Basics", "A small ownership slice of a company.", "You earn if the business grows (price rise) or pays dividends; you can lose if it does badly."),
    "NSE / BSE": ("Basics", "India's two main stock exchanges. NSE hosts the NIFTY 50; BSE hosts the SENSEX.", "Most stocks trade on both. This app uses NSE symbols."),
    "NIFTY 50": ("Basics", "Index of the 50 largest NSE companies.", "Use it as the benchmark: if your portfolio lags NIFTY consistently, an index fund would have done better."),
    "Delivery vs intraday": ("Basics", "Delivery = you take the shares and hold them. Intraday = buy and sell the same day.", "Delivery suits investing; intraday has higher costs, higher risk and different tax treatment."),
    "Market order vs limit order": ("Basics", "Market buys at the best available price now. Limit buys only at your price or better.", "Use limit orders for illiquid stocks to avoid paying a bad price."),
    "Stop-loss": ("Risk", "A pre-decided exit price that caps your loss.", "Set it before entering; place it where the trade idea is proven wrong, not where the loss 'feels' acceptable."),
    "Position sizing": ("Risk", "How many shares to buy so that a stop-out costs only a small % of capital (commonly 1-2%).", "Size = (capital x risk%) / (entry - stop). The Trading page does this for you."),
    "Risk-reward (R)": ("Risk", "Potential gain divided by potential loss. 1:2 means you aim to make Rs 2 for every Rs 1 risked.", "With 1:2 you can be wrong more than half the time and still profit."),
    "Drawdown": ("Risk", "Fall from a peak to a later low.", "Max drawdown tells you the worst pain history delivered. If a -30% fall would make you panic-sell, pick safer assets."),
    "Diversification": ("Risk", "Spreading money across stocks/sectors so one failure does not sink you.", "Avoid >20-25% in one stock and heavy concentration in one sector."),
    "Volatility": ("Risk", "How much a price swings.", "Higher volatility needs wider stops and smaller positions."),
    "Beta": ("Risk", "Sensitivity to the market. Beta 1.3 means it tends to move 30% more than NIFTY.", "High-beta stocks rise faster in rallies and fall harder in sell-offs."),
    "Moving average (SMA/EMA)": ("Technical", "Average price over N days; EMA weights recent days more.", "Price above the 200-day average = long-term uptrend; below = downtrend."),
    "RSI": ("Technical", "Momentum gauge from 0 to 100.", "Above 70 = stretched/overbought, below 30 = oversold. In strong trends RSI can stay high for weeks."),
    "MACD": ("Technical", "Difference between a fast and slow EMA, compared with its own average (signal line).", "MACD crossing above signal suggests rising momentum; below suggests fading."),
    "Bollinger Bands": ("Technical", "A band two standard deviations around the 20-day average.", "Touching the upper band means price is stretched, not an automatic sell."),
    "ATR": ("Technical", "Average True Range: the typical daily price range.", "Use 1.5-2x ATR for stop distance so normal noise does not stop you out."),
    "Support / resistance": ("Technical", "Price levels where buying (support) or selling (resistance) has repeatedly appeared.", "Place stops just beyond support; expect pauses near resistance."),
    "Volume": ("Technical", "Number of shares traded.", "Moves on rising volume are more reliable than moves on thin volume."),
    "Candlestick": ("Technical", "One bar showing open, high, low, close for a period.", "Green/up = closed above open; red/down = closed below."),
    "P/E ratio": ("Fundamental", "Price divided by earnings per share: what you pay for Rs 1 of annual profit.", "Compare with the same sector and with the company's own history. Low P/E is not always cheap (profits may be falling)."),
    "PEG ratio": ("Fundamental", "P/E divided by earnings growth rate.", "Under ~1.5 means you are not overpaying for growth."),
    "P/B ratio": ("Fundamental", "Price divided by book value per share.", "Most useful for banks and asset-heavy companies."),
    "ROE / ROCE": ("Fundamental", "Profit earned per Rs 100 of shareholders' money (ROE) or of total capital (ROCE).", "Consistently above 15% is a sign of a quality business."),
    "Debt / equity": ("Fundamental", "Borrowings relative to shareholders' funds.", "Above 1-1.5 is risky for most non-financial firms. Banks naturally carry high debt."),
    "Profit margin": ("Fundamental", "Share of revenue left as profit.", "Rising margins show pricing power; falling margins are a warning."),
    "Promoter holding & pledging": ("Fundamental", "Shares owned by founders. Pledging means they borrowed against those shares.", "Falling holding or rising pledge % is a red flag; check on NSE/BSE shareholding patterns."),
    "Dividend yield": ("Fundamental", "Annual dividend divided by price.", "Nice income, but a very high yield can signal a falling price."),
    "Market cap": ("Fundamental", "Share price x number of shares: the company's market value.", "Large caps are steadier; small caps move more and can be illiquid."),
    "FII / DII": ("Market", "Foreign / domestic institutional investors.", "Sustained FII selling pressures the market; DII buying often cushions it."),
    "India VIX": ("Market", "Expected near-term volatility of NIFTY.", "High VIX = fear. Reduce position sizes when it spikes."),
    "IPO": ("IPO", "A company's first sale of shares to the public.", "Read the RHP. Prefer fresh issues, fair valuation and profitable companies."),
    "Fresh issue vs OFS": ("IPO", "Fresh issue: new shares, money goes to the company. OFS: existing holders sell.", "Mostly-OFS issues mean insiders are cashing out."),
    "GMP": ("IPO", "Grey Market Premium: unofficial price people pay before listing.", "Treat as a mood indicator only: it is unregulated and can be manipulated."),
    "Anchor investors / QIB": ("IPO", "Large institutions who bid first. QIB = qualified institutional buyers.", "Strong QIB subscription is a better signal than retail excitement."),
    "Allotment": ("IPO", "Oversubscribed IPOs allot by lottery to retail applicants.", "Applying with multiple family PANs improves lottery odds, not returns."),
    "NAV": ("Funds", "Per-unit value of a mutual fund.", "A low NAV is not 'cheap': only returns matter."),
    "SIP": ("Funds", "Fixed amount invested every month.", "Averages your buying price and builds discipline."),
    "Expense ratio": ("Funds", "Yearly fee the fund charges, as % of assets.", "Direct plans cost ~0.5-1% less than regular plans; over 20 years that is a large sum."),
    "XIRR": ("Funds", "Annualised return for investments made on different dates.", "The right way to measure SIP returns."),
    "YTM": ("Bonds", "Yield to maturity: total annual return if you hold the bond to maturity.", "When market rates rise, bond prices fall."),
    "Duration": ("Bonds", "Sensitivity of a bond's price to interest-rate changes.", "Modified duration 5 means a 1% rate rise cuts price ~5%."),
    "Call & put option": ("F&O", "Right to buy (call) or sell (put) at a fixed strike by expiry.", "Buyers risk only the premium; sellers can lose far more."),
    "Premium, strike, expiry": ("F&O", "Premium = option price; strike = agreed price; expiry = last valid date.", "Time decay (theta) erodes option value every day."),
    "Delta, gamma, theta, vega": ("F&O", "Option sensitivities to price, delta's change, time and volatility.", "Long options lose to theta daily; sellers collect it but carry big tail risk."),
    "Lot size": ("F&O", "Minimum contract quantity set by the exchange.", "Exposure = price x lot size, so check it before trading."),
    "STCG / LTCG": ("Tax", "Short/long-term capital gains tax. For listed equity: held up to 12 months = short term.", "Rates and exemptions change by budget; confirm current rules (this app uses 20% STCG, 12.5% LTCG above Rs 1.25 lakh)."),
    "STT & charges": ("Tax", "Securities Transaction Tax, exchange fees, GST, stamp duty, DP charges.", "Costs matter most for frequent traders: always net them from backtests."),
}


def categories() -> list[str]:
    seen: list[str] = []
    for cat, _, _ in GLOSSARY.values():
        if cat not in seen:
            seen.append(cat)
    return seen


def lookup(term: str) -> tuple[str, str, str] | None:
    return GLOSSARY.get(term)

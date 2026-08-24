# MT5 Gold Resilient Scalper

A production-grade, resilient trading bot for **XAUUSD (Gold)** on MetaTrader 5 with a secure web-based dashboard.

## ⚠️ RISK WARNING

**XAUUSD (Gold) is an extremely high-volatility instrument.** This bot is provided for **EDUCATIONAL AND DEMONSTRATION PURPOSES ONLY**. 

- **NEVER** use this on a live account without extensive testing on a demo account
- **ALWAYS** start with minimum position sizes (0.01 lots)
- Past performance does not guarantee future results
- You can lose more than your initial investment
- The authors are not responsible for any financial losses

## Features

### Core Strategy
- **ATR-Based Dynamic Grid**: Uses Average True Range for adaptive entry/exit levels
- **Market Condition Filter**: Automatically pauses during high volatility, wide spreads, or strong trends
- **Bias Detection**: Determines bullish/bearish/neutral bias using EMA + RSI + ADX
- **Single Position Rule**: Maximum 1 position at a time - no martingale, no averaging down

### Risk Management
- **Dynamic Lot Sizing**: Calculates position size based on account balance and SL distance
- **Daily Loss Limit**: Stops trading if daily loss exceeds configured percentage
- **Equity Protection**: Hard stop if equity drops by configured percentage from starting balance
- **Max Positions**: Strictly enforced single position limit

### Web Dashboard
- **Live Status Panel**: Real-time balance, equity, price, spread, ATR
- **Control Panel**: Start/Stop trading, Emergency Close All button
- **Configuration UI**: Adjust risk parameters, SL/TP multipliers, filter thresholds
- **Price Chart**: Live Chart.js visualization with EMA overlay
- **Trade Log**: Recent trade history with P/L tracking

## Requirements

- **Python 3.9+**
- **MetaTrader 5 Terminal** (installed and logged in)
- **Windows OS** (MT5 Python package only works on Windows)

## Installation

### Step 1: Install MetaTrader 5

1. Download MT5 from your broker or [metatrader5.com](https://www.metatrader5.com/)
2. Install and launch the terminal
3. Log into a demo or live account
4. Ensure XAUUSD is available in Market Watch (View → Market Watch)

### Step 2: Install Python Dependencies

```bash
cd mt5-gold-resilient-scalper
pip install -r requirements.txt
```

### Step 3: Verify MT5 Connection

```python
import MetaTrader5 as mt5
if mt5.initialize():
    print("MT5 connected!")
    mt5.shutdown()
else:
    print("MT5 connection failed")
```

## Usage

### Start the Bot

```bash
python app.py
```

The application will:
1. Connect to the MT5 terminal
2. Start the Flask web server on port 5000
3. Display startup messages

### Access the Dashboard

Open your browser and navigate to: **http://localhost:5000**

**Default credentials:**
- Username: `admin`
- Password: `admin123`

**⚠️ Change these credentials in `web/auth.py` for production use!**

### Dashboard Controls

1. **Start Trading**: Begins the strategy execution loop
2. **Stop Trading**: Gracefully stops new order placement
3. **Emergency Close All**: Immediately closes all positions and cancels orders
4. **Configuration**: Adjust parameters in real-time

## Configuration

### Default Parameters (in `config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| Risk % | 1.0% | Risk per trade |
| Daily Loss Limit | 5.0% | Max daily loss before stop |
| Equity Drawdown Limit | 10.0% | Max total drawdown |
| SL Multiplier | 3.0× ATR | Stop loss distance |
| TP Multiplier | 2.0× ATR | Take profit distance |
| Gap Distance | 1.5× ATR | Pending order distance |
| Max Spread | 30 pts | Maximum allowed spread |
| ADX Threshold | 30 | Strong trend detection |
| EMA Period | 50 | Trend direction |
| RSI Period | 14 | Momentum indicator |

### Recommended Initial Settings for XAUUSD

For **demo testing**, start with conservative settings:

```
Risk %: 0.5% (very conservative)
SL Multiplier: 4.0 (wider SL for Gold volatility)
TP Multiplier: 2.0
Max Spread: 40 points (Gold spreads vary widely)
ADX Threshold: 25 (be more cautious about trends)
```

## Strategy Logic

### Entry Conditions

1. **Market Filter Checks** (all must pass):
   - Spread ≤ Max Allowed Spread (default 30 points)
   - ATR ≤ Threshold (not in extreme volatility)
   - ADX ≤ 30 (not in strong trend)

2. **Bias Determination**:
   - **Bullish**: Price > EMA(50) AND RSI > 50
   - **Bearish**: Price < EMA(50) AND RSI < 50
   - **Neutral**: ADX < 25 (range-bound market)

3. **Order Placement**:
   - Bullish: Place Buy Stop only
   - Bearish: Place Sell Stop only
   - Neutral: Place both Buy Stop and Sell Stop

### Order Levels (ATR-Based)

```
Gap Distance = 1.5 × ATR
Take Profit = 2.0 × ATR
Stop Loss = 3.0 × ATR
```

### Exit Rules

- Position closed by TP or SL
- After position close: Cancel all pending orders
- Wait 60 seconds before re-evaluating entry

## Project Structure

```
mt5-gold-resilient-scalper/
├── app.py                  # Main entry point, Flask app, thread management
├── config.py               # Centralized configuration
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .gitignore
├── strategy/
│   ├── __init__.py
│   ├── mt5_connector.py    # MT5 API wrapper with error handling
│   ├── indicators.py       # EMA, RSI, ATR, Bollinger Bands, ADX
│   ├── grid_manager.py     # Order placement logic
│   ├── risk_manager.py     # Lot sizing, drawdown protection
│   └── market_filter.py    # Volatility/spread/trend filters
├── web/
│   ├── __init__.py
│   ├── auth.py             # Login/session management
│   └── routes.py           # API endpoints
├── templates/
│   ├── base.html
│   ├── login.html
│   └── dashboard.html
├── static/
│   ├── css/style.css
│   └── js/dashboard.js
└── logs/
    └── trading.log
```

## Troubleshooting

### MT5 Connection Failed

1. Ensure MT5 terminal is running
2. Check you're logged into a valid account
3. Verify XAUUSD is in Market Watch
4. Run MT5 as Administrator (sometimes needed)

### No Orders Placed

1. Check market conditions (spread, ATR, ADX)
2. Verify account has sufficient margin
3. Check risk limits haven't been hit
4. Review `logs/trading.log` for details

### Dashboard Not Loading

1. Ensure Flask is running (check console output)
2. Verify port 5000 is not blocked by firewall
3. Clear browser cache
4. Check browser console for JavaScript errors

## Development Notes

### Adding New Indicators

Edit `strategy/indicators.py` and add methods following the existing pattern:

```python
def calculate_my_indicator(self, df: pd.DataFrame, period: int) -> Optional[pd.Series]:
    try:
        if len(df) < period:
            return None
        # Calculation logic here
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return None
```

### Modifying Strategy Logic

The core strategy loop is in `strategy/grid_manager.py`. Key method:
- `execute_strategy_cycle()`: Main decision-making function

### Changing Risk Parameters

All risk parameters are in `config.py` under the `RiskConfig` class. Can also be modified via the web dashboard.

## License

This project is provided as-is for educational purposes. No warranty expressed or implied.

## Contributing

Contributions welcome! Please:
1. Test thoroughly on demo account
2. Document any new features
3. Follow existing code style
4. Add appropriate error handling

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Remember: Trading foreign exchange and CFDs carries a high level of risk and may not be suitable for all investors. You should carefully consider your investment objectives, level of experience, and risk appetite before deciding to trade.**

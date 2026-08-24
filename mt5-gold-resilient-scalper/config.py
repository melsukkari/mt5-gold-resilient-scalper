"""
Configuration settings for the MT5 Gold Resilient Scalper.
All magic numbers and parameters are centralized here for easy adjustment.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SymbolConfig:
    """Configuration for XAUUSD symbol properties."""
    SYMBOL: str = "XAUUSD"
    TIMEFRAME_ENTRY: int = 5  # M5 for entry signals
    TIMEFRAME_CONTEXT: int = 60  # H1 for trend/volatility context
    
    # Tick properties (will be dynamically fetched, but defaults provided)
    TICK_SIZE: float = 0.01  # Typical for Gold
    TICK_VALUE: float = 1.0  # Will be calculated based on lot size


@dataclass
class IndicatorConfig:
    """Technical indicator parameters."""
    EMA_PERIOD: int = 50
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    BB_PERIOD: int = 20
    BB_DEVIATION: float = 2.0
    ATR_PERIOD: int = 14


@dataclass
class MarketFilterConfig:
    """Market condition filter thresholds."""
    # Volatility filter: Pause if ATR > this multiplier of average ATR
    ATR_VOLATILITY_MULTIPLIER: float = 2.0
    
    # Spread filter: Maximum allowed spread in points
    MAX_ALLOWED_SPREAD: int = 30
    
    # Trend strength: ADX above this means strong trend (pause grid mode)
    ADX_STRONG_TREND: float = 30.0
    ADX_RANGE_BOUND: float = 25.0


@dataclass
class RiskConfig:
    """Risk management parameters."""
    # Risk per trade as percentage of balance (e.g., 1% = 0.01)
    RISK_PERCENT: float = 0.01
    
    # Daily loss limit as percentage of balance
    DAILY_LOSS_LIMIT_PERCENT: float = 0.05
    
    # Equity protection: Stop if equity drops by this % from starting balance
    EQUITY_DRAWDOWN_LIMIT: float = 0.10
    
    # Maximum open positions (strictly 1 for this strategy)
    MAX_OPEN_POSITIONS: int = 1
    
    # Minimum lot size (broker dependent)
    MIN_LOT_SIZE: float = 0.01
    
    # Maximum lot size
    MAX_LOT_SIZE: float = 10.0
    
    # Lot step increment
    LOT_STEP: float = 0.01


@dataclass
class GridConfig:
    """Grid/Entry strategy parameters using ATR-based distances."""
    # Distance to place pending orders (multiplier of ATR)
    GAP_DISTANCE_MULTIPLIER: float = 1.5
    
    # Take Profit distance (multiplier of ATR)
    TP_MULTIPLIER: float = 2.0
    
    # Stop Loss distance (multiplier of ATR)
    SL_MULTIPLIER: float = 3.0
    
    # Re-evaluation interval in seconds
    CHECK_INTERVAL: int = 60  # Wait 60 seconds after position closes before re-entry


@dataclass
class TradingConfig:
    """Main trading configuration."""
    # Unique identifier for bot's orders
    MAGIC_NUMBER: int = 888888
    
    # Order comment for identification
    ORDER_COMMENT: str = "GoldScalper"
    
    # Slippage tolerance in points
    DEVIATION: int = 10
    
    # Order filling type (FOK, IOC, or Return)
    FILLING_MODE: int = 3  # ORDER_FILLING_FOK or ORDER_FILLING_IOC
    
    # Enable/disable trading
    TRADING_ENABLED: bool = False
    
    # Starting balance for equity protection calculation
    STARTING_BALANCE: Optional[float] = None


@dataclass
class Config:
    """Master configuration class."""
    symbol: SymbolConfig = field(default_factory=SymbolConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    market_filter: MarketFilterConfig = field(default_factory=MarketFilterConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    grid: GridConfig = field(default_factory=GridConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    
    # Flask settings
    SECRET_KEY: str = "change-this-in-production-8888"
    DATABASE_PATH: str = "trading.db"
    LOG_PATH: str = "logs/trading.log"


# Global config instance
config = Config()

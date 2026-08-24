"""
Technical Indicators - Calculation of EMA, RSI, ATR, Bollinger Bands, and ADX.
Uses pandas for efficient vectorized calculations.
"""

import logging
from typing import Dict, Optional, Tuple, List
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

from config import config

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Class for calculating technical indicators from MT5 price data.
    All methods return None if insufficient data is available.
    """
    
    def __init__(self):
        """Initialize indicator calculator."""
        pass
    
    def fetch_rates(self, timeframe: int, num_bars: int = 200) -> Optional[pd.DataFrame]:
        """
        Fetch historical rates from MT5.
        
        Args:
            timeframe: MT5 timeframe constant (e.g., mt5.TIMEFRAME_M5)
            num_bars: Number of bars to fetch
            
        Returns:
            DataFrame with OHLCV data or None if failed.
        """
        try:
            rates = mt5.copy_rates_from_pos(
                config.symbol.SYMBOL,
                timeframe,
                0,
                num_bars
            )
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to fetch rates for timeframe {timeframe}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching rates: {str(e)}")
            return None
    
    def calculate_ema(self, df: pd.DataFrame, period: int, column: str = 'close') -> Optional[pd.Series]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            df: DataFrame with price data
            period: EMA period
            column: Column name to calculate EMA on
            
        Returns:
            Series with EMA values or None.
        """
        try:
            if len(df) < period:
                return None
            
            ema = df[column].ewm(span=period, adjust=False).mean()
            return ema
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {str(e)}")
            return None
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """
        Calculate Relative Strength Index.
        
        Args:
            df: DataFrame with price data
            period: RSI period
            
        Returns:
            Series with RSI values or None.
        """
        try:
            if len(df) < period + 1:
                return None
            
            delta = df['close'].diff()
            
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            
            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            return None
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """
        Calculate Average True Range.
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period
            
        Returns:
            Series with ATR values or None.
        """
        try:
            if len(df) < period + 1:
                return None
            
            high = df['high']
            low = df['low']
            close = df['close']
            
            # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR = EMA of TR
            atr = tr.ewm(span=period, adjust=False).mean()
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            return None
    
    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        deviation: float = 2.0
    ) -> Optional[Tuple[pd.Series, pd.Series, pd.Series]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            df: DataFrame with price data
            period: MA period
            deviation: Standard deviation multiplier
            
        Returns:
            Tuple of (upper_band, middle_band, lower_band) or None.
        """
        try:
            if len(df) < period:
                return None
            
            middle = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            
            upper = middle + (deviation * std)
            lower = middle - (deviation * std)
            
            return (upper, middle, lower)
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            return None
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """
        Calculate Average Directional Index (ADX).
        
        Args:
            df: DataFrame with OHLC data
            period: ADX period
            
        Returns:
            Series with ADX values or None.
        """
        try:
            if len(df) < period * 2:
                return None
            
            high = df['high']
            low = df['low']
            close = df['close']
            
            # Calculate +DM and -DM
            plus_dm = high.diff()
            minus_dm = -low.diff()
            
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            
            # Calculate True Range
            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Smooth with EMA
            atr = tr.ewm(span=period, adjust=False).mean()
            plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
            minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
            
            # Calculate DX
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
            
            # ADX = EMA of DX
            adx = dx.ewm(span=period, adjust=False).mean()
            
            return adx
            
        except Exception as e:
            logger.error(f"Error calculating ADX: {str(e)}")
            return None
    
    def get_all_indicators(
        self,
        entry_timeframe: int,
        context_timeframe: int
    ) -> Optional[Dict[str, any]]:
        """
        Fetch all required indicators for both timeframes.
        
        Args:
            entry_timeframe: M5 timeframe for entry signals
            context_timeframe: H1 timeframe for trend/volatility context
            
        Returns:
            Dictionary with all indicator values or None.
        """
        try:
            # Fetch data for both timeframes
            df_entry = self.fetch_rates(entry_timeframe, num_bars=200)
            df_context = self.fetch_rates(context_timeframe, num_bars=100)
            
            if df_entry is None or df_context is None:
                return None
            
            # Entry timeframe indicators (M5)
            ema = self.calculate_ema(df_entry, config.indicators.EMA_PERIOD)
            rsi = self.calculate_rsi(df_entry, config.indicators.RSI_PERIOD)
            
            # Context timeframe indicators (H1)
            atr = self.calculate_atr(df_context, config.indicators.ATR_PERIOD)
            adx = self.calculate_adx(df_context, config.indicators.ATR_PERIOD)
            
            # Bollinger Bands on entry timeframe
            bb = self.calculate_bollinger_bands(
                df_entry,
                config.indicators.BB_PERIOD,
                config.indicators.BB_DEVIATION
            )
            
            if any(x is None for x in [ema, rsi, atr, adx, bb]):
                logger.warning("Some indicators returned None - insufficient data")
                return None
            
            # Get latest values
            current_price = df_entry['close'].iloc[-1]
            
            result = {
                'current_price': current_price,
                'ema': ema.iloc[-1],
                'rsi': rsi.iloc[-1],
                'atr': atr.iloc[-1],  # ATR in price units
                'adx': adx.iloc[-1],
                'bb_upper': bb[0].iloc[-1],
                'bb_middle': bb[1].iloc[-1],
                'bb_lower': bb[2].iloc[-1],
                'df_entry': df_entry,  # For charting
                'df_context': df_context,
            }
            
            logger.debug(
                f"Indicators: Price={current_price:.2f}, EMA={result['ema']:.2f}, "
                f"RSI={result['rsi']:.2f}, ATR={result['atr']:.2f}, ADX={result['adx']:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting all indicators: {str(e)}", exc_info=True)
            return None
    
    def convert_points_to_price(self, points: float, atr: float) -> float:
        """
        Convert point-based distance to price distance using ATR.
        
        Args:
            points: Distance in points
            atr: Current ATR value
            
        Returns:
            Price distance.
        """
        # For XAUUSD, we use ATR directly as the distance measure
        # This is more adaptive than fixed points
        return atr

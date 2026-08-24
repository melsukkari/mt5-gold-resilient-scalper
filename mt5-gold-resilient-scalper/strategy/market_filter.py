"""
Market Filter - Detects "bad market conditions" and determines when to pause trading.
Critical survival mechanism for XAUUSD's high volatility.
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum

from config import config

logger = logging.getLogger(__name__)


class MarketState(Enum):
    """Enumeration of market states."""
    RUNNING = "RUNNING"
    PAUSED_VOLATILITY = "PAUSED_HIGH_VOLATILITY"
    PAUSED_SPREAD = "PAUSED_HIGH_SPREAD"
    PAUSED_TREND = "PAUSED_STRONG_TREND"
    STOPPED = "STOPPED"


class MarketFilter:
    """
    Market condition filter that evaluates whether it's safe to trade.
    Checks volatility, spread, and trend strength before allowing orders.
    """
    
    def __init__(self):
        """Initialize market filter."""
        self.current_state: MarketState = MarketState.STOPPED
        self.last_check_result: Dict[str, any] = {}
    
    def check_market_conditions(
        self,
        indicators: Dict[str, any],
        current_spread: int
    ) -> Tuple[bool, MarketState, str]:
        """
        Evaluate all market conditions and determine if trading is allowed.
        
        Args:
            indicators: Dictionary with ATR, ADX, and other indicator values
            current_spread: Current spread in points
            
        Returns:
            Tuple of (allowed: bool, state: MarketState, reason: str)
        """
        try:
            atr = indicators.get('atr', 0)
            adx = indicators.get('adx', 0)
            
            # Store check results for dashboard
            self.last_check_result = {
                'atr': atr,
                'adx': adx,
                'spread': current_spread,
            }
            
            # 1. Spread Check - High spread increases slippage risk
            if current_spread > config.market_filter.MAX_ALLOWED_SPREAD:
                self.current_state = MarketState.PAUSED_SPREAD
                reason = f"Spread too high: {current_spread} points (max: {config.market_filter.MAX_ALLOWED_SPREAD})"
                logger.warning(f"Trading PAUSED: {reason}")
                return (False, self.current_state, reason)
            
            # 2. Volatility Check - Extreme volatility increases gap risk
            # We need a baseline ATR to compare against
            # For simplicity, we use an absolute threshold based on typical XAUUSD ATR
            # Typical XAUUSD ATR on H1 is around 5-15 USD
            # If ATR > 2x normal (e.g., > 30), pause trading
            atr_threshold = 30.0  # Adjust based on broker's XAUUSD characteristics
            
            if atr > atr_threshold * config.market_filter.ATR_VOLATILITY_MULTIPLIER:
                self.current_state = MarketState.PAUSED_VOLATILITY
                reason = f"ATR too high: {atr:.2f} (threshold: {atr_threshold * config.market_filter.ATR_VOLATILITY_MULTIPLIER:.2f})"
                logger.warning(f"Trading PAUSED: {reason}")
                return (False, self.current_state, reason)
            
            # 3. Trend Strength Check - Strong trends break grid strategies
            if adx > config.market_filter.ADX_STRONG_TREND:
                self.current_state = MarketState.PAUSED_TREND
                reason = f"Strong trend detected: ADX={adx:.2f} (threshold: {config.market_filter.ADX_STRONG_TREND})"
                logger.info(f"Trading PAUSED: {reason} - Consider trend-following mode")
                return (False, self.current_state, reason)
            
            # All checks passed
            self.current_state = MarketState.RUNNING
            reason = "All market conditions favorable"
            logger.debug(f"Trading ALLOWED: {reason}")
            return (True, self.current_state, reason)
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {str(e)}")
            self.current_state = MarketState.STOPPED
            return (False, self.current_state, f"Error evaluating conditions: {str(e)}")
    
    def get_market_bias(
        self,
        indicators: Dict[str, any]
    ) -> str:
        """
        Determine market bias based on EMA and RSI.
        
        Args:
            indicators: Dictionary with EMA, RSI, ADX values
            
        Returns:
            'bullish', 'bearish', or 'neutral'
        """
        try:
            price = indicators.get('current_price', 0)
            ema = indicators.get('ema', 0)
            rsi = indicators.get('rsi', 50)
            adx = indicators.get('adx', 0)
            
            # In strong trending markets (ADX > 30), follow the trend
            if adx > config.market_filter.ADX_STRONG_TREND:
                if price > ema:
                    return 'bullish'
                elif price < ema:
                    return 'bearish'
            
            # Range-bound market (ADX < 25) - use mean reversion
            if adx < config.market_filter.ADX_RANGE_BOUND:
                # In range-bound markets, fade extremes
                if rsi < config.indicators.RSI_OVERSOLD:
                    return 'bullish'  # Oversold - expect bounce up
                elif rsi > config.indicators.RSI_OVERBOUGHT:
                    return 'bearish'  # Overbought - expect drop down
            
            # Default bias based on EMA and RSI
            if price > ema and rsi > 50:
                return 'bullish'
            elif price < ema and rsi < 50:
                return 'bearish'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error determining market bias: {str(e)}")
            return 'neutral'
    
    def get_state(self) -> MarketState:
        """Get current market state."""
        return self.current_state
    
    def get_last_check_result(self) -> Dict[str, any]:
        """Get results of last market condition check."""
        return self.last_check_result
    
    def reset(self) -> None:
        """Reset filter state."""
        self.current_state = MarketState.STOPPED
        self.last_check_result = {}

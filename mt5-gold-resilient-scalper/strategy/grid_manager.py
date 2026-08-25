"""
Grid Manager - Core logic for order placement, modification, and cancellation.
Implements the ATR-based dynamic grid strategy for XAUUSD.
"""

import logging
import time
from typing import Dict, Tuple

import MetaTrader5 as mt5

from config import config

from .indicators import TechnicalIndicators
from .market_filter import MarketFilter
from .mt5_connector import MT5Connector
from .risk_manager import RiskManager

logger = logging.getLogger(__name__)


class GridManager:
    """
    Manages the dynamic grid strategy for XAUUSD.
    Places pending orders based on ATR distances and market bias.
    """

    def __init__(
        self,
        mt5_connector: MT5Connector,
        indicators: TechnicalIndicators,
        market_filter: MarketFilter,
        risk_manager: RiskManager,
    ):
        """
        Initialize grid manager.

        Args:
            mt5_connector: MT5 API wrapper
            indicators: Technical indicator calculator
            market_filter: Market condition filter
            risk_manager: Risk management controller
        """
        self.mt5 = mt5_connector
        self.indicators = indicators
        self.market_filter = market_filter
        self.risk_manager = risk_manager

        self.last_entry_time: float = 0
        self.position_closed_time: float = 0
        self._last_position_count: int = 0

    def should_place_orders(self) -> Tuple[bool, str]:
        """
        Determine if new orders should be placed.

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check if enough time has passed since last position closed
        if self.position_closed_time > 0:
            time_since_close = time.time() - self.position_closed_time
            if time_since_close < config.grid.CHECK_INTERVAL:
                return (
                    False,
                    f"Waiting {config.grid.CHECK_INTERVAL}s after position close "
                    f"({time_since_close:.0f}s elapsed)",
                )

        return (True, "Ready to place orders")

    def _calculate_order_levels(
        self, current_price: float, atr: float
    ) -> Dict[str, float]:
        """
        Calculate entry, SL, and TP levels based on ATR.

        Args:
            current_price: Current market price
            atr: Average True Range value

        Returns:
            Dictionary with buy and sell order levels.
        """
        gap_distance = atr * config.grid.GAP_DISTANCE_MULTIPLIER
        tp_distance = atr * config.grid.TP_MULTIPLIER
        sl_distance = atr * config.grid.SL_MULTIPLIER

        # Buy Stop order (above current price)
        buy_entry = current_price + gap_distance
        buy_tp = buy_entry + tp_distance
        buy_sl = buy_entry - sl_distance

        # Sell Stop order (below current price)
        sell_entry = current_price - gap_distance
        sell_tp = sell_entry - tp_distance
        sell_sl = sell_entry + sl_distance

        return {
            "buy_entry": buy_entry,
            "buy_tp": buy_tp,
            "buy_sl": buy_sl,
            "sell_entry": sell_entry,
            "sell_tp": sell_tp,
            "sell_sl": sell_sl,
            "sl_distance_points": sl_distance / self.mt5.symbol_info["tick_size"],
        }

    def _get_market_bias(self, indicators: Dict[str, any]) -> str:
        """
        Determine market bias for order placement.

        Args:
            indicators: Dictionary with indicator values

        Returns:
            'bullish', 'bearish', or 'neutral'
        """
        return self.market_filter.get_market_bias(indicators)

    def execute_strategy_cycle(self) -> Dict[str, any]:
        """
        Execute one complete strategy cycle.
        Checks conditions, places/cancels orders as needed.

        Returns:
            Dictionary with execution results.
        """
        result = {
            "success": False,
            "action": "none",
            "message": "",
            "orders_placed": 0,
            "orders_cancelled": 0,
        }

        try:
            # Step 1: Get account info and check risk limits
            account_info = self.mt5.get_account_info()
            if not account_info:
                result["message"] = "Failed to get account info"
                return result

            positions = self.mt5.get_positions(symbol=config.symbol.SYMBOL)
            position_count = len(
                [p for p in positions if p.magic == config.trading.MAGIC_NUMBER]
            )

            # Check if position was just closed
            if self._last_position_count > 0 and position_count == 0:
                self.position_closed_time = time.time()
                logger.info("Position closed - waiting for re-entry cooldown")
                # Cancel all pending orders after position close
                cancelled = self.mt5.cancel_all_pending_orders()
                result["orders_cancelled"] = cancelled

            self._last_position_count = position_count

            # Perform risk checks
            risk_allowed, risk_reason = self.risk_manager.perform_all_risk_checks(
                account_info, position_count
            )
            if not risk_allowed:
                result["message"] = f"Risk check failed: {risk_reason}"
                return result

            # Step 2: Check if we should place orders
            should_place, place_reason = self.should_place_orders()
            if not should_place:
                result["message"] = place_reason
                return result

            # Step 3: Fetch indicators
            indicators = self.indicators.get_all_indicators(
                mt5.TIMEFRAME_M5, mt5.TIMEFRAME_H1
            )

            if not indicators:
                result["message"] = "Failed to fetch indicators"
                return result

            # Step 4: Check market conditions
            spread = self.mt5.get_spread()
            if spread is None:
                result["message"] = "Failed to get spread"
                return result

            allowed, state, reason = self.market_filter.check_market_conditions(
                indicators, spread
            )

            if not allowed:
                result["message"] = f"Market conditions unfavorable: {reason}"
                result["market_state"] = state.value
                return result

            # Step 5: Determine bias and calculate levels
            bias = self._get_market_bias(indicators)
            current_price = indicators["current_price"]
            atr = indicators["atr"]

            levels = self._calculate_order_levels(current_price, atr)

            # Step 6: Place orders based on bias
            orders_placed = 0

            if bias == "bullish":
                # Place only Buy Stop
                success = self._place_pending_order(
                    order_type=mt5.ORDER_TYPE_BUY_STOP,
                    entry=levels["buy_entry"],
                    sl=levels["buy_sl"],
                    tp=levels["buy_tp"],
                    lot_size=self._calculate_lot_size(
                        levels["sl_distance_points"], account_info["balance"]
                    ),
                )
                if success:
                    orders_placed += 1

            elif bias == "bearish":
                # Place only Sell Stop
                success = self._place_pending_order(
                    order_type=mt5.ORDER_TYPE_SELL_STOP,
                    entry=levels["sell_entry"],
                    sl=levels["sell_sl"],
                    tp=levels["sell_tp"],
                    lot_size=self._calculate_lot_size(
                        levels["sl_distance_points"], account_info["balance"]
                    ),
                )
                if success:
                    orders_placed += 1

            else:  # neutral
                # Place both Buy Stop and Sell Stop (grid mode)
                success_buy = self._place_pending_order(
                    order_type=mt5.ORDER_TYPE_BUY_STOP,
                    entry=levels["buy_entry"],
                    sl=levels["buy_sl"],
                    tp=levels["buy_tp"],
                    lot_size=self._calculate_lot_size(
                        levels["sl_distance_points"], account_info["balance"]
                    ),
                )

                success_sell = self._place_pending_order(
                    order_type=mt5.ORDER_TYPE_SELL_STOP,
                    entry=levels["sell_entry"],
                    sl=levels["sell_sl"],
                    tp=levels["sell_tp"],
                    lot_size=self._calculate_lot_size(
                        levels["sl_distance_points"], account_info["balance"]
                    ),
                )

                if success_buy:
                    orders_placed += 1
                if success_sell:
                    orders_placed += 1

            result["success"] = orders_placed > 0
            result["action"] = "orders_placed" if orders_placed > 0 else "no_action"
            result["orders_placed"] = orders_placed
            result["message"] = f"Placed {orders_placed} orders (bias={bias})"
            result["market_state"] = state.value
            result["bias"] = bias

            if orders_placed > 0:
                self.last_entry_time = time.time()

            return result

        except Exception as e:
            logger.error(f"Error in strategy cycle: {str(e)}", exc_info=True)
            result["message"] = f"Strategy error: {str(e)}"
            return result

    def _place_pending_order(
        self, order_type: int, entry: float, sl: float, tp: float, lot_size: float
    ) -> bool:
        """
        Place a pending order if one doesn't already exist.

        Args:
            order_type: BUY_STOP or SELL_STOP
            entry: Entry price
            sl: Stop loss
            tp: Take profit
            lot_size: Lot size

        Returns:
            bool: True if order placed successfully.
        """
        try:
            # Check if similar order already exists
            existing_orders = self.mt5.get_pending_orders()

            for order in existing_orders:
                # Check if order of same type exists within reasonable distance
                if order.type == order_type:
                    price_diff = abs(order.price - entry)
                    if price_diff < 1.0:  # Within $1
                        logger.debug(f"Similar order already exists at {order.price}")
                        return True

            # Place new order
            order_type_name = (
                "BUY_STOP" if order_type == mt5.ORDER_TYPE_BUY_STOP else "SELL_STOP"
            )
            success, ticket = self.mt5.place_order(
                order_type=order_type,
                volume=lot_size,
                price=entry,
                sl=sl,
                tp=tp,
                comment=f"{config.trading.ORDER_COMMENT}_{order_type_name}",
            )

            return success

        except Exception as e:
            logger.error(f"Error placing pending order: {str(e)}")
            return False

    def _calculate_lot_size(self, sl_distance_points: float, balance: float) -> float:
        """
        Calculate lot size using MT5 connector's method.

        Args:
            sl_distance_points: SL distance in points
            balance: Account balance

        Returns:
            float: Calculated lot size.
        """
        return self.mt5.calculate_lot_size(sl_distance_points)

    def emergency_stop(self) -> Dict[str, any]:
        """
        Emergency stop - close all positions and cancel all orders.

        Returns:
            Dictionary with results.
        """
        result = {
            "positions_closed": 0,
            "orders_cancelled": 0,
        }

        # Cancel all pending orders
        result["orders_cancelled"] = self.mt5.cancel_all_pending_orders()

        # Close all positions
        result["positions_closed"] = self.mt5.close_all_positions()

        logger.warning(f"Emergency stop executed: {result}")
        return result

    def get_strategy_status(self) -> Dict[str, any]:
        """
        Get current strategy status.

        Returns:
            Dictionary with status information.
        """
        return {
            "last_entry_time": self.last_entry_time,
            "position_closed_time": self.position_closed_time,
            "market_state": self.market_filter.get_state().value,
            "last_check_result": self.market_filter.get_last_check_result(),
        }

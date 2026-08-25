"""
MT5 Connector - Robust wrapper for MetaTrader 5 API with comprehensive error handling.
Handles connection, symbol info retrieval, order placement, and position management.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import MetaTrader5 as mt5

from config import config

logger = logging.getLogger(__name__)


class MT5Connector:
    """
    Wrapper class for MetaTrader 5 Python API.
    Provides robust connection management and error handling for all MT5 operations.
    """

    def __init__(self):
        """Initialize MT5 connector."""
        self.connected: bool = False
        self.symbol_info: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None

    def connect(self) -> bool:
        """
        Establish connection to MT5 terminal.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            conn_cfg = config.connection
            init_kwargs: Dict[str, Any] = {}

            if conn_cfg.MT5_PATH:
                init_kwargs["path"] = conn_cfg.MT5_PATH
            if conn_cfg.MT5_LOGIN:
                init_kwargs["login"] = conn_cfg.MT5_LOGIN
            if conn_cfg.MT5_PASSWORD:
                init_kwargs["password"] = conn_cfg.MT5_PASSWORD
            if conn_cfg.MT5_SERVER:
                init_kwargs["server"] = conn_cfg.MT5_SERVER

            # Initialize MT5 with explicit terminal path (fixes IPC pipe timeout)
            if not mt5.initialize(**init_kwargs):
                self._last_error = f"MT5 initialize failed: {mt5.last_error()}"
                logger.error(self._last_error)
                return False

            # Check connection
            if not mt5.terminal_info().connected:
                self._last_error = "Terminal not connected to trading server"
                logger.error(self._last_error)
                return False

            self.connected = True
            logger.info("Successfully connected to MT5")

            # Fetch symbol info for XAUUSD
            self._fetch_symbol_info()

            return True

        except Exception as e:
            self._last_error = f"Connection error: {str(e)}"
            logger.error(self._last_error, exc_info=True)
            return False

    def disconnect(self) -> None:
        """Gracefully disconnect from MT5."""
        try:
            if self.connected:
                mt5.shutdown()
                self.connected = False
                logger.info("Disconnected from MT5")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")

    def _fetch_symbol_info(self) -> bool:
        """
        Fetch and cache symbol information for XAUUSD.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            symbol = config.symbol.SYMBOL
            info = mt5.symbol_info(symbol)

            if info is None or not info.visible:
                self._last_error = f"Symbol {symbol} not found or not visible"
                logger.error(self._last_error)
                return False

            self.symbol_info = {
                "name": info.name,
                "digits": info.digits,
                "spread": info.spread,
                "trade_contract_size": info.trade_contract_size,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
                "tick_value": info.trade_tick_value,
                "tick_size": info.trade_tick_size,
            }

            logger.info(f"Symbol info fetched: {self.symbol_info}")
            return True

        except Exception as e:
            self._last_error = f"Error fetching symbol info: {str(e)}"
            logger.error(self._last_error, exc_info=True)
            return False

    def refresh_symbol_info(self) -> bool:
        """Refresh symbol information (call periodically for live spread)."""
        return self._fetch_symbol_info()

    def get_current_price(self) -> Optional[Tuple[float, float]]:
        """
        Get current bid and ask prices.

        Returns:
            Tuple[float, float]: (bid, ask) prices or None if failed.
        """
        try:
            tick = mt5.symbol_info_tick(config.symbol.SYMBOL)
            if tick is None:
                return None
            return (tick.bid, tick.ask)
        except Exception as e:
            logger.error(f"Error getting price: {str(e)}")
            return None

    def get_spread(self) -> Optional[int]:
        """
        Get current spread in points.

        Returns:
            int: Spread in points or None if failed.
        """
        try:
            tick = mt5.symbol_info_tick(config.symbol.SYMBOL)
            if tick is None:
                return None
            # Spread in points = (ask - bid) / tick_size
            spread_points = int((tick.ask - tick.bid) / self.symbol_info["tick_size"])
            return spread_points
        except Exception as e:
            logger.error(f"Error getting spread: {str(e)}")
            return None

    def get_account_info(self) -> Optional[Dict[str, float]]:
        """
        Get account information.

        Returns:
            Dict with balance, equity, margin, margin_level, profit.
        """
        try:
            account = mt5.account_info()
            if account is None:
                return None

            return {
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_level": account.margin_level,
                "profit": account.profit,
                "currency": account.currency,
            }
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None

    def get_positions(self, symbol: Optional[str] = None) -> List[Any]:
        """
        Get open positions.

        Args:
            symbol: Filter by symbol (optional).

        Returns:
            List of position objects.
        """
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()

            return positions if positions else []

        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return []

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[Any]:
        """
        Get pending orders.

        Args:
            symbol: Filter by symbol (optional).

        Returns:
            List of order objects.
        """
        try:
            if symbol:
                orders = mt5.orders_get(symbol=symbol)
            else:
                orders = mt5.orders_get()

            # Filter by magic number
            if orders:
                orders = [o for o in orders if o.magic == config.trading.MAGIC_NUMBER]

            return orders if orders else []

        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            return []

    def calculate_lot_size(self, sl_distance_points: float) -> float:
        """
        Calculate lot size based on risk parameters and SL distance.

        Args:
            sl_distance_points: Stop loss distance in points.

        Returns:
            float: Calculated lot size.
        """
        try:
            account_info = self.get_account_info()
            if not account_info:
                return config.risk.MIN_LOT_SIZE

            balance = account_info["balance"]
            risk_amount = balance * config.risk.RISK_PERCENT

            # Calculate money per point per lot
            tick_value = self.symbol_info["tick_value"]
            tick_size = self.symbol_info["tick_size"]

            # Money per point = tick_value / tick_size
            money_per_point = tick_value / tick_size

            # SL distance in money = sl_distance_points * money_per_point * lots
            # Rearranging: lots = risk_amount / (sl_distance_points * money_per_point)
            if sl_distance_points <= 0:
                return config.risk.MIN_LOT_SIZE

            lot_size = risk_amount / (sl_distance_points * money_per_point)

            # Apply constraints
            lot_size = max(lot_size, config.risk.MIN_LOT_SIZE)
            lot_size = min(lot_size, config.risk.MAX_LOT_SIZE)

            # Round to lot step
            lot_step = self.symbol_info["volume_step"]
            lot_size = round(lot_size / lot_step) * lot_step

            logger.info(
                f"Calculated lot size: {lot_size} (risk={risk_amount:.2f}, sl_points={sl_distance_points})"
            )
            return lot_size

        except Exception as e:
            logger.error(f"Error calculating lot size: {str(e)}")
            return config.risk.MIN_LOT_SIZE

    def place_order(
        self,
        order_type: int,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> Tuple[bool, Optional[int]]:
        """
        Place a pending order (Buy Stop or Sell Stop).

        Args:
            order_type: mt5.ORDER_TYPE_BUY_STOP or mt5.ORDER_TYPE_SELL_STOP
            volume: Lot size
            price: Entry price
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment

        Returns:
            Tuple[bool, Optional[int]]: (success, order_ticket)
        """
        try:
            if not self.connected:
                logger.error("Not connected to MT5")
                return (False, None)

            # Determine order type name for logging
            type_name = (
                "BUY_STOP" if order_type == mt5.ORDER_TYPE_BUY_STOP else "SELL_STOP"
            )

            # Create order request
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": config.symbol.SYMBOL,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": config.trading.DEVIATION,
                "magic": config.trading.MAGIC_NUMBER,
                "comment": comment or config.trading.ORDER_COMMENT,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }

            # Send order
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self._last_error = (
                    f"Order failed: {result.comment} (retcode={result.retcode})"
                )
                logger.error(self._last_error)
                return (False, None)

            logger.info(
                f"Order placed successfully: {type_name} {volume} lots at {price}, SL={sl}, TP={tp}"
            )
            return (True, result.order)

        except Exception as e:
            self._last_error = f"Error placing order: {str(e)}"
            logger.error(self._last_error, exc_info=True)
            return (False, None)

    def cancel_order(self, order_ticket: int) -> bool:
        """
        Cancel a pending order.

        Args:
            order_ticket: The order ticket to cancel.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order_ticket,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Cancel order failed: {result.comment}")
                return False

            logger.info(f"Order {order_ticket} cancelled successfully")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return False

    def cancel_all_pending_orders(self) -> int:
        """
        Cancel all pending orders belonging to this bot.

        Returns:
            int: Number of orders cancelled.
        """
        orders = self.get_pending_orders()
        cancelled_count = 0

        for order in orders:
            if self.cancel_order(order.ticket):
                cancelled_count += 1

        return cancelled_count

    def close_all_positions(self) -> int:
        """
        Close all open positions belonging to this bot.

        Returns:
            int: Number of positions closed.
        """
        positions = self.get_positions(symbol=config.symbol.SYMBOL)
        closed_count = 0

        for position in positions:
            if position.magic != config.trading.MAGIC_NUMBER:
                continue

            try:
                # Determine opposite order type for closing
                if position.type == mt5.POSITION_TYPE_BUY:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = mt5.symbol_info_tick(config.symbol.SYMBOL).bid
                else:
                    order_type = mt5.ORDER_TYPE_BUY
                    price = mt5.symbol_info_tick(config.symbol.SYMBOL).ask

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": config.symbol.SYMBOL,
                    "volume": position.volume,
                    "type": order_type,
                    "position": position.ticket,
                    "price": price,
                    "deviation": config.trading.DEVIATION,
                    "magic": config.trading.MAGIC_NUMBER,
                    "comment": "Emergency Close",
                }

                result = mt5.order_send(request)

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    closed_count += 1
                    logger.info(f"Position {position.ticket} closed successfully")
                else:
                    logger.error(
                        f"Failed to close position {position.ticket}: {result.comment}"
                    )

            except Exception as e:
                logger.error(f"Error closing position: {str(e)}")

        return closed_count

    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        return (
            self.connected and mt5.terminal_info().connected
            if mt5.terminal_info()
            else False
        )

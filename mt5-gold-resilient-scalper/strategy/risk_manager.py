"""
Risk Manager - Dynamic lot sizing, drawdown protection, and daily loss limits.
Critical for capital preservation in high-volatility XAUUSD trading.
"""

import logging
from datetime import date
from typing import Any, Dict, Optional, Tuple

from config import config

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Manages all risk-related calculations and protections.
    Enforces position limits, daily loss limits, and equity protection.
    """

    def __init__(self):
        """Initialize risk manager."""
        self.starting_balance: Optional[float] = None
        self.daily_start_balance: Optional[float] = None
        self.last_reset_date: Optional[date] = None
        self._check_daily_reset()

    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily tracking (new day)."""
        today = date.today()

        if self.last_reset_date != today:
            self.last_reset_date = today
            self.daily_start_balance = None
            logger.info(f"Daily risk tracking reset for {today}")

    def set_starting_balance(self, balance: float) -> None:
        """
        Set the starting balance for equity protection calculations.

        Args:
            balance: Account balance at bot startup.
        """
        self.starting_balance = balance
        self.daily_start_balance = balance
        logger.info(f"Starting balance set: ${balance:.2f}")

    def calculate_position_size(
        self, sl_distance_points: float, account_balance: float
    ) -> float:
        """
        Calculate lot size based on risk percentage and SL distance.

        Formula: Lot = (Balance * Risk%) / (SL_Distance_Points * Money_Per_Point)

        Args:
            sl_distance_points: Stop loss distance in points
            account_balance: Current account balance

        Returns:
            float: Calculated lot size within min/max constraints.
        """
        try:
            # Risk amount in currency
            risk_amount = account_balance * config.risk.RISK_PERCENT

            # For XAUUSD, money per point depends on contract size
            # Standard lot (1.0) = 100 oz of gold
            # 1 point move = $0.01 * 100 = $1 per standard lot
            # But we need to get this from MT5 symbol info dynamically
            # Default assumption: 1 point = $1 per standard lot
            money_per_point_per_lot = 1.0

            if sl_distance_points <= 0:
                logger.warning("Invalid SL distance, using minimum lot")
                return config.risk.MIN_LOT_SIZE

            # Calculate lot size
            lot_size = risk_amount / (sl_distance_points * money_per_point_per_lot)

            # Apply constraints
            lot_size = max(lot_size, config.risk.MIN_LOT_SIZE)
            lot_size = min(lot_size, config.risk.MAX_LOT_SIZE)

            # Round to lot step (typically 0.01)
            lot_step = config.risk.LOT_STEP
            lot_size = round(lot_size / lot_step) * lot_step

            logger.info(
                f"Position size calculated: {lot_size} lots "
                f"(risk=${risk_amount:.2f}, SL={sl_distance_points} points)"
            )

            return lot_size

        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return config.risk.MIN_LOT_SIZE

    def check_daily_loss_limit(self, current_balance: float) -> Tuple[bool, str]:
        """
        Check if daily loss limit has been breached.

        Args:
            current_balance: Current account balance

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        self._check_daily_reset()

        # Initialize daily start balance if not set
        if self.daily_start_balance is None:
            self.daily_start_balance = current_balance
            logger.info(f"Daily start balance initialized: ${current_balance:.2f}")
            return (True, "Daily tracking started")

        # Calculate daily P&L
        daily_pnl = current_balance - self.daily_start_balance
        daily_loss_percent = (
            abs(daily_pnl) / self.daily_start_balance if daily_pnl < 0 else 0
        )

        # Check against limit
        if daily_loss_percent >= config.risk.DAILY_LOSS_LIMIT_PERCENT:
            reason = (
                f"Daily loss limit reached: {daily_loss_percent * 100:.2f}% "
                f"(limit: {config.risk.DAILY_LOSS_LIMIT_PERCENT * 100:.2f}%)"
            )
            logger.warning(f"Trading HALTED: {reason}")
            return (False, reason)

        return (True, f"Daily loss within limits ({daily_loss_percent * 100:.2f}%)")

    def check_equity_protection(self, current_equity: float) -> Tuple[bool, str]:
        """
        Check if equity drawdown exceeds protection threshold.

        Args:
            current_equity: Current account equity

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if self.starting_balance is None:
            return (True, "Starting balance not set")

        # Calculate equity drawdown
        drawdown = self.starting_balance - current_equity
        drawdown_percent = drawdown / self.starting_balance if drawdown > 0 else 0

        if drawdown_percent >= config.risk.EQUITY_DRAWDOWN_LIMIT:
            reason = (
                f"Equity protection triggered: {drawdown_percent * 100:.2f}% drawdown "
                f"(limit: {config.risk.EQUITY_DRAWDOWN_LIMIT * 100:.2f}%)"
            )
            logger.critical(f"EMERGENCY STOP: {reason}")
            return (False, reason)

        return (True, f"Equity drawdown within limits ({drawdown_percent * 100:.2f}%)")

    def check_max_positions(self, current_positions: int) -> Tuple[bool, str]:
        """
        Check if maximum position limit is respected.

        Args:
            current_positions: Number of currently open positions

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        if current_positions >= config.risk.MAX_OPEN_POSITIONS:
            reason = f"Max positions reached: {current_positions} (limit: {config.risk.MAX_OPEN_POSITIONS})"
            return (False, reason)

        return (
            True,
            f"Position count OK ({current_positions}/{config.risk.MAX_OPEN_POSITIONS})",
        )

    def perform_all_risk_checks(
        self, account_info: Dict[str, float], current_positions: int
    ) -> Tuple[bool, str]:
        """
        Perform all risk management checks.

        Args:
            account_info: Dictionary with balance, equity from MT5
            current_positions: Number of open positions

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Initialize starting balance if needed
        if self.starting_balance is None:
            self.set_starting_balance(account_info["balance"])

        # Check daily loss limit
        allowed, reason = self.check_daily_loss_limit(account_info["balance"])
        if not allowed:
            return (False, reason)

        # Check equity protection
        allowed, reason = self.check_equity_protection(account_info["equity"])
        if not allowed:
            return (False, reason)

        # Check max positions
        allowed, reason = self.check_max_positions(current_positions)
        if not allowed:
            return (False, reason)

        return (True, "All risk checks passed")

    def get_risk_summary(self, account_info: Dict[str, float]) -> Dict[str, Any]:
        """
        Get a summary of current risk metrics.

        Args:
            account_info: Dictionary with balance, equity

        Returns:
            Dictionary with risk metrics.
        """
        self._check_daily_reset()

        starting = self.starting_balance or account_info["balance"]
        daily_start = self.daily_start_balance or account_info["balance"]

        total_drawdown = starting - account_info["equity"]
        total_drawdown_pct = (total_drawdown / starting * 100) if starting > 0 else 0

        daily_pnl = account_info["balance"] - daily_start
        daily_pnl_pct = (daily_pnl / daily_start * 100) if daily_start > 0 else 0

        return {
            "starting_balance": starting,
            "daily_start_balance": daily_start,
            "current_balance": account_info["balance"],
            "current_equity": account_info["equity"],
            "total_drawdown_usd": total_drawdown,
            "total_drawdown_percent": total_drawdown_pct,
            "daily_pnl_usd": daily_pnl,
            "daily_pnl_percent": daily_pnl_pct,
            "daily_loss_limit_percent": config.risk.DAILY_LOSS_LIMIT_PERCENT * 100,
            "equity_protection_limit": config.risk.EQUITY_DRAWDOWN_LIMIT * 100,
            "risk_per_trade_percent": config.risk.RISK_PERCENT * 100,
        }

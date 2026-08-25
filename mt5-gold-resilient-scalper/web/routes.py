"""
Web routes for the trading dashboard.
Provides API endpoints for live data and control actions.
"""

import logging
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session

from config import config
from web.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint("web", __name__)

# Global reference to trading bot (set by app.py)
trading_bot = None


def set_trading_bot(bot):
    """Set the trading bot instance for route access."""
    global trading_bot
    trading_bot = bot


def api_login_required(f):
    """Decorator for API endpoints that returns JSON on auth failure."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated_function


@web_bp.route("/")
@login_required
def dashboard():
    """Render main dashboard page."""
    return render_template("dashboard.html")


@web_bp.route("/api/status")
@api_login_required
def api_status():
    """Get current trading status."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        status = trading_bot.get_full_status()
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/start", methods=["POST"])
@api_login_required
def api_start():
    """Start trading."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        trading_bot.start_trading()
        return jsonify({"success": True, "message": "Trading started"})

    except Exception as e:
        logger.error(f"Error starting trading: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/stop", methods=["POST"])
@api_login_required
def api_stop():
    """Stop trading."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        trading_bot.stop_trading()
        return jsonify({"success": True, "message": "Trading stopped"})

    except Exception as e:
        logger.error(f"Error stopping trading: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/emergency", methods=["POST"])
@api_login_required
def api_emergency():
    """Emergency stop - close all positions and cancel orders."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        result = trading_bot.emergency_stop()
        return jsonify(
            {"success": True, "message": "Emergency stop executed", "result": result}
        )

    except Exception as e:
        logger.error(f"Error during emergency stop: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/config", methods=["GET"])
@api_login_required
def api_get_config():
    """Get current configuration."""
    try:
        config_data = {
            "risk_percent": config.risk.RISK_PERCENT * 100,
            "daily_loss_limit": config.risk.DAILY_LOSS_LIMIT_PERCENT * 100,
            "equity_drawdown_limit": config.risk.EQUITY_DRAWDOWN_LIMIT * 100,
            "gap_distance_multiplier": config.grid.GAP_DISTANCE_MULTIPLIER,
            "tp_multiplier": config.grid.TP_MULTIPLIER,
            "sl_multiplier": config.grid.SL_MULTIPLIER,
            "ema_period": config.indicators.EMA_PERIOD,
            "rsi_period": config.indicators.RSI_PERIOD,
            "max_spread": config.market_filter.MAX_ALLOWED_SPREAD,
            "adx_threshold": config.market_filter.ADX_STRONG_TREND,
        }
        return jsonify(config_data)

    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/config", methods=["POST"])
@api_login_required
def api_update_config():
    """Update configuration parameters."""
    try:
        data = request.get_json()

        # Update risk config
        if "risk_percent" in data:
            config.risk.RISK_PERCENT = float(data["risk_percent"]) / 100
        if "daily_loss_limit" in data:
            config.risk.DAILY_LOSS_LIMIT_PERCENT = float(data["daily_loss_limit"]) / 100
        if "equity_drawdown_limit" in data:
            config.risk.EQUITY_DRAWDOWN_LIMIT = (
                float(data["equity_drawdown_limit"]) / 100
            )

        # Update grid config
        if "gap_distance_multiplier" in data:
            config.grid.GAP_DISTANCE_MULTIPLIER = float(data["gap_distance_multiplier"])
        if "tp_multiplier" in data:
            config.grid.TP_MULTIPLIER = float(data["tp_multiplier"])
        if "sl_multiplier" in data:
            config.grid.SL_MULTIPLIER = float(data["sl_multiplier"])

        # Update indicator config
        if "ema_period" in data:
            config.indicators.EMA_PERIOD = int(data["ema_period"])
        if "rsi_period" in data:
            config.indicators.RSI_PERIOD = int(data["rsi_period"])

        # Update market filter config
        if "max_spread" in data:
            config.market_filter.MAX_ALLOWED_SPREAD = int(data["max_spread"])
        if "adx_threshold" in data:
            config.market_filter.ADX_STRONG_TREND = float(data["adx_threshold"])

        logger.info(f"Configuration updated: {data}")

        return jsonify(
            {"success": True, "message": "Configuration updated successfully"}
        )

    except Exception as e:
        logger.error(f"Error updating config: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/trades")
@api_login_required
def api_trades():
    """Get recent trade history."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        trades = trading_bot.get_trade_history()
        return jsonify({"trades": trades})

    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        return jsonify({"error": str(e)}), 500


@web_bp.route("/api/chart_data")
@api_login_required
def api_chart_data():
    """Get chart data for Chart.js."""
    try:
        if trading_bot is None:
            return jsonify({"error": "Trading bot not initialized"}), 500

        chart_data = trading_bot.get_chart_data()
        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting chart data: {str(e)}")
        return jsonify({"error": str(e)}), 500

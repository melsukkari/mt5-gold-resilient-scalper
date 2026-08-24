"""
MT5 Gold Resilient Scalper - Main Application Entry Point

This is the main orchestrator that connects all components:
- MT5 connection and trading loop
- Flask web dashboard
- Strategy execution with risk management

WARNING: XAUUSD (Gold) is a high-volatility instrument. This bot is for
educational/demo purposes only. Always test on a demo account first.
"""

import logging
import threading
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List

from flask import Flask
from config import config
from strategy import MT5Connector, TechnicalIndicators, GridManager, RiskManager, MarketFilter
from web import auth_bp, web_bp, set_trading_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Main trading bot class that orchestrates all components.
    Runs the trading strategy in a background thread while serving the web dashboard.
    """
    
    def __init__(self):
        """Initialize the trading bot with all required components."""
        # Initialize components
        self.mt5 = MT5Connector()
        self.indicators = TechnicalIndicators()
        self.market_filter = MarketFilter()
        self.risk_manager = RiskManager()
        
        # Initialize grid manager with dependencies
        self.grid_manager = GridManager(
            mt5_connector=self.mt5,
            indicators=self.indicators,
            market_filter=self.market_filter,
            risk_manager=self.risk_manager
        )
        
        # State management
        self.is_running: bool = False
        self.trading_enabled: bool = False
        self.stop_event = threading.Event()
        self.trading_thread: Optional[threading.Thread] = None
        
        # Trade history (in-memory, last 100 trades)
        self.trade_history: List[Dict[str, Any]] = []
        self.max_history = 100
        
        # Chart data cache
        self.chart_data_cache: Dict[str, Any] = {
            'labels': [],
            'prices': [],
            'ema': []
        }
        
        logger.info("Trading bot initialized")
    
    def connect(self) -> bool:
        """
        Connect to MT5 terminal.
        
        Returns:
            bool: True if connection successful.
        """
        return self.mt5.connect()
    
    def disconnect(self) -> None:
        """Disconnect from MT5 and cleanup."""
        self.stop_trading()
        self.mt5.disconnect()
        logger.info("Trading bot disconnected")
    
    def start_trading(self) -> bool:
        """
        Start the trading thread.
        
        Returns:
            bool: True if started successfully.
        """
        if self.is_running:
            logger.warning("Trading already running")
            return False
        
        if not self.mt5.is_connected():
            logger.error("Cannot start trading - not connected to MT5")
            return False
        
        self.is_running = True
        self.trading_enabled = True
        self.stop_event.clear()
        
        # Start trading thread
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        
        logger.info("Trading started")
        return True
    
    def stop_trading(self) -> None:
        """Stop the trading thread gracefully."""
        if not self.is_running:
            return
        
        self.trading_enabled = False
        self.stop_event.set()
        
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        
        self.is_running = False
        logger.info("Trading stopped")
    
    def _trading_loop(self) -> None:
        """
        Main trading loop that runs in a background thread.
        Executes strategy cycles at regular intervals.
        """
        logger.info("Trading loop started")
        cycle_count = 0
        
        while not self.stop_event.is_set() and self.trading_enabled:
            try:
                # Check MT5 connection
                if not self.mt5.is_connected():
                    logger.warning("MT5 disconnected - attempting reconnect...")
                    if not self.mt5.connect():
                        time.sleep(5)
                        continue
                
                # Execute strategy cycle
                result = self.grid_manager.execute_strategy_cycle()
                
                if result.get('success'):
                    logger.info(f"Strategy cycle {cycle_count}: {result['message']}")
                
                # Update chart data periodically
                if cycle_count % 12 == 0:  # Every minute (5s * 12)
                    self._update_chart_data()
                
                cycle_count += 1
                
                # Sleep between cycles (5 seconds)
                self.stop_event.wait(5)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}", exc_info=True)
                time.sleep(5)
        
        logger.info("Trading loop exited")
    
    def _update_chart_data(self) -> None:
        """Update cached chart data for the dashboard."""
        try:
            df = self.indicators.fetch_rates(
                self.mt5.TIMEFRAME_M5 if hasattr(self.mt5, 'TIMEFRAME_M5') else 5,
                num_bars=50
            )
            
            if df is not None:
                # Get EMA
                ema = self.indicators.calculate_ema(df, config.indicators.EMA_PERIOD)
                
                # Update cache with latest 20 bars
                self.chart_data_cache = {
                    'labels': df['time'].iloc[-20:].dt.strftime('%H:%M').tolist(),
                    'prices': df['close'].iloc[-20:].tolist(),
                    'ema': ema.iloc[-20:].tolist() if ema is not None else []
                }
        except Exception as e:
            logger.error(f"Error updating chart data: {str(e)}")
    
    def emergency_stop(self) -> Dict[str, int]:
        """
        Emergency stop - close all positions and cancel orders.
        
        Returns:
            Dict with counts of closed positions and cancelled orders.
        """
        logger.critical("EMERGENCY STOP TRIGGERED")
        self.trading_enabled = False
        
        result = self.grid_manager.emergency_stop()
        
        # Record in trade history
        self.trade_history.append({
            'time': time.time(),
            'type': 'EMERGENCY',
            'lots': result['positions_closed'],
            'profit': 0,
            'comment': 'Emergency close all'
        })
        
        return result
    
    def get_full_status(self) -> Dict[str, Any]:
        """
        Get complete status for the dashboard.
        
        Returns:
            Dict with all status information.
        """
        # Get account info
        account_info = self.mt5.get_account_info() or {}
        
        # Get market info
        price_data = self.mt5.get_current_price()
        spread = self.mt5.get_spread()
        
        market_info = {
            'price': price_data[0] if price_data else 0,
            'spread': spread or 0,
            'atr': self.market_filter.get_last_check_result().get('atr', 0),
        }
        
        # Get recent trades
        recent_trades = self.trade_history[-10:] if self.trade_history else []
        
        return {
            'is_running': self.is_running and self.trading_enabled,
            'trading_state': self.market_filter.get_state().value,
            'account': account_info,
            'market': market_info,
            'recent_trades': recent_trades,
            'chart_data': self.chart_data_cache,
            'risk_summary': self.risk_manager.get_risk_summary(account_info) if account_info else {},
        }
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get trade history."""
        return self.trade_history
    
    def get_chart_data(self) -> Dict[str, Any]:
        """Get chart data for Chart.js."""
        return self.chart_data_cache


def create_app(trading_bot: TradingBot) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        trading_bot: TradingBot instance
        
    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(web_bp, url_prefix='/')
    
    # Set trading bot reference for routes
    set_trading_bot(trading_bot)
    
    return app


def main():
    """Main entry point."""
    print("=" * 60)
    print("MT5 Gold Resilient Scalper")
    print("=" * 60)
    print("\n⚠️  WARNING: XAUUSD is a high-volatility instrument.")
    print("   This bot is for EDUCATIONAL/DEMO purposes only.")
    print("   Always test on a demo account before live trading.\n")
    
    # Initialize trading bot
    bot = TradingBot()
    
    # Connect to MT5
    print("Connecting to MT5...")
    if not bot.connect():
        print("❌ Failed to connect to MT5. Please ensure:")
        print("   1. MetaTrader 5 terminal is running")
        print("   2. You are logged into a trading account")
        print("   3. XAUUSD symbol is available in Market Watch")
        sys.exit(1)
    
    print("✓ Connected to MT5")
    
    # Create Flask app
    app = create_app(bot)
    
    # Start trading (optional - can also start from dashboard)
    # bot.start_trading()
    
    print("\n" + "=" * 60)
    print("Starting Web Dashboard...")
    print("Access the dashboard at: http://localhost:5000")
    print("Default login: admin / admin123")
    print("=" * 60 + "\n")
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        bot.disconnect()
        print("Goodbye!")


if __name__ == '__main__':
    main()

/**
 * Dashboard JavaScript - Handles live updates, chart rendering, and user interactions.
 */

// Global variables
let priceChart = null;
let refreshInterval = null;
let isConnected = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initChart();
    loadConfig();
    updateStatus();
    
    // Config form submit handler
    document.getElementById('configForm').addEventListener('submit', saveConfig);
});

/**
 * Initialize Chart.js price chart
 */
function initChart() {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Price',
                    data: [],
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                },
                {
                    label: 'EMA(50)',
                    data: [],
                    borderColor: '#ffc107',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            animation: {
                duration: 0
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        maxTicksLimit: 8
                    }
                },
                y: {
                    display: true,
                    position: 'right'
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}

/**
 * Load current configuration from server
 */
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            
            document.getElementById('cfgRiskPercent').value = config.risk_percent || 1.0;
            document.getElementById('cfgDailyLoss').value = config.daily_loss_limit || 5.0;
            document.getElementById('cfgSlMult').value = config.sl_multiplier || 3.0;
            document.getElementById('cfgTpMult').value = config.tp_multiplier || 2.0;
            document.getElementById('cfgMaxSpread').value = config.max_spread || 30;
            document.getElementById('cfgAdx').value = config.adx_threshold || 30;
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

/**
 * Save configuration to server
 */
async function saveConfig(event) {
    event.preventDefault();
    
    const configData = {
        risk_percent: parseFloat(document.getElementById('cfgRiskPercent').value),
        daily_loss_limit: parseFloat(document.getElementById('cfgDailyLoss').value),
        sl_multiplier: parseFloat(document.getElementById('cfgSlMult').value),
        tp_multiplier: parseFloat(document.getElementById('cfgTpMult').value),
        max_spread: parseInt(document.getElementById('cfgMaxSpread').value),
        adx_threshold: parseFloat(document.getElementById('cfgAdx').value)
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        });
        
        if (response.ok) {
            const result = await response.json();
            alert('Configuration saved successfully!');
        } else {
            alert('Error saving configuration');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert('Error saving configuration');
    }
}

/**
 * Update dashboard status from server
 */
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error('Failed to fetch status');
        }
        
        const data = await response.json();
        
        // Update account info
        if (data.account) {
            document.getElementById('balance').textContent = '$' + data.account.balance.toFixed(2);
            document.getElementById('equity').textContent = '$' + data.account.equity.toFixed(2);
            document.getElementById('marginLevel').textContent = data.account.margin_level.toFixed(0) + '%';
        }
        
        // Update market info
        if (data.market) {
            document.getElementById('currentPrice').textContent = '$' + data.market.price.toFixed(2);
            document.getElementById('spread').textContent = data.market.spread + ' pts';
            document.getElementById('atrValue').textContent = data.market.atr ? data.market.atr.toFixed(2) : 'N/A';
        }
        
        // Update market state badge
        const stateBadge = document.getElementById('marketState');
        if (data.trading_state) {
            stateBadge.textContent = data.trading_state;
            stateBadge.className = 'badge ' + getStateClass(data.trading_state);
        }
        
        // Update button states
        const isRunning = data.is_running || false;
        document.getElementById('btnStart').disabled = isRunning;
        document.getElementById('btnStop').disabled = !isRunning;
        
        // Update trade log
        if (data.recent_trades && data.recent_trades.length > 0) {
            updateTradeLog(data.recent_trades);
        }
        
        // Update chart
        if (data.chart_data) {
            updateChart(data.chart_data);
        }
        
        isConnected = true;
        
    } catch (error) {
        console.error('Error updating status:', error);
        isConnected = false;
        document.getElementById('marketState').textContent = 'DISCONNECTED';
        document.getElementById('marketState').className = 'badge bg-danger';
    }
}

/**
 * Get CSS class for market state
 */
function getStateClass(state) {
    if (state === 'RUNNING') return 'bg-success';
    if (state.includes('PAUSED')) return 'bg-warning text-dark';
    return 'bg-secondary';
}

/**
 * Update trade log table
 */
function updateTradeLog(trades) {
    const tbody = document.getElementById('tradeLogBody');
    tbody.innerHTML = '';
    
    trades.slice(0, 10).forEach(trade => {
        const row = document.createElement('tr');
        const profitClass = trade.profit >= 0 ? 'profit-positive' : 'profit-negative';
        const typeIcon = trade.type === 'BUY' ? '↑' : '↓';
        
        row.innerHTML = `
            <td>${formatTime(trade.time)}</td>
            <td>${typeIcon} ${trade.type}</td>
            <td>${trade.lots}</td>
            <td class="${profitClass}">${trade.profit >= 0 ? '+' : ''}$${trade.profit.toFixed(2)}</td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Update price chart
 */
function updateChart(chartData) {
    if (!priceChart || !chartData) return;
    
    priceChart.data.labels = chartData.labels || [];
    priceChart.data.datasets[0].data = chartData.prices || [];
    priceChart.data.datasets[1].data = chartData.ema || [];
    
    priceChart.update();
}

/**
 * Start auto-refresh interval
 */
function startAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    
    refreshInterval = setInterval(() => {
        const autoRefresh = document.getElementById('autoRefresh');
        if (autoRefresh && autoRefresh.checked) {
            updateStatus();
        }
    }, 5000); // 5 seconds
}

/**
 * Toggle trading state
 */
async function toggleTrading(start) {
    const endpoint = start ? '/api/start' : '/api/stop';
    const action = start ? 'start' : 'stop';
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`Trading ${action}ed:`, result);
            updateStatus();
        } else {
            alert(`Error ${action}ing trading`);
        }
    } catch (error) {
        console.error(`Error ${action}ing trading:`, error);
        alert(`Error ${action}ing trading`);
    }
}

/**
 * Emergency stop - close all positions
 */
async function emergencyStop() {
    if (!confirm('WARNING: This will close ALL open positions immediately. Continue?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/emergency', {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`Emergency stop executed!\nPositions closed: ${result.result.positions_closed}\nOrders cancelled: ${result.result.orders_cancelled}`);
            updateStatus();
        } else {
            alert('Error executing emergency stop');
        }
    } catch (error) {
        console.error('Error during emergency stop:', error);
        alert('Error executing emergency stop');
    }
}

/**
 * Format timestamp for display
 */
function formatTime(timestamp) {
    if (!timestamp) return '--:--';
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

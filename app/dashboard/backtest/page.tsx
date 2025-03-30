'use client';

import React, { useState, useEffect, useMemo } from 'react';
import apiClient from '@/lib/apiClient';
import { supabase } from '@/lib/supabase'; 
import PriceChart from '@/components/charts/PriceChart'; // Import the chart component
import { format } from 'date-fns'; // For formatting dates in trade log

// Placeholder types for now - Ideally define these properly
type BotConfigResponse = any; 
type BacktestResult = any; 
type TradeLogEntry = {
    timestamp: string;
    side: 'BUY' | 'SELL';
    price: number;
    quantity: number;
    // Add other fields if present in backend response
};

const BacktestingPage: React.FC = () => {
  const [configuredBots, setConfiguredBots] = useState<BotConfigResponse[]>([]);
  const [selectedBotId, setSelectedBotId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>(''); // Use YYYY-MM-DD format for input type="date"
  const [endDate, setEndDate] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // Fetch configured bots on component mount
  useEffect(() => {
    const fetchBots = async () => {
      // Set loading true only for initial bot list fetch
      setIsLoading(true); 
      setApiError(null);
      try {
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
        const token = session?.access_token;
        if (!token) throw new Error("Authentication token not found.");

        const response = await apiClient.get('/api/bots', {
          headers: { Authorization: `Bearer ${token}` }
        });
        setConfiguredBots(response.data || []);
        if (response.data?.length > 0) {
          setSelectedBotId(response.data[0].id); // Default select the first bot
        }
      } catch (error: any) {
        console.error("Failed to fetch bot configurations:", error);
        setApiError(error.response?.data?.detail || error.message || "Failed to load bot list.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchBots();
  }, []);

  // Handle backtest form submission
  const handleRunBacktest = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedBotId || !startDate || !endDate) {
      setApiError("Please select a bot and specify start/end dates.");
      return;
    }
    
    setIsLoading(true); // Set loading true for backtest run
    setApiError(null);
    setBacktestResult(null); // Clear previous results

    try {
       const { data: { session }, error: sessionError } = await supabase.auth.getSession();
       if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
       const token = session?.access_token;
       if (!token) throw new Error("Authentication token not found.");

       const payload = {
         bot_config_id: selectedBotId,
         start_date: startDate, 
         end_date: endDate,
       };

       console.log("Running backtest with payload:", payload);
       const response = await apiClient.post('/api/bots/backtest', payload, {
         headers: { Authorization: `Bearer ${token}` }
       });
       
       setBacktestResult(response.data);
       console.log("Backtest results:", response.data);

    } catch (error: any) {
       console.error("Backtest API Error:", error);
       setApiError(error.response?.data?.detail || error.message || "Failed to run backtest.");
       setBacktestResult(null);
    } finally {
       setIsLoading(false); // Set loading false after backtest run
    }
  };

  // Memoize formatted chart data to prevent re-calculation on every render
  const equityChartData = useMemo(() => {
    if (!backtestResult?.equity_curve?.timestamps || !backtestResult?.equity_curve?.values) {
      return { labels: [], datasets: [] }; // Return empty structure if no data
    }
    
    // Ensure timestamps are valid Date objects or parseable strings for the time scale
    // The backend currently formats them as ISO strings, which should work with date-fns adapter
    const labels = backtestResult.equity_curve.timestamps; 
    const data = backtestResult.equity_curve.values;

    return {
      labels: labels, 
      datasets: [
        {
          label: 'Portfolio Equity',
          data: data,
          borderColor: 'rgb(54, 162, 235)', 
          backgroundColor: 'rgba(54, 162, 235, 0.1)', // Use lighter background fill
          tension: 0.1,
          pointRadius: 0, 
          borderWidth: 1.5, // Slightly thicker line
        },
      ],
    };
  }, [backtestResult]);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Strategy Backtesting</h1>

      {/* Backtest Configuration Form */}
      <form onSubmit={handleRunBacktest} className="bg-card p-6 rounded-lg shadow mb-8 space-y-4">
        <h2 className="text-lg font-medium mb-3">Configure Backtest</h2>
        
        {/* Bot Selection */}
        <div>
          <label htmlFor="botSelect" className="block text-sm font-medium text-muted-foreground mb-1">Select Bot Configuration</label>
          <select 
            id="botSelect" 
            value={selectedBotId} 
            onChange={(e) => setSelectedBotId(e.target.value)}
            className="w-full p-2 border border-input rounded bg-background text-foreground focus:ring-ring focus:ring-1 disabled:opacity-50"
            disabled={isLoading || configuredBots.length === 0}
          >
            <option value="" disabled>-- Select a Bot --</option>
            {configuredBots.map((bot) => (
              <option key={bot.id} value={bot.id}>
                {bot.name} ({bot.bot_type} - {bot.symbol})
              </option>
            ))}
          </select>
           {configuredBots.length === 0 && !isLoading && <p className="text-sm text-muted-foreground mt-1">No bot configurations found. Create one first.</p>}
        </div>

        {/* Date Range Selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="startDate" className="block text-sm font-medium text-muted-foreground mb-1">Start Date</label>
            <input 
              type="date" 
              id="startDate" 
              value={startDate} 
              onChange={(e) => setStartDate(e.target.value)} 
              className="w-full p-2 border border-input rounded bg-background text-foreground focus:ring-ring focus:ring-1"
              required
              disabled={isLoading}
            />
          </div>
           <div>
            <label htmlFor="endDate" className="block text-sm font-medium text-muted-foreground mb-1">End Date</label>
            <input 
              type="date" 
              id="endDate" 
              value={endDate} 
              onChange={(e) => setEndDate(e.target.value)} 
              className="w-full p-2 border border-input rounded bg-background text-foreground focus:ring-ring focus:ring-1"
              required
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Submit Button */}
        <button 
          type="submit" 
          disabled={isLoading || !selectedBotId || !startDate || !endDate}
          className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 disabled:opacity-50"
        >
          {isLoading ? 'Running Backtest...' : 'Run Backtest'}
        </button>
        {apiError && <p className="text-destructive text-sm mt-2">Error: {apiError}</p>}
      </form>

      {/* Backtest Results Section */}
      {isLoading && !backtestResult && <div className="text-center p-4">Running backtest...</div>}
      
      {backtestResult && (
        <div className="bg-card p-6 rounded-lg shadow space-y-6">
           <h2 className="text-xl font-semibold">Backtest Results: {backtestResult.bot_type} ({backtestResult.symbol})</h2>
           
           {/* Display Key Metrics */}
           <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 border-b pb-4">
              <div><div className="text-xs text-muted-foreground">Period</div> {backtestResult.start_date} to {backtestResult.end_date}</div>
              <div><div className="text-xs text-muted-foreground">Final Value</div> ${backtestResult.final_portfolio_value?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
              <div className={backtestResult.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}><div className="text-xs text-muted-foreground">Total PnL</div> ${backtestResult.total_pnl?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ({backtestResult.total_pnl_percent?.toFixed(2)}%)</div>
              <div><div className="text-xs text-muted-foreground">Trades</div> {backtestResult.total_trades}</div>
              <div><div className="text-xs text-muted-foreground">Win Rate</div> {backtestResult.win_rate?.toFixed(1)}%</div>
              <div><div className="text-xs text-muted-foreground">Max Drawdown</div> {backtestResult.metrics?.max_drawdown?.toFixed(2)}%</div>
              <div><div className="text-xs text-muted-foreground">Sharpe Ratio</div> {backtestResult.metrics?.sharpe_ratio?.toFixed(2)}</div>
           </div>

           {/* Display Equity Curve Chart */}
            <div className="mt-4">
                <h3 className="text-lg font-medium mb-2">Equity Curve</h3>
                 <PriceChart chartData={equityChartData} title="Portfolio Equity Over Time" />
            </div>

           {/* Display Trade Log Table */}
            <div className="mt-4">
                <h3 className="text-lg font-medium mb-3">Trade Log</h3>
                <div className="overflow-x-auto max-h-96 border rounded"> {/* Added max height and scroll */}
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-muted-foreground uppercase bg-muted sticky top-0"> {/* Sticky header */}
                      <tr>
                        <th scope="col" className="px-4 py-2">Timestamp</th>
                        <th scope="col" className="px-4 py-2">Side</th>
                        <th scope="col" className="px-4 py-2">Price</th>
                        <th scope="col" className="px-4 py-2">Quantity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {backtestResult.trades?.length > 0 ? backtestResult.trades.map((trade: TradeLogEntry, index: number) => (
                        <tr key={index} className="hover:bg-muted/50">
                          <td className="px-4 py-2">{format(new Date(trade.timestamp), 'Pp')}</td>
                          <td className={`px-4 py-2 font-medium ${trade.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>{trade.side}</td>
                          <td className="px-4 py-2">${trade.price?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4})}</td>
                          <td className="px-4 py-2">{trade.quantity?.toFixed(6)}</td>
                        </tr>
                      )) : (
                        <tr>
                          <td colSpan={4} className="text-center py-4 text-muted-foreground">No trades executed during backtest.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default BacktestingPage;

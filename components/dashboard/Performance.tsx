'use client';

import React from 'react';
// Import chart components if needed later
// import { Line } from 'react-chartjs-2';

// TODO: Define interfaces for performance data and trade history
interface PerformanceMetrics {
  totalPnl: number;
  winRate: number;
  totalTrades: number;
  // Add more metrics
}

interface TradeRecord {
  id: string | number;
  timestamp: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  pnl?: number; // Optional profit/loss for this trade
}

interface PerformanceDashboardProps {
  botId?: string; // Optional: Filter performance for a specific bot
}

// TODO: Fetch actual performance data
const fetchPerformanceData = async (botId?: string): Promise<PerformanceMetrics> => {
  console.warn("fetchPerformanceData not implemented, returning dummy data.");
  await new Promise(resolve => setTimeout(resolve, 300));
  return {
    totalPnl: Math.random() * 1000 - 500, // Random PnL
    winRate: Math.random() * 100,
    totalTrades: Math.floor(Math.random() * 50),
  };
};

// TODO: Fetch actual trade history
const fetchTradeHistory = async (botId?: string): Promise<TradeRecord[]> => {
   console.warn("fetchTradeHistory not implemented, returning dummy data.");
   await new Promise(resolve => setTimeout(resolve, 400));
   // Dummy trade data
   return [
     { id: 1, timestamp: new Date().toISOString(), symbol: 'BTCUSDT', side: 'BUY', price: 82000, quantity: 0.001, pnl: 50.5 },
     { id: 2, timestamp: new Date(Date.now() - 3600000).toISOString(), symbol: 'BTCUSDT', side: 'SELL', price: 82500, quantity: 0.001 },
   ];
};


const PerformanceDashboard: React.FC<PerformanceDashboardProps> = ({ botId }) => {
  // TODO: Use state and useEffect (or SWR) to fetch data
  const [metrics, setMetrics] = React.useState<PerformanceMetrics | null>(null);
  const [trades, setTrades] = React.useState<TradeRecord[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [metricsData, tradesData] = await Promise.all([
          fetchPerformanceData(botId),
          fetchTradeHistory(botId)
        ]);
        setMetrics(metricsData);
        setTrades(tradesData);
      } catch (error) {
        console.error("Failed to load performance data:", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [botId]); // Reload if botId changes

  if (loading) {
    return <div className="text-center p-6">Loading performance data...</div>;
  }

  if (!metrics) {
     return <div className="text-center p-6 text-destructive">Failed to load performance metrics.</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        Performance Overview {botId ? `(Bot: ${botId.substring(0, 8)}...)` : '(All Bots)'}
      </h2>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-muted-foreground mb-1">Total PnL</h3>
          <p className={`text-2xl font-bold ${metrics.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${metrics.totalPnl.toFixed(2)}
          </p>
        </div>
        <div className="bg-card p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-muted-foreground mb-1">Win Rate</h3>
          <p className="text-2xl font-bold">{metrics.winRate.toFixed(1)}%</p>
        </div>
        <div className="bg-card p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-muted-foreground mb-1">Total Trades</h3>
          <p className="text-2xl font-bold">{metrics.totalTrades}</p>
        </div>
      </div>

      {/* TODO: Add Equity Curve Chart */}
      <div className="bg-card p-4 rounded-lg shadow">
         <h3 className="text-lg font-medium mb-2">Equity Curve (Placeholder)</h3>
         <div className="h-48 flex items-center justify-center text-muted-foreground">Chart Placeholder</div>
         {/* <Line data={...} options={...} /> */}
      </div>

      {/* Trade History Table */}
      <div className="bg-card p-4 rounded-lg shadow">
        <h3 className="text-lg font-medium mb-3">Trade History</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase border-b">
              <tr>
                <th scope="col" className="px-4 py-2">Date</th>
                <th scope="col" className="px-4 py-2">Symbol</th>
                <th scope="col" className="px-4 py-2">Side</th>
                <th scope="col" className="px-4 py-2">Price</th>
                <th scope="col" className="px-4 py-2">Quantity</th>
                <th scope="col" className="px-4 py-2">PnL</th>
              </tr>
            </thead>
            <tbody>
              {trades.length > 0 ? trades.map((trade) => (
                <tr key={trade.id} className="border-b hover:bg-muted/50">
                  <td className="px-4 py-2">{new Date(trade.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2">{trade.symbol}</td>
                  <td className={`px-4 py-2 ${trade.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>{trade.side}</td>
                  <td className="px-4 py-2">${trade.price.toFixed(2)}</td>
                  <td className="px-4 py-2">{trade.quantity}</td>
                   <td className={`px-4 py-2 ${trade.pnl && trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                     {trade.pnl !== undefined ? `$${trade.pnl.toFixed(2)}` : '-'}
                   </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={6} className="text-center py-4 text-muted-foreground">No trades found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PerformanceDashboard;

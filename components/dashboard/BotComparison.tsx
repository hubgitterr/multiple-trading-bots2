'use client';

import React from 'react';

// TODO: Define interface for bot performance summary data
interface BotPerformanceSummary {
  id: string;
  name: string;
  type: string;
  symbol: string;
  totalPnl: number;
  winRate: number;
  totalTrades: number;
  // Add other relevant comparison metrics
}

interface BotComparisonProps {
  // Props to pass data if needed, e.g., list of active bot summaries
  // summaries: BotPerformanceSummary[]; 
}

// TODO: Fetch data for active bots to compare
const fetchBotSummaries = async (): Promise<BotPerformanceSummary[]> => {
  console.warn("fetchBotSummaries not implemented, returning dummy data.");
  await new Promise(resolve => setTimeout(resolve, 400));
  return [
    { id: 'uuid-1', name: 'Momentum BTC', type: 'momentum', symbol: 'BTCUSDT', totalPnl: 150.75, winRate: 65.2, totalTrades: 20 },
    { id: 'uuid-2', name: 'Grid ETH', type: 'grid', symbol: 'ETHUSDT', totalPnl: -30.10, winRate: 45.0, totalTrades: 40 },
    { id: 'uuid-3', name: 'DCA BNB', type: 'dca', symbol: 'BNBBUSD', totalPnl: 10.50, winRate: 100, totalTrades: 5 }, // DCA might not have win rate in same way
  ];
};

const BotComparison: React.FC<BotComparisonProps> = () => {
  // TODO: Use state and useEffect (or SWR) to fetch data
  const [summaries, setSummaries] = React.useState<BotPerformanceSummary[]>([]);
  const [loading, setLoading] = React.useState(true);

   React.useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const data = await fetchBotSummaries();
        setSummaries(data);
      } catch (error) {
        console.error("Failed to load bot summaries:", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  return (
    <div className="bg-card text-card-foreground p-4 rounded-lg shadow mt-6">
      <h2 className="text-lg font-medium mb-3">Bot Performance Comparison</h2>
      {loading ? (
         <div className="text-center text-muted-foreground">Loading comparison data...</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
             <thead className="text-xs text-muted-foreground uppercase border-b">
              <tr>
                <th scope="col" className="px-4 py-2">Name</th>
                <th scope="col" className="px-4 py-2">Type</th>
                <th scope="col" className="px-4 py-2">Symbol</th>
                <th scope="col" className="px-4 py-2">Total PnL</th>
                <th scope="col" className="px-4 py-2">Win Rate</th>
                <th scope="col" className="px-4 py-2">Trades</th>
              </tr>
            </thead>
            <tbody>
               {summaries.length > 0 ? summaries.map((bot) => (
                <tr key={bot.id} className="border-b hover:bg-muted/50">
                  <td className="px-4 py-2 font-medium">{bot.name}</td>
                  <td className="px-4 py-2">{bot.type}</td>
                  <td className="px-4 py-2">{bot.symbol}</td>
                   <td className={`px-4 py-2 ${bot.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                     ${bot.totalPnl.toFixed(2)}
                   </td>
                  <td className="px-4 py-2">{bot.winRate.toFixed(1)}%</td>
                  <td className="px-4 py-2">{bot.totalTrades}</td>
                </tr>
              )) : (
                 <tr>
                  <td colSpan={6} className="text-center py-4 text-muted-foreground">No bot data available for comparison.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default BotComparison;

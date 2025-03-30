import React from 'react';
import MarketOverview from '@/components/dashboard/MarketOverview'; // Import the component
import PriceChart from '@/components/charts/PriceChart'; // Import chart component

// This is the main dashboard overview page (route: /dashboard)
export default function DashboardOverviewPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Dashboard Overview</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Placeholder Cards */}
        <div className="bg-card text-card-foreground p-4 rounded-lg shadow">
          <h2 className="text-lg font-medium mb-2">Total Portfolio Value</h2>
          <p className="text-3xl font-bold">$ --,--</p>
          <p className="text-sm text-muted-foreground mt-1">+0.0% today</p>
        </div>

        <div className="bg-card text-card-foreground p-4 rounded-lg shadow">
          <h2 className="text-lg font-medium mb-2">Active Bots</h2>
          <p className="text-3xl font-bold">0 / 3</p> 
          <p className="text-sm text-muted-foreground mt-1">Momentum | Grid | DCA</p>
        </div>

        <div className="bg-card text-card-foreground p-4 rounded-lg shadow">
          <h2 className="text-lg font-medium mb-2">Recent Trades</h2>
          <p className="text-sm text-muted-foreground mt-1">No trades yet.</p>
          {/* TODO: List recent trades here */}
        </div>
        {/* Add more summary cards if needed */}
      </div>

      {/* Market Overview Section */}
      <MarketOverview /> 

      {/* Chart Section (Example) */}
      <div className="mt-6">
        {/* Pass placeholder data structure to PriceChart */}
        <PriceChart 
          chartData={{
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], // Example labels
            datasets: [{
              label: 'BTCUSDT Price (Placeholder)',
              data: [65000, 59000, 80000, 81000, 56000, 55000], // Example data
              borderColor: 'rgb(75, 192, 192)',
              tension: 0.1
            }]
          }} 
          title="BTCUSDT Price (Placeholder)" 
        /> 
      </div>

      {/* TODO: Add Bot Status Summary Component */}
      {/* <BotStatusSummary /> */}
      <div className="mt-6 bg-card text-card-foreground p-4 rounded-lg shadow">
        <h2 className="text-lg font-medium mb-2">Bot Status Summary</h2>
        <p className="text-sm text-muted-foreground">Bot status details will appear here...</p>
      </div>

    </div>
  );
}

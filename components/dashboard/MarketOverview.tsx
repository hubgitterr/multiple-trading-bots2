'use client'; // May need client-side fetching

import React, { useState, useEffect } from 'react';
import { fetcher } from '@/lib/apiClient'; // Import the actual fetcher
import useWebSocket from '@/lib/hooks/useWebSocket'; // Import the hook

// Interface matching the backend response for /api/market/price/{symbol}
interface MarketPriceResponse {
  symbol: string;
  price: number; 
}

// Define interface for the expected WebSocket price update message
interface WsPriceUpdateMessage {
  type: 'price_update';
  symbol: string;
  price: number;
  timestamp?: string; // Make timestamp optional for flexibility
}

// Define interface for bot status update message
interface WsBotStatusUpdateMessage {
    type: 'bot_status_update';
    statuses: any[]; // Use 'any' for now, replace with proper BotStatusResponse type later
    timestamp?: string;
}

// Type guard to check if a message is a WsPriceUpdateMessage
function isPriceUpdateMessage(message: any): message is WsPriceUpdateMessage {
  return (
    message &&
    typeof message === 'object' &&
    message.type === 'price_update' &&
    typeof message.symbol === 'string' &&
    typeof message.price === 'number'
  );
}

// Type guard for bot status update
function isBotStatusUpdateMessage(message: any): message is WsBotStatusUpdateMessage {
   return (
    message &&
    typeof message === 'object' &&
    message.type === 'bot_status_update' &&
    Array.isArray(message.statuses) 
  );
}


// Function to fetch market data using the actual API
const fetchMarketData = async (symbols: string[]): Promise<MarketPriceResponse[]> => {
  try {
    // Use Promise.all to fetch data for all symbols concurrently
    const pricePromises = symbols.map(symbol => 
      fetcher(`/api/market/price/${symbol}`) // No token needed for this public endpoint
    );
    const results = await Promise.all(pricePromises);
    // Ensure results match the expected interface
    return results as MarketPriceResponse[]; 
  } catch (error) {
     console.error("Error fetching market data from API:", error);
     // Re-throw or return empty array to indicate failure
     throw error; 
     // return []; 
  }
};

const MarketOverview: React.FC = () => {
  // State now uses the API response interface
  const [marketData, setMarketData] = useState<MarketPriceResponse[]>([]); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null); 
  const symbolsToWatch = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']; 
  const [botStatuses, setBotStatuses] = useState<any[]>([]); // State to hold bot statuses

  // Initialize WebSocket connection (hook is JS, so no generic type argument)
  const { lastMessage, isConnected, error: wsError } = useWebSocket('/ws/updates'); 

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null); // Clear previous errors
      try {
        const data = await fetchMarketData(symbolsToWatch);
        setMarketData(data);
      } catch (err: any) {
        console.error("Failed to fetch market data:", err);
        setError(err.message || "Failed to load market data.");
        setMarketData([]); // Clear data on error
      } finally {
        setLoading(false);
      }
    };
    loadData();
    // Initial load still happens via HTTP request

  }, []); 

  // Effect to handle incoming WebSocket messages
  useEffect(() => {
    // Use the type guard to check the message structure
    if (isPriceUpdateMessage(lastMessage)) {
      const { symbol, price } = lastMessage; // Destructure after type guard confirms properties exist
      console.log(`WS Update received for ${symbol}: ${price}`);
      // Update the specific symbol's price in the marketData state
      setMarketData(prevData => 
        prevData.map(item => 
          item.symbol === symbol ? { ...item, price: price } : item
        )
      );
    } else if (isBotStatusUpdateMessage(lastMessage)) {
        // Explicitly cast after type guard passes to satisfy TypeScript
        const statusUpdate = lastMessage as WsBotStatusUpdateMessage; 
        console.log("WS Bot Status Update received:", statusUpdate.statuses);
        setBotStatuses(statusUpdate.statuses); // Update bot statuses state
        // TODO: Update relevant UI elements based on bot statuses (e.g., Active Bots card)
    } else if (lastMessage) {
        // Log other types of messages if needed
        console.log("Received other WS message:", lastMessage);
    }
  }, [lastMessage]); // Re-run when lastMessage changes

  // Effect to handle WebSocket errors
   useEffect(() => {
    if (wsError) {
      console.error("WebSocket connection error reported:", wsError);
      // Optionally display a persistent error message in the UI
      // setError("Real-time connection error."); 
    }
  }, [wsError]);

  return (
    <div className="bg-card text-card-foreground p-4 rounded-lg shadow mt-6">
      <div className="flex justify-between items-center mb-3">
         <h2 className="text-lg font-medium">Market Overview</h2>
         {/* Display WebSocket connection status */}
         <span className={`text-xs px-2 py-0.5 rounded ${isConnected ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'}`}>
           {isConnected ? 'Live' : 'Disconnected'}
         </span>
      </div>
      
      {loading ? (
        <div className="text-center text-muted-foreground py-4">Loading market data...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {error ? (
             <div className="text-destructive col-span-full text-center">{error}</div>
          ) : marketData.length > 0 ? marketData.map((data) => (
            <div key={data.symbol} className="border border-border p-3 rounded">
              <div className="text-sm font-semibold">{data.symbol}</div>
              {/* Format the price number */}
              <div className="text-xl font-bold mt-1">${data.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              {/* TODO: Add price change indicator */}
            </div>
          )) : (
             <div className="text-muted-foreground col-span-full text-center">No market data available.</div>
          )}
        </div>
      )}
      {/* TODO: Display bot statuses received via WebSocket */}
      {/* <pre className="text-xs mt-4">{JSON.stringify(botStatuses, null, 2)}</pre> */}
    </div>
  );
};

export default MarketOverview;

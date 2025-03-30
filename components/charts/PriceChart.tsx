'use client'; // Required for Chart.js components

import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, // For X axis labels
  LinearScale, // For Y axis numerical scale
  PointElement, // For data points
  LineElement, // For the line itself
  Title, 
  Tooltip, 
  Legend, 
  TimeScale, 
  // CandlestickController, 
  // OhlcElement, 
} from 'chart.js';
import 'chartjs-adapter-date-fns'; // Import adapter for time scale

// Register the components (remove duplicates)
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale 
  // CandlestickController, 
  // OhlcElement 
);

// Define structure for Chart.js data prop
interface ChartData {
  labels: string[]; // Use string array for labels as expected by react-chartjs-2 types
  datasets: {
    label: string;
    data: number[];
    borderColor?: string;
    backgroundColor?: string;
    tension?: number;
    // Add other dataset properties as needed
  }[];
}

interface PriceChartProps {
  chartData: ChartData; // Use the defined interface
  chartOptions?: any; // Keep options flexible for now
  title?: string; // Optional title override
}

const PriceChart: React.FC<PriceChartProps> = ({ chartData, chartOptions, title }) => {
  
  // Default options, can be merged with chartOptions prop
  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false, // Important for custom height
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: !!title, // Show title only if provided
        text: title || 'Price Chart',
      },
      tooltip: {
         mode: 'index' as const,
         intersect: false,
      },
    },
     scales: { // Example scale configuration
       x: {
         type: 'time' as const, // Use time scale if labels are Date objects or timestamps
         time: {
            unit: 'day' as const, // Adjust unit based on data density
            tooltipFormat: 'PPpp' // Format for tooltip (requires date-fns adapter)
         },
         title: {
           display: true,
           text: 'Date'
         }
       },
       y: {
         title: {
           display: true,
           text: 'Price'
         }
       }
     }
  };

  // Merge default options with provided options
  const options = { ...defaultOptions, ...chartOptions };

  // Placeholder data if none provided (for initial render or error state)
  const placeholderData = {
    labels: [],
    datasets: [],
  };

  const dataToDisplay = chartData && chartData.labels && chartData.labels.length > 0 ? chartData : placeholderData;

  return (
    <div className="bg-card text-card-foreground p-4 rounded-lg shadow">
      <div className="relative h-64 md:h-80"> {/* Ensure container has height */}
         {dataToDisplay.labels.length > 0 ? (
             <Line options={options} data={dataToDisplay} />
         ) : (
             <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                 No data available for chart.
             </div>
         )}
      </div>
    </div>
  );
};

export default PriceChart;

'use client';

import React, { useState } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
// No need to import axios directly if using apiClient
import { supabase } from '@/lib/supabase'; // Import supabase client
import apiClient from '@/lib/apiClient'; // Import the configured axios instance

// Define the type for form data based on bot config params
interface MomentumFormData {
  name: string;
  symbol: string;
  rsi_period: number;
  rsi_oversold: number;
  rsi_overbought: number;
  macd_fast: number;
  macd_slow: number;
  macd_signal: number;
  candle_interval: string; 
  trade_quantity: number;
  is_active: boolean;
}

// Map form data to the structure expected by the backend API (BotConfigCreate)
interface MomentumApiPayload {
   name: string;
   bot_type: 'momentum'; // Hardcoded for this form
   symbol: string;
   config_params: {
     rsi_period: number;
     rsi_oversold: number;
     rsi_overbought: number;
     macd_fast: number;
     macd_slow: number;
     macd_signal: number;
     candle_interval: string; 
     trade_quantity: number;
   };
   is_active: boolean;
}


interface MomentumBotFormProps {
  // Pass existing config data for editing (needs mapping from BotConfigResponse)
  existingConfig?: any; // Replace 'any' with actual BotConfigResponse type later
  onFormSubmitSuccess: (data: any) => void; // Callback on successful API response
  onCancel?: () => void; // Optional callback for cancel action
}

const MomentumBotForm: React.FC<MomentumBotFormProps> = ({ 
  existingConfig, 
  onFormSubmitSuccess,
  onCancel
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Map existingConfig to defaultValues for the form
  const defaultValues: Partial<MomentumFormData> = existingConfig ? {
      name: existingConfig.name,
      symbol: existingConfig.symbol,
      rsi_period: existingConfig.config_params?.rsi_period,
      rsi_oversold: existingConfig.config_params?.rsi_oversold,
      rsi_overbought: existingConfig.config_params?.rsi_overbought,
      macd_fast: existingConfig.config_params?.macd_fast,
      macd_slow: existingConfig.config_params?.macd_slow,
      macd_signal: existingConfig.config_params?.macd_signal,
      candle_interval: existingConfig.config_params?.candle_interval,
      trade_quantity: existingConfig.config_params?.trade_quantity,
      is_active: existingConfig.is_active,
  } : {
      // Default values for creation form
      rsi_period: 14,
      rsi_oversold: 30,
      rsi_overbought: 70,
      macd_fast: 12,
      macd_slow: 26,
      macd_signal: 9,
      candle_interval: '1h',
      trade_quantity: 0.001,
      is_active: false,
  };

  const { register, handleSubmit, formState: { errors } } = useForm<MomentumFormData>({ 
      defaultValues 
  });

  const handleFormSubmit: SubmitHandler<MomentumFormData> = async (data) => {
    setIsLoading(true);
    setApiError(null);

    // Map form data to API payload structure
    const apiPayload: MomentumApiPayload = {
        name: data.name,
        bot_type: 'momentum',
        symbol: data.symbol.toUpperCase(), // Ensure uppercase symbol
        config_params: {
            rsi_period: Number(data.rsi_period), // Ensure numbers
            rsi_oversold: Number(data.rsi_oversold),
            rsi_overbought: Number(data.rsi_overbought),
            macd_fast: Number(data.macd_fast),
            macd_slow: Number(data.macd_slow),
            macd_signal: Number(data.macd_signal),
            candle_interval: data.candle_interval,
            trade_quantity: Number(data.trade_quantity),
        },
        is_active: data.is_active,
    };

    try {
        // Get JWT token from Supabase auth session
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) {
            throw new Error(`Supabase auth error: ${sessionError.message}`);
        }
        const token = session?.access_token;

        if (!token) {
            throw new Error("Authentication token not found. Please log in.");
        }

        const headers = { Authorization: `Bearer ${token}` };
        // apiClient already has baseURL configured
        
        let response;
        if (existingConfig?.id) {
            // Update existing bot using apiClient
            console.log(`Updating bot ${existingConfig.id} with payload:`, apiPayload);
            response = await apiClient.put(`/api/bots/${existingConfig.id}`, apiPayload, { headers });
        } else {
            // Create new bot using apiClient
            console.log("Creating new bot with payload:", apiPayload);
            response = await apiClient.post(`/api/bots`, apiPayload, { headers });
        }

        console.log("API Response:", response.data);
        onFormSubmitSuccess(response.data); // Pass response data to parent

    } catch (error: any) {
        console.error("API Error:", error);
        setApiError(error.response?.data?.detail || error.message || "An unexpected error occurred.");
    } finally {
        setIsLoading(false);
    }
  };

  return (
    // Use handleSubmit from react-hook-form
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 bg-card p-6 rounded-lg shadow">
      <h3 className="text-lg font-medium mb-4">
        {existingConfig ? 'Edit Momentum Bot' : 'Create Momentum Bot'}
      </h3>
      {apiError && <p className="text-red-500 text-sm mb-4">Error: {apiError}</p>}
      
      {/* Basic Info */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-muted-foreground mb-1">Bot Name</label>
        <input 
          type="text" 
          id="name" 
          {...register("name", { required: "Bot name is required" })} 
          className={`w-full p-2 border rounded bg-background text-foreground focus:ring-ring focus:ring-1 ${errors.name ? 'border-destructive' : 'border-input'}`}
        />
        {errors.name && <p className="text-destructive text-xs mt-1">{errors.name.message}</p>}
      </div>
      <div>
        <label htmlFor="symbol" className="block text-sm font-medium text-muted-foreground mb-1">Symbol (e.g., BTCUSDT)</label>
        <input 
          type="text" 
          id="symbol" 
          {...register("symbol", { 
              required: "Symbol is required", 
              pattern: { value: /^[A-Z0-9]+$/, message: "Symbol must be uppercase letters/numbers" } 
          })} 
          className={`w-full p-2 border rounded bg-background text-foreground focus:ring-ring focus:ring-1 ${errors.symbol ? 'border-destructive' : 'border-input'}`}
          onChange={(e) => e.target.value = e.target.value.toUpperCase()} // Force uppercase
        />
         {errors.symbol && <p className="text-destructive text-xs mt-1">{errors.symbol.message}</p>}
      </div>

      {/* RSI Parameters */}
      {/* RSI Parameters - Using react-hook-form register */}
      <fieldset className="border border-border p-3 rounded space-y-2">
        <legend className="text-sm font-medium px-1">RSI Settings</legend>
         <div><label htmlFor="rsi_period" className="text-xs">Period:</label><input type="number" id="rsi_period" {...register("rsi_period", { valueAsNumber: true, required: true, min: 1 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         <div><label htmlFor="rsi_oversold" className="text-xs">Oversold:</label><input type="number" step="0.1" id="rsi_oversold" {...register("rsi_oversold", { valueAsNumber: true, required: true, min: 0, max: 100 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         <div><label htmlFor="rsi_overbought" className="text-xs">Overbought:</label><input type="number" step="0.1" id="rsi_overbought" {...register("rsi_overbought", { valueAsNumber: true, required: true, min: 0, max: 100 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         {/* TODO: Add validation messages for errors */}
      </fieldset>

      {/* MACD Parameters */}
       <fieldset className="border border-border p-3 rounded space-y-2">
        <legend className="text-sm font-medium px-1">MACD Settings</legend>
         <div><label htmlFor="macd_fast" className="text-xs">Fast:</label><input type="number" id="macd_fast" {...register("macd_fast", { valueAsNumber: true, required: true, min: 1 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         <div><label htmlFor="macd_slow" className="text-xs">Slow:</label><input type="number" id="macd_slow" {...register("macd_slow", { valueAsNumber: true, required: true, min: 1 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         <div><label htmlFor="macd_signal" className="text-xs">Signal:</label><input type="number" id="macd_signal" {...register("macd_signal", { valueAsNumber: true, required: true, min: 1 })} className="ml-2 p-1 border border-input rounded w-20"/></div>
         {/* TODO: Add validation: fast < slow */}
      </fieldset>

      {/* Other Parameters */}
       <div>
        <label htmlFor="candle_interval" className="block text-sm font-medium text-muted-foreground mb-1">Candle Interval</label>
        {/* TODO: Use a Select component for better UX */}
        <select 
            id="candle_interval" 
            {...register("candle_interval", { required: true })} 
            className="w-full p-2 border border-input rounded bg-background text-foreground focus:ring-ring focus:ring-1"
        >
            <option value="1m">1 Minute</option>
            <option value="5m">5 Minutes</option>
            <option value="15m">15 Minutes</option>
            <option value="1h">1 Hour</option>
            <option value="4h">4 Hours</option>
            <option value="1d">1 Day</option>
        </select>
      </div>
       <div>
        <label htmlFor="trade_quantity" className="block text-sm font-medium text-muted-foreground mb-1">Trade Quantity (Base Asset)</label>
        <input type="number" step="any" id="trade_quantity" {...register("trade_quantity", { valueAsNumber: true, required: true, min: 0 })} className="w-full p-2 border border-input rounded"/>
         {errors.trade_quantity && <p className="text-destructive text-xs mt-1">Trade quantity must be positive.</p>}
      </div>

      {/* Active Status */}
      <div className="flex items-center">
        <input 
          type="checkbox" 
          id="is_active" 
          {...register("is_active")} 
          className="h-4 w-4 text-primary border-input rounded focus:ring-primary" 
        />
        <label htmlFor="is_active" className="ml-2 block text-sm text-foreground">
          Activate Bot on {existingConfig ? 'Update' : 'Create'}
        </label>
      </div>

      {/* Action Buttons */}
       <div className="flex justify-end space-x-3 pt-4">
         {onCancel && (
            <button 
                type="button" 
                onClick={onCancel}
                className="px-4 py-2 bg-secondary text-secondary-foreground rounded hover:opacity-90"
            >
                Cancel
            </button>
         )}
          <button 
            type="submit" 
            disabled={isLoading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 disabled:opacity-50"
          >
            {isLoading ? 'Saving...' : (existingConfig ? 'Update Bot' : 'Create Bot')}
          </button>
       </div>
    </form>
  );
};

export default MomentumBotForm;

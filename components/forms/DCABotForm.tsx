'use client';

import React, { useState } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
// No need for axios directly
import { supabase } from '@/lib/supabase'; 
import apiClient from '@/lib/apiClient';

// Define the type for form data
interface DCAFormData {
  name: string;
  symbol: string;
  purchase_amount_quote: number; // Amount of quote currency (e.g., USDT)
  purchase_interval_seconds: number; 
  is_active: boolean;
}

// Map form data to API payload
interface DcaApiPayload {
   name: string;
   bot_type: 'dca';
   symbol: string;
   config_params: {
     purchase_amount_quote: number;
     purchase_interval_seconds: number;
   };
   is_active: boolean;
}

interface DCABotFormProps {
  existingConfig?: any; 
  onFormSubmitSuccess: (data: any) => void; 
  onCancel?: () => void;
}

const DCABotForm: React.FC<DCABotFormProps> = ({ 
  existingConfig, 
  onFormSubmitSuccess,
  onCancel
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Map existing config to form defaults
  const defaultValues: Partial<DCAFormData> = existingConfig ? {
      name: existingConfig.name,
      symbol: existingConfig.symbol,
      purchase_amount_quote: existingConfig.config_params?.purchase_amount_quote,
      purchase_interval_seconds: existingConfig.config_params?.purchase_interval_seconds,
      is_active: existingConfig.is_active,
  } : {
      // Defaults for creation
      purchase_interval_seconds: 86400, // Default 1 day
      is_active: false,
  };

  const { register, handleSubmit, formState: { errors } } = useForm<DCAFormData>({ 
      defaultValues 
  });

  const handleFormSubmit: SubmitHandler<DCAFormData> = async (data) => {
     setIsLoading(true);
     setApiError(null);

     const apiPayload: DcaApiPayload = {
        name: data.name,
        bot_type: 'dca',
        symbol: data.symbol.toUpperCase(),
        config_params: {
            purchase_amount_quote: Number(data.purchase_amount_quote),
            purchase_interval_seconds: Number(data.purchase_interval_seconds),
        },
        is_active: data.is_active,
     };

     try {
        // Get JWT token
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
        const token = session?.access_token;
        if (!token) throw new Error("Authentication token not found. Please log in.");

        const headers = { Authorization: `Bearer ${token}` };
        
        let response;
        if (existingConfig?.id) {
            // Update using apiClient
            console.log(`Updating DCA bot ${existingConfig.id} with payload:`, apiPayload);
            response = await apiClient.put(`/api/bots/${existingConfig.id}`, apiPayload, { headers });
        } else {
            // Create using apiClient
            console.log("Creating new DCA bot with payload:", apiPayload);
            response = await apiClient.post(`/api/bots`, apiPayload, { headers });
        }

        console.log("API Response:", response.data);
        onFormSubmitSuccess(response.data);

    } catch (error: any) {
        console.error("API Error:", error);
        setApiError(error.response?.data?.detail || error.message || "An unexpected error occurred.");
    } finally {
        setIsLoading(false);
    }
  };

  const intervalOptions = [
    { label: 'Hourly', value: 3600 },
    { label: 'Every 4 Hours', value: 14400 },
    { label: 'Every 12 Hours', value: 43200 },
    { label: 'Daily', value: 86400 },
    { label: 'Weekly', value: 604800 },
    { label: 'Monthly (approx 30d)', value: 2592000 },
  ];

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 bg-card p-6 rounded-lg shadow">
      <h3 className="text-lg font-medium mb-4">
        {existingConfig ? 'Edit DCA Bot' : 'Create DCA Bot'}
      </h3>
      {apiError && <p className="text-red-500 text-sm mb-4">Error: {apiError}</p>}
      
      {/* Basic Info */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-muted-foreground mb-1">Bot Name</label>
        <input type="text" id="name" {...register("name", { required: "Bot name is required" })} className={`w-full p-2 border rounded ${errors.name ? 'border-destructive' : 'border-input'}`} />
         {errors.name && <p className="text-destructive text-xs mt-1">{errors.name.message}</p>}
      </div>
      <div>
        <label htmlFor="symbol" className="block text-sm font-medium text-muted-foreground mb-1">Symbol</label>
        <input type="text" id="symbol" {...register("symbol", { required: "Symbol is required", pattern: { value: /^[A-Z0-9]+$/, message: "Symbol must be uppercase letters/numbers" } })} className={`w-full p-2 border rounded ${errors.symbol ? 'border-destructive' : 'border-input'}`} onChange={(e) => e.target.value = e.target.value.toUpperCase()} />
         {errors.symbol && <p className="text-destructive text-xs mt-1">{errors.symbol.message}</p>}
      </div>

      {/* DCA Parameters */}
      <fieldset className="border border-border p-3 rounded space-y-2">
        <legend className="text-sm font-medium px-1">DCA Settings</legend>
        <div>
          <label htmlFor="purchase_amount_quote" className="text-xs">Purchase Amount (Quote):</label>
          <input type="number" step="any" id="purchase_amount_quote" {...register("purchase_amount_quote", { valueAsNumber: true, required: "Amount is required", min: { value: 0.000001, message: "Must be positive" } })} className={`ml-2 p-1 border rounded w-32 ${errors.purchase_amount_quote ? 'border-destructive' : 'border-input'}`}/>
           {errors.purchase_amount_quote && <p className="text-destructive text-xs mt-1 inline-block ml-2">{errors.purchase_amount_quote.message}</p>}
        </div>
        <div>
           <label htmlFor="purchase_interval_seconds" className="text-xs mr-2">Purchase Interval:</label>
           <select id="purchase_interval_seconds" {...register("purchase_interval_seconds", { valueAsNumber: true })} className="p-1 border border-input rounded">
             {intervalOptions.map(opt => (
               <option key={opt.value} value={opt.value}>{opt.label}</option>
             ))}
           </select>
        </div>
      </fieldset>
      
      {/* Active Status */}
      <div className="flex items-center">
        <input type="checkbox" id="is_active" {...register("is_active")} className="h-4 w-4 text-primary border-input rounded focus:ring-primary" />
        <label htmlFor="is_active" className="ml-2 block text-sm text-foreground">Activate Bot on {existingConfig ? 'Update' : 'Create'}</label>
      </div>

      {/* Action Buttons */}
       <div className="flex justify-end space-x-3 pt-4">
          {onCancel && ( <button type="button" onClick={onCancel} className="px-4 py-2 bg-secondary text-secondary-foreground rounded hover:opacity-90">Cancel</button> )}
          <button type="submit" disabled={isLoading} className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 disabled:opacity-50">
            {isLoading ? 'Saving...' : (existingConfig ? 'Update Bot' : 'Create Bot')}
          </button>
       </div>
    </form>
  );
};

export default DCABotForm;

'use client';

import React, { useState } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
// No need for axios directly
import { supabase } from '@/lib/supabase'; 
import apiClient from '@/lib/apiClient';

// Define the type for form data
interface GridFormData {
  name: string;
  symbol: string;
  lower_bound: number;
  upper_bound: number;
  num_grids: number;
  grid_mode: 'arithmetic' | 'geometric';
  investment_amount: number; 
  is_active: boolean;
}

// Map form data to API payload
interface GridApiPayload {
   name: string;
   bot_type: 'grid';
   symbol: string;
   config_params: {
     lower_bound: number;
     upper_bound: number;
     num_grids: number;
     grid_mode: 'arithmetic' | 'geometric';
     investment_amount: number; 
   };
   is_active: boolean;
}

interface GridBotFormProps {
  existingConfig?: any; // Replace 'any' with actual BotConfigResponse type later
  onFormSubmitSuccess: (data: any) => void; 
  onCancel?: () => void;
}

const GridBotForm: React.FC<GridBotFormProps> = ({ 
  existingConfig, 
  onFormSubmitSuccess,
  onCancel
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Map existing config to form defaults
  const defaultValues: Partial<GridFormData> = existingConfig ? {
      name: existingConfig.name,
      symbol: existingConfig.symbol,
      lower_bound: existingConfig.config_params?.lower_bound,
      upper_bound: existingConfig.config_params?.upper_bound,
      num_grids: existingConfig.config_params?.num_grids,
      grid_mode: existingConfig.config_params?.grid_mode,
      investment_amount: existingConfig.config_params?.investment_amount,
      is_active: existingConfig.is_active,
  } : {
      // Defaults for creation
      num_grids: 5,
      grid_mode: 'arithmetic',
      is_active: false,
  };

  const { register, handleSubmit, watch, formState: { errors } } = useForm<GridFormData>({ 
      defaultValues 
  });
  
  // Watch bounds to validate lower < upper
  const lowerBound = watch("lower_bound");
  const upperBound = watch("upper_bound");

  const handleFormSubmit: SubmitHandler<GridFormData> = async (data) => {
     setIsLoading(true);
     setApiError(null);

     const apiPayload: GridApiPayload = {
        name: data.name,
        bot_type: 'grid',
        symbol: data.symbol.toUpperCase(),
        config_params: {
            lower_bound: Number(data.lower_bound),
            upper_bound: Number(data.upper_bound),
            num_grids: Number(data.num_grids),
            grid_mode: data.grid_mode,
            investment_amount: Number(data.investment_amount),
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
            console.log(`Updating grid bot ${existingConfig.id} with payload:`, apiPayload);
            response = await apiClient.put(`/api/bots/${existingConfig.id}`, apiPayload, { headers });
        } else {
            // Create using apiClient
            console.log("Creating new grid bot with payload:", apiPayload);
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

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 bg-card p-6 rounded-lg shadow">
      <h3 className="text-lg font-medium mb-4">
        {existingConfig ? 'Edit Grid Bot' : 'Create Grid Bot'}
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

      {/* Grid Parameters */}
      <fieldset className="border border-border p-3 rounded space-y-2">
        <legend className="text-sm font-medium px-1">Grid Settings</legend>
        <div>
            <label htmlFor="lower_bound" className="text-xs">Lower Bound:</label>
            <input type="number" step="any" id="lower_bound" {...register("lower_bound", { valueAsNumber: true, required: "Lower bound is required", min: { value: 0, message: "Must be positive" }, validate: value => value < upperBound || "Lower bound must be less than upper bound" })} className={`ml-2 p-1 border rounded w-32 ${errors.lower_bound ? 'border-destructive' : 'border-input'}`}/>
            {errors.lower_bound && <p className="text-destructive text-xs mt-1 inline-block ml-2">{errors.lower_bound.message}</p>}
        </div>
        <div>
            <label htmlFor="upper_bound" className="text-xs">Upper Bound:</label>
            <input type="number" step="any" id="upper_bound" {...register("upper_bound", { valueAsNumber: true, required: "Upper bound is required", min: { value: 0, message: "Must be positive" }, validate: value => value > lowerBound || "Upper bound must be greater than lower bound" })} className={`ml-2 p-1 border rounded w-32 ${errors.upper_bound ? 'border-destructive' : 'border-input'}`}/>
             {errors.upper_bound && <p className="text-destructive text-xs mt-1 inline-block ml-2">{errors.upper_bound.message}</p>}
        </div>
        <div>
            <label htmlFor="num_grids" className="text-xs">Number of Grids:</label>
            <input type="number" id="num_grids" {...register("num_grids", { valueAsNumber: true, required: "Number of grids is required", min: { value: 2, message: "Must have at least 2 grids" } })} className={`ml-2 p-1 border rounded w-20 ${errors.num_grids ? 'border-destructive' : 'border-input'}`}/>
             {errors.num_grids && <p className="text-destructive text-xs mt-1 inline-block ml-2">{errors.num_grids.message}</p>}
        </div>
        <div>
           <label htmlFor="grid_mode" className="text-xs mr-2">Grid Mode:</label>
           <select id="grid_mode" {...register("grid_mode")} className="p-1 border border-input rounded">
             <option value="arithmetic">Arithmetic</option>
             <option value="geometric">Geometric</option>
           </select>
        </div>
      </fieldset>
      
       {/* Investment */}
       <div>
        <label htmlFor="investment_amount" className="block text-sm font-medium text-muted-foreground mb-1">Investment Amount (Quote Currency)</label>
        <input type="number" step="any" id="investment_amount" {...register("investment_amount", { valueAsNumber: true, required: "Investment amount is required", min: { value: 0.000001, message: "Must be positive" } })} className={`w-full p-2 border rounded ${errors.investment_amount ? 'border-destructive' : 'border-input'}`}/>
        {errors.investment_amount && <p className="text-destructive text-xs mt-1">{errors.investment_amount.message}</p>}
        <p className="text-xs text-muted-foreground mt-1">Total quote amount for buy orders below current price.</p>
      </div>

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

export default GridBotForm;

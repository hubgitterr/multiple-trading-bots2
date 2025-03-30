'use client';

import React, { useState } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
import apiClient from '@/lib/apiClient';
import { supabase } from '@/lib/supabase';

interface ApiKeyFormData {
  binance_api_key: string;
  binance_api_secret: string;
}

interface ApiKeyFormProps {
  onSuccess: () => void; // Callback on successful update
}

const ApiKeyForm: React.FC<ApiKeyFormProps> = ({ onSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [apiSuccess, setApiSuccess] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors }, reset } = useForm<ApiKeyFormData>();

  const handleFormSubmit: SubmitHandler<ApiKeyFormData> = async (data) => {
    setIsLoading(true);
    setApiError(null);
    setApiSuccess(null);

    try {
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
      const token = session?.access_token;
      if (!token) throw new Error("Authentication token not found.");

      const headers = { Authorization: `Bearer ${token}` };
      
      // Use PUT request to the specific endpoint
      const response = await apiClient.put('/api/user/api-keys', data, { headers });

      console.log("API Key Update Response:", response.data);
      setApiSuccess(response.data?.message || "API keys updated successfully!");
      reset({ binance_api_key: '', binance_api_secret: '' }); // Clear form on success
      onSuccess(); // Call parent callback if needed

    } catch (error: any) {
      console.error("API Key Update Error:", error);
      setApiError(error.response?.data?.detail || error.message || "Failed to update API keys.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      {apiError && <p className="text-sm text-destructive mb-4">{apiError}</p>}
      {apiSuccess && <p className="text-sm text-green-600 mb-4">{apiSuccess}</p>}
      
      <div>
        <label htmlFor="binance_api_key" className="block text-sm font-medium text-muted-foreground mb-1">API Key</label>
        <input
          id="binance_api_key"
          type="password" // Use password type to obscure input
          autoComplete="off"
          {...register("binance_api_key", { required: "API Key is required" })}
          className={`w-full p-2 border rounded bg-background text-foreground focus:ring-ring focus:ring-1 ${errors.binance_api_key ? 'border-destructive' : 'border-input'}`}
          disabled={isLoading}
        />
        {errors.binance_api_key && <p className="text-destructive text-xs mt-1">{errors.binance_api_key.message}</p>}
      </div>
      
      <div>
        <label htmlFor="binance_api_secret" className="block text-sm font-medium text-muted-foreground mb-1">Secret Key</label>
        <input
          id="binance_api_secret"
          type="password" // Use password type to obscure input
          autoComplete="off"
          {...register("binance_api_secret", { required: "Secret Key is required" })}
          className={`w-full p-2 border rounded bg-background text-foreground focus:ring-ring focus:ring-1 ${errors.binance_api_secret ? 'border-destructive' : 'border-input'}`}
          disabled={isLoading}
        />
        {errors.binance_api_secret && <p className="text-destructive text-xs mt-1">{errors.binance_api_secret.message}</p>}
      </div>

      <button 
        type="submit" 
        disabled={isLoading}
        className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 disabled:opacity-50"
      >
        {isLoading ? 'Saving...' : 'Save API Keys'}
      </button>
    </form>
  );
};

export default ApiKeyForm;

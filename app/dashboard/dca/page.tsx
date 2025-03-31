'use client'; 

import React, { useState, useEffect } from 'react';
import DCABotForm from '@/components/forms/DCABotForm';
import apiClient from '@/lib/apiClient'; 
import { supabase } from '@/lib/supabase'; 

type BotConfigResponse = any; 

export default function DCABotPage() {
  const [bots, setBots] = useState<BotConfigResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBot, setSelectedBot] = useState<BotConfigResponse | null>(null); 
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    fetchBots();
  }, []);

  const fetchBots = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
      const token = session?.access_token;
      if (!token) throw new Error("Authentication token not found.");

      const response = await apiClient.get('/api/bots', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const dcaBots = (response.data || []).filter((bot: BotConfigResponse) => bot.bot_type === 'dca');
      setBots(dcaBots);
    } catch (error: any) {
      console.error("Failed to fetch DCA bots:", error);
      setError(error.response?.data?.detail || error.message || "Failed to load bots.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFormSubmitSuccess = (updatedOrNewBot: BotConfigResponse) => {
    console.log("Form submission successful:", updatedOrNewBot);
    setSelectedBot(null); 
    setShowCreateForm(false); 
    fetchBots(); 
    alert(`Bot ${updatedOrNewBot.id ? 'updated' : 'created'} successfully!`); 
  };

  const handleEdit = (bot: BotConfigResponse) => {
    setSelectedBot(bot);
    setShowCreateForm(false); 
  };

  const handleCancel = () => {
     setSelectedBot(null);
     setShowCreateForm(false);
  };

  const handleStartStop = async (bot: BotConfigResponse, action: 'start' | 'stop') => {
     console.log(`${action} bot ${bot.id}`);
     setError(null);
     try {
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
        const token = session?.access_token;
        if (!token) throw new Error("Authentication token not found.");

        const headers = { Authorization: `Bearer ${token}` };
        const response = await apiClient.post(`/api/bots/${bot.id}/${action}`, {}, { headers });

        alert(`Bot ${action} request sent successfully: ${response.data?.message || ''}`);
        fetchBots(); // Refresh list
     } catch (error: any) {
         console.error(`Failed to ${action} bot:`, error);
         setError(error.response?.data?.detail || error.message || `Failed to ${action} bot.`);
     } finally {
         // Reset specific loading state if implemented
     }
  };

   const handleDelete = async (botId: string) => {
     if (!confirm("Are you sure you want to delete this bot configuration? This action cannot be undone.")) return;
     
     setError(null);
     try {
         const { data: { session }, error: sessionError } = await supabase.auth.getSession();
         if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
         const token = session?.access_token;
         if (!token) throw new Error("Authentication token not found.");

         const headers = { Authorization: `Bearer ${token}` };
         await apiClient.delete(`/api/bots/${botId}`, { headers });

         alert(`Bot ${botId} deleted successfully.`);
         fetchBots(); // Refresh the list
     } catch (error: any) {
         console.error(`Failed to delete bot ${botId}:`, error);
         setError(error.response?.data?.detail || error.message || `Failed to delete bot.`);
     } finally {
         // Reset loading state if implemented
     }
   };

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Dollar-Cost Averaging (DCA) Bot</h1>
      
      {/* List Existing Bots */}
      <div className="mb-8">
        <h2 className="text-lg font-medium mb-3">Your DCA Bots</h2>
        {isLoading && <p>Loading bots...</p>}
        {error && <p className="text-destructive">Error loading bots: {error}</p>}
        {!isLoading && !error && bots.length === 0 && (
          <p className="text-muted-foreground">You haven't created any DCA bots yet.</p>
        )}
        {!isLoading && !error && bots.length > 0 && (
          <div className="space-y-3">
            {bots.map((bot) => (
              <div key={bot.id} className="flex justify-between items-center p-3 border rounded bg-card">
                <div>
                  <span className="font-medium">{bot.name}</span> ({bot.symbol}) - 
                  <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${bot.is_active ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-800'}`}>
                    {bot.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="space-x-2">
                   <button onClick={() => handleStartStop(bot, bot.is_active ? 'stop' : 'start')} className={`text-xs px-2 py-1 rounded ${bot.is_active ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-green-500 hover:bg-green-600'} text-white`}>
                     {bot.is_active ? 'Stop' : 'Start'}
                   </button>
                   <button onClick={() => handleEdit(bot)} className="text-xs px-2 py-1 rounded bg-blue-500 hover:bg-blue-600 text-white">Edit</button>
                   <button onClick={() => handleDelete(bot.id)} className="text-xs px-2 py-1 rounded bg-red-500 hover:bg-red-600 text-white">Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Form Section */}
      {!selectedBot && !showCreateForm && (
         <button 
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90 mb-6"
          >
            + Create New DCA Bot
          </button>
      )}

      {(showCreateForm || selectedBot) && (
        <div className="mt-6">
           <DCABotForm 
              key={selectedBot?.id || 'create'} 
              existingConfig={selectedBot} 
              onFormSubmitSuccess={handleFormSubmitSuccess} 
              onCancel={handleCancel}
            />
        </div>
      )}
    </div>
  );
}

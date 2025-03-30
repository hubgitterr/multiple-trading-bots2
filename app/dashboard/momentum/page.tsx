'use client'; 

import React, { useState, useEffect } from 'react'; // Import hooks
import MomentumBotForm from '@/components/forms/MomentumBotForm';
import apiClient from '@/lib/apiClient'; // Import API client
import { supabase } from '@/lib/supabase'; // Import Supabase client

// Placeholder type - replace with actual type from backend models if defined
type BotConfigResponse = any; 

export default function MomentumBotPage() {
  const [bots, setBots] = useState<BotConfigResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBot, setSelectedBot] = useState<BotConfigResponse | null>(null); // For editing
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Fetch bots on mount
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
      // Filter for momentum bots
      const momentumBots = (response.data || []).filter((bot: BotConfigResponse) => bot.bot_type === 'momentum');
      setBots(momentumBots);
    } catch (error: any) {
      console.error("Failed to fetch momentum bots:", error);
      setError(error.response?.data?.detail || error.message || "Failed to load bots.");
    } finally {
      setIsLoading(false);
    }
  };

  // Handle successful form submission (create or update)
  const handleFormSubmitSuccess = (updatedOrNewBot: BotConfigResponse) => {
    console.log("Form submission successful:", updatedOrNewBot);
    setSelectedBot(null); // Close edit form
    setShowCreateForm(false); // Close create form
    fetchBots(); // Refresh the list
    alert(`Bot ${updatedOrNewBot.id ? 'updated' : 'created'} successfully!`); // Simple feedback
  };

  const handleEdit = (bot: BotConfigResponse) => {
    setSelectedBot(bot);
    setShowCreateForm(false); // Ensure create form is hidden
  };

  const handleCancel = () => {
     setSelectedBot(null);
     setShowCreateForm(false);
  };

  const handleStartStop = async (bot: BotConfigResponse, action: 'start' | 'stop') => {
     // TODO: Implement API call to start/stop bot
     console.log(`${action} bot ${bot.id}`);
     alert(`Bot ${action} logic not implemented yet.`);
     // Example:
     // try { ... apiClient.post(`/api/bots/${bot.id}/${action}`, {}, { headers }) ... fetchBots(); } catch ...
  };

   const handleDelete = async (botId: string) => {
     if (!confirm("Are you sure you want to delete this bot configuration?")) return;
     // TODO: Implement API call to delete bot
     console.log(`Delete bot ${botId}`);
     alert(`Bot delete logic not implemented yet.`);
      // Example:
     // try { ... apiClient.delete(`/api/bots/${botId}`, { headers }) ... fetchBots(); } catch ...
   };


  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Momentum Trading Bot</h1>
      
      {/* List Existing Bots */}
      <div className="mb-8">
        <h2 className="text-lg font-medium mb-3">Your Momentum Bots</h2>
        {isLoading && <p>Loading bots...</p>}
        {error && <p className="text-destructive">Error loading bots: {error}</p>}
        {!isLoading && !error && bots.length === 0 && (
          <p className="text-muted-foreground">You haven't created any Momentum bots yet.</p>
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
                  {/* TODO: Display running status from WebSocket/API */}
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
            + Create New Momentum Bot
          </button>
      )}

      {(showCreateForm || selectedBot) && (
        <div className="mt-6">
           <MomentumBotForm 
              key={selectedBot?.id || 'create'} // Force re-render when selectedBot changes
              existingConfig={selectedBot} 
              onFormSubmitSuccess={handleFormSubmitSuccess} 
              onCancel={handleCancel}
            />
        </div>
      )}
    </div>
  );
}

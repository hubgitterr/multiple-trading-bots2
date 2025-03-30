'use client'; 

import React from 'react';
import ApiKeyForm from '@/components/forms/ApiKeyForm'; // Import the form component

// TODO: Implement other user preference settings

export default function SettingsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Settings</h1>

      <div className="space-y-8">
        {/* API Key Management Section */}
        <section className="bg-card p-6 rounded-lg shadow">
          <h2 className="text-lg font-medium border-b pb-2 mb-4">Binance API Keys</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Enter your Binance API Key and Secret. These are stored securely and used by the backend to execute trades. 
            Use keys generated for the **Testnet** environment for now.
          </p>
          <ApiKeyForm onSuccess={() => {
              // Optional: Show a more persistent success message or refetch user data
              console.log("API Keys updated successfully callback triggered.");
          }} />
        </section>

        {/* Other Settings Section */}
        <section className="bg-card p-6 rounded-lg shadow">
           <h2 className="text-lg font-medium border-b pb-2 mb-4">Preferences</h2>
           {/* TODO: Add theme preference, notification settings etc. */}
           <div className="p-4 border rounded bg-muted text-muted-foreground">
             Placeholder: Other user settings (theme, notifications) will go here.
           </div>
        </section>
      </div>
    </div>
  );
}

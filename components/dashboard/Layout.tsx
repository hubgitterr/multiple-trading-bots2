'use client'; // Need client hooks

import React, { ReactNode, useState, useEffect } from 'react'; 
import Link from 'next/link';
import { useRouter } from 'next/navigation'; 
import { supabase } from '@/lib/supabase'; 
// Import icons
import { FiLogOut, FiSun, FiMoon } from 'react-icons/fi'; 

interface LayoutProps {
  children: ReactNode;
}

const DashboardLayout: React.FC<LayoutProps> = ({ children }) => {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light'); // Default to light

  // Effect to read theme from localStorage and system preference on mount
   useEffect(() => {
    const storedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = storedTheme || (prefersDark ? 'dark' : 'light');
    setTheme(initialTheme);
  }, []);

  // Effect to apply theme class to HTML element
  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove(theme === 'light' ? 'dark' : 'light');
    root.classList.add(theme);
    localStorage.setItem('theme', theme); // Store preference
  }, [theme]);

  // Fetch user email 
  useEffect(() => {
    const fetchUser = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setUserEmail(user?.email || null);
    };
    fetchUser();
  }, []);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.error("Error logging out:", error);
      // Handle logout error (e.g., show notification)
      setIsLoggingOut(false);
    } else {
      // Redirect to login page after successful logout
      // The onAuthStateChange listener in dashboard/layout.tsx should also catch this
      router.push('/login'); 
    }
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-border bg-card text-card-foreground p-4 hidden md:block"> {/* Hide on small screens initially */}
        <div className="mb-8 text-2xl font-semibold text-primary">Trading Bots</div>
        <nav className="space-y-2">
          {/* Navigation Links */}
          <Link href="/dashboard" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>Overview</span>
          </Link>
          <Link href="/dashboard/momentum" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>Momentum Bot</span>
          </Link>
          <Link href="/dashboard/grid" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>Grid Bot</span>
          </Link>
          <Link href="/dashboard/dca" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>DCA Bot</span>
          </Link>
          <Link href="/dashboard/backtest" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>Backtesting</span>
          </Link>
          <Link href="/dashboard/settings" className="flex items-center space-x-2 p-2 rounded hover:bg-accent hover:text-accent-foreground">
            <span>Settings</span>
          </Link>
        </nav>
        {/* Logout Button at bottom of sidebar */}
         <button 
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="mt-auto w-full flex items-center space-x-2 p-2 rounded text-sm text-muted-foreground hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50"
          >
            {/* <FiLogOut className="h-4 w-4" /> */}
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
             </svg>
            <span>{isLoggingOut ? 'Logging out...' : 'Logout'}</span>
          </button>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 flex items-center justify-between border-b border-border bg-card px-6">
          <div>
            {/* Hamburger menu for mobile? */}
            <button className="md:hidden p-2">
              {/* Menu Icon */}
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </button>
            <span className="text-lg font-semibold hidden md:inline">Dashboard</span>
          </div>
          <div className="flex items-center space-x-4">
            {/* User Email */}
            {userEmail && <span className="text-sm text-muted-foreground hidden sm:inline">{userEmail}</span>}
            {/* Theme Toggle Button */}
             <button 
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                className="p-2 rounded hover:bg-accent"
                aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
             >
                 {theme === 'light' ? <FiMoon className="w-5 h-5" /> : <FiSun className="w-5 h-5" />}
             </button>
             {/* Logout Button (mobile only) */}
             <button 
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="p-2 rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50 md:hidden" 
                aria-label="Logout"
              >
                 <FiLogOut className="w-5 h-5" />
              </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;

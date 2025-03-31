'use client'; // Need client hooks

import React, { ReactNode, useState, useEffect } from 'react'; 
import Link from 'next/link';
import { useRouter } from 'next/navigation'; 
import { supabase } from '@/lib/supabase'; 
// Removed react-icons import

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
      <aside className="w-64 flex-shrink-0 border-r border-border bg-card text-card-foreground p-4 hidden md:flex md:flex-col"> {/* Ensure flex column for sidebar */}
        <div> {/* Wrapper for top content */}
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
        </div>
        {/* Logout Button at bottom of sidebar */}
         <button 
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="mt-auto w-full flex items-center space-x-2 p-2 rounded text-sm text-muted-foreground hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50"
          >
             {/* Logout SVG Icon */}
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
                 {/* Use SVGs directly */}
                 {theme === 'light' ? (
                     // Moon Icon SVG
                     <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                       <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
                     </svg>
                 ) : (
                     // Sun Icon SVG
                     <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                       <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
                     </svg>
                 )}
             </button>
             {/* Logout Button (mobile only) */}
             <button 
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="p-2 rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50 md:hidden" 
                aria-label="Logout"
              >
                 {/* Logout SVG Icon */}
                 <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                   <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                 </svg>
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

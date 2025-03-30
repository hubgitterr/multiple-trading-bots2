'use client'; // Need client-side hooks for auth check

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase'; // Import supabase client
import DashboardLayoutComponent from '@/components/dashboard/Layout'; 

export default function DashboardPagesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session }, error } = await supabase.auth.getSession();
      
      if (error) {
        console.error("Error getting auth session:", error);
        router.push('/login'); // Redirect on error
      } else if (!session) {
        console.log("No active session, redirecting to login.");
        router.push('/login'); // Redirect if no session
      } else {
        // User is authenticated
        setIsAuthenticated(true);
      }
      setIsLoading(false);
    };

    checkAuth();

    // Optional: Listen for auth state changes (e.g., logout in another tab)
    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
       if (event === 'SIGNED_OUT' || !session) {
           console.log("Auth state changed to signed out, redirecting.");
           setIsAuthenticated(false);
           router.push('/login');
       } else if (event === 'SIGNED_IN') {
           setIsAuthenticated(true);
       }
    });

    // Cleanup listener on unmount
    return () => {
      authListener?.subscription.unsubscribe();
    };

  }, [router]); // Dependency array includes router

  // Show loading state or null while checking auth
  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>; // Or a proper loading spinner
  }

  // If authenticated, render the layout and children
  // If not authenticated (and not loading), this will return null, 
  // preventing flicker before redirect happens in useEffect.
  if (isAuthenticated) { 
    return (
      <DashboardLayoutComponent>
        {children} 
      </DashboardLayoutComponent>
    );
  }

  // Return null while redirecting or if authentication fails initially
  return null; 
} // Added missing closing brace

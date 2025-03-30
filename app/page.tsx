'use client'; // Need client hooks for auth check and redirect

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

// This page acts as an entry point and redirects based on auth status.
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const checkAuthAndRedirect = async () => {
      const { data: { session } } = await supabase.auth.getSession();

      if (session) {
        // User is logged in, redirect to dashboard
        router.replace('/dashboard'); // Use replace to avoid adding '/' to history
      } else {
        // User is not logged in, redirect to login
        router.replace('/login');
      }
    };

    checkAuthAndRedirect();
  }, [router]);

  // Render minimal content while redirecting
  return (
    <div className="flex items-center justify-center min-h-screen">
      Loading... 
    </div>
  );
}

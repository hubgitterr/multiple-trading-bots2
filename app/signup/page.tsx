'use client';

import React, { useState } from 'react';
import { supabase } from '@/lib/supabase'; // Import Supabase client
import { useRouter } from 'next/navigation'; 
import Link from 'next/link';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null); // For success messages
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSignup = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      // Supabase handles email confirmation by default if enabled in project settings
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        // options: { // Optional: Redirect user after email confirmation
        //   emailRedirectTo: `${window.location.origin}/dashboard`,
        // }
      });

      if (signUpError) {
        throw signUpError;
      }

      // Handle cases based on Supabase project settings (email confirmation required?)
      if (data.user && data.user.identities?.length === 0) {
         // This might indicate email confirmation is required but user already exists (unverified)
         setMessage("Please check your email to confirm your account.");
         // Optionally clear form or redirect to a confirmation pending page
      } else if (data.session) {
         // User signed up and logged in immediately (email confirmation might be off)
         console.log('Signup successful and logged in, redirecting...');
         router.push('/dashboard'); 
      } else {
         // User created, email confirmation likely required
         setMessage("Signup successful! Please check your email to verify your account.");
         // Clear form or redirect
         setEmail('');
         setPassword('');
         setConfirmPassword('');
      }

    } catch (err: any) {
      console.error('Signup error:', err);
      setError(err.message || 'Failed to sign up.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="w-full max-w-md p-8 space-y-6 bg-card rounded-lg shadow">
        <h1 className="text-2xl font-bold text-center text-card-foreground">Create Account</h1>
        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-muted-foreground">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 mt-1 border border-input rounded bg-background text-foreground focus:ring-primary focus:border-primary"
              disabled={loading}
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-muted-foreground">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 mt-1 border border-input rounded bg-background text-foreground focus:ring-primary focus:border-primary"
              disabled={loading}
            />
          </div>
           <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-muted-foreground">Confirm Password</label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={`w-full px-3 py-2 mt-1 border rounded bg-background text-foreground focus:ring-primary focus:border-primary ${password !== confirmPassword && confirmPassword ? 'border-destructive' : 'border-input'}`}
              disabled={loading}
            />
             {password !== confirmPassword && confirmPassword && <p className="text-sm text-destructive mt-1">Passwords do not match.</p>}
          </div>
          
          {error && <p className="text-sm text-destructive">{error}</p>}
          {message && <p className="text-sm text-green-600">{message}</p>}

          <div>
            <button
              type="submit"
              disabled={loading || (password !== confirmPassword && confirmPassword !== '')}
              className="w-full px-4 py-2 font-medium text-primary-foreground bg-primary rounded hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
            >
              {loading ? 'Signing up...' : 'Sign Up'}
            </button>
          </div>
        </form>
         <p className="text-sm text-center text-muted-foreground">
            Already have an account?{' '}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Log in
            </Link>
          </p>
      </div>
    </div>
  );
}

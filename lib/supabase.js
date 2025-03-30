import { createClient } from '@supabase/supabase-js';

// Ensure environment variables are loaded correctly
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
  throw new Error("Missing environment variable: NEXT_PUBLIC_SUPABASE_URL");
}
if (!supabaseAnonKey) {
  throw new Error("Missing environment variable: NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

// Create and export the Supabase client instance
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// You can add helper functions for database operations or authentication here later if needed.
// For example:
// export const getUser = async () => {
//   const { data: { user } } = await supabase.auth.getUser();
//   return user;
// };

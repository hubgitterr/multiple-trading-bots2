-- schema.sql
-- SQL script to set up tables for the Trading Bots application in Supabase.
-- Execute this script in your Supabase SQL Editor.

-- ========= USERS TABLE =========
-- Stores user profile information, linking to Supabase Auth users.
-- Note: Supabase Auth manages the actual user authentication.
-- We add profile-specific data here.

CREATE TABLE IF NOT EXISTS public.users (
    id uuid NOT NULL PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, -- Links to Supabase auth user
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    binance_api_key text NULL, -- Store securely (consider encryption extensions like pgsodium)
    binance_api_secret text NULL, -- Store securely
    preferences jsonb NULL -- For theme, notifications, etc.
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own profile.
CREATE POLICY "Allow individual user read access"
ON public.users
FOR SELECT USING (auth.uid() = id);

-- Policy: Users can update their own profile.
CREATE POLICY "Allow individual user update access"
ON public.users
FOR UPDATE USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- Note: Inserting into users might be handled by triggers on auth.users or manually after signup.
-- For simplicity, we allow inserts if the ID matches the authenticated user.
CREATE POLICY "Allow individual user insert access"
ON public.users
FOR INSERT WITH CHECK (auth.uid() = id);


-- ========= BOT CONFIGS TABLE =========
-- Stores configurations for different trading bot instances created by users.

CREATE TABLE IF NOT EXISTS public.bot_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    bot_type text NOT NULL CHECK (bot_type IN ('momentum', 'grid', 'dca')), -- Enforce bot types
    name text NOT NULL,
    symbol text NOT NULL, -- e.g., 'BTCUSDT'
    is_active boolean DEFAULT false NOT NULL,
    config_params jsonb NOT NULL, -- Bot-specific parameters (grid levels, indicators, etc.)
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.bot_configs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own bot configurations.
CREATE POLICY "Allow individual user read access for bot_configs"
ON public.bot_configs
FOR SELECT USING (auth.uid() = user_id);

-- Policy: Users can create bot configurations for themselves.
CREATE POLICY "Allow individual user insert access for bot_configs"
ON public.bot_configs
FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own bot configurations.
CREATE POLICY "Allow individual user update access for bot_configs"
ON public.bot_configs
FOR UPDATE USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can delete their own bot configurations.
CREATE POLICY "Allow individual user delete access for bot_configs"
ON public.bot_configs
FOR DELETE USING (auth.uid() = user_id);


-- ========= TRADES TABLE =========
-- Records individual trades executed by the bots.

CREATE TABLE IF NOT EXISTS public.trades (
    id bigserial PRIMARY KEY,
    bot_config_id uuid NOT NULL REFERENCES public.bot_configs(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE, -- Denormalized for easier RLS/querying
    binance_order_id text NULL UNIQUE, -- Can be NULL if trade wasn't directly from Binance order (e.g., backtest)
    symbol text NOT NULL,
    side text NOT NULL CHECK (side IN ('BUY', 'SELL')),
    type text NOT NULL CHECK (type IN ('MARKET', 'LIMIT', 'BACKTEST')), -- Added BACKTEST type
    price numeric NOT NULL,
    quantity numeric NOT NULL,
    commission numeric NULL,
    commission_asset text NULL,
    timestamp timestamp with time zone NOT NULL, -- Execution time
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own trades.
CREATE POLICY "Allow individual user read access for trades"
ON public.trades
FOR SELECT USING (auth.uid() = user_id);

-- Policy: Allow backend service role to insert trades (bots run server-side).
-- Authenticated users should NOT insert directly into this table.
-- The service role key will be used by the backend.
CREATE POLICY "Allow service role insert access for trades"
ON public.trades
FOR INSERT WITH CHECK (auth.role() = 'service_role');

-- Note: Updates/Deletes on trades are typically disallowed or restricted.


-- ========= PERFORMANCE TABLE =========
-- Stores periodic performance snapshots or aggregated metrics for bots.

CREATE TABLE IF NOT EXISTS public.performance (
    id bigserial PRIMARY KEY,
    bot_config_id uuid NOT NULL REFERENCES public.bot_configs(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE, -- Denormalized
    timestamp timestamp with time zone NOT NULL, -- Timestamp of the snapshot
    total_pnl numeric DEFAULT 0.0 NOT NULL,
    total_trades integer DEFAULT 0 NOT NULL,
    win_rate numeric DEFAULT 0.0,
    portfolio_value numeric NULL, -- Estimated value at snapshot time
    metrics jsonb NULL, -- Other metrics (Sharpe ratio, drawdown, etc.)
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.performance ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own performance data.
CREATE POLICY "Allow individual user read access for performance"
ON public.performance
FOR SELECT USING (auth.uid() = user_id);

-- Policy: Allow backend service role to insert performance data.
CREATE POLICY "Allow service role insert access for performance"
ON public.performance
FOR INSERT WITH CHECK (auth.role() = 'service_role');

-- Note: Updates/Deletes on performance data are typically restricted.


-- ========= INDEXES =========
-- Add indexes for frequently queried columns to improve performance.

CREATE INDEX IF NOT EXISTS idx_bot_configs_user_id ON public.bot_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_bot_config_id ON public.trades(bot_config_id);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON public.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON public.trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_bot_config_id ON public.performance(bot_config_id);
CREATE INDEX IF NOT EXISTS idx_performance_user_id ON public.performance(user_id);
CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON public.performance(timestamp);


-- ========= HELPER FUNCTIONS (Optional but Recommended) =========
-- Function to automatically update 'updated_at' columns

CREATE OR REPLACE FUNCTION public.trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger function to tables with 'updated_at'
CREATE TRIGGER set_timestamp_users
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.trigger_set_timestamp();

CREATE TRIGGER set_timestamp_bot_configs
BEFORE UPDATE ON public.bot_configs
FOR EACH ROW
EXECUTE FUNCTION public.trigger_set_timestamp();

-- Note: Add triggers for other tables if they get an 'updated_at' column later.

-- End of script

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? null;
const supabaseKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY ??
  null;

function assertSupabaseConfigured(): { supabaseUrl: string; supabaseKey: string } {
  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY only if you need the optional Supabase example.",
    );
  }
  return { supabaseUrl, supabaseKey };
}

const isSupabaseConfigured = Boolean(supabaseUrl && supabaseKey);

export { assertSupabaseConfigured, isSupabaseConfigured, supabaseKey, supabaseUrl };

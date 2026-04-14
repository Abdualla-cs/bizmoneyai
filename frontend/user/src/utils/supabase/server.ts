import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { assertSupabaseConfigured } from "@/utils/supabase/config";

export async function createClient() {
  const cookieStore = await cookies();
  const { supabaseUrl, supabaseKey } = assertSupabaseConfigured();

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // Server Components can't always write cookies directly.
        }
      },
    },
  });
}

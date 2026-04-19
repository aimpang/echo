"use client";

import { createBrowserClient } from "@supabase/ssr";
import { getClientEnv } from "@/env";
import type { Database } from "./database.types";

export function createClient() {
  const env = getClientEnv();
  return createBrowserClient<Database>(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}

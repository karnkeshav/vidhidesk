import { createClient } from "@supabase/supabase-js";

// Strip BOM and whitespace from environment variables (Vercel build may add these)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!.replace(/^﻿/, "").trim();
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!.replace(/^﻿/, "").trim();

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

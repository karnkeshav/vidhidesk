import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const supabase = createClient(supabaseUrl, supabaseAnonKey);
    const templateId = params.id;

    const isUuid =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        templateId
      );

    let query = supabase.from("templates").select("*");
    if (isUuid) {
      query = query.eq("id", templateId);
    } else {
      query = query.eq("template_key", templateId);
    }

    const { data, error } = await query.limit(1);
    if (error || !data || data.length === 0) {
      return NextResponse.json({ detail: "Template not found" }, { status: 404 });
    }
    return NextResponse.json(data[0]);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

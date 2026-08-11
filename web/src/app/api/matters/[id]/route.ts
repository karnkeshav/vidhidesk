import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

function getAuthedClient(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }
  const token = authHeader.split(" ")[1];
  return {
    client: createClient(supabaseUrl, supabaseAnonKey, {
      global: { headers: { Authorization: `Bearer ${token}` } },
    }),
    token,
  };
}

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const authed = getAuthedClient(req);
    if (!authed) {
      return NextResponse.json(
        { detail: "Missing or malformed Authorization header" },
        { status: 401 }
      );
    }

    const matterId = params.id;
    const { data, error } = await authed.client
      .from("matters")
      .select("*")
      .eq("id", matterId)
      .limit(1);

    if (error || !data || data.length === 0) {
      return NextResponse.json({ detail: "Matter not found" }, { status: 404 });
    }

    const matter = data[0];
    if (!matter.template_id) {
      const { data: drafts } = await authed.client
        .from("draft_versions")
        .select("template_id")
        .eq("matter_id", matterId)
        .limit(1);
      if (drafts && drafts.length > 0 && drafts[0].template_id) {
        matter.template_id = drafts[0].template_id;
      }
    }

    return NextResponse.json(matter);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const authed = getAuthedClient(req);
    if (!authed) {
      return NextResponse.json(
        { detail: "Missing or malformed Authorization header" },
        { status: 401 }
      );
    }

    const matterId = params.id;
    const body = await req.json();

    const { data, error } = await authed.client
      .from("matters")
      .update({ title: body.title })
      .eq("id", matterId)
      .select();

    if (error || !data || data.length === 0) {
      return NextResponse.json(
        { detail: error?.message || "Matter not found" },
        { status: 404 }
      );
    }

    return NextResponse.json(data[0]);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

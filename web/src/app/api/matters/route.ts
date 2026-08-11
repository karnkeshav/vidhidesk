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

export async function GET(req: NextRequest) {
  try {
    const authed = getAuthedClient(req);
    if (!authed) {
      return NextResponse.json(
        { detail: "Missing or malformed Authorization header" },
        { status: 401 }
      );
    }

    const { data, error } = await authed.client
      .from("matters")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json(data || []);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const authed = getAuthedClient(req);
    if (!authed) {
      return NextResponse.json(
        { detail: "Missing or malformed Authorization header" },
        { status: 401 }
      );
    }

    const { data: userResp, error: userErr } =
      await authed.client.auth.getUser(authed.token);
    if (userErr || !userResp?.user) {
      return NextResponse.json({ detail: "Invalid session" }, { status: 401 });
    }

    const body = await req.json();
    let resolved_template_id = body.template_id;

    if (resolved_template_id) {
      const isUuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          resolved_template_id
        );
      if (!isUuid) {
        const { data: tplData } = await authed.client
          .from("templates")
          .select("id")
          .eq("template_key", resolved_template_id)
          .limit(1);
        if (tplData && tplData.length > 0) {
          resolved_template_id = tplData[0].id;
        }
      }
    }

    const row: Record<string, unknown> = {
      user_id: userResp.user.id,
      title: body.title,
      client_name: body.client_name || null,
      module: body.module,
    };

    if (resolved_template_id) row.template_id = resolved_template_id;
    if (body.court_category) row.court_category = body.court_category;
    if (body.jurisdiction_state) row.jurisdiction_state = body.jurisdiction_state;
    if (body.cnr_number) row.cnr_number = body.cnr_number;
    if (body.case_number_formatted) row.case_number_formatted = body.case_number_formatted;
    if (body.litigation_stage) row.litigation_stage = body.litigation_stage;
    if (body.court_name) row.court_name = body.court_name;
    if (body.bench_name) row.bench_name = body.bench_name;

    let { data, error } = await authed.client.from("matters").insert([row]).select();

    if (
      error &&
      (error.message?.includes("template_id") || error.code === "PGRST204")
    ) {
      delete row.template_id;
      const retry = await authed.client.from("matters").insert([row]).select();
      data = retry.data;
      error = retry.error;
    }

    if (error || !data || data.length === 0) {
      return NextResponse.json(
        { detail: error?.message || "Failed to create matter" },
        { status: 400 }
      );
    }

    const created = data[0];
    if (!created.template_id && resolved_template_id) {
      created.template_id = resolved_template_id;
    }
    return NextResponse.json(created, { status: 201 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

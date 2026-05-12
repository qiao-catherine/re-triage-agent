/**
 * Server-side proxy to the LangGraph deployment.
 *
 * Reads LANGSMITH_API_KEY (server-only, NOT NEXT_PUBLIC_) and injects the
 * x-api-key header before forwarding. The key never reaches the browser.
 *
 * /api/lg/<path> forwards to ${DEPLOYMENT_URL}/<path>.
 */

import { NextRequest, NextResponse } from "next/server";

const DEPLOYMENT_URL =
  process.env.DEPLOYMENT_URL ?? "http://localhost:2024";
const API_KEY = process.env.LANGSMITH_API_KEY ?? "";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "proxy-connection",
  "te",
  "trailer",
]);

async function forward(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  const upstream = new URL(`${DEPLOYMENT_URL}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((v, k) =>
    upstream.searchParams.set(k, v),
  );

  // Copy headers, drop hop-by-hop and any incoming auth (we set our own).
  const headers = new Headers();
  request.headers.forEach((v, k) => {
    const lk = k.toLowerCase();
    if (HOP_BY_HOP.has(lk)) return;
    if (lk === "host" || lk === "x-api-key" || lk === "authorization") return;
    headers.set(k, v);
  });
  if (API_KEY) headers.set("x-api-key", API_KEY);

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  let upstreamResp: Response;
  try {
    upstreamResp = await fetch(upstream, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (e) {
    return NextResponse.json(
      { error: "upstream unreachable", detail: String(e) },
      { status: 502 },
    );
  }

  // Strip hop-by-hop from the response too.
  const respHeaders = new Headers();
  upstreamResp.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k.toLowerCase())) respHeaders.set(k, v);
  });

  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    headers: respHeaders,
  });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
export const OPTIONS = forward;

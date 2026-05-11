import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

// Load the repo's single .env (one level up from frontend/) so one file
// feeds both backend (langgraph.json reads "../.env") and frontend.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../.env") });

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Only the safe-to-ship NEXT_PUBLIC_* values get inlined into the client
  // bundle. LANGSMITH_API_KEY and DEPLOYMENT_URL stay server-only and are
  // read by app/api/lg/[...path]/route.ts at request time.
  env: {
    NEXT_PUBLIC_GRAPH_ID: process.env.NEXT_PUBLIC_GRAPH_ID ?? "deal_triage",
    NEXT_PUBLIC_INBOX_NAME: process.env.NEXT_PUBLIC_INBOX_NAME ?? "Deal Triage",
  },
};

export default nextConfig;

// Northbrook brand mark — replaces the LangChain agent-inbox logo for the
// forked deal-triage app. Two parts: an orange "N" tile + the wordmark.

export const agentInboxSvg = (
  <div className="flex items-center gap-2.5">
    <div className="w-8 h-8 rounded-md bg-[#ff5b1a] flex items-center justify-center text-white font-bold text-base shrink-0">
      N
    </div>
    <div className="flex flex-col leading-tight">
      <span className="font-semibold text-gray-900 text-[15px] tracking-tight">
        Northbrook
      </span>
      <span className="text-[11px] text-gray-500">Deal Triage</span>
    </div>
  </div>
);

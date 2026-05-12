"use client";

import NextLink from "next/link";
import { usePathname } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
} from "@/components/ui/sidebar";
import { Inbox, CheckSquare, BookOpen } from "lucide-react";
import { agentInboxSvg } from "../agent-inbox/components/agent-inbox-logo";
import { useSidebar } from "@/components/ui/sidebar";
import { TooltipIconButton } from "../ui/assistant-ui/tooltip-icon-button";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  return (
    <Sidebar className="border-r-[0px] bg-[#F9FAFB]">
      <SidebarContent className="flex flex-col h-screen pb-9 pt-6">
        <div className="flex items-center justify-between px-11">
          <NextLink href="/" className="flex-shrink-0 w-full">
            {agentInboxSvg}
          </NextLink>
          <AppSidebarTrigger isOutside={false} className="mt-1" />
        </div>
        <SidebarGroup className="flex-1 overflow-y-auto pt-6">
          <SidebarGroupContent className="h-full">
            <SidebarMenu className="flex flex-col gap-2 justify-between h-full">
              <div className="flex flex-col gap-2 pl-7">
                <PrimaryNav />
              </div>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}

const sidebarTriggerSVG = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M6 2V14M5.2 2H10.8C11.9201 2 12.4802 2 12.908 2.21799C13.2843 2.40973 13.5903 2.71569 13.782 3.09202C14 3.51984 14 4.0799 14 5.2V10.8C14 11.9201 14 12.4802 13.782 12.908C13.5903 13.2843 13.2843 13.5903 12.908 13.782C12.4802 14 11.9201 14 10.8 14H5.2C4.07989 14 3.51984 14 3.09202 13.782C2.71569 13.5903 2.40973 13.2843 2.21799 12.908C2 12.4802 2 11.9201 2 10.8V5.2C2 4.07989 2 3.51984 2.21799 3.09202C2.40973 2.71569 2.71569 2.40973 3.09202 2.21799C3.51984 2 4.0799 2 5.2 2Z"
      stroke="#3F3F46"
      strokeWidth="1.66667"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export function AppSidebarTrigger({
  isOutside,
  className,
}: {
  isOutside: boolean;
  className?: string;
}) {
  const { toggleSidebar, open } = useSidebar();

  if (isOutside && open) {
    // If this component is being rendered outside the sidebar view, then do not render if open.
    // This way we can render the trigger inside the main view when open.
    return null;
  }

  return (
    <TooltipIconButton
      tooltip="Toggle Sidebar"
      onClick={toggleSidebar}
      className={className}
    >
      {sidebarTriggerSVG}
    </TooltipIconButton>
  );
}

// Primary navigation: Review / Done / Firm memory.
function PrimaryNav() {
  const pathname = usePathname();
  const items = [
    { href: "/", label: "For review", icon: Inbox, match: (p: string) => p === "/" },
    { href: "/done", label: "Done", icon: CheckSquare, match: (p: string) => p.startsWith("/done") },
    { href: "/memory", label: "Firm memory", icon: BookOpen, match: (p: string) => p.startsWith("/memory") },
  ];
  return (
    <div className="flex flex-col gap-1">
      {items.map(({ href, label, icon: Icon, match }) => {
        const active = match(pathname ?? "");
        return (
          <NextLink key={href} href={href}>
            <SidebarMenuButton
              className={cn(
                "w-full",
                active ? "bg-gray-100 text-black font-medium" : "text-gray-600"
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </SidebarMenuButton>
          </NextLink>
        );
      })}
    </div>
  );
}

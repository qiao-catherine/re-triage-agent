import type { Metadata } from "next";
import "./globals.css";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/toaster";
import { ThreadsProvider } from "@/components/agent-inbox/contexts/ThreadContext";
import React from "react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar, AppSidebarTrigger } from "@/components/app-sidebar";
import { InboxBootstrap } from "@/components/inbox-bootstrap";
import { cn } from "@/lib/utils";

const inter = Inter({
  subsets: ["latin"],
  preload: true,
  display: "swap",
});

export const metadata: Metadata = {
  title: "Linwood Capital: Deal Triage",
  description: "AC GTM take-home: deal-triage demo for Linwood Capital (scenario 2).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <React.Suspense fallback={<div>Loading (layout)...</div>}>
          <InboxBootstrap />
          <Toaster />
          <ThreadsProvider>
            <SidebarProvider>
              <AppSidebar />
              <main className="flex flex-row w-full min-h-full pt-6 pl-6 gap-6">
                <AppSidebarTrigger isOutside={true} />
                <div className="flex flex-col gap-6 w-full min-h-full">
                  <div
                    className={cn(
                      "h-full bg-white rounded-tl-[58px]",
                      "overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100"
                    )}
                  >
                    {children}
                  </div>
                </div>
              </main>
            </SidebarProvider>
          </ThreadsProvider>
        </React.Suspense>
      </body>
    </html>
  );
}

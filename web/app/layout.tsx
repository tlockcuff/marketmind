import type { Metadata } from "next";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WebSocketProvider } from "@/components/websocket-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Marketmind Dashboard",
  description: "Day Trading Bot Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased min-h-screen bg-background text-foreground">
        <TooltipProvider>
          <WebSocketProvider>
            {children}
          </WebSocketProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}

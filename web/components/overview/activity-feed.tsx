"use client";

interface ActivityFeedProps {
  logs: string[] | null;
}

function formatLogEntry(log: string) {
  // Format: "HH:MM:SS | LEVEL | message"
  const parts = log.split("|", 3);
  const timestamp = parts.length >= 3 ? parts[0].trim() : null;
  const message = parts.length >= 3 ? parts[2].trim() : log;

  // Determine log type and color
  let type = "info";
  let color = "text-muted-foreground";
  
  if (message.includes("BUY") || message.includes("SELL")) {
    type = "trade";
    color = "text-blue-400";
  } else if (message.includes("ERROR") || message.includes("FAILED")) {
    type = "error";
    color = "text-red-400";
  } else if (message.includes("SUCCESS") || message.includes("FILLED")) {
    type = "success";
    color = "text-green-400";
  } else if (message.includes("SIGNAL") || message.includes("SCORE")) {
    type = "signal";
    color = "text-[#ff9e2c]";
  }

  return { timestamp, message, type, color };
}

export function ActivityFeed({ logs }: ActivityFeedProps) {
  const recentLogs = (logs ?? []).slice(-8); // Show last 8 entries

  if (recentLogs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-sm p-6 text-center">
        <div className="text-muted-foreground">
          <span className="text-2xl">📝</span>
          <p className="mt-2 text-sm">No recent activity</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-sm p-4">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#ff9e2c] uppercase tracking-wider">
            Recent Activity
          </h3>
          <span className="text-xs text-muted-foreground">
            Last {recentLogs.length} events
          </span>
        </div>

        <div className="space-y-2">
          {recentLogs.reverse().map((log, index) => {
            const { timestamp, message, color } = formatLogEntry(log);
            
            return (
              <div key={index} className="flex gap-3 text-sm">
                {timestamp && (
                  <span className="text-xs text-muted-foreground font-mono shrink-0">
                    {timestamp}
                  </span>
                )}
                <span className={`${color} leading-snug`}>
                  {message}
                </span>
              </div>
            );
          })}
        </div>

        <div className="pt-2 border-t border-border">
          <a 
            href="/activity" 
            className="text-xs text-[#ff9e2c] hover:opacity-80 font-medium"
          >
            View all activity →
          </a>
        </div>
      </div>
    </div>
  );
}
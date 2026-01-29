import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse rounded bg-[#1e1e28]", className)}
      {...props}
    />
  );
}

function SkeletonRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex justify-between items-center">
          <Skeleton className="h-3.5 rounded" style={{ width: `${30 + Math.random() * 25}%` }} />
          <Skeleton className="h-3.5 w-16 rounded" />
        </div>
      ))}
    </div>
  );
}

function SkeletonTable({ rows = 4, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex gap-3 mb-2">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 rounded" style={{ width: `${100 / cols}%` }} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton
              key={j}
              className="h-3.5 rounded"
              style={{ width: `${100 / cols}%`, opacity: 0.6 + Math.random() * 0.4 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export { Skeleton, SkeletonRows, SkeletonTable };

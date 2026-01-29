"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen } from "lucide-react";
import { Sheet, SheetTrigger, SheetContent } from "@/components/ui/sheet";
import { docs, fileToSlug } from "@/lib/docs";
import type { Components } from "react-markdown";

export function DocsSlideover() {
  const [activeSlug, setActiveSlug] = useState(docs[0].slug);
  const activeDoc = docs.find((d) => d.slug === activeSlug) ?? docs[0];

  const components: Components = {
    img({ src, alt }) {
      // Rewrite relative paths to serve from /public
      const resolvedSrc = src?.startsWith("docs/") ? `/${src}` : src;
      return <img src={resolvedSrc} alt={alt ?? ""} className="rounded max-w-full" />;
    },
    a({ href, children }) {
      if (href?.endsWith(".md")) {
        const filename = href.split("/").pop()!;
        const slug = fileToSlug[filename];
        if (slug) {
          return (
            <button
              className="text-[#ff9e2c] hover:underline"
              onClick={() => setActiveSlug(slug)}
            >
              {children}
            </button>
          );
        }
      }
      // External links open in new tab
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },
  };

  return (
    <Sheet>
      <SheetTrigger asChild>
        <button
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Documentation"
        >
          <BookOpen className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent className="max-w-6xl w-full">
        <div className="flex h-full">
          {/* Doc list sidebar */}
          <nav className="w-[220px] shrink-0 border-r border-border p-3 pt-10 flex flex-col gap-1">
            {docs.map((doc) => (
              <button
                key={doc.slug}
                onClick={() => setActiveSlug(doc.slug)}
                className={`text-left text-xs px-2 py-1.5 rounded transition-colors ${
                  doc.slug === activeSlug
                    ? "bg-[#1a1a24] text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-[#1a1a24]/50"
                }`}
              >
                <span className="mr-1.5">{doc.emoji}</span>
                {doc.title}
              </button>
            ))}
          </nav>

          {/* Markdown content */}
          <div className="flex-1 overflow-y-auto p-6 pt-10">
            <article className="prose-dark">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{activeDoc.content}</ReactMarkdown>
            </article>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

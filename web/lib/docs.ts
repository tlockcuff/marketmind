import backtesting from "../../docs/backtesting.md";
import congressTrading from "../../docs/congress_trading.md";
import riskManagement from "../../docs/risk-management.md";
import scoringSystem from "../../docs/scoring-system.md";
import technicalIndicators from "../../docs/technical-indicators.md";
import introduction from "../../README.md";

export interface DocEntry {
  slug: string;
  title: string;
  emoji: string;
  content: string;
}

// Map md filenames to slugs for internal link resolution
export const fileToSlug: Record<string, string> = {
  "backtesting.md": "backtesting",
  "congress_trading.md": "congress",
  "risk-management.md": "risk",
  "scoring-system.md": "scoring",
  "technical-indicators.md": "indicators",
};

export const docs: DocEntry[] = [
  { slug: "intro", title: "Introduction", emoji: "👋", content: introduction },
  { slug: "scoring", title: "Scoring System", emoji: "💯", content: scoringSystem },
  { slug: "risk", title: "Risk Management", emoji: "🛡️", content: riskManagement },
  { slug: "indicators", title: "Technical Indicators", emoji: "📊", content: technicalIndicators },
  { slug: "backtesting", title: "Backtesting", emoji: "📈", content: backtesting },
  { slug: "congress", title: "Congress Trading", emoji: "🏛️", content: congressTrading },
];

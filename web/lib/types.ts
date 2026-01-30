export interface Position {
  symbol: string;
  name: string;
  qty: number;
  side: string;
  avg_entry: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  score: number | null;
  rationale: string | null;
}

export interface OptionsPosition {
  strategy: string;
  underlying: string;
  contracts: string[];
  net_debit_credit: number;
  max_loss: number;
  max_profit: number;
  status: string;
}

export interface Order {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  filled_qty: number;
  type: string;
  status: string;
  limit_price: number | null;
  stop_price: number | null;
}

export interface Account {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  long_market_value: number;
  short_market_value: number;
  last_equity: number;
  daily_change: number;
  daily_change_pct: number;
  initial_margin: number;
  maintenance_margin: number;
  day_trade_count: number;
  day_trades_remaining: number;
  pattern_day_trader: boolean;
  trading_blocked: boolean;
  account_blocked: boolean;
  is_paper: boolean;
}

export interface Stats {
  position_count: number;
  max_positions: number;
  winners: number;
  losers: number;
  open_orders: number;
  day_trades_remaining: number;
  day_trade_count: number;
  is_paper: boolean;
}

export interface SettingMeta {
  type: "float" | "int" | "bool";
  min?: number;
  max?: number;
  label: string;
  section: string;
}

export interface Config {
  values: Record<string, string | number | boolean>;
  overrides: string[];
  settings_meta: Record<string, SettingMeta>;
}

export interface ApiUsage {
  today: {
    date: string;
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cost: number;
    signals: number;
  };
  total: {
    total_requests: number;
    total_cost: number;
    days_tracked: number;
  };
}

export interface MarketStatus {
  market_status: string;
  session: string;
  is_open: boolean;
  trading_mode: string;
  bot_running: boolean;
  current_time: string;
  time_until_open: number | null;
  time_until_close: number | null;
}

export interface TradeHistoryData {
  open: Record<string, any>;
  closed: any[];
}

export interface NewsItem {
  headline: string;
  summary: string;
  source: string;
  url: string;
  symbols: string[];
  created_at: string;
  sector: string;
}

export interface NewsData {
  articles: NewsItem[];
  sectors: string[];
  updated_at: string;
}

export interface MarketIndex {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
  is_vix: boolean;
}

export interface DashboardData {
  account: Account;
  positions: Position[];
  options: OptionsPosition[];
  orders: Order[];
  stats: Stats;
  config: Config;
  api_usage: ApiUsage;
  logs: string[];
  status: MarketStatus;
  history: TradeHistoryData;
  news: NewsData;
  market_indices: MarketIndex[];
  timestamp: string;
}

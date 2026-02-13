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
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
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

export interface AnalyticsMetrics {
  total_pnl: number;
  total_trades: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  best_trade: number;
  worst_trade: number;
  max_drawdown: number;
  sharpe_ratio: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface CumulativePnlPoint {
  date: string;
  cumulative_pnl: number;
  symbol: string;
  pnl: number;
}

export interface SectorPnl {
  sector: string;
  pnl: number;
}

export interface ClosedTrade {
  symbol: string;
  direction: string;
  qty: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  entry_time: string | null;
  exit_time: string | null;
  sector: string;
  score: number;
}

export interface AnalyticsData {
  equity_curve: EquityPoint[];
  trades: ClosedTrade[];
  cumulative_pnl: CumulativePnlPoint[];
  sector_breakdown: SectorPnl[];
  metrics: AnalyticsMetrics;
}

export interface CryptoPosition {
  symbol: string;
  qty: number;
  avg_entry: number;
  current_price: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  score: number;
  direction: string;
  name: string;
}

export interface DashboardData {
  account: Account;
  positions: Position[];
  options: OptionsPosition[];
  crypto?: CryptoPosition[];
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

#!/usr/bin/env python3
"""Performance analytics for trade history."""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_db, init_db


def load_trades(mode: str) -> list:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT symbol, direction, qty, entry_price, entry_time,
                          stop_loss, take_profit, score, grok_rationale,
                          score_breakdown, status, exit_price, exit_time, pnl,
                          asset_type, option_details, sector, atr_at_entry,
                          trailing_stop_updates, scale_out_level
                   FROM trades WHERE mode = %s AND status != 'open'
                   ORDER BY exit_time DESC""",
                (mode,),
            ).fetchall()
            return [
                {
                    "symbol": r[0], "direction": r[1], "qty": r[2],
                    "entry_price": float(r[3]) if r[3] else 0,
                    "entry_time": r[4].isoformat() if r[4] else None,
                    "score": float(r[7]) if r[7] else 0,
                    "score_breakdown": r[9] or {},
                    "status": r[10],
                    "exit_price": float(r[11]) if r[11] else None,
                    "exit_time": r[12].isoformat() if r[12] else None,
                    "pnl": float(r[13]) if r[13] else None,
                    "sector": r[16],
                }
                for r in rows
            ]
    except Exception as e:
        print(f"Failed to load trades: {e}")
        return []


def load_rejected(mode: str) -> list:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT symbol, direction, score, reason, score_breakdown, sector, created_at
                   FROM rejected_signals WHERE mode = %s
                   ORDER BY created_at DESC""",
                (mode,),
            ).fetchall()
            return [
                {
                    "symbol": r[0], "direction": r[1], "score": float(r[2]) if r[2] else 0,
                    "reason": r[3], "score_breakdown": r[4] or {}, "sector": r[5],
                    "timestamp": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ]
    except Exception as e:
        print(f"Failed to load rejected signals: {e}")
        return []


def fmt_pct(v):
    return f"{v:+.1f}%" if v is not None else "N/A"


def fmt_dollar(v):
    return f"${v:+,.2f}" if v is not None else "N/A"


def compute_stats(trades: list) -> dict:
    if not trades:
        return {}
    pnls = [t.get("pnl", 0) or 0 for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    total_pnl = sum(pnls)
    win_rate = len(winners) / len(pnls) * 100 if pnls else 0
    avg_win = sum(winners) / len(winners) if winners else 0
    avg_loss = sum(losers) / len(losers) if losers else 0
    profit_factor = abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float("inf")

    # Hold time
    hold_hours = []
    for t in trades:
        entry = t.get("entry_time")
        exit_ = t.get("exit_time")
        if entry and exit_:
            try:
                dt_entry = datetime.fromisoformat(entry)
                dt_exit = datetime.fromisoformat(exit_)
                hold_hours.append((dt_exit - dt_entry).total_seconds() / 3600)
            except (ValueError, TypeError):
                pass

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "avg_hold_hours": sum(hold_hours) / len(hold_hours) if hold_hours else 0,
        "median_hold_hours": sorted(hold_hours)[len(hold_hours) // 2] if hold_hours else 0,
    }


def print_overall(trades: list):
    stats = compute_stats(trades)
    if not stats:
        print("No closed trades found.")
        return
    print("=" * 50)
    print("OVERALL STATS")
    print("=" * 50)
    print(f"  Trades:         {stats['total_trades']}")
    print(f"  Win rate:       {stats['win_rate']:.1f}% ({stats['winners']}W / {stats['losers']}L)")
    print(f"  Total P&L:      {fmt_dollar(stats['total_pnl'])}")
    print(f"  Avg win:        {fmt_dollar(stats['avg_win'])}")
    print(f"  Avg loss:       {fmt_dollar(stats['avg_loss'])}")
    print(f"  Profit factor:  {stats['profit_factor']:.2f}")
    print(f"  Avg hold:       {stats['avg_hold_hours']:.1f}h")
    print(f"  Median hold:    {stats['median_hold_hours']:.1f}h")


def print_by_score_bucket(trades: list):
    buckets = {"65-74": [], "75-84": [], "85+": [], "<65": []}
    for t in trades:
        s = t.get("score", 0) or 0
        if s >= 85:
            buckets["85+"].append(t)
        elif s >= 75:
            buckets["75-84"].append(t)
        elif s >= 65:
            buckets["65-74"].append(t)
        else:
            buckets["<65"].append(t)

    print("\n" + "=" * 50)
    print("BY SCORE BUCKET")
    print("=" * 50)
    for label in ["85+", "75-84", "65-74", "<65"]:
        group = buckets[label]
        if not group:
            continue
        stats = compute_stats(group)
        print(f"  [{label:>5}]  {stats['total_trades']} trades  "
              f"WR={stats['win_rate']:.0f}%  "
              f"P&L={fmt_dollar(stats['total_pnl'])}  "
              f"PF={stats['profit_factor']:.2f}")


def print_by_sector(trades: list):
    sectors = defaultdict(list)
    for t in trades:
        sec = t.get("sector") or "Unknown"
        sectors[sec].append(t)

    if len(sectors) <= 1 and "Unknown" in sectors:
        return  # no sector data yet

    print("\n" + "=" * 50)
    print("BY SECTOR")
    print("=" * 50)
    for sec in sorted(sectors, key=lambda s: sum(t.get("pnl", 0) or 0 for t in sectors[s]), reverse=True):
        group = sectors[sec]
        stats = compute_stats(group)
        print(f"  [{sec:>12}]  {stats['total_trades']} trades  "
              f"WR={stats['win_rate']:.0f}%  "
              f"P&L={fmt_dollar(stats['total_pnl'])}")


def print_by_exit_reason(trades: list):
    reasons = defaultdict(list)
    for t in trades:
        r = t.get("status", "unknown")
        reasons[r].append(t)

    print("\n" + "=" * 50)
    print("BY EXIT REASON")
    print("=" * 50)
    for reason in sorted(reasons, key=lambda r: len(reasons[r]), reverse=True):
        group = reasons[reason]
        stats = compute_stats(group)
        print(f"  [{reason:>16}]  {stats['total_trades']} trades  "
              f"WR={stats['win_rate']:.0f}%  "
              f"P&L={fmt_dollar(stats['total_pnl'])}")


def print_by_time_of_day(trades: list):
    buckets = defaultdict(list)
    for t in trades:
        entry = t.get("entry_time")
        if not entry:
            continue
        try:
            dt = datetime.fromisoformat(entry)
            hour = dt.hour
            if hour < 10:
                label = "9:30-10"
            elif hour < 11:
                label = "10-11"
            elif hour < 13:
                label = "11-13"
            elif hour < 15:
                label = "13-15"
            else:
                label = "15-16"
            buckets[label].append(t)
        except (ValueError, TypeError):
            pass

    if not buckets:
        return

    print("\n" + "=" * 50)
    print("BY TIME OF DAY (entry)")
    print("=" * 50)
    for label in ["9:30-10", "10-11", "11-13", "13-15", "15-16"]:
        group = buckets.get(label, [])
        if not group:
            continue
        stats = compute_stats(group)
        print(f"  [{label:>7}]  {stats['total_trades']} trades  "
              f"WR={stats['win_rate']:.0f}%  "
              f"P&L={fmt_dollar(stats['total_pnl'])}")


def print_hold_time_analysis(trades: list):
    winners = [t for t in trades if (t.get("pnl", 0) or 0) > 0]
    losers = [t for t in trades if (t.get("pnl", 0) or 0) <= 0]

    def avg_hold(group):
        hours = []
        for t in group:
            entry = t.get("entry_time")
            exit_ = t.get("exit_time")
            if entry and exit_:
                try:
                    dt_entry = datetime.fromisoformat(entry)
                    dt_exit = datetime.fromisoformat(exit_)
                    hours.append((dt_exit - dt_entry).total_seconds() / 3600)
                except (ValueError, TypeError):
                    pass
        return sum(hours) / len(hours) if hours else 0

    print("\n" + "=" * 50)
    print("HOLD TIME: WINNERS vs LOSERS")
    print("=" * 50)
    print(f"  Winners avg hold: {avg_hold(winners):.1f}h ({len(winners)} trades)")
    print(f"  Losers avg hold:  {avg_hold(losers):.1f}h ({len(losers)} trades)")


def print_score_correlation(trades: list):
    """Simple score component vs P&L correlation."""
    components = ["grok", "technical", "backtest", "volume", "risk_reward"]
    print("\n" + "=" * 50)
    print("SCORE COMPONENT → P&L CORRELATION")
    print("=" * 50)

    for comp in components:
        pairs = []
        for t in trades:
            breakdown = t.get("score_breakdown", {})
            val = breakdown.get(comp)
            pnl = t.get("pnl", 0) or 0
            if val is not None:
                pairs.append((val, pnl))
        if len(pairs) < 5:
            continue

        # Simple Pearson correlation
        n = len(pairs)
        sx = sum(x for x, _ in pairs)
        sy = sum(y for _, y in pairs)
        sxy = sum(x * y for x, y in pairs)
        sx2 = sum(x * x for x, _ in pairs)
        sy2 = sum(y * y for _, y in pairs)
        denom = ((n * sx2 - sx ** 2) * (n * sy2 - sy ** 2)) ** 0.5
        if denom == 0:
            r = 0
        else:
            r = (n * sxy - sx * sy) / denom
        print(f"  {comp:>12}: r={r:+.3f}  (n={n})")


def print_rejection_stats(rejected: list):
    if not rejected:
        return

    reasons = defaultdict(int)
    for r in rejected:
        reasons[r.get("reason", "unknown")] += 1

    print("\n" + "=" * 50)
    print(f"REJECTED SIGNALS ({len(rejected)} total)")
    print("=" * 50)
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:>30}: {count}")


def export_csv(trades: list, path: str):
    if not trades:
        print("No trades to export.")
        return
    keys = set()
    for t in trades:
        keys.update(t.keys())
    keys = sorted(keys)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for t in trades:
            writer.writerow({k: t.get(k, "") for k in keys})
    print(f"Exported {len(trades)} trades to {path}")


def main():
    parser = argparse.ArgumentParser(description="Trading performance analytics")
    parser.add_argument("--mode", default="paper", choices=["paper", "live"])
    parser.add_argument("--csv", metavar="FILE", help="Export trades to CSV")
    args = parser.parse_args()

    init_db()
    trades = load_trades(args.mode)
    rejected = load_rejected(args.mode)

    if args.csv:
        export_csv(trades, args.csv)
        return

    print(f"\nAnalyzing {args.mode} trades ({len(trades)} closed, {len(rejected)} rejected)\n")

    print_overall(trades)
    print_by_score_bucket(trades)
    print_by_sector(trades)
    print_by_exit_reason(trades)
    print_by_time_of_day(trades)
    print_hold_time_analysis(trades)
    print_score_correlation(trades)
    print_rejection_stats(rejected)
    print()


if __name__ == "__main__":
    main()

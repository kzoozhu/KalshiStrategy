import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# --- Config ---
CSV_PATH = r"/Users/kevinzhu/PycharmProjects/KalshiProject/Data/BTC5min.csv"
EMA_PERIOD = 50
RSI_PERIOD = 14
STRIKE_OFFSET = 250.0
HOUR_LOCK = True

# --- RSI helper ---
def compute_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- Load & prep ---
df = pd.read_csv(CSV_PATH)
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)
df = df.dropna(subset=['open','high','low','close']).reset_index(drop=True)
df['hour'] = df['time'].dt.floor('h')

# --- Indicators ---
df['EMA'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
df['RSI'] = compute_rsi(df['close'], window=RSI_PERIOD)

results = []
in_trade = False
current_trade_end = None

for i in range(1, len(df)):
    time = df.at[i, 'time']
    hour = df.at[i, 'hour']
    close = df.at[i, 'close']
    ema = df.at[i, 'EMA']
    rsi_now = df.at[i, 'RSI']
    rsi_prev = df.at[i-1, 'RSI']

    # unlock hourly trade restriction
    if HOUR_LOCK and in_trade and time >= current_trade_end:
        in_trade = False
        current_trade_end = None
    if HOUR_LOCK and in_trade:
        continue

    # --- Long setup (uptrend + RSI rebound) ---
    if close > ema and rsi_prev < 45 and rsi_now >= 50:
        strike = close - STRIKE_OFFSET
        direction = 'long'
        hour_group = df[df['hour'] == hour]
        final_close = hour_group.iloc[-1]['close']
        loss = final_close < strike
        results.append({
            'signal_time': time,
            'signal_hour': hour,
            'direction': direction,
            'signal_close': close,
            'strike': strike,
            'final_close': final_close,
            'RSI': rsi_now,
            'outcome': 'loss' if loss else 'win'
        })
        if HOUR_LOCK:
            in_trade = True
            current_trade_end = hour + pd.Timedelta(hours=1)
        continue

    # --- Short setup (downtrend + RSI rejection) ---
    if close < ema and rsi_prev > 55 and rsi_now <= 50:
        strike = close + STRIKE_OFFSET
        direction = 'short'
        hour_group = df[df['hour'] == hour]
        final_close = hour_group.iloc[-1]['close']
        loss = final_close > strike
        results.append({
            'signal_time': time,
            'signal_hour': hour,
            'direction': direction,
            'signal_close': close,
            'strike': strike,
            'final_close': final_close,
            'RSI': rsi_now,
            'outcome': 'loss' if loss else 'win'
        })
        if HOUR_LOCK:
            in_trade = True
            current_trade_end = hour + pd.Timedelta(hours=1)

# --- Results summary ---
if not results:
    print("\n⚠️ No signals found. Try smaller RSI thresholds (e.g., 48/52).")
else:
    summary = pd.DataFrame(results)
    out_path = os.path.join(os.path.dirname(CSV_PATH), "BTC5min_TrendPullback.csv")
    summary.to_csv(out_path, index=False)

    total = len(summary)
    wins = (summary['outcome'] == 'win').sum()
    losses = (summary['outcome'] == 'loss').sum()
    win_rate = (wins / total * 100) if total > 0 else 0

    print(f"\n✅ Results saved to {out_path}")
    print(f"Total trades: {total} | Wins: {wins} | Losses: {losses} | Win rate: {win_rate:.2f}%")

    print("\n--- Performance by Direction ---")
    print(summary.groupby(['direction', 'outcome']).size().unstack(fill_value=0))

    # --- Plot ---
    plt.figure(figsize=(14,7))
    plt.plot(df['time'], df['close'], color='black', linewidth=1, label='Close')
    plt.plot(df['time'], df['EMA'], color='orange', linewidth=1.5, label=f'EMA({EMA_PERIOD})')

    longs = summary[summary['direction'] == 'long']
    shorts = summary[summary['direction'] == 'short']
    plt.scatter(longs['signal_time'], longs['signal_close'], color='lime', marker='^', s=80, label='Long Signal')
    plt.scatter(shorts['signal_time'], shorts['signal_close'], color='red', marker='v', s=80, label='Short Signal')

    plt.title("Trend Pullback Reentry Strategy (RSI + EMA)")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

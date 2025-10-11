import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# --- Config ---
CSV_PATH = r"/Users/kevinzhu/PycharmProjects/KalshiProject/Data/BTC5min.csv"
EMA_SHORT = 50
EMA_LONG = 200
BOLL_WINDOW = 20
STRIKE_OFFSET = 250.0
HOUR_LOCK = True

# --- Load & prepare ---
df = pd.read_csv(CSV_PATH)
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)
df = df.dropna(subset=['open','high','low','close']).reset_index(drop=True)
df['hour'] = df['time'].dt.floor('h')

# --- Indicators ---
df['EMA50'] = df['close'].ewm(span=EMA_SHORT, adjust=False).mean()
df['EMA200'] = df['close'].ewm(span=EMA_LONG, adjust=False).mean()

# Bollinger Bands
df['mbb'] = df['close'].rolling(BOLL_WINDOW).mean()
df['std'] = df['close'].rolling(BOLL_WINDOW).std()
df['upper_bb'] = df['mbb'] + 2 * df['std']
df['lower_bb'] = df['mbb'] - 2 * df['std']
df['bb_width'] = (df['upper_bb'] - df['lower_bb']) / df['mbb']

# Rolling squeeze threshold
df['squeeze'] = df['bb_width'] < df['bb_width'].rolling(50).mean() * 0.75  # tightness condition

results = []
in_trade = False
current_trade_end = None

for i in range(max(EMA_LONG, BOLL_WINDOW+1), len(df)):
    time = df.at[i, 'time']
    hour = df.at[i, 'hour']
    close = df.at[i, 'close']
    open_ = df.at[i, 'open']
    ema50 = df.at[i, 'EMA50']
    ema200 = df.at[i, 'EMA200']
    squeeze = df.at[i, 'squeeze']
    bb_upper = df.at[i, 'upper_bb']
    bb_lower = df.at[i, 'lower_bb']

    # unlock hourly restriction
    if HOUR_LOCK and in_trade and time >= current_trade_end:
        in_trade = False
        current_trade_end = None
    if HOUR_LOCK and in_trade:
        continue

    # --- Long breakout: Uptrend + Squeeze + close > upper band ---
    if ema50 > ema200 and squeeze and close > bb_upper and close > open_:
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
            'outcome': 'loss' if loss else 'win'
        })
        in_trade = True
        current_trade_end = hour + pd.Timedelta(hours=1)
        continue

    # --- Short breakout: Downtrend + Squeeze + close < lower band ---
    if ema50 < ema200 and squeeze and close < bb_lower and close < open_:
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
            'outcome': 'loss' if loss else 'win'
        })
        in_trade = True
        current_trade_end = hour + pd.Timedelta(hours=1)
        continue

# --- Summary ---
if not results:
    print("\n⚠️ No squeeze breakouts detected. Try lowering the squeeze threshold (e.g., *0.9).")
else:
    summary = pd.DataFrame(results)
    out_path = os.path.join(os.path.dirname(CSV_PATH), "BTC5min_TrendSqueezeBreakout.csv")
    summary.to_csv(out_path, index=False)

    total = len(summary)
    wins = (summary['outcome'] == 'win').sum()
    losses = (summary['outcome'] == 'loss').sum()
    win_rate = (wins / total * 100)
    print(f"\n✅ Results saved to {out_path}")
    print(f"Total trades: {total} | Wins: {wins} | Losses: {losses} | Win rate: {win_rate:.2f}%")

    print("\n--- Performance by Direction ---")
    print(summary.groupby(['direction', 'outcome']).size().unstack(fill_value=0))

    # --- Plot ---
    plt.figure(figsize=(14,7))
    plt.plot(df['time'], df['close'], color='black', linewidth=1, label='Close')
    plt.plot(df['time'], df['EMA50'], color='orange', linewidth=1.2, label='EMA(50)')
    plt.plot(df['time'], df['EMA200'], color='blue', linewidth=1.2, label='EMA(200)')
    plt.fill_between(df['time'], df['lower_bb'], df['upper_bb'], color='gray', alpha=0.1, label='Bollinger Bands')

    longs = summary[summary['direction'] == 'long']
    shorts = summary[summary['direction'] == 'short']
    plt.scatter(longs['signal_time'], longs['signal_close'], color='lime', marker='^', s=80, label='Long Signal')
    plt.scatter(shorts['signal_time'], shorts['signal_close'], color='red', marker='v', s=80, label='Short Signal')

    plt.title("Trend Squeeze Pullback Breakout Strategy")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ======================
# Config
# ======================
CSV_PATH = r"/Users/kevinzhu/PycharmProjects/KalshiProject/Data/BTC5min.csv"
PERIOD = 10
MULTIPLIER = 3.0
STRIKE_OFFSET = 500.0
HOUR_LOCK = True

# ======================
# SuperTrend Calculation
# ======================
def compute_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_supertrend(df, period=10, multiplier=3):
    df = df.copy()
    hl2 = (df['high'] + df['low']) / 2
    atr = compute_atr(df, period)
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    supertrend = [np.nan] * len(df)
    trend = [1] * len(df)

    for i in range(period, len(df)):
        if df['close'].iloc[i] > upperband.iloc[i - 1]:
            trend[i] = 1
        elif df['close'].iloc[i] < lowerband.iloc[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

        if trend[i] == 1:
            supertrend[i] = lowerband.iloc[i]
        else:
            supertrend[i] = upperband.iloc[i]

    df['SuperTrend'] = supertrend
    df['Trend'] = trend
    return df

# ======================
# Load Data
# ======================
df = pd.read_csv(CSV_PATH)
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)
df['hour'] = df['time'].dt.floor('h')
df = compute_supertrend(df, period=PERIOD, multiplier=MULTIPLIER)

# ======================
# Strategy Logic
# ======================
results = []
in_trade = False
current_trade_end = None

for i in range(1, len(df)):
    time = df.at[i, 'time']
    hour = df.at[i, 'hour']
    close = df.at[i, 'close']
    trend_now = df.at[i, 'Trend']
    trend_prev = df.at[i-1, 'Trend']

    # unlock trade restriction once new hour starts
    if HOUR_LOCK and in_trade and time >= current_trade_end:
        in_trade = False
        current_trade_end = None

    if HOUR_LOCK and in_trade:
        continue

    # --- Long setup: trend flips upward ---
    if trend_prev == -1 and trend_now == 1:
        strike = close - STRIKE_OFFSET
        direction = 'long'
        hour_group = df[df['hour'] == hour]
        if not hour_group.empty:
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
            if HOUR_LOCK:
                in_trade = True
                current_trade_end = hour + pd.Timedelta(hours=1)
        continue

    # --- Short setup: trend flips downward ---
    if trend_prev == 1 and trend_now == -1:
        strike = close + STRIKE_OFFSET
        direction = 'short'
        hour_group = df[df['hour'] == hour]
        if not hour_group.empty:
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
            if HOUR_LOCK:
                in_trade = True
                current_trade_end = hour + pd.Timedelta(hours=1)
        continue

# ======================
# Summary
# ======================
if not results:
    print("\n⚠️ No SuperTrend flips detected — try smaller period or multiplier.")
else:
    summary = pd.DataFrame(results)
    out_path = os.path.join(os.path.dirname(CSV_PATH), "BTC5min_SuperTrend_Strategy.csv")
    summary.to_csv(out_path, index=False)

    total = len(summary)
    wins = (summary['outcome'] == 'win').sum()
    losses = (summary['outcome'] == 'loss').sum()
    win_rate = wins / total * 100 if total > 0 else 0

    print(f"\n✅ Results saved to {out_path}")
    print(f"Total trades: {total}, Wins: {wins}, Losses: {losses}, Win rate: {win_rate:.2f}%")
    print("\n--- Performance by Direction ---")
    print(summary.groupby(['direction', 'outcome']).size().unstack(fill_value=0))

    unique_hours = summary['signal_hour'].nunique()
    print(f"\nUnique trading hours with signals: {unique_hours}")
    print(f"Total signals: {total}")

    # ======================
    # Plot
    # ======================
    plt.figure(figsize=(14, 7))
    plt.plot(df['time'], df['close'], color='black', linewidth=1, label='Close')
    plt.plot(df['time'], df['SuperTrend'], color='orange', linewidth=1.5, label='SuperTrend')

    longs = summary[summary['direction'] == 'long']
    shorts = summary[summary['direction'] == 'short']
    plt.scatter(longs['signal_time'], longs['signal_close'], color='lime', marker='^', s=80, label='Long Signal')
    plt.scatter(shorts['signal_time'], shorts['signal_close'], color='red', marker='v', s=80, label='Short Signal')

    plt.title("SuperTrend Momentum Ride Strategy")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

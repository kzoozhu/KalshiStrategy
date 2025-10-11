import pandas as pd
import os

# --- File path ---
csv_path = r"C:\Users\kevin\PycharmProjects\KalshiProject\Data\BTC5min.csv"

# --- Load & prepare data ---
df = pd.read_csv(csv_path)
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time').reset_index(drop=True)
df['hour'] = df['time'].dt.floor('h')

results = []
prev_state = None
in_trade = False
current_trade_end = None

for i in range(len(df)):
    row = df.iloc[i]
    time = row['time']
    k, d = row['K'], row['D']

    # --- skip missing values ---
    if pd.isna(k) or pd.isna(d):
        continue

    # --- exit trade lock once the next hour begins ---
    if in_trade and time >= current_trade_end:
        in_trade = False
        current_trade_end = None

    # --- if still in trade, skip ---
    if in_trade:
        continue

    # --- determine state ---
    if k > d:
        curr_state = 'k_over_d'
    elif k < d:
        curr_state = 'd_over_k'
    else:
        curr_state = prev_state

    signal_time = time
    signal_hour = row['hour']
    signal_close = row['close']

    # --- Long setup (K crosses above D and K < 20) ---
    if prev_state == 'd_over_k' and curr_state == 'k_over_d' and k < 20:
        strike = signal_close - 250
        direction = 'long'
        hour_group = df[df['hour'] == signal_hour]

        if not hour_group.empty:
            final_close = hour_group.iloc[-1]['close']
            final_close_time = hour_group.iloc[-1]['time']
            loss = final_close < strike
            results.append({
                'signal_time': signal_time,
                'signal_hour': signal_hour,
                'direction': direction,
                'signal_close': signal_close,
                'strike': strike,
                'final_close_time': final_close_time,
                'final_close': final_close,
                'outcome': 'loss' if loss else 'win'
            })

            # ✅ lock until next hour begins
            in_trade = True
            current_trade_end = signal_hour + pd.Timedelta(hours=1)

    # --- Short setup (K crosses below D and K > 80) ---
    if prev_state == 'k_over_d' and curr_state == 'd_over_k' and k > 80:
        strike = signal_close + 250
        direction = 'short'
        hour_group = df[df['hour'] == signal_hour]

        if not hour_group.empty:
            final_close = hour_group.iloc[-1]['close']
            final_close_time = hour_group.iloc[-1]['time']
            loss = final_close > strike
            results.append({
                'signal_time': signal_time,
                'signal_hour': signal_hour,
                'direction': direction,
                'signal_close': signal_close,
                'strike': strike,
                'final_close_time': final_close_time,
                'final_close': final_close,
                'outcome': 'loss' if loss else 'win'
            })

            # ✅ lock until next hour begins
            in_trade = True
            current_trade_end = signal_hour + pd.Timedelta(hours=1)

    prev_state = curr_state


# --- Results summary ---
if not results:
    print("\n⚠️ No full K/D reversals found. Try with more data.")
else:
    summary = pd.DataFrame(results)

    # ✅ Save in same folder as input file
    output_path = os.path.join(
        os.path.dirname(csv_path),
        "BTC5min_KD_full_strategy.csv"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    summary.to_csv(output_path, index=False)

    print("\n✅ Strategy results saved to:")
    print(output_path)
    print("\n--- Signals & Outcomes ---")
    print(summary)

    total = len(summary)
    wins = (summary['outcome'] == 'win').sum()
    losses = (summary['outcome'] == 'loss').sum()
    win_rate = (wins / total * 100) if total > 0 else 0

    print("\n--- Overall Performance ---")
    print(f"Total signals: {total}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win rate: {win_rate:.2f}%")

    print("\n--- Performance by Direction ---")
    print(summary.groupby(['direction', 'outcome']).size().unstack(fill_value=0))

    # ✅ Sanity check — ensure one trade per hour
    unique_hours = summary['signal_hour'].nunique()
    print(f"\nUnique trading hours with signals: {unique_hours}")
    print(f"Total signals: {total}")

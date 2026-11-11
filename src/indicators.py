"""Pure-Python technical indicators; no third-party numerical dependency."""
from __future__ import annotations

def sma(values: list[float], period: int) -> float | None:
    if len(values) < period: return None
    return sum(values[-period:]) / period

def ema_series(values: list[float], period: int) -> list[float]:
    if not values: return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]: result.append(alpha * value + (1 - alpha) * result[-1])
    return result

def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period: return None
    gains, losses = [], []
    for previous, current in zip(values[:-1], values[1:]):
        delta = current - previous
        gains.append(max(delta, 0.0)); losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period; avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0: return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    if len(values) < slow + signal: return {"macd": None, "signal": None, "histogram": None}
    fast_line, slow_line = ema_series(values, fast), ema_series(values, slow)
    line = [a - b for a, b in zip(fast_line, slow_line)]
    signal_line = ema_series(line, signal)
    return {"macd": line[-1], "signal": signal_line[-1], "histogram": line[-1] - signal_line[-1]}

def stochastic_kd(highs: list[float], lows: list[float], closes: list[float], period: int = 9) -> dict:
    if len(closes) < period: return {"k": None, "d": None}
    ks = []
    for end in range(period, len(closes) + 1):
        hh, ll = max(highs[end-period:end]), min(lows[end-period:end])
        ks.append(50.0 if hh == ll else (closes[end-1] - ll) / (hh - ll) * 100)
    previous_k = previous_d = 50.0
    for raw_k in ks:
        current_k = (2 * previous_k + raw_k) / 3
        current_d = (2 * previous_d + current_k) / 3
        previous_k, previous_d = current_k, current_d
    return {"k": previous_k, "d": previous_d}

def calculate(history: list[dict]) -> dict:
    rows = sorted(history, key=lambda row: row["date"])
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    highs = [float(row.get("high") or row["close"]) for row in rows]
    lows = [float(row.get("low") or row["close"]) for row in rows]
    volumes = [float(row.get("volume") or 0) for row in rows]
    m, kd = macd(closes), stochastic_kd(highs, lows, closes)
    return {"ma5": sma(closes, 5), "ma20": sma(closes, 20), "ma60": sma(closes, 60),
            "rsi14": rsi(closes, 14), **m, "k": kd["k"], "d": kd["d"],
            "volume_ma5": sma(volumes, 5), "volume_ma20": sma(volumes, 20), "history_days": len(closes)}

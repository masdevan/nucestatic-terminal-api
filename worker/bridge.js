export async function fetchCandles(bridgeUrl, symbol, timeframe, limit) {
  const base = bridgeUrl.replace(/\/+$/, '')
  const before = Math.floor(Date.now() / 1000)
  const url = `${base}/api/ohlc/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}&before=${before}`
  const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
  if (!res.ok) throw new Error(`Bridge responded HTTP ${res.status}`)
  const data = await res.json()
  const rows = Array.isArray(data?.data) ? data.data : []
  return rows
    .filter((candle) => candle && typeof candle.time === 'string' && Number.isFinite(candle.close))
    .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
}

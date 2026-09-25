import { createHmac } from 'node:crypto'

const API_BASE_URL = (process.env.API_BASE_URL || 'http://localhost:8311').replace(/\/+$/, '')
const JWT_SECRET = process.env.JWT_SECRET || ''
const ALARM_TIMEOUT_MS = 8000

function signToken(userId) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')
  const payload = Buffer.from(
    JSON.stringify({ sub: String(userId), exp: Math.floor(Date.now() / 1000) + 300 })
  ).toString('base64url')
  const data = `${header}.${payload}`
  const signature = createHmac('sha256', JWT_SECRET).update(data).digest('base64url')
  return `${data}.${signature}`
}

export function normalizeAlarms(rawAlarms, symbol) {
  if (!Array.isArray(rawAlarms)) return []
  const alarms = []
  for (const raw of rawAlarms) {
    if (!raw || typeof raw !== 'object') continue
    const type = typeof raw.type === 'string' ? raw.type.toLowerCase() : ''
    if (type !== 'buy' && type !== 'sell') continue
    const entry = Number(raw.entry)
    if (!Number.isFinite(entry) || entry <= 0) continue
    const tp = Number(raw.tp)
    const sl = Number(raw.sl)
    const customSymbol = typeof raw.symbol === 'string' ? raw.symbol.trim() : ''
    const timeframe = typeof raw.timeframe === 'string' ? raw.timeframe.trim().toUpperCase() : ''
    const description =
      typeof raw.description === 'string' ? raw.description.trim().slice(0, 500) : ''
    const webhook = typeof raw.webhook === 'string' ? raw.webhook.trim() : ''
    alarms.push({
      symbol: customSymbol || symbol,
      entry_type: type,
      entry_price: entry,
      tp_price: Number.isFinite(tp) && tp > 0 ? tp : null,
      sl_price: Number.isFinite(sl) && sl > 0 ? sl : null,
      timeframe: timeframe || null,
      description: description || null,
      webhook: webhook || null
    })
  }
  return alarms
}

export async function sendAlarms(job, alarms) {
  const token = signToken(job.user_id)
  let sent = 0
  for (const alarm of alarms) {
    const payload = {
      symbol: alarm.symbol,
      description: alarm.description,
      entry_type: alarm.entry_type,
      entry_price: alarm.entry_price,
      tp_price: alarm.tp_price,
      sl_price: alarm.sl_price,
      timeframe: alarm.timeframe || job.timeframe,
      webhook: job.webhook_url || alarm.webhook,
      backtest: false
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/alarms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(ALARM_TIMEOUT_MS)
      })
      if (res.ok) sent += 1
      else console.error(`[cron] alarm rejected: HTTP ${res.status}`)
    } catch (err) {
      console.error(`[cron] alarm failed: ${err.message}`)
    }
  }
  return sent
}

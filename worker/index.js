import mysql from 'mysql2/promise'
import { fetchCandles } from './bridge.js'
import { runIndicator } from './indicator.js'
import { normalizeAlarms, sendAlarms } from './alarms.js'

const POLL_MS = 5000
const CANDLE_LIMIT = 1000

const pool = mysql.createPool({
  host: process.env.MYSQL_HOST || 'localhost',
  port: Number(process.env.MYSQL_PORT || 3306),
  user: process.env.MYSQL_USER || 'root',
  password: process.env.MYSQL_PASSWORD || '',
  database: process.env.MYSQL_DATABASE || 'nucestatic_terminal',
  connectionLimit: 5,
  waitForConnections: true
})

async function dueJobs() {
  const [rows] = await pool.query(`
    SELECT cj.id, cj.user_id, cj.indicator_id, i.name AS indicator_name, cj.symbol, cj.timeframe,
           cj.webhook_url, cj.params_json, cj.last_candle_time,
           b.url AS bridge_url
      FROM cron_jobs cj
      JOIN bridge_apis b ON b.id = cj.bridge_id
      JOIN indicators i ON i.id = cj.indicator_id
     WHERE cj.enabled = 1 AND b.active = 1 AND b.mode = 'dynamic'
       AND (cj.last_run_at IS NULL OR TIMESTAMPDIFF(SECOND, cj.last_run_at, NOW()) >= cj.interval_seconds)
     ORDER BY cj.id
  `)
  return rows
}

async function markRun(ids) {
  if (ids.length === 0) return
  await pool.query('UPDATE cron_jobs SET last_run_at = NOW() WHERE id IN (?)', [ids])
}

async function activeBridgeModes() {
  const [rows] = await pool.query('SELECT url, mode FROM bridge_apis WHERE active = 1')
  const modes = new Map()
  for (const row of rows) {
    modes.set(String(row.url).trim().replace(/\/+$/, ''), row.mode)
  }
  return modes
}

async function indicatorFiles(indicatorId) {
  const [rows] = await pool.query(
    'SELECT path, content FROM indicator_files WHERE indicator_id = ? ORDER BY path',
    [indicatorId]
  )
  return rows.map((row) => ({ path: row.path, content: row.content }))
}

async function indicatorValues(userId, indicatorId) {
  const [rows] = await pool.query(
    'SELECT values_json FROM indicator_settings WHERE user_id = ? AND indicator_key = ?',
    [userId, `custom:${indicatorId}`]
  )
  if (rows.length === 0) return {}
  try {
    const parsed = JSON.parse(rows[0].values_json)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function jobValues(row) {
  if (!row.params_json) return {}
  try {
    const parsed = JSON.parse(row.params_json)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function errorText(err) {
  const message = err instanceof Error ? err.message : 'Unknown error'
  return message.slice(0, 255)
}

async function setError(id, message) {
  await pool.query('UPDATE cron_jobs SET last_error = ? WHERE id = ?', [message, id])
}

async function recordAlert(id, candleTime) {
  await pool.query(
    'UPDATE cron_jobs SET last_alert_at = NOW(), last_candle_time = ?, last_error = NULL WHERE id = ?',
    [candleTime, id]
  )
}

const KEEP_RUNS = 100

async function recordRun(job, result, durationMs, error = null) {
  await pool.query(
    `INSERT INTO cron_job_runs (job_id, user_id, status, candle_time, alarms, duration_ms, error)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [job.id, job.user_id, result.status, result.candleTime, result.alarms, durationMs, error]
  )
  await pool.query(
    `DELETE FROM cron_job_runs
      WHERE job_id = ? AND id NOT IN (
        SELECT id FROM (
          SELECT id FROM cron_job_runs WHERE job_id = ? ORDER BY id DESC LIMIT ${KEEP_RUNS}
        ) AS keep
      )`,
    [job.id, job.id]
  )
}

async function runJob(row, candles, bridgeModes) {
  const latest = candles[candles.length - 1].time
  if (row.last_candle_time && latest <= row.last_candle_time) {
    return { status: 'skip', candleTime: latest, alarms: 0 }
  }
  const files = await indicatorFiles(row.indicator_id)
  const settings = await indicatorValues(row.user_id, row.indicator_id)
  const values = { ...settings, ...jobValues(row) }
  const { alarms } = await runIndicator(files, candles, values, row.bridge_url, bridgeModes)
  const normalized = normalizeAlarms(alarms, row.symbol)
  if (normalized.length === 0) {
    await setError(row.id, null)
    return { status: 'ok', candleTime: latest, alarms: 0 }
  }
  const sent = await sendAlarms(row, normalized)
  if (sent > 0) await recordAlert(row.id, latest)
  return { status: 'ok', candleTime: latest, alarms: sent }
}

async function runCycle() {
  const jobs = await dueJobs()
  if (jobs.length === 0) return
  await markRun(jobs.map((job) => job.id))
  const bridgeModes = await activeBridgeModes()
  const candleCache = new Map()
  for (const job of jobs) {
    const startedAt = Date.now()
    try {
      const key = `${job.bridge_url}|${job.symbol}|${job.timeframe}`
      let candles = candleCache.get(key)
      if (!candles) {
        candles = await fetchCandles(job.bridge_url, job.symbol, job.timeframe, CANDLE_LIMIT)
        candleCache.set(key, candles)
      }
      if (candles.length === 0) throw new Error('No candles returned by bridge')
      const result = await runJob(job, candles, bridgeModes)
      await recordRun(job, result, Date.now() - startedAt).catch(() => undefined)
    } catch (err) {
      console.error(`[cron] job ${job.id} failed: ${err.message}`)
      await setError(job.id, errorText(err)).catch(() => undefined)
      await recordRun(
        job,
        { status: 'error', candleTime: null, alarms: 0 },
        Date.now() - startedAt,
        errorText(err)
      ).catch(() => undefined)
    }
  }
}

let running = false

async function tick() {
  if (running) return
  running = true
  try {
    await runCycle()
  } catch (err) {
    console.error(`[cron] cycle failed: ${err.message}`)
  } finally {
    running = false
  }
}

console.log('[cron] worker started')
void tick()
const timer = setInterval(() => void tick(), POLL_MS)

async function shutdown() {
  clearInterval(timer)
  await pool.end()
  process.exit(0)
}

process.on('SIGTERM', () => void shutdown())
process.on('SIGINT', () => void shutdown())

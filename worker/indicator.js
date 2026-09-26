import vm from 'node:vm'
import { createHash } from 'node:crypto'

const COMPUTE_TIMEOUT_MS = 15000
const HTTP_TIMEOUT_MS = 8000
const HTTP_CACHE_TTL_MS = 60000
const moduleCache = new Map()
const httpCache = new Map()

async function requestJson(url, options = {}) {
  const method = options.method || 'GET'
  const key = JSON.stringify([method, url, options.headers ?? {}, options.body ?? null])
  const cached = httpCache.get(key)
  if (cached && Date.now() - cached.fetchedAt < HTTP_CACHE_TTL_MS) return cached.data
  const headers = { ...(options.headers ?? {}) }
  let body
  if (options.body !== undefined) {
    body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
    if (!Object.keys(headers).some((name) => name.toLowerCase() === 'content-type')) {
      headers['Content-Type'] = 'application/json'
    }
  }
  const res = await fetch(url, {
    method,
    headers,
    body,
    signal: AbortSignal.timeout(options.timeoutMs ?? HTTP_TIMEOUT_MS)
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  httpCache.set(key, { fetchedAt: Date.now(), data })
  return data
}

const http = {
  get: (url, options) => requestJson(url, { ...options, method: 'GET' }),
  post: (url, body, options) => requestJson(url, { ...options, method: 'POST', body }),
  json: (url, options) => requestJson(url, options)
}

const draw = new Proxy({}, { get: () => () => null })

const TF_MS = {
  M1: 60000,
  M5: 300000,
  M15: 900000,
  M30: 1800000,
  H1: 3600000,
  H4: 14400000,
  D1: 86400000,
  W1: 604800000,
  MN1: 2592000000
}
const MARKET_CACHE_TTL_MS = 60000
const marketCache = new Map()

function normalizeUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '')
}

function parseTime(value) {
  if (typeof value !== 'string' || value.trim() === '') return null
  const ms = Date.parse(value.replace(' ', 'T') + 'Z')
  return Number.isFinite(ms) ? ms : null
}

async function fetchMarketCandles(target, symbol, timeframe, limit) {
  const key = `${target}|${symbol}|${timeframe}|${limit}`
  const hit = marketCache.get(key)
  if (hit && Date.now() - hit.fetchedAt < MARKET_CACHE_TTL_MS) return hit.candles
  const before = Math.floor(Date.now() / 1000)
  const url = `${target}/api/ohlc/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}&before=${before}`
  const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
  if (!res.ok) throw new Error(`Bridge responded HTTP ${res.status}`)
  const data = await res.json()
  const rows = Array.isArray(data?.data) ? data.data : []
  const candles = rows
    .filter((candle) => candle && typeof candle.time === 'string' && Number.isFinite(candle.close))
    .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
  marketCache.set(key, { fetchedAt: Date.now(), candles })
  return candles
}

function createMarketRequest(bridgeUrl, lastTime, bridgeModes) {
  const ohlc = async (symbol, timeframe, options = {}) => {
    const name = String(symbol || '').trim()
    const frame = String(timeframe || '').trim().toUpperCase()
    if (!name || !frame) throw new Error('request.ohlc requires symbol and timeframe')
    const limit = Math.max(1, Math.min(5000, Math.round(options.limit ?? 1000)))
    const target = normalizeUrl(options.bridgeUrl ?? bridgeUrl)
    if (!target) throw new Error('No bridge available for request.ohlc')
    const mode = bridgeModes?.get(target) ?? ''
    const candles = await fetchMarketCandles(target, name, frame, limit)
    const lastMs = parseTime(lastTime)
    if (lastMs == null) return candles
    if (mode === 'dynamic') {
      return candles.filter((candle) => {
        const ms = parseTime(candle.time)
        return ms != null && ms <= lastMs
      })
    }
    const spanMs = TF_MS[frame] ?? 60000
    return candles.filter((candle) => {
      const ms = parseTime(candle.time)
      return ms != null && ms + spanMs <= lastMs
    })
  }
  return { ohlc }
}

function resolvePath(fromPath, spec) {
  const parts = fromPath.split('/').slice(0, -1)
  for (const part of spec.split('/')) {
    if (part === '' || part === '.') continue
    if (part === '..') {
      if (parts.length === 0) return null
      parts.pop()
    } else {
      parts.push(part)
    }
  }
  return parts.join('/')
}

async function evaluateModule(files) {
  const context = vm.createContext({ http, console })
  const sources = new Map(files.map((file) => [file.path, file.content]))
  const modules = new Map()
  const load = async (path) => {
    const existing = modules.get(path)
    if (existing) return existing
    const source = sources.get(path)
    if (source == null) throw new Error(`Missing module ${path}`)
    const module = new vm.SourceTextModule(source, { identifier: path, context })
    modules.set(path, module)
    await module.link(async (specifier, referencing) => {
      const target = resolvePath(referencing.identifier, specifier)
      if (!target) throw new Error(`Cannot resolve ${specifier}`)
      return load(target)
    })
    return module
  }
  const entry = await load('index.js')
  await entry.evaluate()
  return entry.namespace.default
}

async function loadIndicator(files) {
  const key = createHash('sha256')
    .update(JSON.stringify(files.map((file) => [file.path, file.content])))
    .digest('hex')
  const cached = moduleCache.get(key)
  if (cached) return cached
  const def = await evaluateModule(files)
  moduleCache.set(key, def)
  return def
}

function buildParams(def, values) {
  const params = {}
  if (def && def.defaults && typeof def.defaults === 'object') {
    Object.assign(params, def.defaults)
  }
  const inputs = Array.isArray(def?.inputs) ? def.inputs : []
  for (const input of inputs) {
    if (!input || input.type === 'label') continue
    if (input.default !== undefined) params[input.key] = input.default
  }
  for (const [key, value] of Object.entries(values ?? {})) {
    if (key === '__colors') continue
    params[key] = value
  }
  return params
}

export async function runIndicator(files, candles, values, bridgeUrl, bridgeModes) {
  const def = await loadIndicator(files)
  if (!def || typeof def.compute !== 'function') return { alarms: [] }
  const params = buildParams(def, values)
  const request = createMarketRequest(
    bridgeUrl,
    candles.length > 0 ? candles[candles.length - 1].time : '',
    bridgeModes
  )
  const output = await Promise.race([
    Promise.resolve(def.compute(candles, params, http, draw, undefined, request)),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('indicator timed out')), COMPUTE_TIMEOUT_MS)
    )
  ])
  if (!output || Array.isArray(output)) return { alarms: [] }
  return { alarms: Array.isArray(output.alarms) ? output.alarms : [] }
}

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

export async function runIndicator(files, candles, values) {
  const def = await loadIndicator(files)
  if (!def || typeof def.compute !== 'function') return { alarms: [] }
  const params = buildParams(def, values)
  const output = await Promise.race([
    Promise.resolve(def.compute(candles, params, http, draw)),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('indicator timed out')), COMPUTE_TIMEOUT_MS)
    )
  ])
  if (!output || Array.isArray(output)) return { alarms: [] }
  return { alarms: Array.isArray(output.alarms) ? output.alarms : [] }
}

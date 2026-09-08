// Jedno místo pro veškerou komunikaci s API — CSRF hlavička, chyby, JSON i
// multipart. Komponenty nikdy nevolají `fetch` samy.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

export class ApiError extends Error {
  constructor(status, detail, fieldErrors) {
    super(detail || `Něco se nepovedlo (${status}).`)
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
  }

  static async fromResponse(res) {
    const contentType = res.headers.get('content-type') || ''
    let detail = null
    let fieldErrors = null

    // Nad 200 MB pošle nginx 413 s HTML tělem, ne JSON — o to se `res.json()`
    // rozbije. Tělo se parsuje jen když appka slíbí, že je to JSON.
    if (contentType.includes('application/json')) {
      try {
        const data = await res.json()
        if (typeof data.detail === 'string') {
          detail = data.detail
        } else if (data && typeof data === 'object') {
          fieldErrors = data
        }
      } catch {
        // tělo se přesto nepodařilo přečíst — spadneme na obecnou hlášku níž
      }
    }

    if (!detail && !fieldErrors) {
      if (res.status === 413) {
        detail = 'Soubor je příliš velký.'
      } else if (res.status === 404) {
        detail = 'Nenalezeno.'
      } else {
        detail = `Něco se nepovedlo (${res.status}).`
      }
    }

    return new ApiError(res.status, detail, fieldErrors)
  }
}

// Volá se AuthContextem, aby uměl rozlišit vypršelou session (přesměrovat na
// přihlášení) od běžného "na tohle nemáš právo" (ukázat chybu na místě).
let forbiddenHandler = null
export function registerForbiddenHandler(fn) {
  forbiddenHandler = fn
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export async function apiFetch(path, { method = 'GET', body, isFormData = false } = {}) {
  const headers = {}
  if (!isFormData && body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (!SAFE_METHODS.has(method)) {
    const csrftoken = getCookie('csrftoken')
    if (csrftoken) headers['X-CSRFToken'] = csrftoken
  }

  const res = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  })

  if (res.status === 403 && forbiddenHandler) {
    // DRF se SessionAuthentication vrací na "nepřihlášeno" 403, ne 401 —
    // handler ověří přes /api/auth/me/, jestli jde o vypršelou session, nebo
    // jen o zápis, na který uživatel nemá právo.
    await forbiddenHandler()
  }

  if (!res.ok) {
    throw await ApiError.fromResponse(res)
  }

  if (res.status === 204) return null

  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return res.json()
  return null
}

export const api = {
  get: (path) => apiFetch(path, { method: 'GET' }),
  post: (path, body, opts = {}) => apiFetch(path, { method: 'POST', body, ...opts }),
  patch: (path, body, opts = {}) => apiFetch(path, { method: 'PATCH', body, ...opts }),
  put: (path, body, opts = {}) => apiFetch(path, { method: 'PUT', body, ...opts }),
  del: (path) => apiFetch(path, { method: 'DELETE' }),
}

// Binární odpověď (PDF noty) — stejná CSRF/403/chybová logika jako apiFetch,
// ale bez pokusu o `res.json()`. Použito čtečkou, ne běžnými komponentami.
//
// Kešuje se v paměti podle cesty: přechod mezi běžnou čtečkou a stage mode
// pro tutéž verzi tak PDF nestahuje znovu. Neúspěch se nekešuje, ať jde
// znovu zkusit.
const blobCache = new Map()

export function fetchBlob(path) {
  const cached = blobCache.get(path)
  if (cached) return cached

  const promise = (async () => {
    const res = await fetch(path, { method: 'GET', credentials: 'same-origin' })

    if (res.status === 403 && forbiddenHandler) {
      await forbiddenHandler()
    }

    if (!res.ok) {
      throw await ApiError.fromResponse(res)
    }

    return res.blob()
  })()

  blobCache.set(path, promise)
  promise.catch(() => blobCache.delete(path))
  return promise
}

/**
 * Thin typed fetch wrapper. All calls are same-origin ('/api/...'); in dev
 * Vite proxies /api to http://localhost:8000.
 */

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ')
    }
    if (typeof data?.error === 'string') return data.error
    return res.statusText
  } catch {
    return res.statusText
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  // no-store: los datos del API deben ser siempre frescos y evita que una respuesta
  // HTML cacheada (p. ej. index.html servido durante un reinicio) envenene la caché.
  const res = await fetch(path, { cache: 'no-store' })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE' })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

export async function apiUpload<T>(path: string, files: File[]): Promise<T> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const res = await fetch(path, { method: 'POST', body: fd })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

/** POST multipart/form-data con campos arbitrarios (fichero + texto). */
export async function apiPostForm<T>(path: string, fields: Record<string, string | Blob>): Promise<T> {
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) fd.append(k, v)
  const res = await fetch(path, { method: 'POST', body: fd })
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  return res.json() as Promise<T>
}

/** Trigger a browser download of a binary endpoint (e.g. the PDF report). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(path)
  if (!res.ok) throw new ApiError(await parseError(res), res.status)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fallbackName
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

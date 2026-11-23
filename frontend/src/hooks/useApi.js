import { useEffect, useState } from 'react'

/** Fetches one dashboard endpoint. Dev server proxies /api -> the FastAPI backend. */
export function useApi(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(path)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `${res.status} ${res.statusText}`)
        }
        return res.json()
      })
      .then((json) => {
        if (!cancelled) setData(json)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [path])

  return { data, error, loading }
}

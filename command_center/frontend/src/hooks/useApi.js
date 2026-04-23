import { useState, useEffect, useCallback } from 'react'

export default function useApi(apiFn, deps = [], options = {}) {
  const { autoFetch = true, interval = null } = options
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Proteção: se o caller passar `null`/undefined, tratamos como "sem dependências".
  // Passar null direto em useCallback recria a função a cada render e dispara
  // loop infinito de fetches via o useEffect abaixo.
  const safeDeps = Array.isArray(deps) ? deps : []

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const result = await apiFn()
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, safeDeps)

  useEffect(() => {
    if (!autoFetch) {
      setLoading(false)
      return
    }
    fetchData()

    if (interval) {
      const id = setInterval(fetchData, interval)
      return () => clearInterval(id)
    }
  }, [fetchData, autoFetch, interval])

  return { data, loading, error, refetch: fetchData }
}

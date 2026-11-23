import { useEffect, useState } from 'react'

/**
 * Linking a real bank/card via SimpleFIN Bridge happens on SimpleFIN's own
 * hosted site (see the README), which hands you a one-time "setup token"
 * to paste here. This just claims that token — no widget/iframe needed like
 * Plaid Link, since the actual bank-login UI is entirely on SimpleFIN's end.
 */
export function SimpleFinLinkForm() {
  const [linked, setLinked] = useState(null) // null = unknown yet
  const [setupToken, setSetupToken] = useState('')
  const [status, setStatus] = useState('idle') // idle | claiming | error | done

  useEffect(() => {
    fetch('/api/simplefin/status')
      .then((res) => res.json())
      .then((json) => setLinked(json.linked))
      .catch(() => setLinked(false))
  }, [])

  if (linked) {
    return <p className="status">SimpleFIN account linked ✓</p>
  }

  const submit = (e) => {
    e.preventDefault()
    setStatus('claiming')
    fetch('/api/simplefin/claim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ setup_token: setupToken.trim() }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        setStatus('done')
        setLinked(true)
      })
      .catch(() => setStatus('error'))
  }

  return (
    <form className="simplefin-form" onSubmit={submit}>
      <input
        type="text"
        placeholder="Paste your SimpleFIN setup token"
        value={setupToken}
        onChange={(e) => setSetupToken(e.target.value)}
      />
      <button type="submit" disabled={!setupToken.trim() || status === 'claiming'}>
        {status === 'claiming' ? 'Linking…' : 'Link account'}
      </button>
      {status === 'error' && (
        <p className="status status-error">Couldn't claim that token — get a fresh one from your SimpleFIN bridge (each is single-use).</p>
      )}
    </form>
  )
}

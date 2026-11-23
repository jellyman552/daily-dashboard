import { useEffect, useState } from 'react'
import { Card } from './Card'

const currency = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

// en-CA happens to format as YYYY-MM-DD, and (crucially) in the browser's
// own local time - not UTC, which would shift the date near midnight. Same
// class of bug we already fixed on the backend (see app/localtime.py); a
// date input has to respect *your* today, not some other clock.
const todayISO = () => new Date().toLocaleDateString('en-CA')

export function ManualTransactionForm() {
  const [categories, setCategories] = useState([])
  const [recent, setRecent] = useState([])
  const [date, setDate] = useState(todayISO())
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('idle') // idle | scanning | submitting | error
  const [errorMsg, setErrorMsg] = useState('')

  const loadRecent = () => {
    fetch('/api/transactions/manual')
      .then((res) => res.json())
      .then(setRecent)
      .catch(() => {})
  }

  useEffect(() => {
    fetch('/api/spending/categories')
      .then((res) => res.json())
      .then(setCategories)
      .catch(() => {})
    loadRecent()
  }, [])

  const handleScan = async (e) => {
    const file = e.target.files[0]
    e.target.value = '' // allow re-selecting the same file later
    if (!file) return
    setStatus('scanning')
    setErrorMsg('')
    const body = new FormData()
    body.append('file', file)
    try {
      const res = await fetch('/api/transactions/receipt/parse', { method: 'POST', body })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `${res.status} ${res.statusText}`)
      }
      const parsed = await res.json()
      setDate(parsed.date)
      setAmount(String(parsed.amount))
      setDescription(parsed.merchant)
      setStatus('idle')
    } catch (err) {
      setErrorMsg(err.message)
      setStatus('error')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus('submitting')
    setErrorMsg('')
    try {
      const res = await fetch('/api/transactions/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, amount: parseFloat(amount), description, category: category || null }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `${res.status} ${res.statusText}`)
      }
      // The backend already recomputed every spending/budget snapshot by the
      // time this response comes back - reload so the other cards, which
      // each fetch independently, pick up the fresh numbers.
      window.location.reload()
    } catch (err) {
      setErrorMsg(err.message)
      setStatus('error')
    }
  }

  const handleDelete = async (id) => {
    await fetch(`/api/transactions/manual/${id}`, { method: 'DELETE' })
    window.location.reload()
  }

  return (
    <Card title="Add a Transaction">
      <form className="manual-txn-form" onSubmit={handleSubmit}>
        <div className="manual-txn-row">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          <input
            type="number"
            step="0.01"
            min="0"
            placeholder="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </div>
        <input
          type="text"
          placeholder="Description (e.g. Chipotle lunch)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Auto-detect category</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <div className="manual-txn-actions">
          <label className="scan-button">
            {status === 'scanning' ? 'Scanning…' : '📷 Scan receipt'}
            <input type="file" accept="image/*" capture="environment" onChange={handleScan} hidden />
          </label>
          <button type="submit" disabled={status === 'submitting' || status === 'scanning'}>
            {status === 'submitting' ? 'Adding…' : 'Add'}
          </button>
        </div>
        {status === 'error' && <p className="status status-error">{errorMsg}</p>}
      </form>

      {recent.length > 0 && (
        <ul className="breakdown manual-txn-recent">
          {recent.slice(0, 5).map((t) => (
            <li key={t.id}>
              <span>
                {t.date} · {t.description}
                {t.matched && <small className="muted"> (matched to bank)</small>}
              </span>
              <span>
                {currency(t.amount)}{' '}
                <button type="button" className="delete-link" onClick={() => handleDelete(t.id)} aria-label="Delete">
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

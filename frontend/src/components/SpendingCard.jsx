import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Card, CardStatus } from './Card'

const currency = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

const TABS = [
  { key: 'daily', label: 'Today' },
  { key: 'weekly', label: 'This Week' },
  { key: 'monthly', label: 'This Month' },
]

export function SpendingCard() {
  const [tab, setTab] = useState('weekly')
  const { data, error, loading } = useApi(`/api/spending/${tab}`)

  return (
    <Card title="Spending">
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={t.key === tab ? 'tab active' : 'tab'} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>
      <CardStatus loading={loading} error={error} />
      {data && (
        <>
          <p className="big-number">{currency(data.total)}</p>
          {data.by_category.length === 0 ? (
            <p className="muted">No spending yet</p>
          ) : (
            <ul className="breakdown">
              {data.by_category.map((c) => (
                <li key={c.category}>
                  <span>{c.category}</span>
                  <span>{currency(c.amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}

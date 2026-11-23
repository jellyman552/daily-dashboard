import { Card, CardStatus } from './Card'

const currency = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

function ChargeList({ charges }) {
  if (charges.length === 0) return <p className="muted">None detected yet</p>
  return (
    <ul className="breakdown">
      {charges.map((c) => (
        <li key={c.merchant}>
          <span>
            {c.merchant} <small>({c.frequency.toLowerCase()})</small>
          </span>
          <span>{currency(c.amount)}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Both cards share one fetch (see App.jsx) so switching tabs doesn't double
 * up network calls or show mismatched loading states. `kind` on each charge
 * comes from the backend's homegrown classifier (categorizer.classify_recurring_kind) -
 * "other" recurring charges (neither a subscription nor an obvious bill)
 * land in Bills, since that's the more general of the two buckets.
 */
export function SubscriptionsCard({ data, error, loading }) {
  return (
    <Card title="Subscriptions">
      <CardStatus loading={loading} error={error} />
      {data && <ChargeList charges={data.charges.filter((c) => c.kind === 'subscription')} />}
    </Card>
  )
}

export function BillsCard({ data, error, loading }) {
  return (
    <Card title="Bills">
      <CardStatus loading={loading} error={error} />
      {data && <ChargeList charges={data.charges.filter((c) => c.kind !== 'subscription')} />}
    </Card>
  )
}

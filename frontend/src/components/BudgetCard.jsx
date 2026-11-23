import { useApi } from '../hooks/useApi'
import { Card, CardStatus } from './Card'

const currency = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export function BudgetCard() {
  const { data, error, loading } = useApi('/api/spending/budget')

  return (
    <Card title="This Month">
      <CardStatus loading={loading} error={error} />
      {data && (
        <>
          <p className={`big-number budget-${data.status}`}>
            {currency(data.spent)} <small>spent</small>
          </p>
          <p className="muted">
            {currency(data.income)} earned so far
            {data.percent_used != null && ` · ${data.percent_used}% of income`}
          </p>
          {data.income > 0 && (
            <div className="meter">
              <div
                className={`meter-fill meter-${data.status}`}
                style={{ width: `${Math.min(data.percent_used, 100)}%` }}
              />
            </div>
          )}
          <p className={`status-line budget-${data.status}`}>
            {data.status === 'over'
              ? `${currency(-data.remaining)} over what you've made this month`
              : `${currency(data.remaining)} left before you'd be spending more than you've made`}
          </p>
        </>
      )}
    </Card>
  )
}

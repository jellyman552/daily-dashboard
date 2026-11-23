import { useApi } from '../hooks/useApi'
import { Card, CardStatus } from './Card'

const currency = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

function BudgetRow({ c }) {
  return (
    <div className="budget-row">
      <div className="budget-row-header">
        <span>{c.category}</span>
        <span className="muted">
          {currency(c.spent)} / {currency(c.budget)}
        </span>
      </div>
      <div className="meter">
        <div
          className={`meter-fill meter-${c.status}`}
          style={{ width: `${Math.min(c.percent_used, 100)}%` }}
        />
      </div>
      <p className={`budget-row-note budget-${c.status}`}>
        {c.status === 'over'
          ? `${currency(-c.remaining)} over budget`
          : c.safe_per_day != null
            ? `${currency(c.safe_per_day)}/day left to stay on budget`
            : `${currency(c.remaining)} left`}
      </p>
    </div>
  )
}

export function CategoryBudgetsCard() {
  const { data, error, loading } = useApi('/api/spending/budgets')

  return (
    <Card title="Budgets">
      <CardStatus loading={loading} error={error} />
      {data && data.categories.length === 0 && (
        <p className="muted">No budgets configured yet — add backend/data/budgets.json</p>
      )}
      {data && data.categories.map((c) => <BudgetRow key={c.category} c={c} />)}
    </Card>
  )
}

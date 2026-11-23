import './App.css'
import { BudgetCard } from './components/BudgetCard'
import { CalendarCard } from './components/CalendarCard'
import { CategoryBudgetsCard } from './components/CategoryBudgetsCard'
import { ManualTransactionForm } from './components/ManualTransactionForm'
import { BillsCard, SubscriptionsCard } from './components/RecurringCard'
import { SimpleFinLinkForm } from './components/SimpleFinLinkForm'
import { SpendingCard } from './components/SpendingCard'
import { WeatherCard } from './components/WeatherCard'
import { useApi } from './hooks/useApi'

function App() {
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })

  // Fetched once here (rather than in each card) so Subscriptions/Bills
  // split the same data instead of doubling up the network call.
  const recurring = useApi('/api/spending/recurring')
  const health = useApi('/api/health')

  return (
    <div className="dashboard">
      {health.data?.demo && (
        <p className="demo-banner" role="note">
          Live demo with made-up bank, weather and calendar data. Add a transaction if you like: it all resets nightly.
        </p>
      )}
      <header>
        <h1>Good morning</h1>
        <p className="muted">{today}</p>
        <SimpleFinLinkForm />
      </header>
      <div className="grid">
        <WeatherCard />
        <CalendarCard />
        <ManualTransactionForm />
        <BudgetCard />
        <CategoryBudgetsCard />
        <SpendingCard />
        <SubscriptionsCard {...recurring} />
        <BillsCard {...recurring} />
      </div>
    </div>
  )
}

export default App

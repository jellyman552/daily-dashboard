import { useApi } from '../hooks/useApi'
import { Card, CardStatus } from './Card'

const formatTime = (iso) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })

export function CalendarCard() {
  const { data, error, loading } = useApi('/api/calendar/today')

  return (
    <Card title="Today's Events">
      <CardStatus loading={loading} error={error} />
      {data && (
        <ul className="breakdown">
          {data.events.length === 0 && <li>No events today 🎉</li>}
          {data.events.map((e) => (
            <li key={`${e.title}-${e.start}`}>
              <span>{e.title}</span>
              <span>{e.all_day ? 'All day' : formatTime(e.start)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

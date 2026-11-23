import { useApi } from '../hooks/useApi'
import { Card, CardStatus } from './Card'

export function WeatherCard() {
  const { data, error, loading } = useApi('/api/weather')

  return (
    <Card title="Weather">
      <CardStatus loading={loading} error={error} />
      {data && (
        <>
          {data.temperature_f != null && <p className="big-number">{Math.round(data.temperature_f)}°F</p>}
          <p>{data.short_forecast}</p>
          {data.detailed_forecast && <p className="muted">{data.detailed_forecast}</p>}
        </>
      )}
    </Card>
  )
}

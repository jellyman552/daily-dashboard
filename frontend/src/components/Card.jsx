export function Card({ title, children }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

export function CardStatus({ loading, error }) {
  if (loading) return <p className="status">Loading…</p>
  if (error) return <p className="status status-error">Couldn't load: {error}</p>
  return null
}

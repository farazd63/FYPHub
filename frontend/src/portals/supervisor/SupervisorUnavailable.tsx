export function SupervisorUnavailable({ title }: { title: string }) {
  return <section className="supervisor-page" aria-labelledby="supervisor-unavailable-heading"><div className="supervisor-page-heading"><p>Supervisor workspace</p><h1 id="supervisor-unavailable-heading">{title}</h1></div><div className="supervisor-card supervisor-empty"><h2>Unavailable</h2></div></section>;
}

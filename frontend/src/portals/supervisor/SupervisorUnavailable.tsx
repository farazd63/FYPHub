export function SupervisorUnavailable({ title, description }: { title: string; description: string }) {
  return <section className="supervisor-page" aria-labelledby="supervisor-unavailable-heading"><div className="supervisor-page-heading"><p>Supervisor workspace</p><h1 id="supervisor-unavailable-heading">{title}</h1><span>{description}</span></div><div className="supervisor-card supervisor-empty"><h2>Unavailable</h2><p className="mt-2">No supervisor API currently exposes this data or action. Nothing has been fabricated.</p></div></section>;
}

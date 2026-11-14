export function OpportunityList({ items }: { items: string[] }) {
  return (
    <section aria-label="Improvement opportunities" className="space-y-2">
      <h3 className="text-sm font-semibold text-violet-700">Improvement opportunities</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None identified.</p>
      ) : (
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {items.map((item, i) => (
            <li key={`${i}-${item}`}>{item}</li>
          ))}
        </ol>
      )}
    </section>
  )
}

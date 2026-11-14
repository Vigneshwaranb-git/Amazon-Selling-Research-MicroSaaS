import { PageWrapper } from '@/components/layout/PageWrapper'
import { MeshBackground } from '@/components/layout/MeshBackground'
import { GlassCard } from '@/components/ui/GlassCard'

interface PlaceholderPageProps {
  title: string
  route: string
  showBackground?: boolean
}

export function PlaceholderPage({ title, route, showBackground = false }: PlaceholderPageProps) {
  return (
    <PageWrapper>
      {showBackground && <MeshBackground />}
      <main className="mx-auto max-w-4xl p-8">
        <GlassCard>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-2 text-muted-foreground">Placeholder for route {route}</p>
        </GlassCard>
      </main>
    </PageWrapper>
  )
}

import type { ReactNode } from 'react'
import { MeshBackground } from '@/components/layout/MeshBackground'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'

interface AuthPageLayoutProps {
  title: string
  subtitle?: string
  children: ReactNode
}

export function AuthPageLayout({ title, subtitle, children }: AuthPageLayoutProps) {
  return (
    <PageWrapper>
      <MeshBackground />
      <main className="mx-auto flex min-h-screen max-w-md items-center p-4">
        <GlassCard className="w-full">
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-1 mb-6 text-sm text-muted-foreground">{subtitle}</p>
          {children}
        </GlassCard>
      </main>
    </PageWrapper>
  )
}

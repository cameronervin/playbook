import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminShell } from '@/src/components/features/admin/AdminShell'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

const currentUser = vi.hoisted(() => ({
  role: 'athlete',
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: {
      name: 'Jordan',
      email: 'jordan@example.com',
      role: currentUser.role,
      profile_complete: true,
    },
    isLoading: false,
  }),
  useLogout: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/src/hooks/useAdmin', () => ({
  useAdminUsers: () => ({ data: [], isLoading: false }),
  useUpdateUserRole: () => ({ mutate: vi.fn(), isPending: false }),
  useAuditLogs: () => ({ data: [], isLoading: false }),
}))

vi.mock('@/src/hooks/useKBDocuments', () => ({
  useKBDocuments: () => ({ data: [], isLoading: false }),
  useUploadKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useRetryKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateKBDocumentMetadata: () => ({ mutate: vi.fn(), isPending: false }),
}))

function renderAdmin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <AdminShell />
    </QueryClientProvider>,
  )
}

describe('AdminShell', () => {
  it('denies athlete access', () => {
    currentUser.role = 'athlete'
    renderAdmin()

    expect(screen.getByRole('heading', { name: /admins only/i })).toBeInTheDocument()
  })

  it('shows super-admin-only users navigation for super admins', () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    expect(screen.getByRole('button', { name: /users & roles/i })).toBeInTheDocument()
  })
})

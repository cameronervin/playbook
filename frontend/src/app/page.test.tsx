import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import HomePage from '@/src/app/page'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('HomePage', () => {
  it('renders the scaffold heading', () => {
    renderWithProviders(<HomePage />)
    expect(
      screen.getByRole('heading', { name: /agentic app scaffold/i }),
    ).toBeInTheDocument()
  })
})

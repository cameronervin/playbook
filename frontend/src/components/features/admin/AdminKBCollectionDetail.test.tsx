import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AdminKBCollectionDetail } from '@/src/components/features/admin/AdminKBCollectionDetail'
import type { KBCollectionViewModel, KBDocument, UploadKBDocumentRequest } from '@/src/types/kb'

const collectionBase: KBCollectionViewModel = {
  id: 'compliance',
  name: 'Compliance & NIL',
  icon: 'shield',
  blurb: 'NIL, eligibility, and recruiting rules.',
  keywords: ['nil', 'compliance'],
  documents: [],
  failedCount: 0,
  processingCount: 0,
}

function documentFromUpload(request: UploadKBDocumentRequest): KBDocument {
  return {
    id: 'doc-uploaded',
    organization_id: 'org-1',
    uploaded_by: 'u1',
    title: 'Queued document',
    filename: request.file.name,
    content_type: request.file.type,
    size_bytes: request.file.size,
    processing_status: 'ready',
    failure_reason: null,
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: request.metadata_tags ?? {},
    source_date: request.source_date ?? null,
    kb_service_document_id: 'kb-doc-uploaded',
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  }
}

describe('AdminKBCollectionDetail', () => {
  it('removes a completed local upload row when the server document appears', async () => {
    const onUpload = vi.fn(async (request: UploadKBDocumentRequest) => {
      request.onProgress?.({ loaded: 5, percent: 100, total: 5 })
      return documentFromUpload(request)
    })
    const props = {
      canManage: true,
      collection: collectionBase,
      onBack: vi.fn(),
      onDelete: vi.fn(),
      onEdit: vi.fn(),
      onRetry: vi.fn(),
      onUpload,
    }
    const { rerender } = render(<AdminKBCollectionDetail {...props} />)

    await userEvent.click(screen.getByRole('button', { name: /Upload document/i }))
    const dialog = screen.getByRole('dialog', { name: /Upload document/i })
    const file = new File(['hello'], 'queued-doc.pdf', { type: 'application/pdf' })
    await userEvent.upload(within(dialog).getByLabelText(/Document file/i), file)
    await userEvent.click(within(dialog).getByRole('button', { name: /^Upload$/i }))

    expect(await screen.findByText('queued-doc.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Queued')).toBeInTheDocument()

    rerender(
      <AdminKBCollectionDetail
        {...props}
        collection={{
          ...collectionBase,
          documents: [documentFromUpload({ file })],
        }}
      />,
    )

    await waitFor(() => expect(screen.queryByText('queued-doc.pdf')).not.toBeInTheDocument())
    expect(screen.getByText('Queued document')).toBeInTheDocument()
  })
})

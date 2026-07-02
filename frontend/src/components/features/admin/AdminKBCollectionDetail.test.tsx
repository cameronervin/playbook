import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AdminKBCollectionDetail } from '@/src/components/features/admin/AdminKBCollectionDetail'
import type { KBCollectionViewModel, KBDocument, UploadKBDocumentRequest } from '@/src/types/kb'

const collectionBase: KBCollectionViewModel = {
  id: 'collection-compliance',
  organization_id: 'org-1',
  slug: 'compliance',
  title: 'Compliance & NIL',
  icon: 'shield',
  description: 'NIL, eligibility, and recruiting rules.',
  sort_order: 10,
  is_active: true,
  created_at: '2026-06-29T12:00:00Z',
  updated_at: '2026-06-29T12:00:00Z',
  documents: [],
  failedCount: 0,
  processingCount: 0,
}

const metadataTags = [
  {
    id: 'tag-nil',
    organization_id: 'org-1',
    slug: 'nil',
    label: 'NIL',
    sort_order: 10,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
]

function documentFixture(
  overrides: Partial<KBDocument> & Pick<KBDocument, 'id' | 'processing_status' | 'title'>,
): KBDocument {
  const { id, processing_status, title, ...rest } = overrides
  const filename = `${title.toLowerCase().replaceAll(' ', '-')}.pdf`
  return {
    id,
    organization_id: 'org-1',
    uploaded_by: 'u1',
    title,
    filename,
    content_type: 'application/pdf',
    size_bytes: 42_000,
    processing_status,
    failure_reason: null,
    collection_id: collectionBase.id,
    tag_slugs: [],
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: { collection: 'compliance' },
    source_date: null,
    kb_service_document_id: null,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
    ...rest,
  }
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
    collection_id: request.collection_id,
    tag_slugs: request.tag_slugs ?? [],
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: { collection: 'compliance', tag_slugs: request.tag_slugs ?? [] },
    source_date: request.source_date ?? null,
    kb_service_document_id: 'kb-doc-uploaded',
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  }
}

describe('AdminKBCollectionDetail', () => {
  it('shows the persisted ingestion lifecycle states, including ready', () => {
    render(
      <AdminKBCollectionDetail
        canManage
        collection={{
          ...collectionBase,
          documents: [
            documentFixture({
              id: 'doc-pending',
              processing_status: 'upload_pending',
              title: 'Pending upload document',
            }),
            documentFixture({
              id: 'doc-uploaded',
              processing_status: 'uploaded',
              title: 'Queued document',
            }),
            documentFixture({
              id: 'doc-processing',
              processing_status: 'processing',
              title: 'Processing document',
            }),
            documentFixture({
              id: 'doc-ready',
              processing_status: 'ready',
              title: 'Ready document',
            }),
            documentFixture({
              failure_reason: 'NO_TEXT_EXTRACTED: No usable text could be extracted.',
              id: 'doc-failed',
              processing_status: 'failed',
              title: 'Failed document',
            }),
          ],
        }}
        metadataTags={metadataTags}
        onBack={vi.fn()}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onRetry={vi.fn()}
        onUpload={vi.fn()}
      />,
    )

    expect(screen.getByText('Pending upload')).toBeInTheDocument()
    expect(screen.getByText('Queued')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('NO_TEXT_EXTRACTED: No usable text could be extracted.')).toBeInTheDocument()
  })

  it('lets admins retry a failed persisted document and reflects retry status updates', async () => {
    const onRetry = vi.fn()
    const failedDocument = documentFixture({
      failure_reason: 'NO_TEXT_EXTRACTED: No usable text could be extracted.',
      id: 'doc-failed',
      processing_status: 'failed',
      title: 'Failed document',
    })
    const props = {
      canManage: true,
      collection: {
        ...collectionBase,
        documents: [failedDocument],
      },
      metadataTags,
      onBack: vi.fn(),
      onDelete: vi.fn(),
      onEdit: vi.fn(),
      onRetry,
      onUpload: vi.fn(),
    }
    const { rerender } = render(<AdminKBCollectionDetail {...props} />)

    expect(screen.getByText('NO_TEXT_EXTRACTED: No usable text could be extracted.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Retry Failed document/i }))

    expect(onRetry).toHaveBeenCalledWith('doc-failed')

    rerender(
      <AdminKBCollectionDetail
        {...props}
        collection={{
          ...collectionBase,
          documents: [
            {
              ...failedDocument,
              failure_reason: null,
              processing_status: 'uploaded',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Queued')).toBeInTheDocument()
    expect(screen.queryByText('NO_TEXT_EXTRACTED: No usable text could be extracted.')).not.toBeInTheDocument()

    rerender(
      <AdminKBCollectionDetail
        {...props}
        collection={{
          ...collectionBase,
          documents: [
            {
              ...failedDocument,
              failure_reason: 'NO_TEXT_EXTRACTED: No usable text could be extracted.',
              processing_status: 'failed',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('NO_TEXT_EXTRACTED: No usable text could be extracted.')).toBeInTheDocument()
  })

  it('keeps the upload drop area centered, accessible, and file-selectable', async () => {
    render(
      <AdminKBCollectionDetail
        canManage
        collection={collectionBase}
        metadataTags={metadataTags}
        onBack={vi.fn()}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onRetry={vi.fn()}
        onUpload={vi.fn()}
      />,
    )

    const uploadSection = screen.getByRole('region', { name: /Document upload/i })
    const dropButton = within(uploadSection).getByRole('button', {
      name: /Upload knowledge-base document to Compliance & NIL/i,
    })
    expect(within(uploadSection).getByRole('heading', { name: /Upload documents/i })).toBeInTheDocument()
    expect(dropButton).toHaveTextContent('Drag and Drop here')
    expect(dropButton).toHaveTextContent('or')
    expect(dropButton).toHaveTextContent('Browse files')
    expect(dropButton).toHaveTextContent('Accepted file types: PDF, DOCX, PPTX, or XLSX.')
    expect(dropButton).toHaveTextContent('Only upload department-approved content.')

    const file = new File(['hello'], 'active-upload.pdf', { type: 'application/pdf' })
    await act(async () => {
      fireEvent.dragEnter(dropButton, dragData([file]))
    })
    expect(dropButton).toHaveTextContent('Drop document here')

    const uploadInput = within(uploadSection)
      .getAllByLabelText(/Upload knowledge-base document/i)
      .find((element): element is HTMLInputElement => element instanceof HTMLInputElement)
    expect(uploadInput).toBeDefined()

    await userEvent.upload(uploadInput!, file)

    expect(screen.getByRole('dialog', { name: /Upload document/i })).toBeInTheDocument()
  })

  it('removes a completed local upload row when the server document appears', async () => {
    const onUpload = vi.fn(async (request: UploadKBDocumentRequest) => {
      request.onProgress?.({ loaded: 5, percent: 100, total: 5 })
      return documentFromUpload(request)
    })
    const props = {
      canManage: true,
      collection: collectionBase,
      metadataTags,
      onBack: vi.fn(),
      onDelete: vi.fn(),
      onEdit: vi.fn(),
      onRetry: vi.fn(),
      onUpload,
    }
    const { rerender } = render(<AdminKBCollectionDetail {...props} />)

    const file = new File(['hello'], 'queued-doc.pdf', { type: 'application/pdf' })
    const uploadInput = screen
      .getAllByLabelText(/Upload knowledge-base document/i)
      .find((element): element is HTMLInputElement => element instanceof HTMLInputElement)
    expect(uploadInput).toBeDefined()
    await userEvent.upload(uploadInput!, file)
    const dialog = screen.getByRole('dialog', { name: /Upload document/i })
    await userEvent.click(within(dialog).getByRole('button', { name: /^Upload$/i }))

    expect(await screen.findByText('queued-doc.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Queued')).toBeInTheDocument()

    rerender(
      <AdminKBCollectionDetail
        {...props}
        collection={{
          ...collectionBase,
          documents: [documentFromUpload({ collection_id: collectionBase.id, file })],
        }}
      />,
    )

    await waitFor(() => expect(screen.queryByText('queued-doc.pdf')).not.toBeInTheDocument())
    expect(screen.getByText('Queued document')).toBeInTheDocument()
  })
})

function dragData(files: File[]) {
  return {
    dataTransfer: {
      files,
      items: files.map((file) => ({
        getAsFile: () => file,
        kind: 'file',
        type: file.type,
      })),
      types: ['Files'],
    },
  }
}

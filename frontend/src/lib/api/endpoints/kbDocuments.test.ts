import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  completeKBDocumentUpload,
  createKBDocumentUploadIntent,
  uploadKBDocument,
} from '@/src/lib/api/endpoints/kbDocuments'
import { apiClient } from '@/src/lib/api/client'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import type { KBDocument, KBDocumentUploadIntentResponse } from '@/src/types/kb'

vi.mock('@/src/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('@/src/lib/api/directUpload', () => ({
  postDirectUpload: vi.fn(),
}))

const document: KBDocument = {
  id: 'doc-1',
  organization_id: 'org-1',
  uploaded_by: 'user-1',
  title: 'NIL Handbook',
  filename: 'nil-handbook.pdf',
  content_type: 'application/pdf',
  size_bytes: 12,
  processing_status: 'upload_pending',
  failure_reason: null,
  visibility_policy: { scope: 'all_athletes' },
  metadata_tags: { collection: 'compliance' },
  source_date: '2026-06-01',
  kb_service_document_id: null,
  created_at: '2026-06-17T12:00:00Z',
  updated_at: '2026-06-17T12:00:00Z',
}

const intent: KBDocumentUploadIntentResponse = {
  document,
  upload: {
    upload_request_id: 'upload-request-1',
    method: 'POST',
    url: 'https://storage.example/upload',
    fields: { key: 'private/key.pdf' },
    expires_at: '2026-06-17T12:15:00Z',
  },
}

describe('kb document upload endpoints', () => {
  beforeEach(() => {
    vi.mocked(apiClient).mockReset()
    vi.mocked(postDirectUpload).mockReset()
  })

  it('creates an upload intent with JSON metadata instead of FormData', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce(intent)

    await createKBDocumentUploadIntent({
      filename: 'nil-handbook.pdf',
      content_type: 'application/pdf',
      size_bytes: 12,
      title: 'NIL Handbook',
      metadata_tags: { collection: 'compliance' },
      source_date: '2026-06-01',
    })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/admin/kb/documents', {
      method: 'POST',
      json: {
        filename: 'nil-handbook.pdf',
        content_type: 'application/pdf',
        size_bytes: 12,
        title: 'NIL Handbook',
        metadata_tags: { collection: 'compliance' },
        source_date: '2026-06-01',
      },
    })
  })

  it('completes an upload with only the upload request id', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ ...document, processing_status: 'uploaded' })

    await completeKBDocumentUpload('doc-1', 'upload-request-1')

    expect(apiClient).toHaveBeenCalledWith('/api/v1/admin/kb/documents/doc-1/upload-complete', {
      method: 'POST',
      json: { upload_request_id: 'upload-request-1' },
    })
  })

  it('performs intent, storage POST, then completion for the high-level upload', async () => {
    const file = new File(['hello world'], 'nil-handbook.pdf', { type: 'application/pdf' })
    vi.mocked(apiClient)
      .mockResolvedValueOnce(intent)
      .mockResolvedValueOnce({ ...document, processing_status: 'uploaded' })

    await uploadKBDocument({ file, title: 'NIL Handbook', metadata_tags: { collection: 'compliance' } })

    expect(postDirectUpload).toHaveBeenCalledWith(expect.objectContaining({ contract: intent.upload, file }))
    expect(apiClient).toHaveBeenNthCalledWith(2, '/api/v1/admin/kb/documents/doc-1/upload-complete', {
      method: 'POST',
      json: { upload_request_id: 'upload-request-1' },
    })
  })
})

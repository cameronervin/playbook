import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import type { DirectUploadContract } from '@/src/types/uploads'

const originalXMLHttpRequest = global.XMLHttpRequest

interface SentFormEntry {
  name: string
  value: FormDataEntryValue
}

class MockXMLHttpRequest {
  static latest: MockXMLHttpRequest | null = null
  static nextStatus = 204

  readonly upload = new EventTarget()
  method: string | null = null
  onerror: (() => void) | null = null
  onload: (() => void) | null = null
  sentEntries: SentFormEntry[] = []
  status = 0
  url: string | null = null

  constructor() {
    MockXMLHttpRequest.latest = this
  }

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }

  send(body: FormData) {
    this.sentEntries = Array.from(body.entries()).map(([name, value]) => ({ name, value }))
    this.status = MockXMLHttpRequest.nextStatus
    this.onload?.()
  }
}

const contract: DirectUploadContract = {
  upload_request_id: 'upload-request-1',
  method: 'POST',
  url: 'https://storage.example/upload',
  fields: {
    key: 'private/object/key.pdf',
    policy: 'signed-policy',
  },
  expires_at: '2026-06-17T12:15:00Z',
}

describe('postDirectUpload', () => {
  beforeEach(() => {
    vi.stubGlobal('XMLHttpRequest', MockXMLHttpRequest)
    MockXMLHttpRequest.latest = null
    MockXMLHttpRequest.nextStatus = 204
  })

  afterEach(() => {
    vi.stubGlobal('XMLHttpRequest', originalXMLHttpRequest)
    vi.restoreAllMocks()
  })

  it('posts contract fields before the file and reports upload progress', async () => {
    const progress = vi.fn()
    const file = new File(['hello'], 'policy.pdf', { type: 'application/pdf' })

    const upload = postDirectUpload({ contract, file, onProgress: progress })
    MockXMLHttpRequest.latest?.upload.dispatchEvent(
      new ProgressEvent('progress', { lengthComputable: true, loaded: 5, total: 10 }),
    )
    await upload

    expect(MockXMLHttpRequest.latest?.method).toBe('POST')
    expect(MockXMLHttpRequest.latest?.url).toBe(contract.url)
    expect(MockXMLHttpRequest.latest?.sentEntries.map((entry) => entry.name)).toEqual(['key', 'policy', 'file'])
    expect(MockXMLHttpRequest.latest?.sentEntries[2]?.value).toBe(file)
    expect(progress).toHaveBeenCalledWith({ loaded: 5, percent: 50, total: 10 })
  })

  it('rejects failed storage responses with a sanitized error', async () => {
    MockXMLHttpRequest.nextStatus = 403
    const file = new File(['hello'], 'policy.pdf', { type: 'application/pdf' })

    await expect(postDirectUpload({ contract, file })).rejects.toThrow('File upload failed before Playbook received it.')
  })
})

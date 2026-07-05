import { describe, expect, it } from 'vitest'
import {
  COLLECTION_ICON_COMPONENTS,
  formatBytes,
  formatLocalUploadPhase,
  getSafeUploadErrorMessage,
  type AdminKBLocalUploadRow,
} from '@/src/components/features/admin/kbFormatting'
import type { KBCollectionIcon } from '@/src/types/kb'

function upload(phase: AdminKBLocalUploadRow['phase'], percent = 0): AdminKBLocalUploadRow {
  const file = new File(['hello'], 'handbook.pdf', { type: 'application/pdf' })
  return {
    file,
    id: `upload-${phase}`,
    percent,
    phase,
    request: { collection_id: 'collection-compliance', file, title: 'handbook.pdf' },
  }
}

describe('kbFormatting', () => {
  it('formats local upload phases without changing copy', () => {
    expect(formatLocalUploadPhase(upload('requesting'))).toBe('Preparing')
    expect(formatLocalUploadPhase(upload('uploading', 42))).toBe('Uploading 42%')
    expect(formatLocalUploadPhase(upload('queued'))).toBe('Queued')
    expect(formatLocalUploadPhase(upload('failed'))).toBe('Failed')
  })

  it('formats byte counts with existing labels', () => {
    expect(formatBytes(0)).toBe('Unknown size')
    expect(formatBytes(Number.NaN)).toBe('Unknown size')
    expect(formatBytes(500)).toBe('1 KB')
    expect(formatBytes(42_400)).toBe('42 KB')
    expect(formatBytes(1_250_000)).toBe('1.3 MB')
  })

  it('keeps safe upload error messaging bounded', () => {
    expect(getSafeUploadErrorMessage(new Error('File upload failed before Playbook received it.'))).toBe(
      'File upload failed before Playbook received it.',
    )
    expect(getSafeUploadErrorMessage('raw failure')).toBe('Upload failed before Playbook received it.')
  })

  it('supports every configured KB collection icon', () => {
    const supportedIcons: KBCollectionIcon[] = ['book-open', 'database', 'plane', 'shield', 'users']

    expect(Object.keys(COLLECTION_ICON_COMPONENTS).sort()).toEqual(supportedIcons.sort())
  })
})

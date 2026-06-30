import {
  BookOpen,
  Database,
  Plane,
  Shield,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { KBCollectionIcon } from '@/src/types/kb'
import type { UploadKBDocumentRequest } from '@/src/types/kb'

export type AdminKBLocalUploadPhase = 'requesting' | 'uploading' | 'queued' | 'failed'

export type AdminKBUploadRetryRequest = Pick<
  UploadKBDocumentRequest,
  'collection_id' | 'file' | 'source_date' | 'tag_slugs' | 'title'
>

export interface AdminKBLocalUploadRow {
  errorMessage?: string
  file: File
  id: string
  percent: number
  phase: AdminKBLocalUploadPhase
  request: AdminKBUploadRetryRequest
}

export const COLLECTION_ICON_COMPONENTS: Record<KBCollectionIcon, LucideIcon> = {
  'book-open': BookOpen,
  database: Database,
  plane: Plane,
  shield: Shield,
  users: Users,
}

export function formatLocalUploadPhase(upload: AdminKBLocalUploadRow): string {
  if (upload.phase === 'requesting') return 'Preparing'
  if (upload.phase === 'uploading') return `Uploading ${upload.percent}%`
  if (upload.phase === 'queued') return 'Queued'
  return 'Failed'
}

export function getSafeUploadErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Upload failed before Playbook received it.'
}

export function formatBytes(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return 'Unknown size'
  if (sizeBytes >= 1_000_000) return `${(sizeBytes / 1_000_000).toFixed(1)} MB`
  return `${Math.max(1, Math.round(sizeBytes / 1_000))} KB`
}

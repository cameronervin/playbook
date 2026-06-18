import { AlertTriangle, FileText, LoaderCircle, RefreshCw } from 'lucide-react'
import {
  formatBytes,
  formatLocalUploadPhase,
  type AdminKBLocalUploadRow,
} from '@/src/components/features/admin/kbFormatting'

interface AdminKBLocalUploadRowProps {
  onRetry: () => void
  upload: AdminKBLocalUploadRow
}

export function AdminKBLocalUploadRowView({ onRetry, upload }: AdminKBLocalUploadRowProps) {
  const failed = upload.phase === 'failed'

  return (
    <article className="pb-admin-kb-doc-row" data-failed={failed}>
      <div className="pb-admin-kb-doc-main">
        <span className="pb-admin-kb-file-icon" aria-hidden="true">
          <FileText size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="pb-admin-kb-doc-title">{upload.file.name}</span>
          </div>
          <p className="pb-admin-kb-doc-meta">{formatBytes(upload.file.size)} · Direct upload</p>
        </div>
        <span className={failed ? 'pb-admin-kb-status text-danger' : 'pb-admin-kb-status text-info'}>
          {failed ? <AlertTriangle size={14} /> : <LoaderCircle className="pb-spin" size={14} />}
          {formatLocalUploadPhase(upload)}
        </span>
      </div>
      {upload.phase === 'uploading' && (
        <div className="px-3 pb-3">
          <div className="h-1.5 overflow-hidden rounded-pill bg-surface-hover" aria-hidden="true">
            <span
              className="block h-full rounded-pill bg-brand"
              style={{ width: `${upload.percent}%` }}
            />
          </div>
          <p className="pb-ui-xs mt-1 text-fg-3" role="status">
            Uploading {upload.percent}%
          </p>
        </div>
      )}
      {failed && (
        <div className="pb-admin-kb-failure">
          <AlertTriangle className="shrink-0 text-danger" size={14} />
          <span className="flex-1">{upload.errorMessage ?? 'Upload failed.'}</span>
          <button className="pb-admin-kb-inline-action" onClick={onRetry} type="button">
            <RefreshCw size={13} />
            Try again
          </button>
        </div>
      )}
    </article>
  )
}

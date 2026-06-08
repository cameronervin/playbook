import { RefreshCw, Shield, Trash2 } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { Badge, IconButton, Surface } from '@/src/components/ui'

interface KBPanelProps {
  canManage: boolean
  documents: Array<{ id: string; title: string; processing_status: string; is_official: boolean; failure_reason: string | null }>
  onDelete: (id: string) => void
  onRetry: (id: string) => void
  onToggleOfficial: (id: string, isOfficial: boolean) => void
}

export function KBPanel({ canManage, documents, onDelete, onRetry, onToggleOfficial }: KBPanelProps) {
  return (
    <AdminPageScaffold
      contentClassName="py-7"
      subtitle={`${documents.length} ${documents.length === 1 ? 'document' : 'documents'} in knowledge base`}
      title="Knowledge base"
    >
      <div className="grid gap-3">
        {documents.length === 0 && <Surface className="p-5 text-sm text-fg-3">No documents yet.</Surface>}
        {documents.map((doc) => (
          <Surface className="flex items-center justify-between gap-4 p-4" key={doc.id}>
            <div>
              <p className="text-sm font-semibold text-fg-1">{doc.title}</p>
              <p className="mt-1 text-xs text-fg-4">{doc.failure_reason ?? 'Visible to all athletes'}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={doc.processing_status === 'failed' ? 'danger' : 'success'}>{doc.processing_status}</Badge>
              {canManage && (
                <>
                  <IconButton aria-label={`Retry ${doc.title}`} onClick={() => onRetry(doc.id)}>
                    <RefreshCw className="h-4 w-4" />
                  </IconButton>
                  <IconButton aria-label={`Toggle official ${doc.title}`} onClick={() => onToggleOfficial(doc.id, !doc.is_official)}>
                    <Shield className="h-4 w-4" />
                  </IconButton>
                  <IconButton aria-label={`Delete ${doc.title}`} onClick={() => onDelete(doc.id)}>
                    <Trash2 className="h-4 w-4" />
                  </IconButton>
                </>
              )}
            </div>
          </Surface>
        ))}
      </div>
    </AdminPageScaffold>
  )
}

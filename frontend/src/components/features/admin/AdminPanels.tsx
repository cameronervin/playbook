import { RefreshCw, Shield, Trash2 } from 'lucide-react'
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
    <div className="mx-auto w-full max-w-[1000px] px-7 py-7">
      <h1 className="pb-page-title">Knowledge base</h1>
      <div className="mt-6 grid gap-3">
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
    </div>
  )
}

interface UsersPanelProps {
  auditCount: number
  onRoleChange: (id: string, role: 'athlete' | 'admin' | 'super_admin') => void
  users: Array<{ id: string; name: string; email: string; role: 'athlete' | 'admin' | 'super_admin' }>
}

export function UsersPanel({ auditCount, onRoleChange, users }: UsersPanelProps) {
  return (
    <div className="mx-auto w-full max-w-[1000px] px-7 py-7">
      <h1 className="pb-page-title">Users & roles</h1>
      <p className="mt-2 text-sm text-fg-3">{auditCount} audit events available.</p>
      <div className="mt-6 grid gap-3">
        {users.length === 0 && <Surface className="p-5 text-sm text-fg-3">No users returned yet.</Surface>}
        {users.map((adminUser) => (
          <Surface className="flex items-center justify-between gap-4 p-4" key={adminUser.id}>
            <div>
              <p className="text-sm font-semibold text-fg-1">{adminUser.name}</p>
              <p className="text-xs text-fg-4">{adminUser.email}</p>
            </div>
            <select
              className="rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg-1"
              onChange={(event) => onRoleChange(adminUser.id, event.target.value as 'athlete' | 'admin' | 'super_admin')}
              value={adminUser.role}
            >
              <option value="athlete">Athlete</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super admin</option>
            </select>
          </Surface>
        ))}
      </div>
    </div>
  )
}

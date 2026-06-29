'use client'

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import { Button, Dialog, Input } from '@/src/components/ui'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { SUPPORTED_UPLOAD_ACCEPT } from '@/src/lib/constants/uploads'
import { collectionUploadMetadata } from '@/src/lib/fixtures/kbCollections'
import type { AdminKBUploadRetryRequest } from '@/src/components/features/admin/kbFormatting'
import type { KBCollectionViewModel } from '@/src/types/kb'

interface AdminKBUploadDialogProps {
  collection: KBCollectionViewModel
  onOpenChange: (open: boolean) => void
  onSubmit: (request: AdminKBUploadRetryRequest) => void
  open: boolean
}

export function AdminKBUploadDialog({
  collection,
  onOpenChange,
  onSubmit,
  open,
}: AdminKBUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState(collection.name)
  const [sourceDate, setSourceDate] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const [dateError, setDateError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setFile(null)
      setTitle('')
      setTags(collection.name)
      setSourceDate('')
      setFileError(null)
      setDateError(null)
    }
  }, [collection.name, open])

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null
    if (!selectedFile) return
    try {
      const validated = validateUploadFile(selectedFile)
      setFile(selectedFile)
      setTitle(validated.filename)
      setFileError(null)
    } catch (error) {
      setFile(null)
      setTitle('')
      setFileError(error instanceof Error ? error.message : 'Choose a supported file to upload.')
    }
    event.target.value = ''
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) {
      setFileError('Choose a supported file to upload.')
      return
    }
    const normalizedDate = sourceDate.trim()
    if (normalizedDate && !isValidISODate(normalizedDate)) {
      setDateError('Use YYYY-MM-DD.')
      return
    }
    setDateError(null)
    validateUploadFile(file)
    onSubmit({
      file,
      metadata_tags: {
        ...collectionUploadMetadata(collection),
        topics: parseTags(tags),
      },
      source_date: normalizedDate || null,
      title: title.trim() || file.name,
    })
    onOpenChange(false)
  }

  return (
    <Dialog
      description="Choose a supported file and the source metadata Playbook should use before processing starts."
      onOpenChange={onOpenChange}
      open={open}
      title="Upload document"
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <label>
          <span className="pb-admin-kb-field-label block">Document file</span>
          <input
            accept={SUPPORTED_UPLOAD_ACCEPT}
            className="sr-only"
            onChange={handleFileChange}
            type="file"
          />
          <span className="pb-focus-control flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-md border border-border-strong bg-surface px-3 py-2.5 text-left pb-ui-sm text-fg-1 transition hover:bg-surface-hover">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-surface-hover text-brand">
              <FileText size={16} />
            </span>
            <span className="min-w-0 flex-1 truncate">
              {file ? file.name : 'Choose PDF, DOCX, PPTX, or XLSX'}
            </span>
          </span>
        </label>
        {fileError && <p className="pb-ui-xs text-danger">{fileError}</p>}

        <label>
          <span className="pb-admin-kb-field-label block">Title</span>
          <Input onChange={(event) => setTitle(event.target.value)} value={title} />
        </label>

        <label>
          <span className="pb-admin-kb-field-label block">Metadata tags</span>
          <Input
            onChange={(event) => setTags(event.target.value)}
            placeholder="NIL, Compliance"
            value={tags}
          />
        </label>

        <label>
          <span className="pb-admin-kb-field-label block">Source date</span>
          <Input
            inputMode="numeric"
            onChange={(event) => {
              setSourceDate(event.target.value)
              if (dateError) setDateError(null)
            }}
            placeholder="YYYY-MM-DD"
            value={sourceDate}
          />
        </label>
        {dateError && <p className="pb-ui-xs text-danger">{dateError}</p>}

        <div className="mt-1 flex justify-end gap-2">
          <Button onClick={() => onOpenChange(false)} size="sm" type="button" variant="secondary">
            Cancel
          </Button>
          <Button size="sm" type="submit">
            <Upload size={15} />
            Upload
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

function parseTags(value: string): string[] {
  const parsed = value
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
  return parsed.length > 0 ? parsed : []
}

function isValidISODate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [yearPart, monthPart, dayPart] = value.split('-')
  const year = Number(yearPart)
  const month = Number(monthPart)
  const day = Number(dayPart)
  const date = new Date(Date.UTC(year, month - 1, day))
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  )
}

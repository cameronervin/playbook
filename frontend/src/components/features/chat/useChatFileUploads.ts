'use client'

import { useCallback, useState } from 'react'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import type { ChatUploadRow } from '@/src/components/features/chat/chatTypes'
import type { UploadConversationFileRequest } from '@/src/types/conversations'

interface UploadConversationFileOptions {
  onError?: (error: unknown) => void
  onSuccess?: () => void
}

export type UploadConversationFileMutation = (
  request: UploadConversationFileRequest,
  options?: UploadConversationFileOptions,
) => void

interface UseChatFileUploadsOptions {
  activeConversationId: string | null
  uploadConversationFile: UploadConversationFileMutation
}

export function useChatFileUploads({
  activeConversationId,
  uploadConversationFile,
}: UseChatFileUploadsOptions) {
  const [localUploads, setLocalUploads] = useState<ChatUploadRow[]>([])

  const startConversationFileUpload = useCallback(
    (conversationId: string, upload: ChatUploadRow) => {
      setLocalUploads((current) =>
        current.map((currentUpload) =>
          currentUpload.id === upload.id
            ? { ...currentUpload, errorMessage: undefined, phase: 'requesting', percent: 0 }
            : currentUpload,
        ),
      )
      uploadConversationFile(
        {
          conversationId,
          file: upload.file,
          onProgress: (progress) => {
            setLocalUploads((current) =>
              current.map((currentUpload) =>
                currentUpload.id === upload.id
                  ? { ...currentUpload, percent: progress.percent, phase: 'uploading' }
                  : currentUpload,
              ),
            )
          },
        },
        {
          onSuccess: () => {
            setLocalUploads((current) =>
              current.map((currentUpload) =>
                currentUpload.id === upload.id ? { ...currentUpload, percent: 100, phase: 'queued' } : currentUpload,
              ),
            )
          },
          onError: (error) => {
            setLocalUploads((current) =>
              current.map((currentUpload) =>
                currentUpload.id === upload.id
                  ? {
                      ...currentUpload,
                      errorMessage: getSafeUploadErrorMessage(error),
                      phase: 'failed',
                    }
                  : currentUpload,
              ),
            )
          },
        },
      )
    },
    [uploadConversationFile],
  )

  const clearLocalUploads = useCallback(() => {
    setLocalUploads([])
  }, [])

  const handleAttachFile = useCallback(
    (file: File) => {
      const id = `${file.name}-${file.lastModified}-${Date.now()}`
      try {
        validateUploadFile(file)
      } catch (error) {
        setLocalUploads((current) => [
          {
            errorMessage: getSafeUploadErrorMessage(error),
            file,
            id,
            percent: 0,
            phase: 'failed',
          },
          ...current,
        ])
        return
      }

      const upload: ChatUploadRow = { file, id, percent: 0, phase: activeConversationId ? 'requesting' : 'pending' }
      setLocalUploads((current) => [upload, ...current])
      if (activeConversationId) startConversationFileUpload(activeConversationId, upload)
    },
    [activeConversationId, startConversationFileUpload],
  )

  const uploadPendingFiles = useCallback(
    (conversationId: string) => {
      localUploads
        .filter((upload) => upload.phase === 'pending')
        .forEach((upload) => startConversationFileUpload(conversationId, upload))
    },
    [localUploads, startConversationFileUpload],
  )

  return {
    clearLocalUploads,
    handleAttachFile,
    localUploads,
    uploadPendingFiles,
  }
}

function getSafeUploadErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Upload failed before Playbook received it.'
}

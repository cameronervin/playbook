import type { DirectUploadContract, DirectUploadProgress } from '@/src/types/uploads'

interface PostDirectUploadRequest {
  contract: DirectUploadContract
  file: File
  onProgress?: (progress: DirectUploadProgress) => void
}

export class DirectUploadError extends Error {
  constructor(message = 'File upload failed before Playbook received it.') {
    super(message)
    this.name = 'DirectUploadError'
  }
}

export function postDirectUpload({
  contract,
  file,
  onProgress,
}: PostDirectUploadRequest): Promise<void> {
  if (contract.method !== 'POST') {
    return Promise.reject(new DirectUploadError())
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', contract.url)

    xhr.upload.addEventListener('progress', (event) => {
      if (!event.lengthComputable) return
      const percent = event.total > 0 ? Math.round((event.loaded / event.total) * 100) : 0
      onProgress?.({ loaded: event.loaded, percent, total: event.total })
    })

    xhr.onerror = () => reject(new DirectUploadError())
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
        return
      }
      reject(new DirectUploadError())
    }

    const formData = new FormData()
    Object.entries(contract.fields).forEach(([key, value]) => {
      formData.append(key, value)
    })
    formData.append('file', file)

    xhr.send(formData)
  })
}

export class UploadValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'UploadValidationError'
  }
}

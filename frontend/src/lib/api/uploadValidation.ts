import {
  DEFAULT_CONVERSATION_FILE_MAX_UPLOAD_BYTES,
  SUPPORTED_UPLOAD_CONTENT_TYPES,
  SUPPORTED_UPLOAD_EXTENSIONS,
} from '@/src/lib/constants/uploads'
import { UploadValidationError } from '@/src/lib/api/directUpload'

export interface ValidatedUploadFile {
  contentType: string
  filename: string
  sizeBytes: number
}

export function validateUploadFile(
  file: File,
  options: { maxSizeBytes?: number } = {},
): ValidatedUploadFile {
  const filename = sanitizeFilename(file.name)
  if (file.size <= 0) {
    throw new UploadValidationError('Choose a non-empty PDF, DOCX, PPTX, or XLSX file.')
  }

  const maxSizeBytes = options.maxSizeBytes ?? DEFAULT_CONVERSATION_FILE_MAX_UPLOAD_BYTES
  if (file.size > maxSizeBytes) {
    throw new UploadValidationError('That file is too large for upload.')
  }

  const extension = getSupportedExtension(filename)
  if (!extension) {
    throw new UploadValidationError('Playbook supports PDF, DOCX, PPTX, and XLSX uploads.')
  }

  const expectedContentType = SUPPORTED_UPLOAD_CONTENT_TYPES[extension]
  if (file.type && file.type !== expectedContentType) {
    throw new UploadValidationError('Playbook supports PDF, DOCX, PPTX, and XLSX uploads.')
  }

  return {
    contentType: expectedContentType,
    filename,
    sizeBytes: file.size,
  }
}

function sanitizeFilename(name: string): string {
  const filename = name.replace(/\\/g, '/').split('/').pop()?.trim() ?? ''
  if (!filename) {
    throw new UploadValidationError('Choose a supported file to upload.')
  }
  return filename
}

function getSupportedExtension(filename: string): keyof typeof SUPPORTED_UPLOAD_CONTENT_TYPES | null {
  const lowered = filename.toLowerCase()
  const extension = SUPPORTED_UPLOAD_EXTENSIONS.find((candidate) => lowered.endsWith(candidate))
  return extension ? (extension as keyof typeof SUPPORTED_UPLOAD_CONTENT_TYPES) : null
}

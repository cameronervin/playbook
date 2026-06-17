export const SUPPORTED_UPLOAD_CONTENT_TYPES = {
  '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
} as const

export const SUPPORTED_UPLOAD_EXTENSIONS = Object.keys(SUPPORTED_UPLOAD_CONTENT_TYPES)

export const SUPPORTED_UPLOAD_ACCEPT = [
  '.pdf',
  '.docx',
  '.pptx',
  '.xlsx',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
].join(',')

export const DEFAULT_CONVERSATION_FILE_MAX_UPLOAD_BYTES = 200 * 1024 * 1024

export interface DirectUploadContract {
  upload_request_id: string
  method: 'POST'
  url: string
  fields: Record<string, string>
  expires_at: string
}

export interface DirectUploadProgress {
  loaded: number
  percent: number
  total: number
}

export interface DirectUploadMutationOptions {
  onProgress?: (progress: DirectUploadProgress) => void
}

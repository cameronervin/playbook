import type { Event, TransactionEvent } from '@sentry/core'

export const SENTRY_REDACTION = '[REDACTED]'
export const DEFAULT_SENTRY_TRACES_SAMPLE_RATE = 0.1

type SentryEvent = Event | TransactionEvent
type MutableRecord = Record<string, unknown>

const CONTENT_FIELD_NAMES = new Set([
  'answer',
  'body',
  'completion',
  'completions',
  'content',
  'contents',
  'extracted_text',
  'file_contents',
  'input',
  'inputs',
  'model_input',
  'model_inputs',
  'model_output',
  'model_outputs',
  'output',
  'outputs',
  'prompt',
  'prompts',
  'raw_text',
  'response',
  'responses',
  'source_text',
  'source_texts',
  'text',
  'tool_input',
  'tool_inputs',
  'tool_output',
  'tool_outputs',
])

const LOCAL_VARIABLE_FIELD_NAMES = new Set(['local_variables', 'locals', 'vars'])

const SENSITIVE_FIELD_PARTS = [
  'api_key',
  'apikey',
  'authorization',
  'cookie',
  'database_url',
  'db_url',
  'password',
  'passwd',
  'presigned_url',
  'private_key',
  'secret',
  'signature',
  'signed_url',
  'source_uri',
  'token',
]

const RAW_IP_FIELD_NAMES = new Set([
  'cf_connecting_ip',
  'client_ip',
  'forwarded',
  'ip_address',
  'remote_addr',
  'remote_ip',
  'true_client_ip',
  'x_forwarded_for',
  'x_real_ip',
])

const SENSITIVE_HEADERS = new Set([
  'authorization',
  'cookie',
  'forwarded',
  'set-cookie',
  'x-forwarded-for',
  'x-real-ip',
  'cf-connecting-ip',
  'true-client-ip',
])

const BEARER_RE = /\b(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi
const SECRET_TOKEN_RE = /\b(?:sk|pk|rk|key)-[A-Za-z0-9._-]+\b/g
const SENSITIVE_QUERY_RE =
  /(^|[?&;])((?:state|code|token|access_token|refresh_token|id_token|signature|x-amz-signature|x-amz-security-token|x-amz-credential)=)([^&#\s"'<>]+)/gi
const ASSIGNMENT_RE =
  /\b([A-Z0-9_]*(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|DATABASE_URL|DB_URL|AUTHORIZATION|SIGNATURE|ACCESS_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*[:=]\s*)([^,&?\s;}]+)/gi

export function resolveSentryTracesSampleRate(value: string | undefined): number {
  if (value === undefined || value.trim() === '') {
    return DEFAULT_SENTRY_TRACES_SAMPLE_RATE
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return DEFAULT_SENTRY_TRACES_SAMPLE_RATE
  }

  return Math.min(Math.max(parsed, 0), 1)
}

export function scrubSentryEvent<T extends SentryEvent>(event: T): T | null {
  const scrubbed = scrubValue(event) as T
  if (!isRecord(scrubbed)) {
    return null
  }

  delete scrubbed.user
  const request = scrubbed.request
  if (isRecord(request)) {
    scrubRequest(request)
  }
  return scrubbed as T
}

function scrubRequest(request: MutableRecord): void {
  delete request.cookies
  delete request.data
  delete request.env
  delete request.json
  if ('query_string' in request) {
    request.query_string = SENTRY_REDACTION
  }

  const headers = request.headers
  if (!isRecord(headers)) {
    return
  }

  for (const key of Object.keys(headers)) {
    if (SENSITIVE_HEADERS.has(key.toLowerCase())) {
      headers[key] = SENTRY_REDACTION
    }
  }
}

function scrubValue(value: unknown, key?: string): unknown {
  const normalizedKey = normalizeKey(key)
  if (normalizedKey && shouldRedactField(normalizedKey)) {
    return SENTRY_REDACTION
  }
  if (typeof value === 'string') {
    return redactString(value)
  }
  if (Array.isArray(value)) {
    return value.map((item) => scrubValue(item))
  }
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [
        entryKey,
        scrubValue(entryValue, entryKey),
      ]),
    )
  }
  return value
}

function shouldRedactField(normalizedKey: string): boolean {
  return (
    CONTENT_FIELD_NAMES.has(normalizedKey) ||
    LOCAL_VARIABLE_FIELD_NAMES.has(normalizedKey) ||
    RAW_IP_FIELD_NAMES.has(normalizedKey) ||
    normalizedKey.endsWith('_ip') ||
    SENSITIVE_FIELD_PARTS.some((part) => normalizedKey.includes(part))
  )
}

function normalizeKey(key: string | undefined): string {
  return key?.toLowerCase().replaceAll('-', '_') ?? ''
}

function redactString(value: string): string {
  return value
    .replace(BEARER_RE, `$1${SENTRY_REDACTION}`)
    .replace(SENSITIVE_QUERY_RE, `$1$2${SENTRY_REDACTION}`)
    .replace(ASSIGNMENT_RE, `$1${SENTRY_REDACTION}`)
    .replace(SECRET_TOKEN_RE, SENTRY_REDACTION)
}

function isRecord(value: unknown): value is MutableRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

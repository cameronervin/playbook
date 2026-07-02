import { SECURITY_TXT } from '@/src/lib/legalContent'

export function GET() {
  return new Response(SECURITY_TXT, {
    headers: {
      'cache-control': 'public, max-age=3600',
      'content-type': 'text/plain; charset=utf-8',
    },
  })
}

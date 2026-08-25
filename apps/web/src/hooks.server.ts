import type { Handle } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';

const HTML_CACHE_CONTROL = 'no-store';
const ASSET_CACHE_CONTROL = 'public, max-age=31536000, immutable';

function isImmutableAsset(contentType: string): boolean {
  return (
    contentType.startsWith('text/css') ||
    contentType.includes('javascript') ||
    contentType.startsWith('font/') ||
    contentType.startsWith('image/') ||
    contentType.startsWith('application/wasm')
  );
}

export const handle: Handle = async ({ event, resolve }) => {
  const requestId = event.request.headers.get('x-request-id') || randomUUID();
  const startedAt = performance.now();
  const response = await resolve(event);
  const contentType = response.headers.get('content-type') ?? '';
  const durationMs = performance.now() - startedAt;

  response.headers.set('X-Request-ID', requestId);
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('Referrer-Policy', 'same-origin');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Permissions-Policy', 'geolocation=(), camera=(), microphone=()');
  response.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
  response.headers.set('Cross-Origin-Resource-Policy', 'same-origin');
  response.headers.set('X-DNS-Prefetch-Control', 'off');
  response.headers.set('Server-Timing', `app;dur=${durationMs.toFixed(1)}`);

  if (contentType.includes('text/html')) {
    response.headers.set('Cache-Control', HTML_CACHE_CONTROL);
  } else if (isImmutableAsset(contentType)) {
    response.headers.set('Cache-Control', ASSET_CACHE_CONTROL);
  }

  return response;
};

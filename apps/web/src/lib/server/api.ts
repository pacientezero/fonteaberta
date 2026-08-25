export function getApiBaseUrl(): string {
  return process.env.API_INTERNAL_BASE_URL || process.env.PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

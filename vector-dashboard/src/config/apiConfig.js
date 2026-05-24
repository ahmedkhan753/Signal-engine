/**
 * Backend API configuration.
 *
 * Defaults to the local VECTOR API layer (`python api.py` -> :8000).
 * Override without code changes by setting `VITE_API_BASE_URL` in a `.env`
 * file or the shell environment before `npm run dev` / `npm run build`.
 */
const DEFAULT_API_BASE_URL = 'http://localhost:8000'

export const API_BASE_URL =
  (import.meta.env && import.meta.env.VITE_API_BASE_URL) || DEFAULT_API_BASE_URL

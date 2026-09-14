/*
 * Economy constants for UI copy. These mirror backend/config.py defaults;
 * the server is always the source of truth — if the backend overrides these
 * via env vars, the copy here drifts. Acceptable for V1 (frontend.txt §3).
 */
export const ECONOMY = {
  UPLOAD_REWARD: 10,
  DOWNLOAD_COST: 5,
  DAILY_REWARD_CAP: 5,
  MAX_FILE_SIZE_MB: 25,
  MIN_PAGES: 1,
  MAX_PAGES: 500,
} as const

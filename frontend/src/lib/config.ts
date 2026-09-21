export const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const API_BASE = `${BACKEND_URL}/api/v1`;
export const TOKEN_COOKIE = "big_token";

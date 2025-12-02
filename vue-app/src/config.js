// Backend configuration
// Use relative path to avoid CORS issues when deployed via ngrok
// Vite proxy (in vite.config.js) will handle /api requests in development
// In production/ngrok, relative paths work automatically
const BACKEND_URL = ''

// For production with explicit backend URL, uncomment and update:
// const BACKEND_URL = 'https://your-server-domain.com'

export { BACKEND_URL }

// API endpoints
export const API_ENDPOINTS = {
  PARTICIPANTS_STATUS: `${BACKEND_URL}/api/participants/status`,
  PRODUCE_SHAPE: `${BACKEND_URL}/api/produce-shape`,
  FULFILL_ORDERS: `${BACKEND_URL}/api/fulfill-orders`,
  CREATE_TRADE_OFFER: `${BACKEND_URL}/api/create-trade-offer`,
  RESPOND_TRADE_OFFER: `${BACKEND_URL}/api/respond-trade-offer`,
  NEGOTIATE_TRADE_OFFER: `${BACKEND_URL}/api/negotiate-trade-offer`,
  SEND_MESSAGE: `${BACKEND_URL}/api/send-message`,
  GAME_STATE: `${BACKEND_URL}/api/game-state`,
  PARTICIPANT_TRADES: `${BACKEND_URL}/api/participant-trades`,
  MESSAGES: `${BACKEND_URL}/api/messages`,
  PARTICIPANT_MESSAGES: `${BACKEND_URL}/api/participant-messages`,
  AUTH_LOGOUT: `${BACKEND_URL}/api/auth/logout`,
  AUTH_VERIFY: `${BACKEND_URL}/api/auth/verify`,
  PROCESS_COMPLETED_PRODUCTIONS: `${BACKEND_URL}/api/process-completed-productions`,
  AUTH_LOGIN: `${BACKEND_URL}/api/auth/login`
}

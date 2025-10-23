// Backend configuration
// Use a simple approach that works in both development and production
// Change this URL to your server address when deploying
const BACKEND_URL = 'http://localhost:5002' // Default for development

// For production, uncomment and update the line below with your server URL:
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

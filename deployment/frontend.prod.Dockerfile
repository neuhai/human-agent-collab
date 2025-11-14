# Production Frontend Dockerfile - Multi-stage build

# Build stage
FROM node:22-slim AS builder

# Enable Corepack for Yarn
RUN corepack enable

WORKDIR /app

# Copy package files
COPY vue-app/package.json vue-app/yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile --production=false

# Copy source code
COPY vue-app/ .

# Build for production
RUN yarn build

# Production stage - Use Nginx to serve static files
FROM nginx:alpine

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY deployment/nginx.conf /etc/nginx/conf.d/default.conf

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Expose port
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]

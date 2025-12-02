# Frontend Dockerfile
FROM node:22-slim

# Enable Corepack to use Yarn
RUN corepack enable

# Set working directory
WORKDIR /app

# Copy package files
COPY vue-app/package.json vue-app/yarn.lock ./

# Install dependencies using yarn
RUN yarn install --frozen-lockfile

# Copy frontend code
COPY vue-app/ .

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000', (r) => r.statusCode === 200 ? process.exit(0) : process.exit(1))"

# Run development server
CMD ["yarn", "dev", "--host", "0.0.0.0"]

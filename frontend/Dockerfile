FROM node:20-alpine AS build
WORKDIR /app

COPY package.json yarn.lock ./
RUN corepack enable && corepack prepare yarn@1.22.22 --activate && yarn install --frozen-lockfile

COPY . .

# Same-origin in browser (nginx proxies /api and /socket.io)
ARG VITE_BACKEND_URL=
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN yarn build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

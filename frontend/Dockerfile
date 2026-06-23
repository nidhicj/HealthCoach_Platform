# Build context: repo root  (docker build -f frontend/Dockerfile .)
# scripts/ must be present during build — prebuild calls scripts/build-theme.mjs

FROM node:22-alpine AS builder
WORKDIR /repo

COPY scripts/ ./scripts/

COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /repo/frontend
RUN npm ci

COPY frontend/ .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:22-alpine AS runner
ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /repo/frontend/.next/standalone ./
COPY --from=builder /repo/frontend/.next/static ./.next/static
COPY --from=builder /repo/frontend/public ./public

ENV PORT=8080
EXPOSE 8080
CMD ["node", "server.js"]

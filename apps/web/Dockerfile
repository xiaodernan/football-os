# FOOTBALL OS web shell — the Next.js front end.
# Build context: apps/web (this directory).
# Runs the standalone production server on :3210; expects API_INTERNAL_URL (defaults to the edge door).

FROM node:22-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3210 \
    HOSTNAME=0.0.0.0 \
    API_INTERNAL_URL=http://edge:8080

WORKDIR /app

# The standalone output carries its own minimal node_modules; the static assets do not ride along with it.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3210

CMD ["node", "server.js"]

HEALTHCHECK --interval=15s --timeout=5s --retries=12 --start-period=45s \
    CMD wget -qO- http://127.0.0.1:3210/healthz || exit 1

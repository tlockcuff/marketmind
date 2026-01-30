FROM node:20-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app/web
COPY --from=deps /app/node_modules ./node_modules
COPY web/ .
COPY docs/ ../docs/
COPY README.md ../README.md
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/web/.next/standalone ./
COPY --from=builder /app/web/public ./web/public
COPY --from=builder --chown=nextjs:nodejs /app/web/.next/static ./web/.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# standalone nests server under web/ due to turbopack.root
CMD ["node", "web/server.js"]

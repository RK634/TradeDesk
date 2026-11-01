FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./package.json
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# Nginx unprivileged image listens on 8080 and runs as a non-root user.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

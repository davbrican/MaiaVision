FROM node:22-alpine AS build
WORKDIR /src
COPY apps/frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY apps/frontend ./
RUN npm run build
FROM nginx:1.27-alpine
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80

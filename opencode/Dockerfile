FROM node:18-slim

WORKDIR /app

COPY package*.json ./
RUN apt-get update && apt-get install -y curl && npm install --production

COPY server.js .

ENV PORT=8080

EXPOSE 8080

CMD ["node", "server.js"]

FROM node:18-slim

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY server.js .

ENV PORT=8080
ENV GOOGLE_API_KEY=${GOOGLE_API_KEY:-""}

EXPOSE 8080

CMD ["node", "server.js"]

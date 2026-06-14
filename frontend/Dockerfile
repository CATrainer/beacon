# Local development image — runs the Vite dev server with HMR.
# Production frontend is built & served by Vercel (see docs/DEPLOYMENT.md).
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]

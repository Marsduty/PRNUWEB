FROM node:22-alpine

WORKDIR /app

RUN npm config set registry https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

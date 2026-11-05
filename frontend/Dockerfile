FROM node:20-alpine

WORKDIR /app

# Paketdefinitionen kopieren und Abhängigkeiten installieren
COPY package.json ./
RUN npm install

# Quellcode kopieren
COPY . .

EXPOSE 5173

# Vite Entwicklungsserver mit Zugriff außerhalb des Containers (--host)
CMD ["npm", "run", "dev", "--", "--host"]
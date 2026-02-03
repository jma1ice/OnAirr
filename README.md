# OnAirr - Minimal Plex 'Now Playing' Dashboard

## Docker Compose

Here are the steps to get this tool running in your docker instance with Docker Compose
1. Create a folder for OnAirr and move into it
2. In your OnAirr folder, make a new folder named `app`
3. In the `app` folder, copy the contents of the `.env.example` file into a file named `.env`
4. Edit the `.env` file with your server address, X-Plex-Token, and bool for clickable links
5. Back in your OnAirr folder, save the below as `docker-compose.yml`
```yaml
services:
  onairr:
    container_name: onairr
    image: jma1ice/onairr:latest
    restart: unless-stopped
    volumes:
      - ./app/.env:/app/.env
    ports:
      - 2477:2477
```
6. In the terminal of your choice, navigate to your OnAirr directory and run `docker compose up -d`

The dashboard will be available at `localhost:2477`

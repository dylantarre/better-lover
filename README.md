# Better Lover

A FastAPI service that formats tour dates from both text and images using OpenRouter's AI models, with a Discord bot interface.

## Features

- Text input: Format tour dates from text using GPT-4
- Image input: Extract and format tour dates from images using Claude-3
- Consistent output format: MM/DD City, ST @ Venue Name
- Discord bot: Tag the bot with text, images, or URLs

## Requirements

- Docker
- OpenRouter API key
- Discord bot token (optional)

## Setup

1. Create a `.env` file with your API keys:
```
OPENROUTER_API_KEY=your_key_here
DISCORD_TOKEN=your_discord_token_here  # Optional, for Discord bot
API_URL=http://localhost:4545          # URL where the API is running
```

2. Build and run the Docker container:
```bash
docker build -t tour-date-drake .
docker run -p 4545:4545 --env-file .env tour-date-drake
```

The API will be available at http://localhost:4545

## Discord Bot Setup

1. Create a new Discord application at https://discord.com/developers/applications
2. Create a bot for your application and copy the token
3. Add the bot token to your `.env` file
4. Run the bot:
```bash
python bot_runner.py
```

## Discord Bot Usage

Just tag the bot with:
- Tour dates text: `@Better Lover 1/1 LA, CA @ Venue`
- Image attachment: `@Better Lover` + attach image
- Image URL: `@Better Lover https://example.com/tour-dates.jpg`

## API Endpoints

### Format Text
```bash
curl -X POST "http://localhost:4545/format/text" \
     -H "Content-Type: application/json" \
     -d '{"text": "1/1 New York, NY @ Madison Square Garden"}'
```

### Format Image
```bash
curl -X POST "http://localhost:4545/format/image" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@path/to/image.jpg"
```

## Response Format

Both endpoints return JSON in the format:
```json
{
    "formatted_dates": "MM/DD City, ST @ Venue Name\nMM/DD City, ST @ Venue Name"
}
```

## Error Handling

Errors are returned as HTTP status codes with JSON details:
```json
{
    "detail": "Error message"
}
``` 
import os
import discord
from discord import app_commands
import aiohttp
import logging
from dotenv import load_dotenv
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = os.getenv("API_URL", "http://api:4545")
MAX_DISCORD_LENGTH = 1990  # Leave some room for the code block markers
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def split_message(message: str) -> list[str]:
    """Split a message into chunks that fit within Discord's character limit."""
    chunks = []
    current_chunk = ""
    
    for line in message.split('\n'):
        # If adding this line would exceed the limit, start a new chunk
        if len(current_chunk) + len(line) + 1 > MAX_DISCORD_LENGTH:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            current_chunk = current_chunk + '\n' + line if current_chunk else line
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

class BetterLover(discord.Client):
    def __init__(self):
        # Enable all intents we need
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True  # Make sure we can see messages
        intents.guild_messages = True  # For server messages
        intents.dm_messages = True  # For DMs
        intents.guilds = True  # For server info
        super().__init__(intents=intents)

    async def setup_hook(self):
        # No need to sync commands anymore
        pass

    async def on_message(self, message):
        # Add more debug logging
        logger.info(f"Message received from {message.author}: {message.content}")
        logger.info(f"Channel: {message.channel}")
        logger.info(f"Bot mentioned: {self.user.mentioned_in(message)}")

        # Check if bot is mentioned using mentioned_in
        if not self.user.mentioned_in(message):
            logger.info("Bot not mentioned, ignoring")
            return

        # Ignore messages from the bot itself
        if message.author == self.user:
            logger.info("Ignoring message from self")
            return

        logger.info("Bot was mentioned, processing message")
        # Remove both types of mentions
        content = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
        
        if not content and not message.attachments:
            await message.reply("Please provide some tour dates, an image, or an image URL.")
            return

        await message.add_reaction('⏳')  # Show we're processing

        try:
            # Check for image attachments first
            if message.attachments and message.attachments[0].content_type.startswith('image/'):
                await self.process_image(message, message.attachments[0])
            # Then check for URLs
            elif content.startswith(('http://', 'https://')) and any(ext in content.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                await self.process_image_url(message, content)
            # Otherwise process as text
            else:
                await self.process_text(message, content)
        except Exception as e:
            await message.clear_reactions()
            await message.add_reaction('❌')
            await message.reply(f"Error: {str(e)}")

    async def process_text(self, message, text):
        try:
            # First respond that we're working on it
            await message.add_reaction('⏳')
            
            async with aiohttp.ClientSession() as session:
                # Process as regular text
                logger.info(f"Processing text: {text[:100]}...")
                async with session.post(
                    f"{API_URL}/format/text",
                    json={"text": text},
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=aiohttp.ClientTimeout(total=180)  # 3 minute timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        try:
                            error_json = await response.json()
                            error_detail = error_json.get('detail', 'Unknown error')
                        except:
                            error_detail = error_text
                        logger.error(f"API error response: {error_text}")
                        await message.clear_reactions()
                        await message.add_reaction('❌')
                        await message.reply(f"Error: {error_detail}")
                        return
                    
                    result = await response.json()

                formatted_dates = result.get("formatted_dates", "Error: No dates found")
                logger.info(f"Sending formatted response to Discord: {formatted_dates}")
                
                # Split long messages
                chunks = split_message(formatted_dates)
                
                # Send first chunk as initial response
                try:
                    await message.reply(f"```\n{chunks[0]}\n```\n\nPlease double-check all info as Better Lover can make mistakes.")
                except discord.NotFound:
                    logger.error("Initial interaction expired, creating new message")
                    return
                    
                # Send remaining chunks as follow-ups
                if len(chunks) > 1:
                    try:
                        for chunk in chunks[1:]:
                            await message.reply(f"```\n(continued...)\n{chunk}\n```")
                    except discord.NotFound:
                        logger.error("Follow-up interaction expired")
                        return

        except asyncio.TimeoutError:
            logger.error("Request timed out")
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply("Error: Request timed out. Please try again.")
            except discord.NotFound:
                logger.error("Interaction expired during timeout")
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}", exc_info=True)
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply(f"Error: {str(e)}")
            except discord.NotFound:
                logger.error("Interaction expired during error handling")

    async def process_image(self, message, attachment):
        try:
            # First respond that we're working on it
            await message.add_reaction('⏳')
            
            async with aiohttp.ClientSession() as session:
                # Process image
                logger.info(f"Processing image: {attachment.filename}")
                
                # Download the image
                image_data = await attachment.read()
                
                # Send to our API using proper multipart form
                form = aiohttp.FormData()
                form.add_field('file', 
                              image_data,
                              filename=attachment.filename,
                              content_type=attachment.content_type)
                
                async with session.post(
                    f"{API_URL}/format/image",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=180)  # 3 minute timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        try:
                            error_json = await response.json()
                            error_detail = error_json.get('detail', 'Unknown error')
                        except:
                            error_detail = error_text
                        logger.error(f"API error response: {error_text}")
                        await message.clear_reactions()
                        await message.add_reaction('❌')
                        await message.reply(f"Error: {error_detail}")
                        return
                    result = await response.json()
                    logger.info(f"Parsed API response: {result}")

                formatted_dates = result.get("formatted_dates", "Error: No dates found")
                logger.info(f"Sending formatted response to Discord: {formatted_dates}")
                
                # Split long messages
                chunks = split_message(formatted_dates)
                
                # Send first chunk as initial response
                try:
                    await message.reply(f"```\n{chunks[0]}\n```\n\nPlease double-check all info as Better Lover can make mistakes.")
                except discord.NotFound:
                    logger.error("Initial interaction expired, creating new message")
                    return
                    
                # Send remaining chunks as follow-ups
                if len(chunks) > 1:
                    try:
                        for chunk in chunks[1:]:
                            await message.reply(f"```\n(continued...)\n{chunk}\n```")
                    except discord.NotFound:
                        logger.error("Follow-up interaction expired")
                        return

        except asyncio.TimeoutError:
            logger.error("Request timed out")
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply("Error: Request timed out. Please try again.")
            except discord.NotFound:
                logger.error("Interaction expired during timeout")
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}", exc_info=True)
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply(f"Error: {str(e)}")
            except discord.NotFound:
                logger.error("Interaction expired during error handling")

    async def process_image_url(self, message, url):
        try:
            # First respond that we're working on it
            await message.add_reaction('⏳')
            
            async with aiohttp.ClientSession() as session:
                # Download the image from URL
                logger.info(f"Downloading image from URL: {url}")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download image: HTTP {response.status}")
                    
                    # Get content type and filename
                    content_type = response.headers.get('content-type', 'image/jpeg')
                    filename = url.split('/')[-1]
                    
                    # Download the image data
                    image_data = await response.read()
                    
                    # Send to API using the same format as successful image upload
                    form = aiohttp.FormData()
                    form.add_field('file',
                                 image_data,
                                 filename=filename,
                                 content_type=content_type)
                    
                    async with session.post(
                        f"{API_URL}/format/image",
                        data=form,
                        timeout=aiohttp.ClientTimeout(total=180)  # 3 minute timeout
                    ) as api_response:
                        if api_response.status != 200:
                            error_text = await api_response.text()
                            try:
                                error_json = await api_response.json()
                                error_detail = error_json.get('detail', 'Unknown error')
                            except:
                                error_detail = error_text
                            logger.error(f"API error response: {error_text}")
                            await message.clear_reactions()
                            await message.add_reaction('❌')
                            await message.reply(f"Error: {error_detail}")
                            return
                        result = await api_response.json()
                        logger.info(f"Parsed API response: {result}")

                formatted_dates = result.get("formatted_dates", "Error: No dates found")
                logger.info(f"Sending formatted response to Discord: {formatted_dates}")
                
                # Split long messages
                chunks = split_message(formatted_dates)
                
                # Send first chunk as initial response
                try:
                    await message.reply(f"```\n{chunks[0]}\n```\n\nPlease double-check all info as Better Lover can make mistakes.")
                except discord.NotFound:
                    logger.error("Initial interaction expired, creating new message")
                    return
                    
                # Send remaining chunks as follow-ups
                if len(chunks) > 1:
                    try:
                        for chunk in chunks[1:]:
                            await message.reply(f"```\n(continued...)\n{chunk}\n```")
                    except discord.NotFound:
                        logger.error("Follow-up interaction expired")
                        return

        except asyncio.TimeoutError:
            logger.error("Request timed out")
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply("Error: Request timed out. Please try again.")
            except discord.NotFound:
                logger.error("Interaction expired during timeout")
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}", exc_info=True)
            try:
                await message.clear_reactions()
                await message.add_reaction('❌')
                await message.reply(f"Error: {str(e)}")
            except discord.NotFound:
                logger.error("Interaction expired during error handling")

client = BetterLover()

@client.event
async def on_ready():
    try:
        invite_link = discord.utils.oauth_url(
            client.user.id,
            permissions=discord.Permissions(
                send_messages=True,
                read_messages=True,
                attach_files=True,
                read_message_history=True
            )
        )
        logger.info(f"Bot is ready! Logged in as {client.user}")
        logger.info(f"Invite the bot using this link: {invite_link}")
    except Exception as e:
        logger.error(f"Error syncing commands: {str(e)}", exc_info=True)

def run_bot():
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")
    
    client.run(DISCORD_TOKEN) 
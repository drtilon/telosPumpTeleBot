import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables
load_dotenv()

async def get_channel_info():
    """Get channel information including numeric ID"""
    bot_token = os.getenv('BOT_TOKEN')
    channel_username = os.getenv('CHANNEL_ID')  # @telospump
    
    if not bot_token:
        print("❌ BOT_TOKEN not found in .env file")
        return
    
    if not channel_username:
        print("❌ CHANNEL_ID not found in .env file")
        return
    
    try:
        bot = Bot(token=bot_token)
        
        # Get chat info using the username
        chat = await bot.get_chat(channel_username)
        
        print("✅ Channel Information:")
        print(f"   Channel ID: {chat.id}")
        print(f"   Channel Title: {chat.title}")
        print(f"   Channel Type: {chat.type}")
        print(f"   Channel Username: @{chat.username}")
        
        print(f"\n🔧 Update your .env file:")
        print(f"   CHANNEL_ID={chat.id}")
        
    except Exception as e:
        print(f"❌ Error getting channel info: {e}")
        print("Make sure:")
        print("1. Your bot is added to the channel as an admin")
        print("2. The channel username is correct (with @)")
        print("3. Your bot token is valid")

if __name__ == "__main__":
    asyncio.run(get_channel_info())

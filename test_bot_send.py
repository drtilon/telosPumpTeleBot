import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ALERTS_THREAD_ID = os.getenv('ALERTS_THREAD_ID')  # Add this to your .env file

async def test_send_message():
    """Test function to send a message to the Telegram alerts topic"""
    bot = Bot(token=BOT_TOKEN)
    
    print("Testing message sending to alerts topic...")
    print(f"Channel ID: {CHANNEL_ID}")
    print(f"Alerts Thread ID: {ALERTS_THREAD_ID}")
    
    try:
        if not ALERTS_THREAD_ID:
            print("❌ Error: ALERTS_THREAD_ID not found in .env file")
            print("Please add ALERTS_THREAD_ID=your_topic_id to your .env file")
            return
        
        # Send test message to alerts topic only
        message = await bot.send_message(
            chat_id=CHANNEL_ID, 
            text="🚨 Alerts topic test - bot connection successful!",
            message_thread_id=int(ALERTS_THREAD_ID)
        )
        print(f"✅ Message sent to alerts topic successfully! Message ID: {message.message_id}")
        
    except Exception as e:
        print(f"❌ Error sending message to alerts topic: {e}")
        print("💡 Make sure your ALERTS_THREAD_ID is correct and the bot has permissions")

if __name__ == "__main__":
    # Run the async function
    asyncio.run(test_send_message())

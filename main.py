import os
import asyncio
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from web3 import Web3
from web3.providers.rpc import HTTPProvider

# Import our modules
from config_manager import ConfigManager
from admin_handlers import AdminHandlers
from blockchain_monitor import BlockchainMonitor
from telegram_utils import send_telegram_message

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
RPC_URL = os.getenv('RPC_URL')

# Initialize Web3 and configuration
w3 = Web3(HTTPProvider(RPC_URL))
config_manager = ConfigManager()

def setup_bot_application():
    """Setup the Telegram bot application"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Initialize admin handlers
    admin_handlers = AdminHandlers(config_manager, w3)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", admin_handlers.start_command))
    application.add_handler(CommandHandler("admin", admin_handlers.admin_command))
    application.add_handler(CommandHandler("add_token", admin_handlers.add_token_command))
    application.add_handler(CommandHandler("add_tier", admin_handlers.add_tier_command))
    application.add_handler(CommandHandler("edit_tier", admin_handlers.edit_tier_command))
    application.add_handler(CommandHandler("set_tier_video", admin_handlers.set_tier_video_command))
    application.add_handler(CommandHandler("list_videos", admin_handlers.list_videos_command))
    application.add_handler(CallbackQueryHandler(admin_handlers.button_callback))
    
    return application

async def main():
    """Main function to run both bot and monitor"""
    try:
        # Test connection
        if not w3.is_connected():
            print("❌ Failed to connect to RPC endpoint")
            print(f"   RPC URL: {RPC_URL}")
            return
        
        print(f"✅ Connected to RPC: {RPC_URL}")
        print(f"👥 Admin IDs: {os.getenv('ADMIN_IDS')}")
        
        # MST token is now fixed - no need to check configuration
        mst_address = config_manager.get_mst_token_address()
        print(f"🏆 MST Token (fixed): {mst_address}")
        print(f"💰 USD pricing: Enabled (CoinGecko API)")
        print(f"🎬 Video support: Enabled")
        
        # Setup bot application
        application = setup_bot_application()
        
        # Initialize blockchain monitor
        monitor = BlockchainMonitor(w3, config_manager)
        
        print("🤖 Starting Telegram bot...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        print("🔍 Starting buy monitor...")
        # Run monitoring in the background
        monitor_task = asyncio.create_task(monitor.monitor_buys())
        
        # Keep the main coroutine running
        await monitor_task
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        await send_telegram_message("🛑 TelosPump monitor stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        await send_telegram_message(f"❌ Monitor crashed: {str(e)}")
    finally:
        if 'application' in locals():
            await application.stop()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

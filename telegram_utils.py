import os
import requests
import asyncio
from telegram import Bot

# Telegram configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ALERTS_THREAD_ID = os.getenv('ALERTS_THREAD_ID')

# CoinGecko API configuration
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"
MST_USD_PRICE_CACHE = {"price": 0.0, "last_update": 0}
PRICE_CACHE_DURATION = 300  # 5 minutes

async def get_mst_usd_price():
    """Get MST price in USD from CoinGecko API with caching"""
    import time
    
    current_time = time.time()
    
    # Return cached price if it's still valid
    if (current_time - MST_USD_PRICE_CACHE["last_update"]) < PRICE_CACHE_DURATION:
        return MST_USD_PRICE_CACHE["price"]
    
    try:
        params = {
            "ids": "meridian-mst",
            "vs_currencies": "usd"
        }
        
        response = requests.get(COINGECKO_API_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        mst_price = data.get("meridian-mst", {}).get("usd", 0.0)
        
        # Update cache
        MST_USD_PRICE_CACHE["price"] = mst_price
        MST_USD_PRICE_CACHE["last_update"] = current_time
        
        print(f"💰 Updated MST price: ${mst_price:.6f}")
        return mst_price
        
    except Exception as e:
        print(f"❌ Error fetching MST price from CoinGecko: {e}")
        # Return cached price if available, otherwise 0
        return MST_USD_PRICE_CACHE["price"]

async def send_telegram_message(message, video_path=None):
    """Send message to Telegram alerts topic with optional video"""
    try:
        if not BOT_TOKEN:
            print("❌ Error: BOT_TOKEN not configured in .env file")
            return False
            
        if not CHANNEL_ID:
            print("❌ Error: CHANNEL_ID not configured in .env file")
            return False
            
        bot = Bot(token=BOT_TOKEN)
        
        # Determine send function and parameters
        send_params = {
            "chat_id": CHANNEL_ID,
            "parse_mode": 'HTML'
        }
        
        if ALERTS_THREAD_ID:
            send_params["message_thread_id"] = int(ALERTS_THREAD_ID)
        
        # Send video if provided, otherwise send text message
        if video_path and os.path.exists(video_path):
            try:
                with open(video_path, 'rb') as video_file:
                    send_params["video"] = video_file
                    send_params["caption"] = message
                    
                    if ALERTS_THREAD_ID:
                        try:
                            await bot.send_video(**send_params)
                            print(f"✅ Video message sent to thread {ALERTS_THREAD_ID}: {message[:50]}...")
                            return True
                        except Exception as thread_error:
                            print(f"❌ Failed to send video to thread: {thread_error}")
                            # Try without thread
                            del send_params["message_thread_id"]
                            await bot.send_video(**send_params)
                            print(f"✅ Video message sent to main channel: {message[:50]}...")
                            return True
                    else:
                        await bot.send_video(**send_params)
                        print(f"✅ Video message sent: {message[:50]}...")
                        return True
                        
            except Exception as video_error:
                print(f"❌ Failed to send video: {video_error}")
                print("🔄 Falling back to text message...")
                # Fall back to text message if video fails
                video_path = None
        
        # Send text message (either as fallback or primary)
        if not video_path:
            send_params["text"] = message
            
            if ALERTS_THREAD_ID:
                try:
                    await bot.send_message(**send_params)
                    print(f"✅ Message sent to thread {ALERTS_THREAD_ID}: {message[:50]}...")
                    return True
                except Exception as thread_error:
                    print(f"❌ Failed to send to thread: {thread_error}")
                    # Try without thread
                    del send_params["message_thread_id"]
            
            await bot.send_message(**send_params)
            print(f"✅ Message sent: {message[:50]}...")
            return True
        
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        print("💡 Check your configuration:")
        print(f"   BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
        print(f"   CHANNEL_ID: {CHANNEL_ID}")
        print(f"   ALERTS_THREAD_ID: {ALERTS_THREAD_ID}")
        if video_path:
            print(f"   VIDEO_PATH: {video_path} ({'✅' if os.path.exists(video_path) else '❌'})")
        return False

def format_number(number):
    """Format large numbers with appropriate suffixes"""
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.2f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.2f}K"
    else:
        return f"{number:.2f}"

def format_usd(amount):
    """Format USD amounts with appropriate precision"""
    if amount >= 1000:
        return f"{amount:,.0f}"
    elif amount >= 1:
        return f"{amount:.2f}"
    else:
        return f"{amount:.4f}"

async def send_buy_alert(tier_data, token_data, token_amount, mst_amount, buyer_address, tx_hash, block_number):
    """Send a buy alert with all the formatting and video support"""
    try:
        # Get MST price in USD
        mst_usd_price = await get_mst_usd_price()
        usd_value = mst_amount * mst_usd_price if mst_usd_price > 0 else 0
        
        # Format amounts
        formatted_amount = format_number(token_amount)
        formatted_mst = format_number(mst_amount)
        formatted_usd = format_usd(usd_value)
        
        # Create message using the tier template
        message = tier_data["template"].format(
            amount=formatted_amount,
            symbol=token_data['symbol'],
            mst_value=formatted_mst,
            usd_value=formatted_usd,
            buyer_address=buyer_address,
            block_number=block_number,
            tx_hash=tx_hash
        )
        
        # Get video path if configured
        video_path = tier_data.get("video_path", "")
        video_full_path = None
        
        if video_path:
            # Check if it's a relative path (from videos folder) or absolute
            if not os.path.isabs(video_path):
                videos_folder = "videos"  # Default folder
                video_full_path = os.path.join(videos_folder, video_path)
            else:
                video_full_path = video_path
            
            # Verify video file exists
            if not os.path.exists(video_full_path):
                print(f"⚠️ Video file not found: {video_full_path}")
                video_full_path = None
        
        # Send the alert
        success = await send_telegram_message(message, video_full_path)
        
        if success:
            video_info = f" with video ({video_path})" if video_full_path else ""
            print(f"🔔 Buy alert sent{video_info}: {formatted_amount} {token_data['symbol']} (~{formatted_mst} MST, ${formatted_usd})")
        
        return success
        
    except Exception as e:
        print(f"❌ Error sending buy alert: {e}")
        return False

import os
import time
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from web3 import Web3
from web3.providers.rpc import HTTPProvider

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
TOKEN_ADDRESS = Web3.to_checksum_address(os.getenv('TELOSPUMP_CONTRACT'))
LP_ADDRESS = Web3.to_checksum_address(os.getenv('LP_ADDRESS'))
RPC_URL = os.getenv('RPC_URL')

# Set up Web3 with HTTP provider
w3 = Web3(HTTPProvider(RPC_URL))
bot = Bot(token=BOT_TOKEN)

async def send_telegram_message(message):
    """Send message to Telegram alerts topic only"""
    try:
        ALERTS_THREAD_ID = os.getenv('ALERTS_THREAD_ID')
        
        if not ALERTS_THREAD_ID:
            print("❌ Error: ALERTS_THREAD_ID not configured in .env file")
            return
            
        await bot.send_message(
            chat_id=CHANNEL_ID, 
            text=message,
            message_thread_id=int(ALERTS_THREAD_ID)
        )
        print(f"✅ Message sent to alerts: {message[:50]}...")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

async def monitor_buys():
    print("🔍 Starting TelosPump buy monitor...")
    
    # Send startup message
    await send_telegram_message("🤖 TelosPump monitor started!")
    
    # Calculate Transfer event signature
    transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()
    
    # Get the latest block to start monitoring from
    latest_block = w3.eth.get_block('latest')['number']
    print(f"📦 Starting from block: {latest_block}")
    
    while True:
        try:
            # Get current block
            current_block = w3.eth.get_block('latest')['number']
            
            # Create filter for new blocks only
            if current_block > latest_block:
                # Get logs for Transfer events in the new blocks
                logs = w3.eth.get_logs({
                    "address": TOKEN_ADDRESS,
                    "topics": [transfer_event_signature],
                    "fromBlock": latest_block + 1,
                    "toBlock": current_block
                })
                
                for log in logs:
                    tx_hash = log['transactionHash'].hex()
                    
                    # Decode addresses from topics
                    from_address = '0x' + log['topics'][1].hex()[-40:]
                    to_address = '0x' + log['topics'][2].hex()[-40:]
                    
                    # Convert to checksum addresses for comparison
                    from_address_checksum = Web3.to_checksum_address(from_address)
                    to_address_checksum = Web3.to_checksum_address(to_address)
                    
                    # Check if it's a buy (transfer from LP address)
                    if from_address_checksum == LP_ADDRESS:
                        # Get transaction details for more info
                        try:
                            tx = w3.eth.get_transaction(log['transactionHash'])
                            
                            message = (
                                f"🟢 Buy detected!\n"
                                f"Buyer: {to_address_checksum}\n"
                                f"Block: {log['blockNumber']}\n"
                                f"Tx: https://telos.blockscout.com/tx/{tx_hash}"
                            )
                            await send_telegram_message(message)
                            
                        except Exception as tx_error:
                            print(f"❌ Error getting transaction details: {tx_error}")
                
                # Update the latest block
                latest_block = current_block
            
            # Wait before checking again
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            await asyncio.sleep(10)

async def main():
    """Main function to run the monitor"""
    try:
        # Test connection
        if not w3.is_connected():
            print("❌ Failed to connect to RPC endpoint")
            return
        
        print(f"✅ Connected to RPC: {RPC_URL}")
        print(f"🎯 Monitoring token: {TOKEN_ADDRESS}")
        print(f"🏊 LP Address: {LP_ADDRESS}")
        
        # Start monitoring
        await monitor_buys()
        
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        await send_telegram_message("🛑 TelosPump monitor stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        await send_telegram_message(f"❌ Monitor crashed: {str(e)}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

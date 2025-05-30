import asyncio
import requests
from web3 import Web3
from config_manager import ConfigManager
from telegram_utils import send_telegram_message, send_buy_alert, format_number

# ERC20 ABI for getting token info
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# Uniswap V2 Pair ABI for getting reserves
PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"}
        ],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    }
]

class BlockchainMonitor:
    def __init__(self, w3, config_manager: ConfigManager):
        self.w3 = w3
        self.config_manager = config_manager
        # Calculate Transfer event signature
        self.transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()

    async def get_token_price_in_mst(self, token_address, lp_address):
        """Get token price in MST tokens by reading LP reserves with fallback methods"""
        try:
            mst_address = self.config_manager.get_mst_token_address()
            if not mst_address:
                print("❌ MST token not configured")
                return None

            print(f"🔍 Getting price for token {token_address} from LP {lp_address}")
            
            # Method 1: Try standard Uniswap V2 ABI
            try:
                return await self.get_price_standard_v2(token_address, lp_address, mst_address)
            except Exception as e:
                print(f"❌ Standard V2 method failed: {e}")
            
            # Method 2: Try alternative ABI formats
            try:
                return await self.get_price_alternative_abi(token_address, lp_address, mst_address)
            except Exception as e:
                print(f"❌ Alternative ABI method failed: {e}")
            
            # Method 3: Use transaction analysis fallback
            try:
                return await self.get_price_from_transactions(token_address, mst_address)
            except Exception as e:
                print(f"❌ Transaction analysis method failed: {e}")
            
            # Method 4: Use configured fallback rate
            fallback_rate = self.config_manager.get_fallback_mst_rate()
            if fallback_rate > 0:
                print(f"💡 Using fallback rate: 1 token = {fallback_rate} MST")
                return fallback_rate
            
            print("❌ All pricing methods failed")
            return None

        except Exception as e:
            print(f"❌ Error getting token price in MST for {token_address}: {e}")
            return None

    async def get_price_standard_v2(self, token_address, lp_address, mst_address):
        """Standard Uniswap V2 pricing method"""
        # Get LP contract
        lp_contract = self.w3.eth.contract(address=lp_address, abi=PAIR_ABI)
        
        # Get token addresses in the pair
        token0 = lp_contract.functions.token0().call()
        token1 = lp_contract.functions.token1().call()
        print(f"   LP Pair: {token0} / {token1}")
        
        # Get reserves
        reserves = lp_contract.functions.getReserves().call()
        reserve0, reserve1, _ = reserves
        print(f"   Reserves: {reserve0} / {reserve1}")
        
        # Convert addresses to checksum for comparison
        token0_checksum = Web3.to_checksum_address(token0)
        token1_checksum = Web3.to_checksum_address(token1)
        token_address_checksum = Web3.to_checksum_address(token_address)
        mst_address_checksum = Web3.to_checksum_address(mst_address)
        
        print(f"   Looking for token: {token_address_checksum}")
        print(f"   Looking for MST: {mst_address_checksum}")
        
        # Determine which token is which
        token_reserve = 0
        mst_reserve = 0
        
        if token0_checksum == token_address_checksum:
            token_reserve = reserve0
            if token1_checksum == mst_address_checksum:
                mst_reserve = reserve1
                print("   ✅ Found: Token is token0, MST is token1")
            else:
                raise Exception(f"LP pair token1 ({token1_checksum}) is not MST ({mst_address_checksum})")
        elif token1_checksum == token_address_checksum:
            token_reserve = reserve1
            if token0_checksum == mst_address_checksum:
                mst_reserve = reserve0
                print("   ✅ Found: Token is token1, MST is token0")
            else:
                raise Exception(f"LP pair token0 ({token0_checksum}) is not MST ({mst_address_checksum})")
        else:
            raise Exception(f"LP pair does not contain the target token")
        
        if token_reserve == 0 or mst_reserve == 0:
            raise Exception(f"Invalid reserves in LP: token={token_reserve}, mst={mst_reserve}")
        
        # Get token decimals
        try:
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            token_decimals = token_contract.functions.decimals().call()
            mst_decimals = self.config_manager.get_mst_decimals()
            print(f"   Decimals: token={token_decimals}, mst={mst_decimals}")
        except Exception as e:
            print(f"❌ Failed to get token decimals: {e}")
            # Use defaults
            token_decimals = 18
            mst_decimals = 18
        
        # Calculate price (MST per 1 token)
        price_per_token = (mst_reserve / (10 ** mst_decimals)) / (token_reserve / (10 ** token_decimals))
        
        print(f"   💰 Price: 1 token = {price_per_token:.6f} MST")
        return price_per_token

    async def get_price_alternative_abi(self, token_address, lp_address, mst_address):
        """Try alternative ABI formats for different DEX implementations"""
        # Alternative ABI with different function names
        alt_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "reserves",
                "outputs": [
                    {"name": "_reserve0", "type": "uint112"},
                    {"name": "_reserve1", "type": "uint112"},
                    {"name": "_blockTimestampLast", "type": "uint32"}
                ],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "tokenA",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "tokenB",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            }
        ]
        
        lp_contract = self.w3.eth.contract(address=lp_address, abi=alt_abi)
        
        # Try alternative function names
        try:
            token0 = lp_contract.functions.tokenA().call()
            token1 = lp_contract.functions.tokenB().call()
        except:
            # Try other common names
            token0 = lp_contract.functions.token0().call()
            token1 = lp_contract.functions.token1().call()
        
        try:
            reserves = lp_contract.functions.reserves().call()
        except:
            reserves = lp_contract.functions.getReserves().call()
        
        # Continue with standard pricing logic...
        print(f"   Alternative ABI - Pair: {token0} / {token1}")
        print(f"   Alternative ABI - Reserves: {reserves[0]} / {reserves[1]}")
        
        # Similar logic as standard method but using alternative data
        # (Implementation details similar to get_price_standard_v2)
        raise Exception("Alternative ABI method needs implementation based on debug results")

    async def get_price_from_transactions(self, token_address, mst_address):
        """Estimate price by analyzing recent swap transactions"""
        print("🔄 Trying to estimate price from recent transactions...")
        
        # Look for recent Transfer events to find actual swap ratios
        from_block = self.w3.eth.get_block('latest')['number'] - 500  # Last 500 blocks
        
        # Get recent token transfers
        transfer_signature = self.w3.keccak(text="Transfer(address,address,uint256)").hex()
        
        token_logs = self.w3.eth.get_logs({
            "address": token_address,
            "topics": [transfer_signature],
            "fromBlock": from_block,
            "toBlock": "latest"
        })
        
        mst_logs = self.w3.eth.get_logs({
            "address": mst_address,
            "topics": [transfer_signature],
            "fromBlock": from_block,
            "toBlock": "latest"
        })
        
        # Find transactions that have both token and MST transfers (swaps)
        token_txs = {log['transactionHash'].hex(): log for log in token_logs}
        mst_txs = {log['transactionHash'].hex(): log for log in mst_logs}
        
        common_txs = set(token_txs.keys()) & set(mst_txs.keys())
        
        if len(common_txs) > 0:
            print(f"   Found {len(common_txs)} transactions with both tokens")
            
            # Try multiple recent transactions to find a good price estimate
            for recent_tx in reversed(list(common_txs)[-5:]):  # Check last 5 transactions
                try:
                    token_log = token_txs[recent_tx]
                    mst_log = mst_txs[recent_tx]
                    
                    # Decode amounts properly - handle both hex string and bytes
                    # For token amount
                    token_data = token_log['data']
                    if isinstance(token_data, str):
                        if token_data.startswith('0x'):
                            token_amount_wei = int(token_data, 16)
                        else:
                            token_amount_wei = int('0x' + token_data, 16)
                    else:
                        token_amount_wei = int(token_data.hex(), 16)
                    
                    # For MST amount  
                    mst_data = mst_log['data']
                    if isinstance(mst_data, str):
                        if mst_data.startswith('0x'):
                            mst_amount_wei = int(mst_data, 16)
                        else:
                            mst_amount_wei = int('0x' + mst_data, 16)
                    else:
                        mst_amount_wei = int(mst_data.hex(), 16)
                    
                    token_amount = token_amount_wei / (10 ** 18)  # Assume 18 decimals
                    mst_amount = mst_amount_wei / (10 ** 18)
                    
                    if token_amount > 0 and mst_amount > 0:
                        # Estimate price ratio
                        estimated_price = mst_amount / token_amount
                        print(f"   💡 Estimated price from recent tx: 1 token = {estimated_price:.6f} MST")
                        return estimated_price
                        
                except Exception as decode_error:
                    print(f"   ❌ Error decoding transaction data: {decode_error}")
                    # Continue to next transaction
                    pass
        
        raise Exception("Could not estimate price from recent transactions")

    async def get_token_price_via_intermediate(self, token_address, lp_address, intermediate_token):
        """Try to get token price via intermediate token (like TLOS) then convert to MST"""
        try:
            print(f"🔄 Trying to get price via intermediate token: {intermediate_token}")
            
            # For now, use fallback rate
            fallback_rate = self.config_manager.get_fallback_mst_rate()
            print(f"   Using fallback rate: 1 token = {fallback_rate} MST")
            
            if fallback_rate > 0:
                return fallback_rate
            
            # You can implement multi-hop pricing later if needed
            # This would involve finding Token->TLOS->MST or Token->USDT->MST paths
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting price via intermediate token: {e}")
            return None

    async def monitor_buys(self):
        """Monitor token buys across all configured tokens"""
        print("🔍 Starting TelosPump buy monitor (MST-based with USD pricing)...")
        print("🛡️ ONLY BUY DETECTION - Sells will be ignored!")
        
        # Check if MST token is configured (it's fixed now, so this should always pass)
        mst_address = self.config_manager.get_mst_token_address()
        print(f"🏆 MST Token: {mst_address} (fixed)")
        
        # Startup message removed - no need to spam chat on every restart
        print("📢 Monitor ready - Telegram notifications configured")
        
        # Get the latest block to start monitoring from
        latest_block = self.w3.eth.get_block('latest')['number']
        print(f"📦 Starting from block: {latest_block}")
        
        while True:
            try:
                # Reload config to get any updates
                self.config_manager.config = self.config_manager.load_config()
                active_tokens = self.config_manager.get_active_tokens()
                
                if not active_tokens:
                    print("⏸️ No active tokens to monitor, waiting...")
                    await asyncio.sleep(30)
                    continue
                
                # Get current block
                current_block = self.w3.eth.get_block('latest')['number']
                
                # Create filter for new blocks only
                if current_block > latest_block:
                    # Monitor transactions in the new blocks
                    await self.monitor_transactions_in_blocks(latest_block + 1, current_block, active_tokens)
                    
                    # Update the latest block
                    latest_block = current_block
                
                # Wait before checking again
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    async def monitor_transactions_in_blocks(self, from_block, to_block, active_tokens):
        """Monitor transactions in blocks to find token swaps"""
        try:
            mst_address = self.config_manager.get_mst_token_address()
            mst_address_checksum = Web3.to_checksum_address(mst_address)
            
            # Get all blocks in range
            for block_num in range(from_block, to_block + 1):
                try:
                    block = self.w3.eth.get_block(block_num, full_transactions=True)
                    
                    # Check each transaction in the block
                    for tx in block.transactions:
                        # Skip if transaction failed
                        receipt = self.w3.eth.get_transaction_receipt(tx.hash)
                        if receipt.status != 1:
                            continue
                            
                        # Analyze this transaction for token swaps
                        await self.analyze_transaction_for_swaps(tx, receipt, active_tokens, mst_address_checksum)
                        
                except Exception as block_error:
                    print(f"❌ Error processing block {block_num}: {block_error}")
                    continue
                    
        except Exception as e:
            print(f"❌ Error monitoring transactions: {e}")

    async def analyze_transaction_for_swaps(self, tx, receipt, active_tokens, mst_address):
        """Analyze a transaction to find token purchases with MST"""
        try:
            # Get all Transfer events in this transaction
            transfer_events = []
            
            for log in receipt.logs:
                # Check if this is a Transfer event - FIXED: >= 3 instead of == 3
                if (len(log.topics) >= 3 and 
                    log.topics[0].hex() == self.transfer_event_signature):
                    
                    # Decode the transfer
                    from_address = '0x' + log.topics[1].hex()[-40:]
                    to_address = '0x' + log.topics[2].hex()[-40:]
                    
                    # Handle amount data properly - FIXED: avoid double 0x prefix
                    amount_data = log.data
                    if isinstance(amount_data, str):
                        if amount_data.startswith('0x'):
                            amount_hex = amount_data
                        else:
                            amount_hex = '0x' + amount_data
                    else:
                        amount_hex = amount_data.hex()
                        if not amount_hex.startswith('0x'):
                            amount_hex = '0x' + amount_hex
                    
                    try:
                        amount_wei = int(amount_hex, 16)
                    except ValueError:
                        continue
                    
                    transfer_events.append({
                        'token_address': log.address,
                        'from': Web3.to_checksum_address(from_address),
                        'to': Web3.to_checksum_address(to_address),
                        'amount_wei': amount_wei,
                        'tx_hash': tx.hash.hex(),
                        'block_number': receipt.blockNumber
                    })
            
            # Now analyze the transfers to find MST → Token swaps (BUYS ONLY)
            await self.find_mst_token_buys_only(transfer_events, active_tokens, mst_address, tx.hash.hex())
            
        except Exception as e:
            print(f"❌ Error analyzing transaction {tx.hash.hex()}: {e}")

    async def find_mst_token_buys_only(self, transfers, active_tokens, mst_address, tx_hash):
        """Find token purchases - detects both direct and multi-hop swaps - BUYS ONLY"""
        try:
            mst_address_checksum = Web3.to_checksum_address(mst_address)
            
            # Look for any user receiving monitored tokens from LP addresses
            # This catches both direct MST→Token and multi-hop swaps
            for token_address, token_data in active_tokens.items():
                token_address_checksum = Web3.to_checksum_address(token_address)
                lp_address_checksum = Web3.to_checksum_address(token_data['lp_address'])
                
                # Find token transfers FROM the LP address (tokens being bought)
                token_from_lp = [t for t in transfers 
                               if (t['token_address'] == token_address_checksum and 
                                   t['from'] == lp_address_checksum)]
                
                for token_transfer in token_from_lp:
                    buyer_address = token_transfer['to']
                    token_amount_wei = token_transfer['amount_wei']
                    token_amount = token_amount_wei / (10 ** token_data['decimals'])
                    
                    print(f"🔍 Potential Buy: {format_number(token_amount)} {token_data['symbol']} to {buyer_address}")
                    
                    # Check if this is a sell (user sending tokens TO LP)
                    # If the same user also sent tokens to the LP in this tx, it's likely a sell
                    user_sells_to_lp = [t for t in transfers 
                                       if (t['token_address'] == token_address_checksum and 
                                           t['from'] == buyer_address and 
                                           t['to'] == lp_address_checksum)]
                    
                    if user_sells_to_lp:
                        print(f"⚠️ Skipping: User {buyer_address} also sold tokens to LP (likely a sell or arbitrage)")
                        continue
                    
                    # Calculate MST equivalent using current price
                    token_price_mst = await self.get_token_price_in_mst(token_address, token_data['lp_address'])
                    if not token_price_mst:
                        print(f"⚠️ Skipping: Could not get MST price for {token_data['symbol']}")
                        continue
                    
                    mst_equivalent = token_amount * token_price_mst
                    
                    # Filter out very small purchases (likely dust or MEV) 
                    # Set very low threshold to catch almost all transactions
                    if mst_equivalent < 0.01:  # Only filter dust (less than 0.01 MST)
                        print(f"⚠️ Skipping: Too small ({mst_equivalent:.4f} MST equivalent)")
                        continue
                    
                    # Check for router/contract addresses (common patterns)
                    if self.is_likely_router_or_contract(buyer_address):
                        print(f"⚠️ Skipping: Buyer {buyer_address} appears to be a router/contract")
                        continue
                    
                    print(f"✅ Valid Buy: {format_number(token_amount)} {token_data['symbol']} (~{format_number(mst_equivalent)} MST) by {buyer_address}")
                    
                    # Create buy alert
                    await self.create_buy_alert(
                        token_data, 
                        token_amount, 
                        mst_equivalent, 
                        buyer_address,
                        tx_hash, 
                        token_transfer['block_number']
                    )
            
        except Exception as e:
            print(f"❌ Error finding token buys: {e}")

    def is_likely_router_or_contract(self, address):
        """Check if an address is likely a router or contract (not an end user)"""
        try:
            # First, let's be less aggressive about filtering out contracts
            # Many legitimate users interact through contracts/wallets
            
            # Common router addresses on Telos (add more as needed)
            known_routers = [
                "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 Router
                "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106",  # PancakeSwap Router
                "0x2F9bC2C529FaFdc9D8be9F9eF4c82fB6e9c6E1b7",  # Example DEX router
                "0x8888888888888888888888888888888888888888",  # Add actual Telos routers here
                # Add more known router addresses here
            ]
            
            address_checksum = Web3.to_checksum_address(address)
            
            # Check against known routers only
            if address_checksum in [Web3.to_checksum_address(r) for r in known_routers]:
                print(f"   🚫 Known router detected: {address_checksum}")
                return True
            
            # For now, let's not filter out contracts automatically
            # Many users use smart wallets, multisigs, etc.
            
            # Only filter out addresses that have A LOT of code (likely complex contracts)
            try:
                code = self.w3.eth.get_code(address_checksum)
                # If it has a very large amount of code, it's likely a complex contract/router
                if len(code) > 10000:  # More than ~5KB of bytecode
                    print(f"   🚫 Large contract detected: {address_checksum} ({len(code)} bytes)")
                    return True
            except:
                pass  # If we can't check, assume it's a user
            
            # Allow all other addresses (including smart wallets, simple contracts)
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking if {address} is router/contract: {e}")
            return False  # If we can't determine, assume it's a user and allow it

    async def create_buy_alert(self, token_data, token_amount, mst_amount, buyer_address, tx_hash, block_number):
        """Create and send a buy alert with tier-based messaging and video support"""
        try:
            # Get the appropriate message tier based on MST value
            tier_data = self.config_manager.get_message_tier_for_mst(mst_amount)
            
            if not tier_data:
                print(f"❌ No message tier found for MST amount: {mst_amount}")
                return
            
            # Send the buy alert using the tier system
            success = await send_buy_alert(
                tier_data=tier_data,
                token_data=token_data,
                token_amount=token_amount,
                mst_amount=mst_amount,
                buyer_address=buyer_address,
                tx_hash=tx_hash,
                block_number=block_number
            )
            
            if not success:
                print(f"❌ Failed to send buy alert for {token_data['symbol']}")
            
        except Exception as e:
            print(f"❌ Error creating buy alert: {e}")

    async def process_transfer_log(self, log, token_address, token_data):
        """Process a transfer log to check if it's a buy (legacy method for backward compatibility)"""
        try:
            tx_hash = log['transactionHash'].hex()
            
            # Decode addresses from topics
            from_address = '0x' + log['topics'][1].hex()[-40:]
            to_address = '0x' + log['topics'][2].hex()[-40:]
            
            # Decode the amount from the data field
            amount_data = log['data']
            
            # Handle both hex string and bytes object
            if isinstance(amount_data, str):
                # If it's already a hex string
                if amount_data.startswith('0x'):
                    amount_hex = amount_data
                else:
                    amount_hex = '0x' + amount_data
            else:
                # If it's bytes, convert to hex string
                amount_hex = '0x' + amount_data.hex()
            
            # Convert hex to integer
            try:
                amount_wei = int(amount_hex, 16)
            except ValueError as e:
                print(f"❌ Error converting amount hex to int: {e}")
                print(f"   Raw data: {amount_data}")
                print(f"   Processed hex: {amount_hex}")
                return
            
            amount_tokens = amount_wei / (10 ** token_data['decimals'])
            
            # Convert to checksum addresses for comparison
            from_address_checksum = Web3.to_checksum_address(from_address)
            to_address_checksum = Web3.to_checksum_address(to_address)
            lp_address_checksum = Web3.to_checksum_address(token_data['lp_address'])
            
            # Check if it's a buy (transfer from LP address)
            if from_address_checksum == lp_address_checksum:
                # Get token price in MST
                token_price_mst = await self.get_token_price_in_mst(token_address, token_data['lp_address'])
                
                # Calculate MST value
                mst_value = amount_tokens * token_price_mst if token_price_mst else 0
                
                # Skip if we couldn't calculate MST value
                if mst_value <= 0:
                    print(f"⚠️ Skipping buy alert - couldn't calculate MST value for {token_data['symbol']}")
                    return
                
                # Create buy alert with tier support
                await self.create_buy_alert(
                    token_data, 
                    amount_tokens, 
                    mst_value, 
                    to_address_checksum, 
                    tx_hash, 
                    log['blockNumber']
                )
                
        except Exception as e:
            print(f"❌ Error processing transfer log: {e}")
            print(f"   Transaction hash: {log.get('transactionHash', 'Unknown')}")
            print(f"   Block number: {log.get('blockNumber', 'Unknown')}")
            # Print more debug info
            try:
                print(f"   Raw log data: {log.get('data', 'No data')}")
                print(f"   Log topics: {[topic.hex() if hasattr(topic, 'hex') else str(topic) for topic in log.get('topics', [])]}")
            except:
                pass

import os
import json
from web3 import Web3

# Configuration file path
CONFIG_FILE = 'bot_config.json'

# Fixed MST token configuration - no need for users to set this
MST_TOKEN_ADDRESS = "0x568524DA340579887db50Ecf602Cd1BA8451b243"
MST_DECIMALS = 18

# Default configuration with message tiers based on MST amounts (buyer address removed)
DEFAULT_CONFIG = {
    "tokens": {},
    "message_tiers": [
        {
            "min_mst": 0,
            "max_mst": 1000,
            "name": "Small Buy",
            "template": """🟢 <b>{symbol} Small Buy Detected!</b>

💰 <b>Amount:</b> {amount} {symbol}
🏆 <b>MST Value:</b> ~{mst_value} MST
💵 <b>USD Value:</b> ~${usd_value}
📦 <b>Block:</b> {block_number}
🔗 <a href='https://teloscan.io/tx/{tx_hash}'>View Transaction</a>""",
            "video_path": ""  # Optional video file path
        },
        {
            "min_mst": 1000,
            "max_mst": 5000,
            "name": "Medium Buy",
            "template": """🔥 <b>{symbol} MEDIUM BUY ALERT!</b> 🔥

💰 <b>Amount:</b> {amount} {symbol}
🏆 <b>MST Value:</b> ~{mst_value} MST
💵 <b>USD Value:</b> ~${usd_value}
📦 <b>Block:</b> {block_number}
🔗 <a href='https://teloscan.io/tx/{tx_hash}'>View Transaction</a>

🚀 Someone believes in {symbol}! 🚀""",
            "video_path": ""
        },
        {
            "min_mst": 5000,
            "max_mst": 20000,
            "name": "Large Buy",
            "template": """🚨 <b>{symbol} BIG BUY INCOMING!</b> 🚨

💰 <b>Amount:</b> {amount} {symbol}
🏆 <b>MST Value:</b> ~{mst_value} MST
💵 <b>USD Value:</b> ~${usd_value}
📦 <b>Block:</b> {block_number}
🔗 <a href='https://teloscan.io/tx/{tx_hash}'>View Transaction</a>

🔥🔥 {symbol} BULLISH SIGNAL! 🔥🔥
💎 Diamond hands are accumulating {symbol}! 💎""",
            "video_path": ""
        },
        {
            "min_mst": 20000,
            "max_mst": 100000,
            "name": "Whale Buy",
            "template": """🐋 <b>{symbol} WHALE ALERT!</b> 🐋
━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Amount:</b> {amount} {symbol}
🏆 <b>MST Value:</b> ~{mst_value} MST
💵 <b>USD Value:</b> ~${usd_value}
📦 <b>Block:</b> {block_number}
🔗 <a href='https://teloscan.io/tx/{tx_hash}'>View Transaction</a>

🌊🌊 MASSIVE {symbol} WHALE MOVEMENT! 🌊🌊
🚀 {symbol} TO THE MOON! 🚀
💰 Smart money is flowing into {symbol}! 💰""",
            "video_path": ""
        },
        {
            "min_mst": 100000,
            "max_mst": float('inf'),
            "name": "Mega Whale",
            "template": """🚨🐋 <b>{symbol} MEGA WHALE DETECTED!</b> 🐋🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Amount:</b> {amount} {symbol}
🏆 <b>MST Value:</b> ~{mst_value} MST
💵 <b>USD Value:</b> ~${usd_value}
📦 <b>Block:</b> {block_number}
🔗 <a href='https://teloscan.io/tx/{tx_hash}'>View Transaction</a>

🔥🔥🔥 INSANE {symbol} BUY PRESSURE! 🔥🔥🔥
🚀🚀🚀 {symbol} MOON MISSION ACTIVATED! 🚀🚀🚀
💎 INSTITUTIONAL MONEY FLOWING INTO {symbol}! 💎
⚡ THIS IS THE {symbol} SIGNAL WE'VE BEEN WAITING FOR! ⚡""",
            "video_path": ""
        }
    ],
    "fallback_mst_rate": 1.0,  # Fallback conversion rate for tokens without direct MST pairs
    "videos_folder": "videos"  # Folder where video files are stored
}

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
        # Ensure videos folder exists
        videos_folder = self.config.get("videos_folder", "videos")
        if not os.path.exists(videos_folder):
            os.makedirs(videos_folder)
            print(f"📁 Created videos folder: {videos_folder}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Ensure all required keys exist
                    for key in DEFAULT_CONFIG:
                        if key not in config:
                            config[key] = DEFAULT_CONFIG[key]
                    
                    # Update existing tiers to include video_path if missing
                    for tier in config.get("message_tiers", []):
                        if "video_path" not in tier:
                            tier["video_path"] = ""
                    
                    return config
            else:
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    
    def add_token(self, token_address, lp_address, symbol, decimals=18):
        """Add a new token to monitor"""
        token_address = Web3.to_checksum_address(token_address)
        lp_address = Web3.to_checksum_address(lp_address)
        
        self.config["tokens"][token_address] = {
            "lp_address": lp_address,
            "symbol": symbol,
            "decimals": decimals,
            "active": True
        }
        return self.save_config()
    
    def remove_token(self, token_address):
        """Remove a token from monitoring"""
        token_address = Web3.to_checksum_address(token_address)
        if token_address in self.config["tokens"]:
            del self.config["tokens"][token_address]
            return self.save_config()
        return False
    
    def toggle_token(self, token_address):
        """Toggle token active status"""
        token_address = Web3.to_checksum_address(token_address)
        if token_address in self.config["tokens"]:
            self.config["tokens"][token_address]["active"] = not self.config["tokens"][token_address]["active"]
            return self.save_config()
        return False
    
    def add_message_tier(self, min_mst, max_mst, name, template, video_path=""):
        """Add a new message tier"""
        new_tier = {
            "min_mst": min_mst,
            "max_mst": max_mst,
            "name": name,
            "template": template,
            "video_path": video_path
        }
        self.config["message_tiers"].append(new_tier)
        # Sort tiers by min_mst
        self.config["message_tiers"].sort(key=lambda x: x["min_mst"])
        return self.save_config()
    
    def update_message_tier(self, tier_index, min_mst, max_mst, name, template, video_path=""):
        """Update an existing message tier"""
        if 0 <= tier_index < len(self.config["message_tiers"]):
            self.config["message_tiers"][tier_index] = {
                "min_mst": min_mst,
                "max_mst": max_mst,
                "name": name,
                "template": template,
                "video_path": video_path
            }
            # Sort tiers by min_mst
            self.config["message_tiers"].sort(key=lambda x: x["min_mst"])
            return self.save_config()
        return False
    
    def remove_message_tier(self, tier_index):
        """Remove a message tier"""
        if 0 <= tier_index < len(self.config["message_tiers"]):
            del self.config["message_tiers"][tier_index]
            return self.save_config()
        return False
    
    def set_tier_video(self, tier_index, video_path):
        """Set video for a specific tier"""
        if 0 <= tier_index < len(self.config["message_tiers"]):
            self.config["message_tiers"][tier_index]["video_path"] = video_path
            return self.save_config()
        return False
    
    def get_message_tier_for_mst(self, mst_value):
        """Get the appropriate message tier based on MST value"""
        for tier in self.config["message_tiers"]:
            if tier["min_mst"] <= mst_value < tier["max_mst"]:
                return tier
        # Fallback to the last tier if no match found
        return self.config["message_tiers"][-1] if self.config["message_tiers"] else None
    
    def get_active_tokens(self):
        """Get all active tokens"""
        return {addr: data for addr, data in self.config["tokens"].items() if data.get("active", True)}
    
    def get_mst_token_address(self):
        """Get MST token address (fixed)"""
        return MST_TOKEN_ADDRESS
    
    def get_mst_decimals(self):
        """Get MST token decimals (fixed)"""
        return MST_DECIMALS
    
    def set_fallback_mst_rate(self, rate):
        """Set fallback MST conversion rate"""
        self.config["fallback_mst_rate"] = float(rate)
        return self.save_config()
    
    def get_fallback_mst_rate(self):
        """Get fallback MST conversion rate"""
        return self.config.get("fallback_mst_rate", 1.0)
    
    def get_videos_folder(self):
        """Get videos folder path"""
        return self.config.get("videos_folder", "videos")
    
    def list_available_videos(self):
        """List all available video files in the videos folder"""
        videos_folder = self.get_videos_folder()
        if not os.path.exists(videos_folder):
            return []
        
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.gif']
        videos = []
        
        for file in os.listdir(videos_folder):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                videos.append(file)
        
        return sorted(videos)

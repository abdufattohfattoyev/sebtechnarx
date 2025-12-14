# stats_database.py
import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "iphone_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_stats_tables():
    """Statistika uchun jadvallar yaratish"""
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchilar jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            is_registered BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Eski bazalarga phone_number va is_registered ustunlarini qo'shish (migration)
    try:
        c.execute("SELECT phone_number FROM users LIMIT 1")
    except sqlite3.OperationalError:
        print("📞 phone_number ustuni qo'shilmoqda...")
        c.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
        conn.commit()
        print("✅ phone_number ustuni qo'shildi!")

    try:
        c.execute("SELECT is_registered FROM users LIMIT 1")
    except sqlite3.OperationalError:
        print("✅ is_registered ustuni qo'shilmoqda...")
        c.execute("ALTER TABLE users ADD COLUMN is_registered BOOLEAN DEFAULT 0")
        conn.commit()
        print("✅ is_registered ustuni qo'shildi!")

    # Narxlatish tarixi - har bir tugallangan narxlatish jarayoni
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            storage_size TEXT NOT NULL,
            color_name TEXT NOT NULL,
            sim_type TEXT NOT NULL,
            battery_label TEXT NOT NULL,
            has_box INTEGER NOT NULL,
            damage_pct TEXT NOT NULL,
            final_price TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Indekslar tezkorlik uchun
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_user ON price_history(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_model ON price_history(model_name)')

    conn.commit()
    conn.close()
    print("✅ Statistika jadvallari yaratildi")


# Foydalanuvchi funksiyalari
def add_or_update_user(user_id, username=None, first_name=None, last_name=None, phone_number=None):
    """Foydalanuvchini qo'shish yoki yangilash"""
    conn = get_conn()
    c = conn.cursor()

    # Agar phone_number berilmagan bo'lsa, mavjud telefon raqamni saqlash
    if phone_number is None:
        try:
            c.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            if row and row['phone_number']:
                phone_number = row['phone_number']
        except:
            pass

    # is_registered: agar phone_number bor bo'lsa True, aks holda False
    is_registered = 1 if phone_number else 0

    c.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, phone_number, is_registered, last_active)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            phone_number = COALESCE(excluded.phone_number, phone_number),
            is_registered = CASE 
                WHEN excluded.phone_number IS NOT NULL THEN 1 
                ELSE is_registered 
            END,
            last_active = CURRENT_TIMESTAMP
    """, (user_id, username, first_name, last_name, phone_number, is_registered))

    conn.commit()

    # Yangilangan ma'lumotni qaytarish
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()

    return dict(user_data) if user_data else None


def register_user(user_id, phone_number):
    """Foydalanuvchini ro'yxatdan o'tkazish"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        UPDATE users 
        SET phone_number = ?, is_registered = 1, last_active = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (phone_number, user_id))

    conn.commit()

    # Yangilangan ma'lumotni qaytarish
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()

    return dict(user_data) if user_data else None


def is_user_registered(user_id):
    """Foydalanuvchi ro'yxatdan o'tganligini tekshirish"""
    conn = get_conn()
    c = conn.cursor()

    try:
        c.execute("SELECT phone_number, is_registered FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()

        if row:
            # Agar phone_number bor va is_registered True bo'lsa
            return bool(row['phone_number']) and bool(row['is_registered'])
        return False
    except:
        conn.close()
        return False


def get_user_by_telegram_id(user_id):
    """Telegram ID orqali foydalanuvchi ma'lumotlarini olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# Narxlatish tarixi funksiyalari
def save_price_inquiry(user_id, model_name, storage, color, sim, battery, box, damage, price):
    """Tugallangan narxlatishni saqlash"""
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchi ID sini olish
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row:
        conn.close()
        return False

    db_user_id = user_row['id']

    c.execute("""
        INSERT INTO price_history 
        (user_id, model_name, storage_size, color_name, sim_type, 
         battery_label, has_box, damage_pct, final_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (db_user_id, model_name, storage, color, sim, battery, box, damage, price))

    conn.commit()
    conn.close()
    return True


# STATISTIKA FUNKSIYALARI

def get_user_stats(user_id, period='all'):
    """
    Foydalanuvchi statistikasi
    period: 'today', 'week', 'month', 'all'
    """
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchi DB ID sini olish
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row:
        conn.close()
        return None

    db_user_id = user_row['id']

    # Vaqt filtri
    date_filter = ""
    if period == 'today':
        date_filter = f"AND DATE(created_at) = DATE('now')"
    elif period == 'week':
        date_filter = f"AND created_at >= DATE('now', '-7 days')"
    elif period == 'month':
        date_filter = f"AND created_at >= DATE('now', '-30 days')"

    # Umumiy statistika
    c.execute(f"""
        SELECT 
            COUNT(*) as total_inquiries,
            COUNT(DISTINCT model_name) as unique_models,
            COUNT(DISTINCT DATE(created_at)) as active_days
        FROM price_history 
        WHERE user_id = ? {date_filter}
    """, (db_user_id,))

    stats = dict(c.fetchone())

    # Eng ko'p narxlatilgan modellar (TOP 5)
    c.execute(f"""
        SELECT 
            model_name,
            COUNT(*) as count
        FROM price_history 
        WHERE user_id = ? {date_filter}
        GROUP BY model_name
        ORDER BY count DESC
        LIMIT 5
    """, (db_user_id,))

    stats['top_models'] = [dict(row) for row in c.fetchall()]

    conn.close()
    return stats


def get_global_stats(period='all'):
    """
    Umumiy statistika (barcha foydalanuvchilar)
    """
    conn = get_conn()
    c = conn.cursor()

    # Vaqt filtri
    date_filter = ""
    if period == 'today':
        date_filter = f"WHERE DATE(created_at) = DATE('now')"
    elif period == 'week':
        date_filter = f"WHERE created_at >= DATE('now', '-7 days')"
    elif period == 'month':
        date_filter = f"WHERE created_at >= DATE('now', '-30 days')"

    # Umumiy statistika
    c.execute(f"""
        SELECT 
            COUNT(*) as total_inquiries,
            COUNT(DISTINCT user_id) as active_users,
            COUNT(DISTINCT model_name) as unique_models
        FROM price_history 
        {date_filter}
    """)

    stats = dict(c.fetchone())

    # TOP modellar
    c.execute(f"""
        SELECT 
            model_name,
            COUNT(*) as count
        FROM price_history 
        {date_filter}
        GROUP BY model_name
        ORDER BY count DESC
        LIMIT 10
    """)

    stats['top_models'] = [dict(row) for row in c.fetchall()]

    # TOP foydalanuvchilar
    c.execute(f"""
        SELECT 
            u.username,
            u.first_name,
            COUNT(ph.id) as count
        FROM price_history ph
        JOIN users u ON ph.user_id = u.id
        {date_filter}
        GROUP BY ph.user_id
        ORDER BY count DESC
        LIMIT 10
    """)

    stats['top_users'] = [dict(row) for row in c.fetchall()]

    conn.close()
    return stats


def get_all_users():
    """Barcha foydalanuvchilarni olish (admin uchun)"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT 
            user_id,
            username,
            first_name,
            last_name,
            phone_number,
            is_registered,
            created_at,
            last_active
        FROM users
        ORDER BY last_active DESC
    """)

    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users


def get_total_users():
    """Jami foydalanuvchilar soni"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users")
    count = c.fetchone()['count']
    conn.close()
    return count


def get_registered_users_count():
    """Ro'yxatdan o'tgan foydalanuvchilar soni"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users WHERE is_registered = 1")
    count = c.fetchone()['count']
    conn.close()
    return count


def get_active_users(days=7):
    """Faol foydalanuvchilar soni (oxirgi N kun)"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as count 
        FROM users 
        WHERE last_active >= DATE('now', ? || ' days')
    """, (f'-{days}',))
    count = c.fetchone()['count']
    conn.close()
    return count


# Avtomatik ishga tushirish
init_stats_tables()
# utils/db_api/stats_database.py - TO'LIQ VERSIYA
import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "stats.db")


def get_conn():
    """Statistika database ulanishini yaratish"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_stats_tables():
    """Statistika uchun jadvallar yaratish"""
    conn = get_conn()
    c = conn.cursor()

    # USERS jadvali
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

    # PRICE_HISTORY jadvali
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

    # Indekslar
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_user ON price_history(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_price_history_model ON price_history(model_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_registered ON users(is_registered)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(last_active)')

    conn.commit()
    conn.close()
    print("✅ stats.db yaratildi (statistika)")


# ==================== FOYDALANUVCHI FUNKSIYALARI ====================

def add_or_update_user(user_id, username=None, first_name=None, last_name=None, phone_number=None):
    """Foydalanuvchini qo'shish yoki yangilash"""
    conn = get_conn()
    c = conn.cursor()

    if phone_number is None:
        try:
            c.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            if row and row['phone_number']:
                phone_number = row['phone_number']
        except:
            pass

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
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    return dict(user_data) if user_data else None


def is_user_registered(user_id):
    """Foydalanuvchi ro'yxatdan o'tganligini tekshirish"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT phone_number, is_registered FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return bool(row['phone_number']) and bool(row['is_registered'])
        return False
    except:
        return False


def get_user_by_telegram_id(user_id):
    """Telegram ID orqali foydalanuvchi ma'lumotlarini olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    """Barcha foydalanuvchilarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, first_name, last_name, phone_number, 
               is_registered, created_at, last_active
        FROM users
        ORDER BY last_active DESC
    """)
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users


def get_total_users():
    """Jami foydalanuvchilar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM users")
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


def get_registered_users_count():
    """Ro'yxatdan o'tgan foydalanuvchilar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM users WHERE is_registered = 1 AND phone_number IS NOT NULL")
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


def get_active_users(days=7):
    """Faol foydalanuvchilar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE last_active >= datetime('now', ? || ' days')
        """, (f'-{days}',))
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


# ==================== NARXLATISH TARIXI ====================

def save_price_inquiry(user_id, model_name, storage, color, sim, battery, box, damage, price):
    """Tugallangan narxlatishni saqlash"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row:
        conn.close()
        return False

    db_user_id = user_row['id']
    has_box_int = 1 if box == 'Bor' or box == 1 else 0

    c.execute("""
        INSERT INTO price_history 
        (user_id, model_name, storage_size, color_name, sim_type, 
         battery_label, has_box, damage_pct, final_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (db_user_id, model_name, storage, color, sim, battery, has_box_int, damage, price))

    conn.commit()
    conn.close()
    return True


def get_total_price_inquiries():
    """Jami narxlatishlar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM price_history")
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


def get_price_inquiries_by_period(period='today'):
    """Vaqt davri bo'yicha narxlatishlar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()

        if period == 'today':
            date_filter = "WHERE DATE(created_at) = DATE('now')"
        elif period == 'week':
            date_filter = "WHERE created_at >= datetime('now', '-7 days')"
        elif period == 'month':
            date_filter = "WHERE created_at >= datetime('now', '-30 days')"
        else:
            date_filter = ""

        c.execute(f"SELECT COUNT(*) as count FROM price_history {date_filter}")
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


# ==================== STATISTIKA ====================

def get_user_stats(user_id, period='all'):
    """Foydalanuvchi statistikasi"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row:
        conn.close()
        return None

    db_user_id = user_row['id']

    date_filter = ""
    if period == 'today':
        date_filter = "AND DATE(created_at) = DATE('now')"
    elif period == 'week':
        date_filter = "AND created_at >= datetime('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND created_at >= datetime('now', '-30 days')"

    c.execute(f"""
        SELECT 
            COUNT(*) as total_inquiries,
            COUNT(DISTINCT model_name) as unique_models,
            COUNT(DISTINCT DATE(created_at)) as active_days
        FROM price_history 
        WHERE user_id = ? {date_filter}
    """, (db_user_id,))

    stats = dict(c.fetchone())

    c.execute(f"""
        SELECT model_name, COUNT(*) as count
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
    """Umumiy statistika"""
    conn = get_conn()
    c = conn.cursor()

    date_filter = ""
    if period == 'today':
        date_filter = "WHERE DATE(created_at) = DATE('now')"
    elif period == 'week':
        date_filter = "WHERE created_at >= datetime('now', '-7 days')"
    elif period == 'month':
        date_filter = "WHERE created_at >= datetime('now', '-30 days')"

    c.execute(f"""
        SELECT 
            COUNT(*) as total_inquiries,
            COUNT(DISTINCT user_id) as active_users,
            COUNT(DISTINCT model_name) as unique_models
        FROM price_history 
        {date_filter}
    """)

    stats = dict(c.fetchone())

    c.execute(f"""
        SELECT model_name, COUNT(*) as count
        FROM price_history 
        {date_filter}
        GROUP BY model_name
        ORDER BY count DESC
        LIMIT 10
    """)

    stats['top_models'] = [dict(row) for row in c.fetchall()]

    where_clause = date_filter.replace("WHERE", "AND") if date_filter else ""

    c.execute(f"""
        SELECT u.username, u.first_name, COUNT(ph.id) as count
        FROM price_history ph
        JOIN users u ON ph.user_id = u.id
        WHERE 1=1 {where_clause}
        GROUP BY ph.user_id, u.username, u.first_name
        ORDER BY count DESC
        LIMIT 10
    """)

    stats['top_users'] = [dict(row) for row in c.fetchall()]
    conn.close()
    return stats


def get_recent_history(user_id, limit=10):
    """Foydalanuvchining oxirgi narxlatish tarixi"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row:
        conn.close()
        return []

    db_user_id = user_row['id']

    c.execute("""
        SELECT model_name, storage_size, color_name, sim_type,
               battery_label, has_box, damage_pct, final_price,
               datetime(created_at, 'localtime') as created_at
        FROM price_history 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (db_user_id, limit))

    history = [dict(row) for row in c.fetchall()]
    conn.close()
    return history


def get_top_models(limit=10):
    """Eng ko'p narxlatilgan modellar"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT model_name, COUNT(*) as count,
                   COUNT(DISTINCT user_id) as unique_users
            FROM price_history
            GROUP BY model_name
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        models = [dict(row) for row in c.fetchall()]
        conn.close()
        return models
    except:
        return []


def get_recent_registrations(limit=10):
    """So'nggi ro'yxatdan o'tganlar"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT user_id, username, first_name, last_name,
                   phone_number, datetime(created_at, 'localtime') as created_at
            FROM users 
            WHERE is_registered = 1
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        users = [dict(row) for row in c.fetchall()]
        conn.close()
        return users
    except:
        return []


def get_top_active_users(limit=10):
    """Eng faol foydalanuvchilar"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT u.username, u.first_name, u.last_name, u.phone_number,
                   COUNT(ph.id) as request_count
            FROM users u
            JOIN price_history ph ON u.id = ph.user_id
            GROUP BY u.id
            ORDER BY request_count DESC
            LIMIT ?
        """, (limit,))
        users = [dict(row) for row in c.fetchall()]
        conn.close()
        return users
    except:
        return []


# ==================== MODEL STATISTIKASI ====================

def get_today_model_stats():
    """Bugun qaysi modellar necha kishi narxladi"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT model_name,
                   COUNT(DISTINCT user_id) as unique_users,
                   COUNT(*) as total_requests
            FROM price_history 
            WHERE DATE(created_at) = DATE('now')
            GROUP BY model_name
            ORDER BY unique_users DESC, total_requests DESC
        """)
        stats = [dict(row) for row in c.fetchall()]
        conn.close()
        return stats
    except:
        return []


def get_weekly_model_stats():
    """Bu hafta qaysi modellar necha kishi narxladi"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT model_name,
                   COUNT(DISTINCT user_id) as unique_users,
                   COUNT(*) as total_requests
            FROM price_history 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY model_name
            ORDER BY unique_users DESC, total_requests DESC
        """)
        stats = [dict(row) for row in c.fetchall()]
        conn.close()
        return stats
    except:
        return []


def get_monthly_model_stats():
    """Bu oy qaysi modellar necha kishi narxladi"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT model_name,
                   COUNT(DISTINCT user_id) as unique_users,
                   COUNT(*) as total_requests
            FROM price_history 
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY model_name
            ORDER BY unique_users DESC, total_requests DESC
        """)
        stats = [dict(row) for row in c.fetchall()]
        conn.close()
        return stats
    except:
        return []


def get_all_time_model_stats():
    """Barcha vaqt davomida qaysi modellar necha kishi narxladi"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT model_name,
                   COUNT(DISTINCT user_id) as unique_users,
                   COUNT(*) as total_requests
            FROM price_history 
            GROUP BY model_name
            ORDER BY unique_users DESC, total_requests DESC
        """)
        stats = [dict(row) for row in c.fetchall()]
        conn.close()
        return stats
    except:
        return []


def get_today_stats():
    """Bugun uchun umumiy statistika"""
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT COUNT(DISTINCT user_id) as active_users
            FROM price_history 
            WHERE DATE(created_at) = DATE('now')
        """)
        active_users = c.fetchone()['active_users']

        c.execute("""
            SELECT COUNT(*) as total_requests
            FROM price_history 
            WHERE DATE(created_at) = DATE('now')
        """)
        total_requests = c.fetchone()['total_requests']

        c.execute("""
            SELECT COUNT(*) as new_registrations
            FROM users 
            WHERE DATE(created_at) = DATE('now') AND is_registered = 1
        """)
        new_registrations = c.fetchone()['new_registrations']

        conn.close()

        return {
            'active_users': active_users,
            'total_requests': total_requests,
            'new_registrations': new_registrations
        }
    except:
        return {
            'active_users': 0,
            'total_requests': 0,
            'new_registrations': 0
        }


def get_registration_stats():
    """Ro'yxatdan o'tish statistikasi"""
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) as total FROM users")
        total_users = c.fetchone()['total']

        c.execute("SELECT COUNT(*) as registered FROM users WHERE is_registered = 1")
        registered_users = c.fetchone()['registered']

        not_registered = total_users - registered_users

        c.execute("""
            SELECT COUNT(*) as today 
            FROM users 
            WHERE DATE(created_at) = DATE('now') AND is_registered = 1
        """)
        today_registered = c.fetchone()['today']

        c.execute("""
            SELECT COUNT(*) as this_week 
            FROM users 
            WHERE created_at >= datetime('now', '-7 days') AND is_registered = 1
        """)
        week_registered = c.fetchone()['this_week']

        c.execute("""
            SELECT COUNT(*) as this_month 
            FROM users 
            WHERE created_at >= datetime('now', '-30 days') AND is_registered = 1
        """)
        month_registered = c.fetchone()['this_month']

        conn.close()

        return {
            'total_users': total_users,
            'registered_users': registered_users,
            'not_registered': not_registered,
            'today_registered': today_registered,
            'week_registered': week_registered,
            'month_registered': month_registered
        }
    except:
        return {
            'total_users': 0,
            'registered_users': 0,
            'not_registered': 0,
            'today_registered': 0,
            'week_registered': 0,
            'month_registered': 0
        }


def debug_database():
    """Bazani tekshirish"""
    conn = get_conn()
    c = conn.cursor()

    print("\n=== DATABASE DEBUG ===")

    try:
        c.execute("SELECT COUNT(*) as count FROM users")
        users_count = c.fetchone()['count']
        print(f"✅ Users jadvali: {users_count} ta")

        c.execute("SELECT COUNT(*) as count FROM users WHERE is_registered = 1")
        reg_count = c.fetchone()['count']
        print(f"✅ Ro'yxatdan o'tganlar: {reg_count} ta")

        c.execute("""
            SELECT user_id, username, first_name, phone_number, is_registered, 
                   datetime(last_active, 'localtime') as last_active
            FROM users 
            ORDER BY last_active DESC 
            LIMIT 5
        """)
        print("\nSo'nggi 5 ta foydalanuvchi:")
        for row in c.fetchall():
            print(f"  • {row['first_name']} (@{row['username']}) - {row['last_active']}")
    except Exception as e:
        print(f"❌ Users jadvalidagi xato: {e}")

    try:
        c.execute("SELECT COUNT(*) as count FROM price_history")
        history_count = c.fetchone()['count']
        print(f"\n✅ Price history jadvali: {history_count} ta")

        c.execute("""
            SELECT ph.model_name, ph.final_price, 
                   datetime(ph.created_at, 'localtime') as created_at,
                   u.first_name
            FROM price_history ph
            LEFT JOIN users u ON ph.user_id = u.id
            ORDER BY ph.created_at DESC 
            LIMIT 5
        """)
        print("\nSo'nggi 5 ta narxlatish:")
        for row in c.fetchall():
            print(f"  • {row['model_name']} - ${row['final_price']} ({row['first_name']})")
    except Exception as e:
        print(f"❌ Price history jadvalidagi xato: {e}")

    conn.close()
    print("======================\n")


# Avtomatik ishga tushirish
if __name__ != "__main__":
    init_stats_tables()
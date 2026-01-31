# utils/db_api/user_database.py - PostgreSQL TO'LIQ VERSIYA (0 DAN YOZILGAN)
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env faylni yuklash
load_dotenv()

# Database konfiguratsiyasi
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'phones_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '12345678'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}


def get_user_conn():
    """PostgreSQL database ulanishini yaratish"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ User database ga ulanishda xato: {e}")
        raise
    except Exception as e:
        print(f"❌ Kutilmagan xato: {e}")
        raise


def init_user_db():
    """User database yaratish - PostgreSQL"""
    conn = get_user_conn()
    cursor = conn.cursor()

    try:
        print("\n" + "=" * 60)
        print("🚀 PostgreSQL User Database yaratilmoqda...")
        print("=" * 60)

        # ===================== USERS JADVALI =====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                phone_number VARCHAR(20),
                full_name VARCHAR(255),
                username VARCHAR(255),
                free_trials_left INTEGER DEFAULT 5,
                balance INTEGER DEFAULT 0,
                total_pricings INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ USERS jadvali yaratildi")

        # ===================== PRICING_HISTORY JADVALI =====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                telegram_id BIGINT NOT NULL,
                phone_model VARCHAR(255) NOT NULL,
                storage VARCHAR(50),
                color VARCHAR(100),
                battery VARCHAR(50),
                sim_type VARCHAR(50),
                has_box VARCHAR(10),
                damage VARCHAR(255),
                price INTEGER,
                is_free_trial BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ PRICING_HISTORY jadvali yaratildi")

        # ===================== PAYMENT_HISTORY JADVALI =====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                telegram_id BIGINT NOT NULL,
                order_id VARCHAR(255) UNIQUE,
                tariff_name VARCHAR(100),
                amount NUMERIC(10, 2) NOT NULL,
                count INTEGER NOT NULL,
                payment_status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        print("✅ PAYMENT_HISTORY jadvali yaratildi")

        conn.commit()

        # ===================== INDEKSLAR =====================
        print("\n🔄 Indekslar yaratilmoqda...")

        # USERS indekslari
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number) WHERE phone_number IS NOT NULL')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at DESC)')
        print("✅ USERS: 4 ta indeks")

        # PRICING_HISTORY indekslari
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_user ON pricing_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_telegram ON pricing_history(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_created ON pricing_history(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_free ON pricing_history(is_free_trial)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_model ON pricing_history(phone_model)')
        print("✅ PRICING_HISTORY: 5 ta indeks")

        # PAYMENT_HISTORY indekslari
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_user ON payment_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_order ON payment_history(order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_status ON payment_history(payment_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_created ON payment_history(created_at DESC)')
        print("✅ PAYMENT_HISTORY: 4 ta indeks")

        conn.commit()

        print("\n" + "=" * 60)
        print("✅ PostgreSQL user database tayyor!")
        print("✅ Jami 13 ta indeks yaratildi")
        print("=" * 60 + "\n")

        # VACUUM ANALYZE
        try:
            conn.autocommit = True
            cursor.execute("ANALYZE users")
            cursor.execute("ANALYZE pricing_history")
            cursor.execute("ANALYZE payment_history")
            print("✅ Database optimizatsiya qilindi!")
        except Exception as e:
            print(f"⚠️ VACUUM ANALYZE xato (kritik emas): {e}")
        finally:
            conn.autocommit = False

    except Exception as e:
        conn.rollback()
        print(f"❌ Database yaratishda xato: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# ============================================================
# USER BOSHQARUV FUNKSIYALARI
# ============================================================

def create_user(telegram_id, full_name, username=None, phone_number=None):
    """User yaratish yoki yangilash - 5 TA BEPUL URINISH"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Mavjud usermi tekshirish
        cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
        user = cursor.fetchone()

        if user:
            # Mavjud user - faqat ma'lumotlarni yangilash
            cursor.execute("""
                UPDATE users 
                SET full_name = %s, 
                    username = %s, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                RETURNING *
            """, (full_name, username, telegram_id))
            user = cursor.fetchone()
            conn.commit()

            return {
                'success': True,
                'user': dict(user),
                'is_new': False,
                'message': '✅ Xush kelibsiz!'
            }
        else:
            # YANGI user yaratish
            cursor.execute("""
                INSERT INTO users 
                (telegram_id, full_name, username, phone_number, free_trials_left, balance, total_pricings, is_active)
                VALUES (%s, %s, %s, %s, 5, 0, 0, TRUE)
                RETURNING *
            """, (telegram_id, full_name, username, phone_number))
            user = cursor.fetchone()
            conn.commit()

            return {
                'success': True,
                'user': dict(user),
                'is_new': True,
                'message': '🎁 Sizga 5 ta bepul urinish berildi!'
            }

    except psycopg2.IntegrityError:
        conn.rollback()
        # Race condition - qayta tekshirish
        try:
            cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            user = cursor.fetchone()
            if user:
                return {
                    'success': True,
                    'user': dict(user),
                    'is_new': False,
                    'message': '✅ Xush kelibsiz!'
                }
        except:
            pass

        return {'success': False, 'error': 'Database xatosi'}
    except Exception as e:
        conn.rollback()
        print(f"❌ User yaratishda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def get_user(telegram_id):
    """User ma'lumotlarini olish"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
        user = cursor.fetchone()

        if user:
            return {'success': True, 'user': dict(user)}
        else:
            return {'success': False, 'error': 'User topilmadi'}
    except Exception as e:
        print(f"❌ User olishda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def update_phone_number(telegram_id, phone_number):
    """Telefon raqamini yangilash"""
    conn = get_user_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE users 
            SET phone_number = %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = %s
            RETURNING id
        """, (phone_number, telegram_id))

        result = cursor.fetchone()
        conn.commit()

        if result:
            return {'success': True, 'message': '✅ Telefon raqami saqlandi'}
        else:
            return {'success': False, 'error': 'User topilmadi'}
    except Exception as e:
        conn.rollback()
        print(f"❌ Telefon raqamini yangilashda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# NARXLASH FUNKSIYALARI
# ============================================================

def check_can_price(telegram_id):
    """Narxlash imkoniyatini tekshirish"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute("""
            SELECT free_trials_left, phone_number, balance, is_active
            FROM users
            WHERE telegram_id = %s
        """, (telegram_id,))

        user = cursor.fetchone()

        if not user:
            return {
                'success': False,
                'error': 'User topilmadi',
                'can_price': False
            }

        free_trials = int(user['free_trials_left'] or 0)
        phone = user['phone_number']
        balance = int(user['balance'] or 0)
        is_active = user['is_active']

        if not is_active:
            return {
                'success': False,
                'error': '❌ Hisobingiz faol emas',
                'can_price': False
            }

        if not phone:
            return {
                'success': False,
                'error': '📱 Avval telefon raqamingizni kiriting',
                'can_price': False,
                'needs_phone': True
            }

        if free_trials > 0 or balance > 0:
            return {
                'success': True,
                'can_price': True,
                'free_trials_left': free_trials,
                'balance': balance,
                'phone_number': phone
            }
        else:
            return {
                'success': False,
                'error': '💰 Balans yetarli emas',
                'can_price': False,
                'free_trials_left': 0,
                'balance': 0,
                'needs_payment': True
            }

    except Exception as e:
        print(f"❌ Narxlash tekshirishda xato: {e}")
        return {'success': False, 'error': 'Tekshirishda xato', 'can_price': False}
    finally:
        cursor.close()
        conn.close()


def use_pricing(telegram_id, phone_model, storage, color, battery, sim_type, has_box, damage, price):
    """Narxlashni ishlatish - AVVAL BEPUL, KEYIN BALANS"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        conn.autocommit = False

        # User ni lock bilan olish
        cursor.execute("""
            SELECT id, free_trials_left, balance, phone_number, is_active
            FROM users
            WHERE telegram_id = %s
            FOR UPDATE
        """, (telegram_id,))

        user = cursor.fetchone()

        if not user:
            conn.rollback()
            return {'success': False, 'error': 'User topilmadi'}

        user_id = user['id']
        free_trials = int(user['free_trials_left'] or 0)
        balance = int(user['balance'] or 0)
        phone = user['phone_number']
        is_active = user['is_active']

        # Tekshirishlar
        if not is_active:
            conn.rollback()
            return {'success': False, 'error': '❌ Hisobingiz faol emas'}

        if not phone:
            conn.rollback()
            return {'success': False, 'error': '📱 Avval telefon raqamingizni kiriting'}

        if free_trials <= 0 and balance <= 0:
            conn.rollback()
            return {
                'success': False,
                'error': '💰 Balans yetarli emas',
                'needs_payment': True
            }

        # Narxlash turini aniqlash
        is_free_trial = free_trials > 0

        if is_free_trial:
            # Bepul urinishdan
            cursor.execute("""
                UPDATE users 
                SET free_trials_left = free_trials_left - 1,
                    total_pricings = total_pricings + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                RETURNING free_trials_left, balance
            """, (telegram_id,))
        else:
            # Balansdan
            cursor.execute("""
                UPDATE users 
                SET balance = balance - 1,
                    total_pricings = total_pricings + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                RETURNING free_trials_left, balance
            """, (telegram_id,))

        updated = cursor.fetchone()

        # Tarixga yozish
        cursor.execute("""
            INSERT INTO pricing_history 
            (user_id, telegram_id, phone_model, storage, color, battery, sim_type, has_box, damage, price, is_free_trial)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
        user_id, telegram_id, phone_model, storage, color, battery, sim_type, has_box, damage, price, is_free_trial))

        conn.commit()

        return {
            'success': True,
            'free_trials_left': int(updated['free_trials_left']),
            'balance': int(updated['balance']),
            'is_free_trial': is_free_trial,
            'message': '✅ Narx ko\'rildi' + (' (bepul)' if is_free_trial else ' (balansdan)')
        }

    except Exception as e:
        conn.rollback()
        print(f"❌ Narxlashda xato: {e}")
        return {'success': False, 'error': 'Xatolik yuz berdi'}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# BALANS BOSHQARUVI
# ============================================================

def get_user_balance(telegram_id):
    """User balansini olish"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute("""
            SELECT balance, free_trials_left, total_pricings
            FROM users
            WHERE telegram_id = %s
        """, (telegram_id,))

        user = cursor.fetchone()

        if user:
            return {
                'success': True,
                'balance': int(user['balance'] or 0),
                'free_trials_left': int(user['free_trials_left'] or 0),
                'total_pricings': int(user['total_pricings'] or 0)
            }
        else:
            return {
                'success': False,
                'error': 'User topilmadi',
                'balance': 0,
                'free_trials_left': 0
            }
    except Exception as e:
        print(f"❌ Balans olishda xato: {e}")
        return {'success': False, 'error': str(e), 'balance': 0, 'free_trials_left': 0}
    finally:
        cursor.close()
        conn.close()


def add_balance(telegram_id, count):
    """Balans qo'shish"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        conn.autocommit = False

        cursor.execute("""
            UPDATE users 
            SET balance = balance + %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = %s
            RETURNING balance, free_trials_left
        """, (count, telegram_id))

        user = cursor.fetchone()

        if user:
            conn.commit()
            return {
                'success': True,
                'balance': int(user['balance']),
                'free_trials_left': int(user['free_trials_left']),
                'message': f'✅ {count} ta narxlash qo\'shildi'
            }
        else:
            conn.rollback()
            return {'success': False, 'error': 'User topilmadi'}

    except Exception as e:
        conn.rollback()
        print(f"❌ Balans qo'shishda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# TO'LOV FUNKSIYALARI
# ============================================================

def add_payment_record(telegram_id, order_id, tariff_name, amount, count):
    """To'lov yozuvini qo'shish"""
    conn = get_user_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
        user = cursor.fetchone()

        if not user:
            return {'success': False, 'error': 'User topilmadi'}

        user_id = user[0]

        cursor.execute("""
            INSERT INTO payment_history 
            (user_id, telegram_id, order_id, tariff_name, amount, count, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (user_id, telegram_id, order_id, tariff_name, amount, count))

        conn.commit()
        return {'success': True, 'message': '✅ To\'lov yozuvi yaratildi'}
    except psycopg2.IntegrityError:
        conn.rollback()
        return {'success': False, 'error': 'Bu order_id allaqachon mavjud'}
    except Exception as e:
        conn.rollback()
        print(f"❌ To'lov yozuvini qo'shishda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


def complete_payment(order_id, count):
    """To'lovni yakunlash"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        conn.autocommit = False

        cursor.execute("""
            SELECT user_id, telegram_id, count, payment_status
            FROM payment_history 
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        payment = cursor.fetchone()

        if not payment:
            conn.rollback()
            return {'success': False, 'error': 'To\'lov topilmadi'}

        if payment['payment_status'] == 'completed':
            conn.rollback()
            return {'success': False, 'error': 'To\'lov allaqachon bajarilgan'}

        # Balansni yangilash
        cursor.execute("""
            UPDATE users 
            SET balance = balance + %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING balance, free_trials_left
        """, (count, payment['user_id']))

        user = cursor.fetchone()

        # To'lovni yakunlash
        cursor.execute("""
            UPDATE payment_history 
            SET payment_status = 'completed', 
                completed_at = CURRENT_TIMESTAMP
            WHERE order_id = %s
        """, (order_id,))

        conn.commit()

        return {
            'success': True,
            'balance': int(user['balance']),
            'free_trials_left': int(user['free_trials_left']),
            'message': f'✅ {count} ta narxlash qo\'shildi'
        }

    except Exception as e:
        conn.rollback()
        print(f"❌ To'lovni yakunlashda xato: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# TARIX FUNKSIYALARI
# ============================================================

def get_user_history(telegram_id, limit=10):
    """User tarixini olish"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute("""
            SELECT * FROM pricing_history
            WHERE telegram_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (telegram_id, limit))

        rows = cursor.fetchall()
        return {'success': True, 'history': [dict(row) for row in rows]}
    except Exception as e:
        print(f"❌ Tarix olishda xato: {e}")
        return {'success': False, 'error': str(e), 'history': []}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# STATISTIKA FUNKSIYALARI ⭐ YANGI!
# ============================================================

def get_users_statistics():
    """FOYDALANUVCHILAR STATISTIKASI - Kunlik, Oylik, Jami, Aktiv"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        stats = {}

        # ========== 1. JAMI FOYDALANUVCHILAR ==========
        cursor.execute("SELECT COUNT(*) as count FROM users")
        stats['total_users'] = cursor.fetchone()['count'] or 0

        # ========== 2. JAMI AKTIV FOYDALANUVCHILAR ==========
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
        stats['total_active_users'] = cursor.fetchone()['count'] or 0

        # ========== 3. JAMI AKTIV EMAS FOYDALANUVCHILAR ==========
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = FALSE")
        stats['total_inactive_users'] = cursor.fetchone()['count'] or 0

        # ========== 4. BUGUNGI YANGI FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        stats['today_new_users'] = cursor.fetchone()['count'] or 0

        # ========== 5. BUGUNGI AKTIV FOYDALANUVCHILAR (narxlash qilganlar) ==========
        cursor.execute("""
            SELECT COUNT(DISTINCT telegram_id) as count
            FROM pricing_history
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        stats['today_active_users'] = cursor.fetchone()['count'] or 0

        # ========== 6. OYLIK YANGI FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['month_new_users'] = cursor.fetchone()['count'] or 0

        # ========== 7. OYLIK AKTIV FOYDALANUVCHILAR (narxlash qilganlar) ==========
        cursor.execute("""
            SELECT COUNT(DISTINCT telegram_id) as count
            FROM pricing_history
            WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['month_active_users'] = cursor.fetchone()['count'] or 0

        # ========== 8. TELEFON RAQAMI BOR FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE phone_number IS NOT NULL
        """)
        stats['users_with_phone'] = cursor.fetchone()['count'] or 0

        # ========== 9. BALANS BOR FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE balance > 0
        """)
        stats['users_with_balance'] = cursor.fetchone()['count'] or 0

        # ========== 10. BEPUL URINISH BOR FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE free_trials_left > 0
        """)
        stats['users_with_free_trials'] = cursor.fetchone()['count'] or 0

        # ========== 11. FOIZLAR ==========
        if stats['total_users'] > 0:
            stats['active_percentage'] = round((stats['total_active_users'] / stats['total_users']) * 100, 1)
            stats['phone_percentage'] = round((stats['users_with_phone'] / stats['total_users']) * 100, 1)
        else:
            stats['active_percentage'] = 0
            stats['phone_percentage'] = 0

        return {
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"❌ Foydalanuvchilar statistikasini olishda xato: {e}")
        return {
            'success': False,
            'error': str(e),
            'stats': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    finally:
        cursor.close()
        conn.close()


def get_detailed_users_statistics():
    """BATAFSIL FOYDALANUVCHILAR STATISTIKASI"""
    conn = get_user_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        stats = {}

        # Asosiy statistikani olish
        basic_stats = get_users_statistics()
        if basic_stats['success']:
            stats.update(basic_stats['stats'])

        # ========== HAFTALIK STATISTIKA ==========
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        stats['week_new_users'] = cursor.fetchone()['count'] or 0

        cursor.execute("""
            SELECT COUNT(DISTINCT telegram_id) as count
            FROM pricing_history
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        stats['week_active_users'] = cursor.fetchone()['count'] or 0

        # ========== TOP 10 AKTIV FOYDALANUVCHILAR ==========
        cursor.execute("""
            SELECT 
                u.telegram_id,
                u.full_name,
                u.username,
                u.phone_number,
                u.balance,
                u.free_trials_left,
                u.total_pricings as pricing_count,
                u.created_at
            FROM users u
            WHERE u.is_active = TRUE
            ORDER BY u.total_pricings DESC, u.created_at DESC
            LIMIT 10
        """)
        stats['top_users'] = [dict(row) for row in cursor.fetchall()]

        # ========== KUNLIK TREND (oxirgi 7 kun) ==========
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as new_users
            FROM users
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)
        stats['daily_trend'] = [dict(row) for row in cursor.fetchall()]

        # ========== JAMI NARXLASHLAR ==========
        cursor.execute("SELECT COUNT(*) as count FROM pricing_history")
        stats['total_pricings'] = cursor.fetchone()['count'] or 0

        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM pricing_history 
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        stats['today_pricings'] = cursor.fetchone()['count'] or 0

        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM pricing_history 
            WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['month_pricings'] = cursor.fetchone()['count'] or 0

        # ========== BEPUL VS PULLIK NARXLASHLAR ==========
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN is_free_trial = TRUE THEN 1 END) as free_count,
                COUNT(CASE WHEN is_free_trial = FALSE THEN 1 END) as paid_count
            FROM pricing_history
        """)
        ratio = cursor.fetchone()
        stats['free_pricings'] = ratio['free_count'] or 0
        stats['paid_pricings'] = ratio['paid_count'] or 0

        # ========== UMUMIY BALANS VA BEPUL URINISHLAR ==========
        cursor.execute("""
            SELECT 
                COALESCE(SUM(balance), 0) as total_balance,
                COALESCE(SUM(free_trials_left), 0) as total_free_trials
            FROM users
        """)
        totals = cursor.fetchone()
        stats['total_balance'] = int(totals['total_balance'])
        stats['total_free_trials'] = int(totals['total_free_trials'])

        # ========== TO'LOVLAR STATISTIKASI ==========
        cursor.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(CASE WHEN payment_status = 'completed' THEN 1 END) as completed_payments,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_payments
            FROM payment_history
        """)
        payments = cursor.fetchone()
        stats['total_payments'] = payments['total_payments'] or 0
        stats['total_paid_amount'] = float(payments['total_amount'] or 0)
        stats['completed_payments'] = payments['completed_payments'] or 0
        stats['pending_payments'] = payments['pending_payments'] or 0

        # ========== ENG KO'P NARXLANAYOTGAN TELEFONLAR ==========
        cursor.execute("""
            SELECT 
                phone_model,
                COUNT(*) as count
            FROM pricing_history
            WHERE phone_model IS NOT NULL AND phone_model != ''
            GROUP BY phone_model
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_phone_models'] = [dict(row) for row in cursor.fetchall()]

        return {
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"❌ Batafsil statistikani olishda xato: {e}")
        return {
            'success': False,
            'error': str(e),
            'stats': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    finally:
        cursor.close()
        conn.close()


def get_all_users_count():
    """Jami userlar soni (aktiv)"""
    conn = get_user_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        return cursor.fetchone()[0] or 0
    except:
        return 0
    finally:
        cursor.close()
        conn.close()


def get_total_pricings():
    """Jami narxlashlar soni"""
    conn = get_user_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM pricing_history")
        return cursor.fetchone()[0] or 0
    except:
        return 0
    finally:
        cursor.close()
        conn.close()


# ============================================================
# TEST FUNKSIYASI
# ============================================================

def test_user_connection():
    """PostgreSQL ulanishini tekshirish"""
    try:
        conn = get_user_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL user database ga muvaffaqiyatli ulandi!")
        print(f"📊 Versiya: {version}")

        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('users', 'pricing_history', 'payment_history')
        """)
        tables = cursor.fetchall()
        print(f"📋 Mavjud jadvallar: {[t[0] for t in tables]}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ulanishda xato: {e}")
        return False


# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    if test_user_connection():
        init_user_db()
        print("\n" + "=" * 60)
        print("✅ PostgreSQL user database to'liq tayyor!")
        print("=" * 60)
        print("\n📊 MAVJUD FUNKSIYALAR:")
        print("\n🔹 USER BOSHQARUV:")
        print("   - create_user()")
        print("   - get_user()")
        print("   - update_phone_number()")
        print("\n🔹 NARXLASH:")
        print("   - check_can_price()")
        print("   - use_pricing()")
        print("\n🔹 BALANS:")
        print("   - get_user_balance()")
        print("   - add_balance()")
        print("\n🔹 TO'LOVLAR:")
        print("   - add_payment_record()")
        print("   - complete_payment()")
        print("\n🔹 TARIX:")
        print("   - get_user_history()")
        print("\n🔹 STATISTIKA: ⭐")
        print("   - get_users_statistics()")
        print("   - get_detailed_users_statistics()")
        print("   - get_all_users_count()")
        print("   - get_total_pricings()")
        print("\n" + "=" * 60 + "\n")
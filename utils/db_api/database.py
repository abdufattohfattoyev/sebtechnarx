# utils/db_api/database.py - TO'LIQ VERSIYA
import sqlite3
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "phones.db")


def get_conn():
    """Database ulanishini yaratish"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Asosiy database yaratish - NARXLAR"""
    conn = get_conn()
    c = conn.cursor()

    # MODELS jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            order_num INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # STORAGES jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS storages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            size TEXT NOT NULL,
            price_difference REAL DEFAULT 0,
            is_standard BOOLEAN DEFAULT 0,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE,
            UNIQUE(model_id, size)
        )
    ''')

    # COLORS jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            name TEXT NOT NULL,
            color_type TEXT DEFAULT 'standard',
            price_difference REAL DEFAULT 0,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE,
            UNIQUE(model_id, name)
        )
    ''')

    # BATTERIES jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS batteries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            label TEXT NOT NULL,
            min_percent INTEGER DEFAULT 100,
            max_percent INTEGER DEFAULT 100,
            price_difference REAL DEFAULT 0,
            is_standard BOOLEAN DEFAULT 1,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE,
            UNIQUE(model_id, label)
        )
    ''')

    # SIM_TYPES jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS sim_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            type TEXT NOT NULL,
            price_difference REAL DEFAULT 0,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE,
            UNIQUE(model_id, type)
        )
    ''')

    # PARTS jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            part_name TEXT NOT NULL,
            price_difference REAL DEFAULT 0,
            UNIQUE(model_id, part_name),
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE
        )
    ''')

    # PRICES jadvali
    c.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            storage_size TEXT NOT NULL,
            color_name TEXT DEFAULT '',
            sim_type TEXT DEFAULT 'physical',
            battery_label TEXT DEFAULT '100%',
            has_box BOOLEAN DEFAULT 1,
            damage_pct TEXT DEFAULT 'Yangi',
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE,
            UNIQUE(model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct)
        )
    ''')

    # Indekslar
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_model ON prices(model_id)')
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_prices_lookup ON prices(model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_models_active ON models(is_active)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_storages_model ON storages(model_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_colors_model ON colors(model_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_batteries_model ON batteries(model_id)')

    conn.commit()
    conn.close()
    print("✅ phones.db yaratildi (narxlar)")


# ============= NORMALIZE FUNKSIYALARI =============

def normalize_damage_format(damage_text):
    """Damage textini normallashtirish - Bot formatiga"""
    if not damage_text:
        return "Yangi"

    damage_text = str(damage_text).strip()

    # Bo'sh yoki Yangi
    if damage_text.lower() in ["yangi", "none", "nan", ""]:
        return "Yangi"

    # Bo'shliqlarni tozalash
    damage_text = damage_text.replace('  ', ' ')
    damage_text = damage_text.replace(' + ', '+')
    damage_text = damage_text.replace(' +', '+')
    damage_text = damage_text.replace('+ ', '+')
    damage_text = damage_text.replace(', ', '+')

    # Mapping: har qanday format -> bot format (lowercase)
    part_mapping = {
        # Batareyka
        'batareyka': 'battery', 'batareya': 'battery', 'battery': 'battery',
        'батарея': 'battery', 'аккумулятор': 'battery',

        # Krishka
        'krishka': 'back_cover', 'back_cover': 'back_cover', 'back cover': 'back_cover',
        'backcover': 'back_cover', 'кришка': 'back_cover',

        # Face ID
        'face id': 'face_id', 'faceid': 'face_id', 'face_id': 'face_id',

        # Oyna
        'oyna': 'glass', 'glass': 'glass', 'ойна': 'glass', 'стекло': 'glass',

        # Ekran
        'ekran': 'screen', 'screen': 'screen', 'экран': 'screen',

        # Kamera
        'kamera': 'camera', 'camera': 'camera', 'камера': 'camera',

        # Qirilgan
        'qirilgan': 'broken', 'broken': 'broken', 'разбит': 'broken',

        # Korpus
        'korpus': 'body', 'body': 'body', 'корпус': 'body',
    }

    # Split qilish
    if '+' in damage_text:
        parts = [p.strip() for p in damage_text.split('+')]
    else:
        parts = [damage_text]

    # Normalize
    normalized_parts = []
    for part in parts:
        part_lower = part.lower().strip()

        if not part_lower:
            continue

        # Mappingdan topish
        if part_lower in part_mapping:
            normalized_parts.append(part_mapping[part_lower])
        else:
            # Agar topilmasa, original nomni saqlaymiz
            normalized_parts.append(part_lower)

    if not normalized_parts:
        return "Yangi"

    # Sort (consistency uchun)
    normalized_parts.sort()

    return '+'.join(normalized_parts)


def normalize_for_search(damage_text):
    """Qidirish uchun damage textini normallashtirish"""
    if not damage_text:
        return "yangi"

    damage_text = str(damage_text).strip()

    if damage_text.lower() in ["yangi", "none", "nan", ""]:
        return "yangi"

    # Normalize qilamiz
    normalized = normalize_damage_format(damage_text)

    # Agar "Yangi" bo'lsa
    if normalized == "Yangi":
        return "yangi"

    # Lowercase
    return normalized.lower()


# ===================== MODEL FUNKSIYALARI =====================

def get_models():
    """Barcha faol modellarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM models WHERE is_active = 1 ORDER BY order_num, name")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_model(model_id):
    """Bitta modelni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM models WHERE id = ?", (model_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def add_model(name, order_num=0):
    """Model qo'shish"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO models (name, order_num) VALUES (?, ?)", (name, order_num))
        c.execute("SELECT id FROM models WHERE name = ?", (name,))
        row = c.fetchone()
        model_id = row['id'] if row else None
        conn.commit()
        return model_id
    except Exception as e:
        print(f"Model qo'shishda xato: {e}")
        return None
    finally:
        conn.close()


# ===================== STORAGE FUNKSIYALARI =====================

def get_storages(model_id):
    """Model uchun barcha xotiralarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM storages WHERE model_id = ? ORDER BY size", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_storage(model_id, size):
    """Xotira qo'shish"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO storages (model_id, size) VALUES (?, ?)", (model_id, size))
        conn.commit()
        return True
    except Exception as e:
        print(f"Xotira qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


# ===================== COLOR FUNKSIYALARI =====================

def get_colors(model_id):
    """Model uchun barcha ranglarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM colors WHERE model_id = ? ORDER BY name", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows] if rows else [{"name": "Standart"}]


def add_color(model_id, name):
    """Rang qo'shish"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO colors (model_id, name) VALUES (?, ?)", (model_id, name))
        conn.commit()
        return True
    except Exception as e:
        print(f"Rang qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


# ===================== BATTERY FUNKSIYALARI =====================

def get_batteries(model_id):
    """Model uchun barcha batareyalarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM batteries WHERE model_id = ? ORDER BY min_percent DESC", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows] if rows else [{"label": "100%"}]


def add_battery(model_id, label):
    """Batareya qo'shish"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO batteries (model_id, label) VALUES (?, ?)", (model_id, label))
        conn.commit()
        return True
    except Exception as e:
        print(f"Batareya qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


# ===================== SIM TYPE FUNKSIYALARI =====================

def get_sim_types(model_id):
    """Model uchun SIM turlarini olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM sim_types WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    types = [dict(row)['type'] for row in rows]
    return [{"type": t} for t in types] if types else [{"type": "physical"}]


def add_sim_type(model_id, sim_type):
    """SIM turi qo'shish"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO sim_types (model_id, type) VALUES (?, ?)", (model_id, sim_type))
        conn.commit()
        return True
    except Exception as e:
        print(f"SIM turi qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


# ===================== PARTS FUNKSIYALARI =====================

def get_parts_for_model(model_id):
    """Model uchun alohida qismlarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT part_name FROM parts WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row)['part_name'] for row in rows]


def add_part(model_id, part_name):
    """Alohida qism qo'shish - bot formatida"""
    conn = get_conn()
    c = conn.cursor()
    try:
        # Normalize qilamiz (bot formatiga)
        normalized_part = normalize_damage_format(part_name)
        c.execute("INSERT OR IGNORE INTO parts (model_id, part_name) VALUES (?, ?)", (model_id, normalized_part))
        conn.commit()
        return True
    except Exception as e:
        print(f"Qism qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


# ===================== PRICE FUNKSIYALARI =====================

def get_price(model_id, storage, color, sim_type, battery, has_box, damage):
    """Narxni olish - DEBUG VERSION"""
    conn = get_conn()
    c = conn.cursor()

    # Color to'g'rilash
    color_name = color if color and color != "Standart" else ""

    # Box holati
    has_box_int = 1 if has_box == "Bor" or has_box == True else 0

    # Damage ni normallashtirish
    damage_pct = str(damage).strip()
    if not damage_pct or damage_pct.lower() in ["yangi", "none", "nan"]:
        damage_pct = "Yangi"
    else:
        damage_pct = normalize_damage_format(damage_pct)

    # Qidirish formati
    search_damage = normalize_for_search(damage_pct)

    # ANIQ QIDIRISH
    c.execute("""
        SELECT price, damage_pct FROM prices 
        WHERE model_id = ? 
        AND storage_size = ? 
        AND color_name = ? 
        AND sim_type = ? 
        AND battery_label = ? 
        AND has_box = ?
    """, (model_id, storage, color_name, sim_type, battery, has_box_int))

    matching_rows = c.fetchall()

    if matching_rows:
        for row in matching_rows:
            db_damage = row['damage_pct']
            normalized_db_damage = normalize_for_search(db_damage)

            if normalized_db_damage == search_damage:
                conn.close()
                return row['price']

    conn.close()
    return None


def get_prices_for_model(model_id):
    """Model uchun barcha narxlarni olish"""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM prices 
        WHERE model_id=? 
        ORDER BY price DESC 
        LIMIT 100
    """, (model_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_total_prices_count():
    """Bazadagi jami narxlar soni"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM prices")
        count = c.fetchone()['count']
        conn.close()
        return count
    except:
        return 0


def add_price_record(model_id, storage, color, sim_type, battery, has_box, damage, price):
    """Narxni qo'shish - damage ni bot formatida saqlash"""
    conn = get_conn()
    c = conn.cursor()
    try:
        color_name = color if color and color != "Standart" else ""

        # Damage ni normallashtirish (bot formatiga)
        damage = str(damage).strip()
        if not damage or damage.lower() in ['yangi', 'nan', 'none']:
            damage_pct = "Yangi"
        else:
            damage_pct = normalize_damage_format(damage)

        # Box ni int ga o'tkazish
        has_box_int = 1 if has_box == "Bor" or has_box == True else 0

        c.execute("""
            INSERT OR REPLACE INTO prices 
            (model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct, price, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (model_id, storage, color_name, sim_type, battery, has_box_int, damage_pct, price, datetime.now()))

        conn.commit()
        return True
    except Exception as e:
        print(f"Narx qo'shishda xato: {e}")
        return False
    finally:
        conn.close()


def clear_all_prices():
    """Narxlarni tozalash"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM prices")
        c.execute("DELETE FROM parts")
        conn.commit()
        return True
    except Exception as e:
        print(f"Narxlarni tozalashda xato: {e}")
        return False
    finally:
        conn.close()



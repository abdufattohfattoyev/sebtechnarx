import sqlite3
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "iphone_bot.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Models
    c.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            order_num INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Storages
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

    # Colors
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

    # Batteries
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

    # SIM turlari
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

    # Replaced parts (alohida qismlar uchun jadval)
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

    # Prices - Asosiy jadval
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

    # Indexlar
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_model ON prices(model_id)')
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_prices_lookup ON prices(model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct)')

    conn.commit()
    conn.close()


# ============= NORMALIZE FUNKSIYALARI - TO'G'RILANGAN =============

def normalize_damage_format(damage_text):
    """
    Damage textini normallashtirish - Bot formatiga
    Input: har qanday format
    Output: bot formati (battery, screen, glass, body, etc.)
    """
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
    """
    Qidirish uchun damage textini normallashtirish
    """
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


# ===================== ASOSIY FUNKSIYALAR =====================

def get_models():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM models WHERE is_active = 1 ORDER BY order_num, name")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_storages(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT size FROM storages WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_colors(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name FROM colors WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows] if rows else [{"name": "Standart"}]


def get_batteries(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT label FROM batteries WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows] if rows else [{"label": "100%"}]


def get_sim_types(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT type FROM sim_types WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    types = [dict(row)['type'] for row in rows]
    return [{"type": t} for t in types] if types else [{"type": "physical"}]


def get_parts_for_model(model_id):
    """Model uchun alohida qismlarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT part_name FROM parts WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row)['part_name'] for row in rows]


def get_price(model_id, storage, color, sim_type, battery, has_box, damage):
    """
    ⚡ SUPER DEBUG VERSION - aniq qidirish
    """
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

    print(f"\n{'=' * 70}")
    print(f"🔍 GET_PRICE DEBUG:")
    print(f"{'=' * 70}")
    print(f"📥 INPUT:")
    print(f"   Model ID: {model_id}")
    print(f"   Storage: {storage}")
    print(f"   Color: '{color}' → '{color_name}'")
    print(f"   SIM: {sim_type}")
    print(f"   Battery: {battery}")
    print(f"   Has Box: {has_box} → {has_box_int}")
    print(f"   Damage: '{damage}' → normalized: '{damage_pct}' → search: '{search_damage}'")

    # 1. BAZADAGI BARCHA VARIANTLARNI KO'RISH
    print(f"\n📊 BAZADAGI BARCHA VARIANTLAR (model={model_id}):")
    c.execute("""
        SELECT id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct, price
        FROM prices 
        WHERE model_id = ?
        LIMIT 10
    """, (model_id,))

    all_in_db = c.fetchall()
    if all_in_db:
        for row in all_in_db:
            print(f"   ID={row['id']}: storage={row['storage_size']}, color='{row['color_name']}', "
                  f"sim={row['sim_type']}, battery={row['battery_label']}, "
                  f"box={row['has_box']}, damage='{row['damage_pct']}', price=${row['price']}")
    else:
        print("   ❌ BAZADA HECH NARSA YO'Q!")
        conn.close()
        return None

    # 2. ANIQ PARAMETRLAR BILAN QIDIRISH
    print(f"\n🎯 QIDIRILMOQDA (aniq parametrlar):")
    print(f"   model_id={model_id}, storage={storage}, color='{color_name}'")
    print(f"   sim={sim_type}, battery={battery}, box={has_box_int}, damage='{search_damage}'")

    c.execute("""
        SELECT id, price, damage_pct FROM prices 
        WHERE model_id = ? 
        AND storage_size = ? 
        AND color_name = ? 
        AND sim_type = ? 
        AND battery_label = ? 
        AND has_box = ?
    """, (model_id, storage, color_name, sim_type, battery, has_box_int))

    matching_rows = c.fetchall()

    if matching_rows:
        print(f"   ✅ {len(matching_rows)} ta mos keluvchi variant topildi:")
        for row in matching_rows:
            db_damage = row['damage_pct']
            normalized_db_damage = normalize_for_search(db_damage)
            match = "✅ MOS!" if normalized_db_damage == search_damage else "❌"
            print(
                f"      ID={row['id']}: damage='{db_damage}' → search='{normalized_db_damage}' {match} price=${row['price']}")

            if normalized_db_damage == search_damage:
                print(f"\n🎉 TOPILDI! ID={row['id']}, Price=${row['price']}")
                conn.close()
                return row['price']
    else:
        print(f"   ❌ Hech narsa topilmadi")

    # 3. DAMAGE NI HISOBGA OLMAY QIDIRISH
    print(f"\n🔄 DAMAGE NI HISOBGA OLMAY QIDIRISH:")
    c.execute("""
        SELECT id, damage_pct, price FROM prices 
        WHERE model_id = ? 
        AND storage_size = ? 
        AND color_name = ? 
        AND sim_type = ? 
        AND battery_label = ? 
        AND has_box = ?
    """, (model_id, storage, color_name, sim_type, battery, has_box_int))

    rows = c.fetchall()
    if rows:
        print(f"   Topildi {len(rows)} ta variant (damage turlicha):")
        for row in rows:
            print(f"      ID={row['id']}: damage='{row['damage_pct']}', price=${row['price']}")
    else:
        print(f"   ❌ Hech narsa yo'q")

    # 4. QUTI NI HISOBGA OLMAY QIDIRISH
    print(f"\n🔄 QUTI NI HISOBGA OLMAY QIDIRISH:")
    c.execute("""
        SELECT id, has_box, damage_pct, price FROM prices 
        WHERE model_id = ? 
        AND storage_size = ? 
        AND color_name = ? 
        AND sim_type = ? 
        AND battery_label = ?
    """, (model_id, storage, color_name, sim_type, battery))

    rows = c.fetchall()
    if rows:
        print(f"   Topildi {len(rows)} ta variant:")
        for row in rows:
            print(f"      ID={row['id']}: box={row['has_box']}, damage='{row['damage_pct']}', price=${row['price']}")
    else:
        print(f"   ❌ Hech narsa yo'q")

    print(f"\n❌ NARX TOPILMADI!")
    print(f"{'=' * 70}\n")

    conn.close()
    return None


def add_model(name, order_num=0):
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


def add_storage(model_id, size):
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


def add_color(model_id, name):
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


def add_battery(model_id, label):
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


def add_sim_type(model_id, sim_type):
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


def get_total_prices_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM prices")
    row = c.fetchone()
    conn.close()
    return row['count'] if row else 0


def get_prices_for_model(model_id):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM prices 
        WHERE model_id=? 
        ORDER BY price DESC 
        LIMIT 5
    """, (model_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def clear_all_prices():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM prices")
        conn.commit()
        return True
    except Exception as e:
        print(f"Narxlarni tozalashda xato: {e}")
        return False
    finally:
        conn.close()


# Boshida avto yaratish
init_db()

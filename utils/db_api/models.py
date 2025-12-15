# utils/db_api/models.py - TO'LIQ VERSIYA
from utils.db_api.database import get_conn


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


def get_storages(model_id):
    """Model uchun xotiralarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM storages WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_colors(model_id):
    """Model uchun ranglarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM colors WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_batteries(model_id):
    """Model uchun batareyalarni olish"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM batteries WHERE model_id = ? ORDER BY min_percent DESC", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
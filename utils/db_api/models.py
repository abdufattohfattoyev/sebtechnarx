from utils.db_api.database import get_conn


def get_models():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM models WHERE is_active = 1 ORDER BY order_num")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Model bo'yicha xotira, rang, batareya
def get_storages(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM storages WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_colors(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM colors WHERE model_id = ?", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_batteries(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM batteries WHERE model_id = ? ORDER BY min_pct DESC", (model_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_model(model_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM models WHERE id = ?", (model_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

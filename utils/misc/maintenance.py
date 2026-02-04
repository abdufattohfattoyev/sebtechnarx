# utils/misc/maintenance.py - TAMIRLASH REJIMI UTILITY

import json
import os
from datetime import datetime
from typing import Dict, Optional

MAINTENANCE_FILE = "maintenance_config.json"


def get_maintenance_config() -> Dict:
    """
    Tamirlash rejimi konfiguratsiyasini olish

    Returns:
        dict: Konfiguratsiya ma'lumotlari
    """
    try:
        if os.path.exists(MAINTENANCE_FILE):
            with open(MAINTENANCE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default konfiguratsiya
            default_config = {
                "maintenance_mode": False,
                "features": {
                    "pricing": True,
                    "payment": True,
                    "account": True
                },
                "message": "Bot hozirda texnik ishlar olib borilmoqda.",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_by": None
            }
            save_maintenance_config(default_config)
            return default_config
    except Exception as e:
        print(f"❌ Maintenance config read error: {e}")
        return {
            "maintenance_mode": False,
            "features": {
                "pricing": True,
                "payment": True,
                "account": True
            }
        }


def save_maintenance_config(config: Dict) -> bool:
    """
    Konfiguratsiyani saqlash

    Args:
        config: Konfiguratsiya ma'lumotlari

    Returns:
        bool: Muvaffaqiyatli saqlandi yoki yo'q
    """
    try:
        config['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(MAINTENANCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Maintenance config save error: {e}")
        return False


def is_maintenance_mode() -> bool:
    """
    Tamirlash rejimi yoqilganmi?

    Returns:
        bool: True - yoqilgan, False - o'chirilgan
    """
    config = get_maintenance_config()
    return config.get('maintenance_mode', False)


def is_feature_enabled(feature: str) -> bool:
    """
    Muayyan funksiya yoqilganmi?

    Args:
        feature: 'pricing', 'payment', 'account'

    Returns:
        bool: True - yoqilgan, False - o'chirilgan
    """
    config = get_maintenance_config()

    # Agar global tamirlash rejimi yoqilgan bo'lsa - hamma o'chirilgan
    if config.get('maintenance_mode', False):
        return False

    # Alohida funksiya holatini tekshirish
    features = config.get('features', {})
    return features.get(feature, True)


def toggle_maintenance_mode(user_id: Optional[int] = None) -> Dict:
    """
    Tamirlash rejimini yoqish/o'chirish

    Args:
        user_id: Admin ID

    Returns:
        dict: Yangi holat ma'lumotlari
    """
    config = get_maintenance_config()
    current_mode = config.get('maintenance_mode', False)

    config['maintenance_mode'] = not current_mode
    config['updated_by'] = user_id

    if save_maintenance_config(config):
        return {
            'success': True,
            'maintenance_mode': config['maintenance_mode'],
            'message': '✅ Tamirlash rejimi yoqildi' if config['maintenance_mode'] else '✅ Tamirlash rejimi o\'chirildi'
        }
    else:
        return {
            'success': False,
            'message': '❌ Xatolik yuz berdi'
        }


def toggle_feature(feature: str, user_id: Optional[int] = None) -> Dict:
    """
    Alohida funksiyani yoqish/o'chirish

    Args:
        feature: 'pricing', 'payment', 'account'
        user_id: Admin ID

    Returns:
        dict: Yangi holat ma'lumotlari
    """
    config = get_maintenance_config()
    features = config.get('features', {})

    if feature not in features:
        return {
            'success': False,
            'message': f'❌ {feature} funksiyasi topilmadi'
        }

    current_status = features.get(feature, True)
    features[feature] = not current_status

    config['features'] = features
    config['updated_by'] = user_id

    if save_maintenance_config(config):
        feature_names = {
            'pricing': 'Narxlash',
            'payment': 'To\'lov',
            'account': 'Hisob'
        }
        status = 'yoqildi' if features[feature] else 'o\'chirildi'
        return {
            'success': True,
            'feature': feature,
            'enabled': features[feature],
            'message': f'✅ {feature_names.get(feature, feature)} {status}'
        }
    else:
        return {
            'success': False,
            'message': '❌ Xatolik yuz berdi'
        }


def get_maintenance_status() -> str:
    """
    Tamirlash rejimi holatini matnda olish

    Returns:
        str: Holat matni
    """
    config = get_maintenance_config()

    if config.get('maintenance_mode', False):
        return "⚠️ TO'LIQ TAMIRLASH REJIMI"

    features = config.get('features', {})
    disabled = [name for name, enabled in features.items() if not enabled]

    if disabled:
        feature_names = {
            'pricing': 'Narxlash',
            'payment': 'To\'lov',
            'account': 'Hisob'
        }
        disabled_text = ', '.join([feature_names.get(f, f) for f in disabled])
        return f"⚠️ QISMAN TAMIRLASH ({disabled_text})"

    return "✅ NORMAL ISHLAYDI"


def get_maintenance_message() -> str:
    """
    Tamirlash rejimi xabarini olish

    Returns:
        str: Xabar matni
    """
    config = get_maintenance_config()
    return config.get('message', 'Bot hozirda texnik ishlar olib borilmoqda.')


def update_maintenance_message(message: str, user_id: Optional[int] = None) -> bool:
    """
    Tamirlash rejimi xabarini yangilash

    Args:
        message: Yangi xabar
        user_id: Admin ID

    Returns:
        bool: Muvaffaqiyatli yangilandi yoki yo'q
    """
    config = get_maintenance_config()
    config['message'] = message
    config['updated_by'] = user_id
    return save_maintenance_config(config)
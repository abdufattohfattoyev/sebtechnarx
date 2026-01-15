# utils/api.py - TO'LIQ TUZATILGAN VERSIYA
import aiohttp
import asyncio
import logging
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

# API base URL
API_BASE_URL = "https://sebmarket.uz/api/payments"


class PaymentAPI:
    """Payment API client - ORDER_ID bilan"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _ensure_session(self):
        """Session yaratish yoki qayta ishlatish"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session

    async def close(self):
        """Session ni yopish"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Umumiy request funksiyasi"""
        session = await self._ensure_session()

        # Endpoint ni to'g'ri formatlash
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = f"{self.base_url}{endpoint}"

        headers = kwargs.pop('headers', {})
        headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        logger.debug(f"API Request: {method} {url}")
        if kwargs.get('json'):
            logger.debug(f"Request data: {kwargs['json']}")

        try:
            async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **kwargs
            ) as response:
                try:
                    response_text = await response.text()
                    logger.debug(f"Response text: {response_text[:500]}")

                    result = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}, text: {response_text[:200]}")
                    result = {'success': False, 'error': 'Invalid JSON response'}

                logger.debug(f"API Response {response.status}: {result}")

                if response.status in [200, 201]:
                    return result
                elif response.status == 404:
                    return {'success': False, 'error': f'Endpoint not found: {endpoint}'}
                elif response.status == 500:
                    error_msg = result.get('error', 'Server error')
                    logger.error(f"Server 500 error: {error_msg}")
                    return {'success': False, 'error': f'Server error: {error_msg}'}
                else:
                    error_msg = result.get('error', f'HTTP {response.status}')
                    return {'success': False, 'error': error_msg}

        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            return {'success': False, 'error': f'Connection error: {str(e)}'}
        except asyncio.TimeoutError:
            logger.error(f"Timeout error to {url}")
            return {'success': False, 'error': 'Timeout error (30s)'}
        except Exception as e:
            logger.error(f"Unknown error to {url}: {e}", exc_info=True)
            return {'success': False, 'error': f'Request error: {str(e)}'}

    # ============= FOYDALANUVCHI =============

    async def create_user(self, telegram_id: int, full_name: str, username: str = None) -> Dict[str, Any]:
        """
        Foydalanuvchi yaratish yoki yangilash
        POST /user/create/

        Returns:
            {
                'success': True,
                'telegram_id': int,
                'balance': int,
                'full_name': str,
                'username': str,
                'phone': str or None,  # ✅ PHONE FIELD
                'is_active': bool,
                'created': bool
            }
        """
        data = {
            'telegram_id': telegram_id,
            'full_name': full_name,
            'username': username or ''
        }

        logger.info(f"Creating user: telegram_id={telegram_id}, full_name={full_name}")

        result = await self._make_request('POST', '/user/create/', json=data)

        if result.get('success'):
            return {
                'success': True,
                'telegram_id': result.get('telegram_id', telegram_id),
                'balance': result.get('balance', 0),
                'full_name': result.get('full_name', full_name),
                'username': result.get('username', ''),
                'phone': result.get('phone'),  # ✅ PHONE FIELD QOSHILDI
                'is_active': result.get('is_active', True),
                'created': result.get('created', False)
            }
        else:
            logger.error(f"User creation failed: {result.get('error')}")
            return result

    async def get_balance(self, telegram_id: int) -> Dict[str, Any]:
        """
        Balansni olish
        GET /user/<telegram_id>/balance/

        ✅ urls.py ga mos: path('user/<int:telegram_id>/balance/', ...)
        """
        endpoint = f"/user/{telegram_id}/balance/"

        logger.info(f"Getting balance: telegram_id={telegram_id}")

        result = await self._make_request('GET', endpoint)

        if result.get('success'):
            return {
                'success': True,
                'telegram_id': telegram_id,
                'balance': result.get('balance', 0),
                'full_name': result.get('full_name', ''),
                'username': result.get('username', '')
            }
        else:
            # Foydalanuvchi topilmasa, avtomatik yaratish
            error_str = str(result.get('error', '')).lower()
            if 'topilmadi' in error_str or 'not found' in error_str:
                logger.info(f"User not found, creating: telegram_id={telegram_id}")
                return await self.create_user(
                    telegram_id=telegram_id,
                    full_name=f"User{telegram_id}",
                    username=""
                )
            return result

    # ============= TARIFLAR =============

    async def get_tariffs(self) -> Dict[str, Any]:
        """
        Tariflarni olish
        GET /tariffs/
        """
        logger.info("Getting tariffs")

        result = await self._make_request('GET', '/tariffs/')

        if result.get('success'):
            tariffs = result.get('tariffs', [])
            logger.info(f"Received {len(tariffs)} tariffs")
            return {
                'success': True,
                'tariffs': tariffs
            }
        else:
            # Default tariflar
            logger.warning("No tariffs from API, using defaults")
            return {
                'success': True,
                'tariffs': [
                    {
                        'id': 1,
                        'name': '1 ta narxlash',
                        'count': 1,
                        'price': 5000.0,
                        'price_per_one': 5000.0
                    },
                    {
                        'id': 2,
                        'name': '5 ta narxlash',
                        'count': 5,
                        'price': 20000.0,
                        'price_per_one': 4000.0
                    },
                    {
                        'id': 3,
                        'name': '10 ta narxlash',
                        'count': 10,
                        'price': 35000.0,
                        'price_per_one': 3500.0
                    }
                ]
            }

    # ============= NARXLASH =============

    async def use_pricing(self, telegram_id: int, phone_model: str, price: float) -> Dict[str, Any]:
        """
        Narxlashdan foydalanish (balansni kamaytirish)
        POST /pricing/use/
        """
        data = {
            'telegram_id': telegram_id,
            'phone_model': phone_model,
            'price': float(price)
        }

        logger.info(f"Using pricing: telegram_id={telegram_id}, model={phone_model}, price={price}")

        result = await self._make_request('POST', '/pricing/use/', json=data)

        if result.get('success'):
            logger.info(f"Pricing used successfully, new balance: {result.get('balance')}")
            return {
                'success': True,
                'balance': result.get('balance', 0),
                'message': result.get('message', 'Narxlash muvaffaqiyatli')
            }
        else:
            logger.error(f"Pricing failed: {result.get('error')}")
            return result

    # ============= TO'LOV =============

    async def create_payment(self, telegram_id: int, tariff_id: int) -> Dict[str, Any]:
        """
        To'lov havolasini yaratish
        POST /payment/create/
        """
        data = {
            'telegram_id': telegram_id,
            'tariff_id': tariff_id
        }

        logger.info(f"Creating payment: telegram_id={telegram_id}, tariff_id={tariff_id}")

        result = await self._make_request('POST', '/payment/create/', json=data)

        if result.get('success'):
            payment_url = result.get('payment_url', '')
            order_id = result.get('order_id', '')

            logger.info(f"✅ Payment created successfully:")
            logger.info(f"   - payment_id: {result.get('payment_id')}")
            logger.info(f"   - order_id: {order_id}")
            logger.info(f"   - url: {payment_url}")

            return {
                'success': True,
                'payment_id': result.get('payment_id'),
                'order_id': order_id,
                'payment_url': payment_url,
                'amount': result.get('amount', 0),
                'count': result.get('count', 0),
                'tariff_name': result.get('tariff_name', '')
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ Payment creation failed: {error_msg}")
            return result

    async def check_payment_status(self, order_id: str) -> Dict[str, Any]:
        """
        To'lov holatini order_id orqali tekshirish
        GET /payment/status/<order_id>/

        ✅ urls.py ga mos: path('payment/status/<str:order_id>/', ...)
        """
        endpoint = f"/payment/status/{order_id}/"

        logger.info(f"Checking payment status: order_id={order_id}")

        result = await self._make_request('GET', endpoint)

        if result.get('success'):
            has_payment = result.get('has_payment', False)

            if has_payment:
                state = result.get('state', 1)
                logger.info(f"Payment found: order_id={order_id}, state={state}")
            else:
                logger.info(f"No payment found: order_id={order_id}")

            return {
                'success': True,
                'has_payment': has_payment,
                'order_id': order_id,
                'payment_id': result.get('payment_id'),
                'state': result.get('state', 1),
                'state_display': result.get('state_display', 'Yaratildi'),
                'amount': result.get('amount', 0),
                'count': result.get('count', 0),
                'balance': result.get('balance', 0),
                'created_at': result.get('created_at'),
                'performed_at': result.get('performed_at'),
                'tariff_name': result.get('tariff_name', '')
            }
        else:
            error_msg = result.get('error', '')
            if 'topilmadi' in error_msg.lower() or 'not found' in error_msg.lower():
                logger.warning(f"Payment not found: order_id={order_id}")
                return {
                    'success': False,
                    'error': 'To\'lov topilmadi',
                    'has_payment': False
                }
            return result

    async def update_phone(self, telegram_id: int, phone: str) -> Dict[str, Any]:
        """
        Telefon raqamini yangilash
        POST /user/update-phone/

        Args:
            telegram_id: Telegram user ID
            phone: Telefon raqam (masalan: +998901234567)

        Returns:
            {
                'success': True,
                'telegram_id': int,
                'phone': str,
                'message': str
            }
        """
        data = {
            'telegram_id': telegram_id,
            'phone': phone
        }

        logger.info(f"Updating phone: telegram_id={telegram_id}, phone={phone}")

        result = await self._make_request('POST', '/user/update-phone/', json=data)

        if result.get('success'):
            logger.info(f"✅ Phone updated successfully: {telegram_id} -> {phone}")
            return result
        else:
            logger.error(f"❌ Phone update failed: {result.get('error')}")
            return result

    async def test_connection(self) -> bool:
        """API ga ulanishni test qilish"""
        try:
            logger.info("Testing API connection...")
            result = await self.get_tariffs()

            if result.get('success'):
                logger.info("✅ API connection successful")
                return True
            else:
                logger.error(f"❌ API test failed: {result.get('error')}")
                return False
        except Exception as e:
            logger.error(f"❌ API test error: {e}", exc_info=True)
            return False


# ============= GLOBAL INSTANCE =============

api = PaymentAPI()


# ============= CLEANUP =============

async def cleanup():
    """Dastur tugaganda sessionni yopish"""
    await api.close()
    logger.info("API session closed")

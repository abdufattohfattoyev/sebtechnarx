import requests
from requests.auth import HTTPBasicAuth

merchant_id = "694d35331922c3549c145482"
secret_key = "Cv?%Y0yDqmxeDHd4EUhu84DS3biPqCh%Exqz"

data = {
    "account": {"order_id": "197"},
    "amount": 50000
}

url = "https://test.paycom.uz/api/payments/create"

response = requests.post(url, json=data, auth=HTTPBasicAuth(merchant_id, secret_key))

print(response.status_code)
print(response.text)  # API JSON beradi

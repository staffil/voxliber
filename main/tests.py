import requests

# 계산 테스트
response = requests.post(
    'http://127.0.0.1:8000/calculate/',
    json={'a': 100, 'b': 50}
)

print(response.json())
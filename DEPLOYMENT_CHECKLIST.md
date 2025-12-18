# VoxLiber AWS 배포 체크리스트

## ✅ CRITICAL 문제 해결 완료

- [x] SECRET_KEY 환경변수로 관리
- [x] DEBUG 기본값을 False로 변경
- [x] DB 비밀번호 프로덕션 필수화
- [x] ALLOWED_HOSTS 정리 (프로덕션 도메인만)
- [x] EXTERNAL_TTS_URL 환경변수 필수화
- [x] CORS/CSRF 설정 환경별 분리
- [x] .gitignore 업데이트

---

## 📋 배포 전 준비 사항

### 1. AWS EC2 설정 확인
```bash
# EC2 퍼블릭 IP 확인
# AWS 콘솔 → EC2 → 인스턴스 → 퍼블릭 IPv4 주소
```

### 2. 환경변수 파일 준비
AWS 서버에서 `.env` 파일 생성:

```bash
# EC2에 SSH 접속
ssh -i your-key.pem ubuntu@your-ec2-ip

# 프로젝트 디렉토리로 이동
cd /home/ubuntu/voxliber

# .env 파일 생성
nano .env
```

**`.env` 파일 내용** (.env.production 참조):
```env
DEBUG=False

# 시크릿 키 생성
DJANGO_SECRET_KEY=여기에-생성된-시크릿-키

# AWS EC2 퍼블릭 IP
AWS_EC2_IP=13.209.xxx.xxx

# 데이터베이스
DB_NAME=voxliber
DB_USER=chung
DB_PASSWORD=실제-DB-비밀번호
DB_HOST=localhost
DB_PORT=3306

# TTS 서비스
EXTERNAL_TTS_URL=https://your-production-tts-server.com
```

### 3. 시크릿 키 생성
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 🚀 배포 단계

### 1단계: 코드 업로드
```bash
# 로컬에서 Git 푸시
git add .
git commit -m "Production ready: Security fixes"
git push origin main

# 또는 SCP로 업로드
scp -r C:\AI2502\audioBook\voxliber ubuntu@your-ec2-ip:/home/ubuntu/
```

### 2단계: EC2 서버 설정

#### Python 환경
```bash
sudo apt update
sudo apt install python3-pip python3-venv

cd /home/ubuntu/voxliber
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### MySQL 설정
```bash
sudo apt install mysql-server
sudo mysql_secure_installation

# MySQL 접속
sudo mysql -u root -p

# 데이터베이스 생성
CREATE DATABASE voxliber CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'chung'@'localhost' IDENTIFIED BY '새로운-안전한-비밀번호';
GRANT ALL PRIVILEGES ON voxliber.* TO 'chung'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### Django 마이그레이션
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### 3단계: 배포 검증
```bash
# settings 검증
python manage.py check --deploy

# 서버 테스트 실행
python manage.py runserver 0.0.0.0:8000
```

방화벽에서 8000 포트 열고 브라우저에서 접속:
```
http://your-ec2-ip:8000/admin/
```

### 4단계: Gunicorn 설정
```bash
pip install gunicorn

# Gunicorn 서비스 파일 생성
sudo nano /etc/systemd/system/gunicorn.service
```

**gunicorn.service 내용:**
```ini
[Unit]
Description=Gunicorn daemon for VoxLiber
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/voxliber
Environment="PATH=/home/ubuntu/voxliber/venv/bin"
ExecStart=/home/ubuntu/voxliber/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/ubuntu/voxliber/gunicorn.sock \
    voxliber.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Gunicorn 시작:**
```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl status gunicorn
```

### 5단계: Nginx 설정
```bash
sudo apt install nginx

sudo nano /etc/nginx/sites-available/voxliber
```

**Nginx 설정 파일:**
```nginx
server {
    listen 80;
    server_name voxliber.ink www.voxliber.ink;

    client_max_body_size 10M;

    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static/ {
        alias /home/ubuntu/voxliber/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/voxliber/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/voxliber/gunicorn.sock;
    }
}
```

**Nginx 활성화:**
```bash
sudo ln -s /etc/nginx/sites-available/voxliber /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6단계: SSL 인증서 (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d voxliber.ink -d www.voxliber.ink
```

### 7단계: 방화벽 설정
```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

---

## ✅ 배포 후 확인

### 웹사이트 접속
```
https://voxliber.ink/
https://voxliber.ink/admin/
```

### API 테스트
```bash
# 도서 목록 API
curl https://voxliber.ink/book/api/books/

# 로그인 API
curl -X POST https://voxliber.ink/book/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'
```

### 로그 확인
```bash
# Gunicorn 로그
sudo journalctl -u gunicorn --no-pager

# Nginx 에러 로그
sudo tail -f /var/log/nginx/error.log

# Nginx 액세스 로그
sudo tail -f /var/log/nginx/access.log
```

---

## 🔧 코드 업데이트 시

```bash
# EC2 서버에서
cd /home/ubuntu/voxliber
git pull

# 또는 로컬에서 파일 업로드
scp -r modified-files ubuntu@your-ec2-ip:/home/ubuntu/voxliber/

# 이후 작업
source venv/bin/activate
pip install -r requirements.txt  # 의존성이 변경된 경우
python manage.py migrate  # DB 스키마 변경된 경우
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

---

## ⚠️ 주요 보안 이슈 (해결 필요)

### HIGH 우선순위
1. **@csrf_exempt 24개 위치** - CSRF 보호 재검토
   - `book/api_views.py`: 여러 API 엔드포인트
   - `register/views.py`: OAuth 콜백
   - 해결방법: DRF TokenAuthentication 또는 CSRF 토큰 검증

2. **파일 업로드 검증 부족** - 파일 타입/크기 검증
   - `mypage/views.py`: 프로필 이미지
   - `book/views.py`: 커버 이미지
   - 해결방법: validators.py 생성하여 검증 로직 추가

3. **API Key URL 전달** - 헤더로만 전달하도록 변경
   - `book/api_utils.py`: require_api_key 데코레이터
   - 해결방법: URL 파라미터 제거, 헤더 전용

---

## 📞 문제 해결

### Gunicorn이 시작되지 않을 때
```bash
sudo journalctl -u gunicorn --no-pager
# 로그 확인 후 오류 수정
sudo systemctl restart gunicorn
```

### Nginx 502 Bad Gateway
```bash
# Gunicorn 소켓 파일 확인
ls -l /home/ubuntu/voxliber/gunicorn.sock

# 권한 확인
sudo chown ubuntu:www-data /home/ubuntu/voxliber/gunicorn.sock
```

### 정적 파일이 안 보일 때
```bash
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### 데이터베이스 연결 오류
```bash
# MySQL 서비스 확인
sudo systemctl status mysql

# .env 파일 확인
cat /home/ubuntu/voxliber/.env
```

---

## 📚 참고 문서

- [Django 배포 체크리스트](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Gunicorn 문서](https://docs.gunicorn.org/)
- [Nginx 문서](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)

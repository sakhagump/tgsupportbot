#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="sakhagump"
REPO_NAME="tgsupportbot"
BRANCH="main"
APP_DIR="/opt/tgbot"
SERVICE_NAME="tgbot"

RAW_BASE="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}"

echo "==> Проверка root"
if [[ $EUID -ne 0 ]]; then
  echo "Запустите от root: sudo bash install.sh"
  exit 1
fi

echo "==> Установка системных пакетов"
apt update -y
apt install -y python3-full python3-venv python3-pip curl git

echo "==> Создание каталога $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "==> Скачивание файлов из GitHub"
for f in bot.py requirements.txt tgbot.service .env.example; do
  echo "  -> $f"
  curl -fsSL "$RAW_BASE/$f" -o "$f"
done

echo "==> Создание виртуального окружения"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Настройка .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "⚠️  Заполните $APP_DIR/.env и перезапустите скрипт:"
  echo "   nano $APP_DIR/.env"
  exit 1
fi

echo "==> Установка systemd-сервиса"
cp tgbot.service /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

sleep 2
systemctl --no-pager status ${SERVICE_NAME} || true

echo
echo "✅ Готово. Логи: journalctl -u ${SERVICE_NAME} -f"

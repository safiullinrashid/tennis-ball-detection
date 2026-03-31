import os
import sys

# Добавляем пути
sys.path.insert(0, os.path.dirname(__file__))

# Запускаем Flask приложение
from backend.app import app

if __name__ == '__main__':
    print("Запуск Tennis Ball Detection Server...")
    print("Сервер запущен на http://localhost:5000")
    print("Откройте frontend/index.html в браузере")
    app.run(debug=True, host='0.0.0.0', port=5000)
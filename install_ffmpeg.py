import subprocess, sys, os

print("Установка imageio-ffmpeg...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "imageio-ffmpeg"],
    capture_output=True, text=True
)
print(result.stdout)
if result.returncode == 0:
    print("Готово! Перезапустите сервер.")
else:
    print("Ошибка:", result.stderr)
    print("\nПопробуйте вручную: python -m pip install imageio-ffmpeg")

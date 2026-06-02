"""Запуск: python backend/show_metrics.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ultralytics import YOLO

model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models', 'best.pt')
m = YOLO(model_path)
print(f"Классы: {m.names}")
print(f"Запуск val() — ждите...")
results = m.val(verbose=True)

print("\n=== МЕТРИКИ ===")
if hasattr(results, 'box'):
    b = results.box
    for k in dir(b):
        if not k.startswith('_') and not callable(getattr(b, k)):
            print(f"  {k}: {getattr(b, k)}")
elif hasattr(results, 'metrics'):
    for k, v in vars(results.metrics).items():
        print(f"  {k}: {v}")

if hasattr(results, 'speed'):
    print(f"\nСкорость: {results.speed}")

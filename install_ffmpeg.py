import subprocess, sys, os

print("Installing imageio-ffmpeg...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "imageio-ffmpeg"],
    capture_output=True, text=True
)
print(result.stdout)
if result.returncode == 0:
    print("Done! Restart the server.")
else:
    print("Error:", result.stderr)
    print("\nTry manually: python -m pip install imageio-ffmpeg")

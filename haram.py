import pyautogui
import time

# Delay awal supaya kamu sempat pindah ke target window
print("Script akan mulai dalam 5 detik...")
time.sleep(5)

try:
    while True:
        # Ambil posisi mouse saat ini
        x, y = pyautogui.position()
        
        # Right click di posisi tersebut
        pyautogui.leftClick(x, y)
        print(f"Right click di posisi ({x}, {y})")
        
        # Tunggu 60 detik
        time.sleep(60)

except KeyboardInterrupt:
    print("Script dihentikan.")
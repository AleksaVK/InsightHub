import os
import json

# A beállítások fájl elérési útja
file_path = 'user_settings.json'

# Beállítások mentése
def save_settings(country):
    settings = {'country': country}
    with open(file_path, 'w') as f:
        json.dump(settings, f)
    print(f"Beállítások elmentve: {settings}")

# Beállítások betöltése
def load_settings():
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            settings = json.load(f)
            print(f"Beállítások betöltve: {settings}")
            return settings.get('country', 'Hungary')  # Alapértelmezett érték, ha nincs ország megadva
    else:
        print(f"A '{file_path}' fájl NEM létezik, alapértelmezett beállítások használata.")
        return 'Hungary'

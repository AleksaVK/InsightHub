import json
import os  # Importáld az os modult

def save_settings(selected_country):
    """Mentés: kiválasztott ország elmentése a JSON fájlba."""
    settings = {"country": selected_country}
    with open('user_settings.json', 'w') as f:
        json.dump(settings, f)

def load_settings():
    """Betöltés: a kiválasztott ország visszaadása a JSON fájlból."""
    file_path = 'user_settings.json'
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                settings = json.load(f)
                return settings.get("country", "Hungary")  # Alapértelmezett érték
        except Exception as e:
            print(f"Hiba a fájl beolvasásakor: {e}")
    else:
        print(f"A '{file_path}' fájl NEM létezik.")
        return "Hungary"  # Alapértelmezett érték

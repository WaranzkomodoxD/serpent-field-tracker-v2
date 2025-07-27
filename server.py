import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json
import logging

app = Flask(__name__)

# Ustawienie logowania, aby widzieć błędy i informacje na konsoli serwera
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOSS_STATE_FILE = "boss_state.json"

# Konfiguracja bossów (nazwa, czas respawnu w minutach)
# Ta konfiguracja jest używana przez klienta do wyświetlania i przez serwer do określania czasów respawnu
BOSS_CONFIG = {
    "Szeptotruj #1": 40,
    "Skorpion #1": 40,
    "Serpentor #1": 41,
    "Szeptotruj #2": 40,
    "Skorpion #2": 40,
    "Serpentor #2": 41
}

# Lista kanałów - KLUCZOWA DLA SERWERA, aby wiedział, jakie klucze są poprawne
CHANNELS = ["CH1", "CH2", "CH3", "CH4", "CH5", "CH6"]

def load_boss_state():
    """Ładuje stan bossów z pliku JSON."""
    if os.path.exists(BOSS_STATE_FILE):
        try:
            with open(BOSS_STATE_FILE, 'r') as f:
                state = json.load(f)
                validated_state = {}
                for key, value in state.items():
                    # Walidacja, czy klucz jest zgodny z oczekiwanym formatem (CH_BOSSNAME)
                    # i czy boss_name jest w BOSS_CONFIG
                    parts = key.split('_', 1) # Podziel tylko raz
                    if len(parts) == 2 and parts[0] in CHANNELS and parts[1] in BOSS_CONFIG:
                        if isinstance(value, str):
                            try:
                                datetime.fromisoformat(value)
                                validated_state[key] = value
                            except ValueError:
                                logging.warning(f"Nieprawidłowy timestamp dla klucza {key}: {value}. Ignorowanie.")
                        elif value is None:
                            validated_state[key] = None
                        else:
                            logging.warning(f"Nieprawidłowa wartość dla klucza {key}: {value}. Ignorowanie.")
                    else:
                        logging.warning(f"Nieznany lub nieprawidłowy klucz w pliku boss_state.json: {key}. Ignorowanie.")
                return validated_state
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Błąd ładowania stanu bossów: {e}")
            return {}
    return {}

def save_boss_state(state):
    """Zapisuje stan bossów do pliku JSON."""
    try:
        with open(BOSS_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        logging.error(f"Błąd zapisu stanu bossów: {e}")

# Inicjalizacja stanu bossów przy starcie serwera
boss_state = load_boss_state()

# NOWA LOGIKA: Jeśli boss_state jest pusty po załadowaniu, zainicjuj go domyślnymi wartościami
if not boss_state:
    logging.info("Stan bossów jest pusty lub plik nie istnieje. Inicjalizuję domyślny stan.")
    for channel in CHANNELS:
        for boss_name_from_config in BOSS_CONFIG.keys():
            key = f"{channel}_{boss_name_from_config}"
            boss_state[key] = None # Ustaw początkowy stan na None (niezbity/aktywny)
    save_boss_state(boss_state) # Zapisz zainicjowany stan do pliku

@app.route('/get_state', methods=['GET'])
def get_state():
    """Zwraca aktualny stan wszystkich bossów."""
    logging.info("Odebrano żądanie GET /get_state")
    return jsonify(boss_state)

@app.route('/update_boss_status', methods=['POST'])
def update_boss_status():
    """Aktualizuje status bossa (zbity/aktywny)."""
    data = request.get_json()
    key = data.get('key')
    timestamp = data.get('timestamp') # Może być None dla "aktywny"

    if not key:
        logging.warning("Odebrano żądanie POST /update_boss_status bez klucza.")
        return jsonify({"message": "Błąd: Brak klucza bossa"}), 400

    # Sprawdź, czy klucz jest poprawny (np. "CH1_Szeptotruj #1")
    parts = key.split('_', 1)
    is_valid_key_format = (len(parts) == 2 and parts[0] in CHANNELS and parts[1] in BOSS_CONFIG)

    if is_valid_key_format:
        if timestamp is None:
            boss_state[key] = None
            logging.info(f"Boss {key} ustawiony na aktywny (brak timestampu).")
        else:
            try:
                datetime.fromisoformat(timestamp)
                boss_state[key] = timestamp
                logging.info(f"Boss {key} zbity o: {timestamp}")
            except ValueError:
                logging.warning(f"Nieprawidłowy format timestampu dla klucza {key}: {timestamp}. Użyj ISO 8601.")
                return jsonify({"message": "Błąd: Nieprawidłowy format timestampu"}), 400
    else:
        logging.warning(f"Odebrano żądanie POST /update_boss_status z nieznanym lub nieprawidłowym kluczem: {key}")
        return jsonify({"message": f"Błąd: Nieznany lub nieprawidłowy klucz bossa {key}"}), 404

    save_boss_state(boss_state)
    return jsonify({"message": "Status zaktualizowany pomyślnie", "current_state": boss_state})

@app.route('/reset_channel/<channel_name>', methods=['POST'])
def reset_channel(channel_name):
    """Resetuje wszystkie statusy bossów dla danego kanału."""
    if channel_name not in CHANNELS:
        logging.warning(f"Odebrano żądanie resetu dla nieznanego kanału: {channel_name}")
        return jsonify({"message": f"Błąd: Nieznany kanał {channel_name}"}), 400

    reset_count = 0
    # Iteruj przez kopię kluczy, aby uniknąć RuntimeError podczas modyfikacji słownika
    for key in list(boss_state.keys()):
        # Sprawdź, czy klucz należy do danego kanału i czy część bossa jest w BOSS_CONFIG
        if key.startswith(f"{channel_name}_"):
            boss_part = key[len(f"{channel_name}_"):]
            if boss_part in BOSS_CONFIG: # Upewnij się, że resetujemy tylko znane bossy
                boss_state[key] = None
                reset_count += 1
    
    if reset_count > 0:
        save_boss_state(boss_state)
        logging.info(f"Zresetowano {reset_count} bossów dla kanału {channel_name}.")
        return jsonify({"message": f"Kanał {channel_name} zresetowany pomyślnie", "reseted_bosses_count": reset_count})
    else:
        logging.info(f"Brak bossów do zresetowania dla kanału {channel_name} (być może już są aktywne).")
        return jsonify({"message": f"Brak bossów do zresetowania dla kanału {channel_name}."}), 200 # Zwróć 200 OK, jeśli nic nie zresetowano, ale żądanie było poprawne

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
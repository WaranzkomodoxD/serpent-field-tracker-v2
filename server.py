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
BOSS_CONFIG = {
    "Szeptotruj #1": 40,
    "Skorpion #1": 40,
    "Serpentor #1": 41,
    "Szeptotruj #2": 40,
    "Skorpion #2": 40,
    "Serpentor #2": 41
}

def load_boss_state():
    """Ładuje stan bossów z pliku JSON."""
    if os.path.exists(BOSS_STATE_FILE):
        try:
            with open(BOSS_STATE_FILE, 'r') as f:
                state = json.load(f)
                # Opcjonalna walidacja danych (upewnienie się, że stan ma sens)
                validated_state = {}
                for key, value in state.items():
                    if isinstance(value, str):
                        try:
                            datetime.fromisoformat(value) # Sprawdź, czy to poprawna data
                            validated_state[key] = value
                        except ValueError:
                            logging.warning(f"Nieprawidłowy timestamp dla klucza {key}: {value}. Ignorowanie.")
                    elif value is None:
                        validated_state[key] = None
                    else:
                        logging.warning(f"Nieprawidłowa wartość dla klucza {key}: {value}. Ignorowanie.")
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

    if key in boss_state: # Upewnij się, że klucz jest znany
        if timestamp is None:
            # Boss staje się aktywny
            boss_state[key] = None
            logging.info(f"Boss {key} ustawiony na aktywny (brak timestampu).")
        else:
            try:
                # Sprawdzenie poprawności formatu daty (ISO 8601)
                datetime.fromisoformat(timestamp) 
                boss_state[key] = timestamp
                logging.info(f"Boss {key} zbity o: {timestamp}")
            except ValueError:
                logging.warning(f"Nieprawidłowy format timestampu dla klucza {key}: {timestamp}. Użyj ISO 8601.")
                return jsonify({"message": "Błąd: Nieprawidłowy format timestampu"}), 400
    else:
        logging.warning(f"Odebrano żądanie POST /update_boss_status z nieznanym kluczem: {key}")
        return jsonify({"message": f"Błąd: Nieznany klucz bossa {key}"}), 404

    save_boss_state(boss_state)
    return jsonify({"message": "Status zaktualizowany pomyślnie", "current_state": boss_state})

@app.route('/reset_channel/<channel_name>', methods=['POST'])
def reset_channel(channel_name):
    """Resetuje wszystkie statusy bossów dla danego kanału."""
    reset_count = 0
    for key in list(boss_state.keys()): # Użyj list() do iteracji, bo możesz modyfikować dict
        if key.startswith(f"{channel_name}_"):
            boss_state[key] = None # Ustaw na aktywny (brak ostatniego zbicia)
            reset_count += 1
    
    if reset_count > 0:
        save_boss_state(boss_state)
        logging.info(f"Zresetowano {reset_count} bossów dla kanału {channel_name}.")
        return jsonify({"message": f"Kanał {channel_name} zresetowany pomyślnie", "reseted_bosses_count": reset_count})
    else:
        logging.warning(f"Nie znaleziono bossów do zresetowania dla kanału {channel_name}.")
        return jsonify({"message": f"Nie znaleziono bossów dla kanału {channel_name} do zresetowania."}), 404

if __name__ == '__main__':
    # Uruchomienie serwera
    # Pobiera port ze zmiennej środowiskowej PORT, domyślnie 5000
    port = int(os.environ.get('PORT', 5000)) 
    # Uruchamia na wszystkich dostępnych interfejsach, debug=False na produkcji
    app.run(debug=False, host='0.0.0.0', port=port)
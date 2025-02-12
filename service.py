import sys
import os
import platform
import xbmc
import xbmcaddon
import xbmcgui
from xbmc import Monitor

# Adiciona o diretório do addon e a pasta lib ao sys.path
addon_path = xbmcaddon.Addon().getAddonInfo('path')
lib_path = os.path.join(addon_path, 'lib')
sys.path.append(lib_path)

try:
    import serial
    xbmc.log("PySerial importado com sucesso!", xbmc.LOGINFO)
except ImportError:
    xbmc.log("Falha ao importar PySerial", xbmc.LOGERROR)
    sys.exit()

import time
import threading


# Configuração do Addon
addon = xbmcaddon.Addon()
monitor = Monitor()

# Configuração global com lock de thread
door_status = {
    "driver": "Fechada",
    "passenger": "Fechada",
    "rear_left": "Fechada",
    "rear_right": "Fechada",
    "trunk": "Fechado"
}
status_lock = threading.Lock()

def get_serial_config():
    system = platform.system()
    default_port = "COM3" if system == "Windows" else "/dev/ttyUSB0"

    return {
        'port': addon.getSetting("serial_port") or default_port,
        'baudrate': int(addon.getSetting("baud_rate") or 115200),
        'timeout': 0.1
    }

def parse_can_message(raw_data):
    """Processa os dados brutos do CAN bus e determina o status das portas."""
    global door_status

    try:
        xbmc.log(f"Debug CAN: {str(raw_data)}", xbmc.LOGINFO)

        if "3b3" not in raw_data:
            return

        # Extrai os últimos 2 bytes
        parts = raw_data.split()
        if len(parts) < 6:
            return

        last_bytes = ' '.join(parts[-2:]).upper()

        xbmc.log(f"Debug last_bytes: {str(last_bytes)}", xbmc.LOGINFO)

        # Mapeamento dos status das portas baseado na mensagem CAN
        status_map = {
            "80 0" : { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "80 30": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "80 10": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "80 20": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "81 20": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Fechado" },
            "82 10": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Fechado" },
            "82 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Aberto" },
            "81 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Aberto" },
            "80 04": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Aberto" },
            "81 0" : { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Fechado" },
            "82 0" : { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Fechado" },
            "83 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 14": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 24": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 30": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Fechado" },
        }

        with status_lock:
            if last_bytes in status_map:
                door_status.update(status_map[last_bytes])
                xbmc.log("Status atualizado", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"Erro ao processar CAN: {str(e)}", xbmc.LOGERROR)

def serial_worker():
    """Thread para comunicação serial com otimizações"""
    config = get_serial_config()
    ser = None

    while not monitor.abortRequested():
        try:
            if not ser:
                ser = serial.Serial(**config)
                xbmc.log(f"Conexão serial iniciada em {config['port']}", xbmc.LOGINFO)

            if ser.in_waiting > 0:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
                if raw:
                    parse_can_message(raw)
            
            monitor.waitForAbort(0.01)
        
        except serial.SerialException as e:
            xbmc.log(f"Erro serial: {str(e)}", xbmc.LOGERROR)
            if ser:
                ser.close()
                ser = None
            monitor.waitForAbort(5)

        except Exception as e:
            xbmc.log(f"Erro geral: {str(e)}", xbmc.LOGERROR)
            monitor.waitForAbort(1)

    if ser and ser.is_open:
        ser.close()

def ui_worker():
    """Atualização otimizada da interface"""
    window = xbmcgui.Window(10000)  # Acessa a Home do Kodi
    last_state = {}

    while not monitor.abortRequested():
        try:
            with status_lock:
                current_state = door_status.copy()

            if current_state != last_state:
                # Atualiza as propriedades no Kodi com o status das portas
                window.setProperty("driver_door", door_status["driver"])
                window.setProperty("passenger_door", door_status["passenger"])
                window.setProperty("rear_left_door", door_status["rear_left"])
                window.setProperty("rear_right_door", door_status["rear_right"])
                window.setProperty("trunk", door_status["trunk"])
                last_state = current_state.copy()
                xbmc.log("UI atualizada", xbmc.LOGINFO)
                # Adicione rótulos descritivos nos logs
                xbmc.log(f"Porta Motorista: {door_status['driver']}", xbmc.LOGINFO)
                xbmc.log(f"Porta Passageiro: {door_status['passenger']}", xbmc.LOGINFO)
                xbmc.log(f"Porta Traseira Esquerda: {door_status['rear_left']}", xbmc.LOGINFO)
                xbmc.log(f"Porta Traseira Direita: {door_status['rear_right']}", xbmc.LOGINFO)
                xbmc.log(f"Porta-malas: {door_status['trunk']}", xbmc.LOGINFO)
            
            monitor.waitForAbort(0.5)  # Espera 0.5s de forma não-bloqueante

        except Exception as e:
            xbmc.log(f"Erro UI: {str(e)}", xbmc.LOGERROR)
            monitor.waitForAbort(1)

if __name__ == "__main__":
    xbmc.log("Serviço iniciado", xbmc.LOGINFO)

    # Inicia threads
    serial_thread = threading.Thread(target=serial_worker, daemon=True)
    ui_thread = threading.Thread(target=ui_worker, daemon=True)

    serial_thread.start()
    ui_thread.start()

    # Mantém o serviço ativo
    while not monitor.abortRequested():
        monitor.waitForAbort(1)

    xbmc.log("Serviço encerrado", xbmc.LOGINFO)
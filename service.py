import sys
import os
import xbmc
import xbmcaddon
import xbmcgui
from xbmc import Monitor

# Adiciona o diretório do addon e a pasta lib ao sys.path
addon_path = xbmcaddon.Addon().getAddonInfo('path')
lib_path = os.path.join(addon_path, 'lib')
sys.path.append(lib_path)

import serial

# Teste para ver se o módulo foi importado corretamente
xbmc.log("PySerial importado com sucesso!", xbmc.LOGINFO)

import time
import threading


# Configuração do Addon
addon = xbmcaddon.Addon()
monitor = Monitor()



serial_port_setting = addon.getSetting("serial_port")
baud_rate_setting = addon.getSetting("baud_rate")

xbmc.log(f"Serial Port: {str(serial_port_setting)}", xbmc.LOGERROR)
xbmc.log(f"Baud Rate: {str(baud_rate_setting)}", xbmc.LOGERROR)

SERIAL_PORT = "COM3"
BAUD_RATE = int(baud_rate_setting) if baud_rate_setting.isdigit() else 115200

# Variável global para armazenar o status das portas
door_status = {
    "driver": "Fechada",
    "passenger": "Fechada",
    "rear_left": "Fechada",
    "rear_right": "Fechada"
}

def parse_can_message(raw_data):
    """Processa os dados brutos do CAN bus e determina o status das portas."""
    global door_status
    try:
        parts = raw_data.split(" - ")
        payload = parts[-1].strip()  # O último campo contém os dados das portas

        # Mapeamento dos status das portas baseado na mensagem CAN
        status_map = {
            "80 00": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada" },
            "80 20": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada" },
            "80 40": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Fechada" },
            "80 80": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada" },
            "81 00": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Aberta" }
        }

        # Atualiza o status das portas se a mensagem for reconhecida
        if payload in status_map:
            door_status = status_map[payload]
            xbmc.log(f"Status das portas atualizado: {door_status}", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"Erro ao processar CAN: {str(e)}", xbmc.LOGERROR)

def listen_serial():
    """Escuta a porta serial e processa os dados do CAN bus."""
    while not monitor.abortRequested():
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            xbmcgui.Dialog().notification("CAN Listener", "Serviço iniciado!", xbmcgui.NOTIFICATION_INFO, 3000)
            xbmc.log("Conectado à porta serial!", xbmc.LOGINFO)

            while not monitor.abortRequested():
                if ser.in_waiting > 0:
                    raw_data = ser.readline().decode('utf-8').strip()
                    parse_can_message(raw_data)

                time.sleep(0.1)

        except Exception as e:
            xbmc.log(f"Erro na Serial: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Erro Serial", str(e), xbmcgui.NOTIFICATION_ERROR, 5000)

            time.sleep(5)

def update_door_status():
    """Atualiza o status das portas na interface do Kodi."""
    window = xbmcgui.Window(10000)  # Acessa a Home do Kodi

    while not monitor.abortRequested():
        try:
            # Atualiza as propriedades no Kodi com o status das portas
            window.setProperty("driver_door", door_status["driver"])
            window.setProperty("passenger_door", door_status["passenger"])
            window.setProperty("rear_left_door", door_status["rear_left"])
            window.setProperty("rear_right_door", door_status["rear_right"])

            time.sleep(1)  # Atualiza a cada 1 segundo

        except Exception as e:
            xbmc.log(f"Erro ao atualizar status das portas: {str(e)}", xbmc.LOGERROR)

if __name__ == "__main__":
    # Inicia ambos os serviços em threads separadas
    thread_serial = threading.Thread(target=listen_serial)
    thread_update = threading.Thread(target=update_door_status)

    thread_serial.start()
    thread_update.start()

    # Espera as threads terminarem antes de sair
    thread_serial.join()
    thread_update.join()
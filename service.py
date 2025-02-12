import sys
import os
import platform
import xbmc
import xbmcaddon
import xbmcgui
from xbmc import Monitor
import re

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

xbmc.log(f"Serial Port: {str(serial_port_setting)}", xbmc.LOGINFO)
xbmc.log(f"Baud Rate: {str(baud_rate_setting)}", xbmc.LOGINFO)

# Detecta o sistema operacional
if platform.system() == "Windows":
    SERIAL_PORT_SYSTEM = "COM3"  # Ajuste conforme necessário
elif platform.system() == "Linux":
    SERIAL_PORT_SYSTEM = "/dev/ttyUSB0"  # Ajuste conforme necessário
else:
    xbmc.log("Sistema operacional não suportado!", xbmc.LOGERROR)
    sys.exit(1)  # Sai do programa se o SO não for suportado

SERIAL_PORT = serial_port_setting if serial_port_setting else SERIAL_PORT_SYSTEM
BAUD_RATE = int(baud_rate_setting) if baud_rate_setting.isdigit() else 115200

# Variável global para armazenar o status das portas
door_status = {
    "driver": "Fechada",
    "passenger": "Fechada",
    "rear_left": "Fechada",
    "rear_right": "Fechada",
    "trunk": "Fechado"
}

def parse_can_message(raw_data):
    """Processa os dados brutos do CAN bus e determina o status das portas."""
    global door_status
    try:
        # Expressão regular para capturar os elementos esperados
        match = re.search(r"(\d+) - ([0-9A-Fa-f]+) S \d (\d) ((?:[0-9A-Fa-f]{1,2} )+)", raw_data)

        if not match:
            xbmc.log(f"Formato inválido: {raw_data}", xbmc.LOGWARNING)
            return

        timestamp, can_id, dlc, data_bytes = match.groups()
        data_bytes = data_bytes.strip().upper()  # Remove espaços extras e padroniza maiúsculas

        xbmc.log(f"Recebido CAN ID: {can_id} | Dados: {data_bytes}", xbmc.LOGDEBUG)
        
        parts = raw_data.split(" - ")
        can_id = parts[0]  # O primeiro campo é o endereço da mensagem

        if can_id != "0x3b3":
            xbmc.log(f"Ignorando mensagem de ID {can_id}", xbmc.LOGDEBUG)
            return  # Ignora mensagens de outros IDs
        
        # Divide os bytes em uma lista
        data_list = data_bytes.split()

        # Pega os dois últimos bytes
        last_two_bytes = f"{data_list[-2]} {data_list[-1]}"
        xbmc.log(f"CAN ID: {can_id} | Últimos 2 bytes: {last_two_bytes}", xbmc.LOGDEBUG)

        # Mapeamento dos status das portas baseado na mensagem CAN
        status_map = {
            "80 00": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "80 30": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "80 10": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "80 20": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Fechado" },
            "81 20": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Fechado" },
            "82 10": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Fechado" },
            "82 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Aberto" },
            "81 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Aberto" },
            "80 04": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada", "trunk": "Aberto" },
            "81 00": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada", "trunk": "Fechado" },
            "82 00": { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Aberta", "trunk": "Fechado" },
            "83 34": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 14": { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 24": { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Aberto" },
            "83 30": { "driver": "Aberta", "passenger": "Aberta", "rear_left": "Aberta", "rear_right": "Aberta", "trunk": "Fechado" },
        }

        # Atualiza o status das portas se a mensagem for reconhecida       
        if last_two_bytes in status_map:
            door_status = status_map[last_two_bytes]
            xbmc.log(f"Status das portas atualizado: {door_status}", xbmc.LOGINFO)
        else:
            xbmc.log(f"DataBytes desconhecido: {last_two_bytes}", xbmc.LOGWARNING)

    except Exception as e:
        xbmc.log(f"Erro ao processar CAN: {str(e)}", xbmc.LOGERROR)

def open_serial():
    """Tenta abrir a conexão serial e retorna o objeto da serial."""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        xbmc.log(f"Serial aberta com sucesso: {SERIAL_PORT}", xbmc.LOGINFO)
        return ser
    except serial.SerialException as e:
        xbmc.log(f"Erro ao abrir a serial: {str(e)}", xbmc.LOGERROR)
        return None

def listen_serial():
    """Escuta a porta serial e processa os dados do CAN bus."""
    ser = open_serial()

    while not monitor.abortRequested():
        if ser is None:
            xbmc.log("Tentando reabrir a serial...", xbmc.LOGWARNING)
            ser = open_serial()
            time.sleep(5)  # Espera 5 segundos antes de tentar abrir novamente
            continue


        try:
            if ser.in_waiting > 0:
                raw_data = ser.readline().decode('utf-8').strip()
                parse_can_message(raw_data)

            time.sleep(0.1)

        except serial.SerialException as e:
            xbmc.log(f"Erro na Serial: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Erro Serial", str(e), xbmcgui.NOTIFICATION_ERROR, 5000)
            ser.close()
            ser = None

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
    thread_serial = threading.Thread(target=listen_serial, daemon=True)
    thread_update = threading.Thread(target=update_door_status, daemon=True)

    thread_serial.start()
    thread_update.start()

    # Espera as threads terminarem antes de sair
    thread_serial.join()
    thread_update.join()
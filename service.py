import xbmc
import xbmcgui
import xbmcaddon
import serial
import time

# Configuração do Addon
addon = xbmcaddon.Addon()
#SERIAL_PORT = addon.getSetting("serial_port")
#BAUD_RATE = int(addon.getSetting("baud_rate"))

SERIAL_PORT = "COM3"
BAUD_RATE = 115200


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

        # Verifica o byte relevante para cada porta
        if payload == "80 00":  # Todas as portas fechadas
            door_status = { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada" }
        elif payload == "80 20":  # Só a porta do motorista aberta
            door_status = { "driver": "Aberta", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Fechada" }
        elif payload == "80 40":  # Outra condição de portas
            door_status = { "driver": "Fechada", "passenger": "Aberta", "rear_left": "Fechada", "rear_right": "Fechada" }
        elif payload == "80 80":  # Outra condição de portas
            door_status = { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Aberta", "rear_right": "Fechada" }
        elif payload == "81 00":  # Outra condição de portas
            door_status = { "driver": "Fechada", "passenger": "Fechada", "rear_left": "Fechada", "rear_right": "Aberta" }

        xbmc.log(f"Status das portas: {door_status}", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"Erro ao processar CAN: {str(e)}", xbmc.LOGERROR)

def listen_serial():
    """Escuta a porta serial e processa os dados do CAN bus."""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        xbmcgui.Dialog().notification("CAN Listener", "Serviço iniciado!", xbmcgui.NOTIFICATION_INFO, 3000)

        while not xbmc.abortRequested:
            if ser.in_waiting > 0:
                raw_data = ser.readline().decode('utf-8').strip()
                parse_can_message(raw_data)

            time.sleep(0.1)

    except Exception as e:
        xbmc.log(f"Erro na Serial: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro Serial", str(e), xbmcgui.NOTIFICATION_ERROR, 5000)

def update_door_status():
    """Atualiza o status das portas na interface do Kodi."""
    window = xbmcgui.Window(10000)  # Acessa a Home do Kodi

    while not xbmc.abortRequested:
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
    # Inicia ambos os serviços: escutando a porta serial e atualizando a interface
    listen_serial()
    update_door_status()

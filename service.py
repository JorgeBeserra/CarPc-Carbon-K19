import sys
import os
import platform
import xbmc
import xbmcaddon
import xbmcgui
from xbmc import Monitor, Player

from lib.ReverseGearManager import ReverseGearManager
from lib.can_parser import CANParser

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
    "trunk": "Fechado",
    "reverse_gear": "Não Engatada"
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

# Função para mostrar a caixa de diálogo
def mostrar_dialogo_desligamento():
    xbmc.log("Kodi: Gerando Dialogo", xbmc.LOGINFO)
    # Criação da caixa de diálogo
    dialog = xbmcgui.Dialog()

    # Mensagem da caixa de diálogo
    mensagem = "O desligamento está próximo. Deseja cancelar ou re-agendar?"

    # Opções para os botões
    botoes = ["Cancelar", "Re-agendar"]

    # Mostrar a caixa de diálogo com opções
    escolha = dialog.yesno("Desligamento Próximo", mensagem, "", "", botoes[0], botoes[1])

    # Ação baseada na escolha do usuário
    if escolha == 1:  # Índice do botão "Re-agendar"
        # Aqui você pode adicionar lógica para re-agendar o desligamento
        xbmcgui.Dialog().ok("Desligamento", "Desligamento re-agendado.")
    else:
        # Cancelar o desligamento
        xbmcgui.Dialog().ok("Desligamento", "Desligamento cancelado.")

def parse_can_message(raw_data):
    """Processa os dados brutos do CAN bus e determina o status das portas."""
    global door_status

    try:
        xbmc.log(f"Debug CAN: {str(raw_data)}", xbmc.LOGINFO)

        if raw_data == "ShutdownForInactivity":
            xbmc.log("Kodi: Desligando o sistema após inatividade", xbmc.LOGINFO)
            mostrar_dialogo_desligamento()

        parts = raw_data.split(" : ")

        if len(parts) < 2:
            return  # Ignora mensagens inválidas

        parts = raw_data.split(" : ")
        timestamp = int(parts[0])  # Exemplo: 227760806
        frame_parts = parts[1].split(" ")
        can_id = frame_parts[0]    # Exemplo: 3aa
        can_data = frame_parts[4:]     # Exemplo: ['0', '22', '20', '0', '0', '0', '0', '0']

        # 581 S 0 8 81 0 ff ff ff ff ff ff > CAN ID: Para quando desarma o Alarme

        if can_id == "581":
            with status_lock:
                door_status["alarm"] = "Desarmado"
                xbmc.log("Alarme desarmado (ID 581 detectado)", xbmc.LOGINFO)

        # Verifica mensagem de marcha ré (CAN ID 0x3AA)
        elif can_id == "3aa":
            # Exemplo de dados: 00 22 20 (não engatada) ou 00 22 21 (engatada)
            gear_byte = can_data[2]  # Último byte

            new_status = "Engatada" if gear_byte == "21" else "Não Engatada"

            with status_lock:
                if door_status["reverse_gear"] != new_status:
                    door_status["reverse_gear"] = new_status
                    xbmc.log(f"Marcha ré: {new_status}", xbmc.LOGINFO)

        elif can_id == "3b3":

            if len(parts) < 6:
                return
            
            byte1 = can_data[1]  # Segundo byte
            if byte1 == "48":
                with status_lock:
                    door_status["lighting"] = "Claro"
                    xbmc.log("Ambiente claro detectado (Byte 1 = 0x48)", xbmc.LOGINFO)
            elif byte1 == "88":
                with status_lock:
                    door_status["lighting"] = "Escuro"
                    xbmc.log("Ambiente escuro detectado (Byte 1 = 0x88)", xbmc.LOGINFO)

            last_bytes = ' '.join(can_data[-2:]).upper()

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

# Adicione esta classe de player
class ReverseVideoPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.playing = False

    def play_reverse_video(self):
        if not self.playing:
            # Altere para o caminho do seu dispositivo de captura
            video_url = "v4l2:///dev/video0"  # Exemplo para Linux

            ffmpeg_cmd = (
                "ffmpeg -f v4l2 -input_format mjpeg -i /dev/video0 "  # Formato de entrada MJPEG
                "-vf 'format=yuv420p' "
                "-c:v libx264 -preset ultrafast -tune zerolatency " 
                "-f mpegts -"
            )

            self.play(ffmpeg_cmd)
            self.playing = True
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")

    def stop_reverse_video(self):
        if self.playing:
            self.stop()
            self.playing = False
            xbmc.executebuiltin("Dialog.Close(all,true)")

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
    video_player = ReverseVideoPlayer()

    while not monitor.abortRequested():
        try:
            with status_lock:
                current_state = door_status.copy()
            
            # Controle do vídeo de marcha ré
            if current_state.get("reverse_gear") != last_state.get("reverse_gear"):
                if current_state["reverse_gear"] == "Engatada":
                    video_player.play_reverse_video()
                else:
                    video_player.stop_reverse_video()

            if current_state != last_state:
                # Atualiza as propriedades no Kodi com o status das portas
                window.setProperty("driver_door", door_status["driver"])
                window.setProperty("passenger_door", door_status["passenger"])
                window.setProperty("rear_left_door", door_status["rear_left"])
                window.setProperty("rear_right_door", door_status["rear_right"])
                window.setProperty("trunk", door_status["trunk"])
                window.setProperty("reverse_gear", current_state["reverse_gear"])
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
    mostrar_dialogo_desligamento()

    # Inicia threads
    serial_thread = threading.Thread(target=serial_worker, daemon=True)
    ui_thread = threading.Thread(target=ui_worker, daemon=True)

    serial_thread.start()
    ui_thread.start()

    # Mantém o serviço ativo
    while not monitor.abortRequested():
        monitor.waitForAbort(1)

    xbmc.log("Serviço encerrado", xbmc.LOGINFO)

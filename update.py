import os
import xbmc
import xbmcaddon
import xbmcgui
import urllib.request
import zipfile
import shutil
import xbmcvfs  # Importar a biblioteca correta

# Configuração do repositório
GITHUB_REPO = "https://github.com/SeuUsuario/SeuRepositorio/releases/latest/download/update.zip"
ADDON_PATH = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path'))

def download_update():
    zip_path = os.path.join(ADDON_PATH, "update.zip")

    try:
        xbmcgui.Dialog().notification("Atualizador", "Baixando atualização...", xbmcgui.NOTIFICATION_INFO, 3000)
        urllib.request.urlretrieve(GITHUB_REPO, zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ADDON_PATH)

        os.remove(zip_path)

        xbmcgui.Dialog().notification("Atualizador", "Atualização concluída!", xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.executebuiltin("RestartApp()")  # Reinicia o Kodi para aplicar a atualização

    except Exception as e:
        xbmcgui.Dialog().notification("Erro", f"Falha ao atualizar: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

def check_for_update():
    download_update()

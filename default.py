import xbmc
import xbmcaddon
import xbmcgui
import os
import update
import serial

# Exibir notificação ao iniciar
xbmcgui.Dialog().notification("Atualizador", "Verificando atualizações...", xbmcgui.NOTIFICATION_INFO, 3000)

# Chamar o script de atualização
update.check_for_update()

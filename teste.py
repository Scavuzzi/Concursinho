import sys
import os
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction

# 1. Iniciar a aplicação Qt
app = QApplication(sys.argv)

# Garante que o script não feche se você abrir e fechar outras janelas do app
app.setQuitOnLastWindowClosed(False)

caminho_icone = "assets/tray-icon.png"

if not os.path.exists(caminho_icone):
    print(f"Erro: O arquivo '{caminho_icone}' não foi encontrado!")
    sys.exit(1)

# 2. Criar o ícone da bandeja nativo do Qt
tray = QSystemTrayIcon()
tray.setIcon(QIcon(caminho_icone))
tray.setToolTip("Meu App Python")

# 3. Criar o Menu de contexto ao clicar com o botão direito
menu = QMenu()

# Exemplo de uma ação qualquer
acao_config = QAction("Configurações", menu)
menu.addAction(acao_config)

# Separador visual
menu.addSeparator()

# Ação para fechar o aplicativo completamente
acao_sair = QAction("Sair", menu)
acao_sair.triggered.connect(app.quit)
menu.addAction(acao_sair)

# 4. Vincular o menu ao ícone e torná-lo visível
tray.setContextMenu(menu)
tray.setVisible(True)

# Executa o loop principal do sistema
sys.exit(app.exec())
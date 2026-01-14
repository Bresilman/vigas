import sys
import os

# Correção de Path para encontrar o pacote 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from app.ui.gui.main_window import MainWindow

def main():
    """
    Ponto de entrada para a Interface Gráfica (GUI).
    """
    app = QApplication(sys.argv)
    
    # Estilo Fusion para aparência moderna e consistente em todos os OS
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
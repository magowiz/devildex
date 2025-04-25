import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

def create_minimal_app():
    # Crea l'istanza dell'applicazione Qt
    app = QApplication(sys.argv)

    # Crea una finestra principale (QWidget)
    window = QWidget()
    window.setWindowTitle("Minimal PySide6 App") # Imposta il titolo della finestra
    window.setGeometry(100, 100, 300, 150) # Imposta posizione e dimensioni (x, y, width, height)

    # Aggiunge un layout verticale
    layout = QVBoxLayout()
    window.setLayout(layout)

    # Aggiunge un'etichetta al layout
    label = QLabel("Hello from PySide6!")
    layout.addWidget(label)

    # Mostra la finestra
    window.show()

    # Avvia l'esecuzione dell'applicazione (loop degli eventi)
    sys.exit(app.exec())

if __name__ == "__main__":
    create_minimal_app()
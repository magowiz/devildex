


from kivymd.app import MDApp


class DevildexApp(MDApp):
    """Classe principale dell'applicazione KivyMD per Devildex."""

    def __init__(self, core=None, **kwargs):
        super().__init__(**kwargs)
        self.core = core
        print("PYTHON (KivyMD): DevildexApp inizializzata.")

    def build(self):
        """Costruisce l'interfaccia utente dell'applicazione.
        Questo metodo viene chiamato una sola volta all'avvio.
        """
        print("PYTHON (KivyMD): Metodo build() chiamato.")
        self.theme_cls.primary_palette = "Indigo"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = "Light"


    def handle_button_press(self, instance_button):
        """Gestisce l'evento di click di un bottone generico.
        'instance_button' è l'istanza del bottone che è stato premuto.
        """
        print(f"PYTHON (KivyMD): Bottone '{instance_button.text}' premuto.")
        if self.root and hasattr(self.root, 'ids') and 'status_label' in self.root.ids:
            self.root.ids.status_label.text = f"'{instance_button.text}' premuto!"
        else:
            print("PYTHON (KivyMD) ERRORE: Label 'status_label' non trovata o root non ha ids.")

    def on_start(self):
        """Chiamato dopo che il metodo build() è completato e la finestra è visibile."""
        print("PYTHON (KivyMD): Applicazione avviata (on_start).")

    def on_stop(self):
        """Chiamato quando l'applicazione sta per chiudersi."""
        print("PYTHON (KivyMD): Applicazione in chiusura (on_stop).")

if __name__ == '__main__':
     DevildexApp().run()
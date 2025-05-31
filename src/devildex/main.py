import flet as ft


def main(page: ft.Page):
    page.title = "Flet WebView Esempio"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # URL della pagina web da visualizzare
    url_da_mostrare = "https://flet.dev" # Puoi cambiarlo con qualsiasi URL

    # Creazione del controllo WebView
    webview_control = ft.WebView(
        url_da_mostrare,
        expand=True,  # Fa sì che il WebView occupi lo spazio disponibile
        # Puoi specificare anche larghezza e altezza se non vuoi che si espanda
        # width=800,
        # height=600,
        on_page_started=lambda e: print(f"WebView: Caricamento pagina iniziato - {e.data}"),
        on_page_ended=lambda e: print(f"WebView: Caricamento pagina terminato - {e.data}"),
        on_page_error=lambda e: print(f"WebView: Errore caricamento pagina - {e.data}"),
    )

    # Aggiungiamo un campo di testo e un bottone per cambiare l'URL dinamicamente
    txt_url = ft.TextField(label="Inserisci URL", value=url_da_mostrare, width=400)

    def cambia_url(e):
        nuovo_url = txt_url.value
        if nuovo_url:
            print(f"WebView: Cambio URL a: {nuovo_url}")
            webview_control.url = nuovo_url # Imposta il nuovo URL
            webview_control.update()      # Aggiorna il controllo WebView
            page.update()                 # Aggiorna la pagina per riflettere le modifiche
        else:
            print("WebView: URL non valido.")

    btn_carica = ft.ElevatedButton("Carica URL", on_click=cambia_url)

    page.add(
        ft.Column(
            [
                ft.Row([txt_url, btn_carica], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container( # Usiamo un Container per dare dimensioni al WebView se expand=True
                    content=webview_control,
                    width=800,  # Larghezza desiderata per il contenitore del WebView
                    height=600, # Altezza desiderata
                    bgcolor=ft.colors.BLACK12, # Colore di sfondo per vedere i bordi
                    padding=5
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )
    )

# Avvia l'applicazione Flet
# Se vuoi eseguirla come app web: ft.app(target=main, view=ft.WEB_BROWSER)
# Per un'app desktop (predefinito):
ft.app(target=main)
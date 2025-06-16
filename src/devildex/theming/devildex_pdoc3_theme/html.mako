    <%
        # La variabile 'module' è quella principale fornita da pdoc3 per il modulo corrente.
        # La assegniamo a 'mod' per brevità, come facevi tu nel vecchio file.
        mod = module
    %>
    <!DOCTYPE html>
    <html lang="it">
    <head>
        ${self.include_file('head.mako')}
        <% # Qui potresti aggiungere altri meta tag o link specifici se necessario in futuro %>
    </head>
    <body>

        <% # Il contenuto principale della pagina (navbar, corpo, footer) andrà qui nei prossimi passi %>
        <h1>Contenuto Provvisorio da html.mako</h1>
        <p>Se vedi questo, html.mako è stato aggiornato e head.mako dovrebbe essere incluso.</p>
        <p>Verifica il tag &lt;head&gt; per i link CSS!</p>

        <hr>
        <h2>Debug Info (Variabile 'mod'):</h2>
        <pre>
Tipo di 'mod': ${type(mod)}
Attributi di 'mod': ${dir(mod) if mod else "N/A"}
mod.name: ${mod.name if mod and hasattr(mod, 'name') else "Non disponibile"}
        </pre>

        <script src="static/bootstrap/js/bootstrap.bundle.min.js"></script>
        <script src="static/js/devildex_pdoc3.js"></script>
    </body>
    </html>
    
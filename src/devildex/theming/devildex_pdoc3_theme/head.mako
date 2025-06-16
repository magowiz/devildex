    <%doc>pdoc template: head.mako - Injected before </head></%doc>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${module.name if module and module.name else "Documentazione"} - Tema pdoc3 DevilDex</title>

    <% # Percorsi relativi alla directory 'static' del tema.
       # pdoc3 servirà i file da lì quando usi --template-dir.
    %>
    <link rel="stylesheet" href="static/bootstrap/css/bootstrap.min.css">
    <link rel="stylesheet" href="static/pdoc3_devildex.css">

    <%
    # Rimuoviamo lo style inline per il banner da qui,
    # lo integreremo direttamente in html.mako se necessario
    # o nel CSS principale.
    # Il banner rosso e lo script per il banner verranno gestiti diversamente
    # o integrati nel corpo principale di html.mako e nel CSS dedicato.
    %>

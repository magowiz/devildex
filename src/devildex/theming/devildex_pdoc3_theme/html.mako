        ## File: src/devildex/theming/devildex_pdoc3_theme/html.mako
        <%!
            from pdoc import doc, html
            import os
        %>
        <%
            mod = module  # module è una variabile speciale fornita da pdoc
        %>
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>${mod.name if mod else "Documentation"} - Devildex pdoc3 Theme</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f0fff0; /* Honeydew - un verde molto chiaro per distinguerlo */
                    margin: 20px;
                }
                h1, h2 {
                    color: #2E8B57; /* SeaGreen */
                }
                .container {
                    padding: 15px;
                    background-color: white;
                    border: 1px solid #ccc;
                }
                pre {
                    background-color: #f8f8f8;
                    border: 1px solid #ddd;
                    padding: 10px;
                    overflow-x: auto;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Modulo: ${mod.name if mod else "N/A"}</h1>
                <p><em>(Stile da devildex_pdoc3_theme/html.mako)</em></p>

                % if mod:
                    <p><strong>Percorso file:</strong> ${mod.obj.__file__ if hasattr(mod.obj, '__file__') and mod.obj.__file__ else 'N/D (potrebbe essere built-in o un package senza __init__.py diretto)'}</p>
                    <h2>Docstring:</h2>
                    <pre>${mod.docstring if mod.docstring else "Nessuna docstring per il modulo."}</pre>

                    % if mod.submodules():
                        <h2>Sottomoduli:</h2>
                        <ul>
                        % for submod in mod.submodules():
                            <li><a href="${html.url(submod, relative_to=mod) if submod else '#'}">${submod.name if submod else 'Errore sottomodulo'}</a></li>
                        % endfor
                        </ul>
                    % endif

                    <h2>Membri del modulo:</h2>
                    <ul>
                        % for member_name, member_doc in mod.members(sort=True):
                            <li>
                                <strong>${member_name}</strong>
                                % if hasattr(member_doc, 'kind'):
                                    <em>(${member_doc.kind})</em>
                                % endif
                                <pre>${member_doc.docstring if member_doc and member_doc.docstring else "Nessuna docstring."}</pre>
                            </li>
                        % endfor
                    </ul>
                % else:
                    <p>Errore: oggetto modulo non disponibile per il rendering.</p>
                % endif
            </div>
        </body>
        </html>

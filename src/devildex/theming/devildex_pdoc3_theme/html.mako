    <%doc>
        Extremely basic pdoc3 html.mako template for debugging.
    </%doc>
    <%
        mod = module  # Main module object from pdoc
    %>
    <!DOCTYPE html>
    <html>
    <head>

                <%include file="head.mako"/>

    </head>
    <body>
        <h1>Modulo: ${mod.name if mod and hasattr(mod, 'name') else "N/A"}</h1>

        % if mod and hasattr(mod, 'docstring_parsed') and mod.docstring_parsed:
            <div class="docstring">
                ${mod.docstring_parsed.html | n}
            </div>
        % elif mod and hasattr(mod, 'docstring'):
            <pre>${mod.docstring}</pre>
        % else:
            <p>Nessun docstring per il modulo.</p>
        % endif

        % if hasattr(mod, 'members') and mod.members:
            <h2>Membri:</h2>
            <ul>
            % for member_name, member_obj in mod.members.items():
                <li>
                    <strong>${member_name}</strong> (${member_obj.kind if hasattr(member_obj, 'kind') else 'N/A'})
                    % if hasattr(member_obj, 'docstring_parsed') and member_obj.docstring_parsed:
                    <div class="docstring">
                        ${member_obj.docstring_parsed.html | n}
                    </div>
                    % elif hasattr(member_obj, 'docstring') and member_obj.docstring:
                    <pre>${member_obj.docstring}</pre>
                    % endif
                </li>
            % endfor
            </ul>
        % endif

        <hr>
        <p><em>Test base di html.mako completato.</em></p>
        <script src="static/bootstrap/js/bootstrap.bundle.min.js"></script>
        <script src="static/js/pdoc3_devildex.js"></script>
    </body>
    </html>
    
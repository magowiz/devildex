<%
    mod = module
%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>${mod.name if mod and mod.name else "Documentazione"} - Tema pdoc3 Devildex</title>
    <style>
        body {
            background-color: lightcoral;
            font-family: sans-serif;
            margin: 20px;
        }
        h1, h2 {
            color: navy;
        }
        pre {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            padding: 10px;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <h1>Modulo: ${mod.name if mod and mod.name else "N/A"}</h1>
    <p>(Tema pdoc3 Devildex con stile inline)</p>

    % if mod and hasattr(mod, 'docstring') and mod.docstring:
        <h2>Docstring del Modulo:</h2>
        <pre>${mod.docstring}</pre>
    % else:
        <p>Nessuna docstring trovata per questo modulo.</p>
    % endif

    <hr>
    <h2>Debug Info (Variabile 'mod'):</h2>
    <pre>
        Tipo di 'mod': ${type(mod)}
        Attributi di 'mod': ${dir(mod) if mod else "N/A"}
        mod.name: ${mod.name if mod and hasattr(mod, 'name') else "Non disponibile"}
        mod.docstring: ${mod.docstring if mod and hasattr(mod, 'docstring') else "Non disponibile"}
        mod (raw): ${mod if mod else "N/A"}
    </pre>
</body>
</html>
        <%doc>pdoc template: head.mako - Injected before </head></%doc>
        <style>
          body {
            background-color: red !important;
            margin-top: 60px !important; /* Spazio per il banner */
            padding-top: 10px;
          }
          #devildex-pdoc-banner {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background-color: black;
            color: white;
            text-align: center;
            padding: 15px 0;
            font-size: 1.8em;
            font-weight: bold;
            z-index: 10000;
            box-sizing: border-box;
          }
        </style>
        <script>
          document.addEventListener('DOMContentLoaded', function() {
            if (!document.getElementById('devildex-pdoc-banner')) {
              const banner = document.createElement('div');
              banner.id = 'devildex-pdoc-banner';
              banner.textContent = 'DEVILDEX PDOC3 THEME';
              document.body.insertBefore(banner, document.body.firstChild);
            }
          });
        </script>

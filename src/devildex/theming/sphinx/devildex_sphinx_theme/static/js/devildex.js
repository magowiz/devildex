            document.addEventListener('DOMContentLoaded', function() {
              if (!document.getElementById('devildex-sphinx-banner')) {
                const banner = document.createElement('div');
                banner.id = 'devildex-sphinx-banner';
                banner.textContent = 'DEVILDEX SPHINX THEME';
                document.body.insertBefore(banner, document.body.firstChild);
              }
            });

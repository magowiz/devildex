document.addEventListener('DOMContentLoaded', function () {
    /* --- Gestione della Navbar --- */
    // ... (il codice della navbar rimane invariato) ...
    const navbarContent = document.getElementById('devildexNavbarContent');
    if (navbarContent) {
        const tocList = navbarContent.querySelector('ul');
        if (tocList) {
            tocList.classList.add('navbar-nav', 'me-auto', 'mb-2', 'mb-lg-0');
            const navItems = tocList.querySelectorAll(':scope > li');
            navItems.forEach(function (li) {
                const link = li.querySelector('a');
                const sublist = li.querySelector('ul');
                if (sublist) {
                    li.classList.add('nav-item', 'dropdown');
                    if (link) {
                        link.classList.add('nav-link', 'dropdown-toggle');
                        link.setAttribute('role', 'button');
                        link.setAttribute('data-bs-toggle', 'dropdown');
                        link.setAttribute('aria-expanded', 'false');
                    }
                    sublist.classList.add('dropdown-menu');
                    const sublistItems = sublist.querySelectorAll('li');
                    sublistItems.forEach(function(sub_li){
                        const sub_link = sub_li.querySelector('a');
                        if(sub_link){
                            sub_link.classList.add('dropdown-item');
                        }
                    });
                } else {
                    li.classList.add('nav-item');
                    if (link) {
                        link.classList.add('nav-link');
                    }
                }
            });
        }
    }

    /* --- Gestione della Sidebar --- */
    // Trova il contenitore della sidebar
    /* --- Gestione della Sidebar --- */
    // Trova il contenitore della sidebar
    const sidebarWrapper = document.querySelector('.devildex-sidebar-wrapper');
    if (sidebarWrapper) {
        // Il codice per aggiungere .card, .card-body e .card-title è stato RIMOSSO
        // perché la struttura è ora definita direttamente in layout.html.

        // Trova tutte le liste di navigazione generate da toctree() nella sidebar
        const sidebarTocs = sidebarWrapper.querySelectorAll('ul');
        sidebarTocs.forEach(function(toc) {
            // Applica le classi per una navigazione verticale di Bootstrap
            toc.classList.add('nav', 'flex-column');

            // Aggiungi le classi a ogni link e item della lista
            const listItems = toc.querySelectorAll('li');
            listItems.forEach(function(li) {
                li.classList.add('nav-item');
                const link = li.querySelector('a');
                if (link) {
                    link.classList.add('nav-link');
                }
            });
        });
    }

    /* --- Rendi le immagini nel contenuto principale responsive --- */
    const contentImages = document.querySelectorAll('main img');
    contentImages.forEach(function(img) {
        img.classList.add('img-fluid');
    });
});
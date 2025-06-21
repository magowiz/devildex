document.addEventListener('DOMContentLoaded', function () {
    /* --- Gestione della Navbar --- */
    // Trova il div del menu collassabile
    const navbarContent = document.getElementById('devildexNavbarContent');
    if (navbarContent) {
        // Dentro il div, trova il primo (e unico) <ul> generato da toctree()
        const tocList = navbarContent.querySelector('ul');
        if (tocList) {
            // 1. Aggiungi le classi Bootstrap all'<ul> principale per farlo diventare una navbar
            tocList.classList.add('navbar-nav', 'me-auto', 'mb-2', 'mb-lg-0');

            // 2. Itera su tutti gli <li> DIRETTI di questa lista
            const navItems = tocList.querySelectorAll(':scope > li');
            navItems.forEach(function (li) {
                const link = li.querySelector('a');
                const sublist = li.querySelector('ul');

                // Se l'elemento ha un sottomenu (es. "Tutorial"), lo trasformiamo in un dropdown
                if (sublist) {
                    li.classList.add('nav-item', 'dropdown');
                    if (link) {
                        link.classList.add('nav-link', 'dropdown-toggle');
                        link.setAttribute('role', 'button');
                        link.setAttribute('data-bs-toggle', 'dropdown');
                        link.setAttribute('aria-expanded', 'false');
                    }
                    sublist.classList.add('dropdown-menu');

                    // Aggiungiamo le classi agli elementi del sottomenu
                    const sublistItems = sublist.querySelectorAll('li');
                    sublistItems.forEach(function(sub_li){
                        const sub_link = sub_li.querySelector('a');
                        if(sub_link){
                            sub_link.classList.add('dropdown-item');
                        }
                    });
                } else {
                    // Se è un link normale, applichiamo le classi base
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
    const sidebar = document.querySelector('.sphinxsidebar .devildex-sidebar-wrapper');
    if (sidebar) {
        // Trova tutte le liste di navigazione generate da toctree() nella sidebar
        const sidebarTocs = sidebar.querySelectorAll('ul');
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

    const contentImages = document.querySelectorAll('main img');

    contentImages.forEach(function(img) {
        img.classList.add('img-fluid');
    });
});
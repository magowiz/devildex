document.addEventListener('DOMContentLoaded', function () {
  // --- INIZIO CODICE PER LA NAVBAR ---
  const bootstrapNavUl = document.querySelector('#devildexNavbarContent .navbar-nav');

  if (!bootstrapNavUl) {
    console.warn('Devildex Theme: Elemento .navbar-nav non trovato in #devildexNavbarContent.');
    // Considera se il return è appropriato; se la navbar non è critica,
    // potresti voler permettere al codice della sidebar di eseguirsi comunque.
    return;
  }

  const toctreeGeneratedUl = bootstrapNavUl.querySelector(':scope > ul');

  if (toctreeGeneratedUl) {
    while (toctreeGeneratedUl.firstChild) {
      const listItem = toctreeGeneratedUl.firstChild;

      if (listItem.nodeType === Node.ELEMENT_NODE && listItem.tagName === 'LI') {
        const link = listItem.querySelector(':scope > a');
        const subMenuUl = listItem.querySelector(':scope > ul');

        if (subMenuUl) {
          listItem.classList.add('nav-item', 'dropdown');

          if (link) {
            link.classList.add('nav-link', 'dropdown-toggle');
            link.setAttribute('href', '#');
            link.setAttribute('role', 'button');
            link.setAttribute('data-bs-toggle', 'dropdown');
            link.setAttribute('aria-expanded', 'false');
          }

          subMenuUl.classList.add('dropdown-menu');
          const subListItems = subMenuUl.querySelectorAll(':scope > li');
          subListItems.forEach(subLi => {
            const subLink = subLi.querySelector(':scope > a');
            if (subLink) {
              subLink.classList.add('dropdown-item');
            }
          });

        } else {
          listItem.classList.add('nav-item');
          if (link) {
            link.classList.add('nav-link');
          }
        }
        bootstrapNavUl.appendChild(listItem);
      } else {
        toctreeGeneratedUl.removeChild(listItem);
      }
    }
    bootstrapNavUl.removeChild(toctreeGeneratedUl);
  } else {
    const directListItems = bootstrapNavUl.querySelectorAll(':scope > li');
    directListItems.forEach(listItem => {
      if (!listItem.classList.contains('nav-item')) {
        listItem.classList.add('nav-item');
      }
      const link = listItem.querySelector(':scope > a');
      if (link && !link.classList.contains('nav-link')) {
        link.classList.add('nav-link');
      }
    });
  }
  // --- FINE CODICE PER LA NAVBAR ---

  // --- INIZIO CODICE PER LA SIDEBAR ---
  const sidebarElement = document.querySelector('.sphinxsidebar'); // L'elemento <aside>
  const sidebarWrapper = document.querySelector('.sphinxsidebarwrapper');

  if (sidebarElement && sidebarWrapper) {
    // Applica stile al contenitore principale della sidebar
    // Puoi provare 'bg-body-tertiary' se usi Bootstrap 5.3+ per uno sfondo leggermente diverso
    sidebarElement.classList.add('bg-light', 'p-3', 'rounded', 'border');

    // Rimuoviamo il padding-top dal wrapper interno se lo aggiungiamo all'esterno,
    // dato che 'p-3' sull'elemento <aside> gestisce già il padding.
    // Il 'pt-3' era nel layout.html originale per .sphinxsidebarwrapper
    sidebarWrapper.classList.remove('pt-3');


    // 1. Stilizzare i titoli della sidebar (h3, h4)
    const sidebarHeadings = sidebarWrapper.querySelectorAll('h3, h4');
    sidebarHeadings.forEach(heading => {
      if (heading.tagName === 'H3') {
        heading.classList.add('h5', 'mt-3', 'mb-2');
      } else if (heading.tagName === 'H4') {
        heading.classList.add('h6', 'mt-3', 'mb-1');
      }
      // Rimuoviamo il margine superiore per il primo titolo se è il primo figlio del wrapper
      // (o del suo nuovo contenitore se la struttura cambia)
      if (heading === sidebarWrapper.firstElementChild || (heading.parentElement && heading.parentElement === sidebarWrapper && heading.previousElementSibling === null) ) {
          heading.classList.remove('mt-3');
          heading.classList.add('mt-0');
      }
    });

    // 2. Stilizzare il Table of Contents (TOC) locale
    const tocDivs = Array.from(sidebarWrapper.querySelectorAll('div')).filter(div => {
        const firstUl = div.querySelector(':scope > ul');
        const firstChild = div.firstElementChild;
        return firstUl && (firstChild && (firstChild.tagName === 'H3' || firstChild.tagName === 'H4') || firstChild === firstUl);
    });

    tocDivs.forEach(div => {
      const tocUl = div.querySelector(':scope > ul');
      if (tocUl) {
        tocUl.classList.add('nav', 'flex-column', 'mb-3');

        const styleTocLinks = (ulElement, isSublevel = false) => {
          const listItems = ulElement.querySelectorAll(':scope > li');
          listItems.forEach(li => {
            const link = li.querySelector(':scope > a');
            if (link) {
              link.classList.add('nav-link', 'py-1'); // Aggiunto py-1 per padding verticale
              if (li.classList.contains('current')) {
                link.classList.add('active');
              } else {
                link.classList.add('link-body-emphasis'); // Per colore link non attivo
              }

              if (isSublevel) {
                link.classList.add('ps-3');
              }
            }
            const subUl = li.querySelector(':scope > ul');
            if (subUl) {
              subUl.classList.add('nav', 'flex-column');
              styleTocLinks(subUl, true);
            }
          });
        };
        styleTocLinks(tocUl);
      }
    });

    // 3. Stilizzare i link di relazione (Previous/Next)
    const relationDivs = sidebarWrapper.querySelectorAll('div');
    relationDivs.forEach(div => {
        const h4 = div.querySelector(':scope > h4');
        const pTopless = div.querySelector(':scope > p.topless');

        if (h4 && pTopless && (h4.textContent.includes('Previous topic') || h4.textContent.includes('Next topic'))) {
            const link = pTopless.querySelector('a');
            if (link) {
                link.classList.add('d-block', 'link-body-emphasis', 'py-1', 'text-decoration-none', 'small');
                // Rimuoviamo la classe 'topless' se interferisce o non è più necessaria
                // pTopless.classList.remove('topless');
                // pTopless.classList.add('mb-2'); // Aggiungi un po' di margine sotto
            }
        }
    });

    // 4. Stilizzare il link "Show Source"
    const showSourceDiv = sidebarWrapper.querySelector('div[role="note"]');
    if (showSourceDiv) {
        const sourceUl = showSourceDiv.querySelector('ul.this-page-menu');
        if (sourceUl) {
            sourceUl.classList.add('nav', 'flex-column', 'small', 'mb-3');
             const listItems = sourceUl.querySelectorAll('li');
            listItems.forEach(li => {
                const link = li.querySelector('a');
                if (link) {
                  link.classList.add('nav-link', 'link-body-emphasis', 'py-1');
                }
            });
        }
    }

    // 5. Stilizzare il box di ricerca (#searchbox)
    const searchBox = sidebarWrapper.querySelector('#searchbox');
    if (searchBox) {
      const searchForm = searchBox.querySelector('form');
      if (searchForm) {
        const searchInput = searchForm.querySelector('input[type="text"]');
        if (searchInput) {
          searchInput.classList.add('form-control', 'form-control-sm', 'mb-2');
        }
        const searchButton = searchForm.querySelector('input[type="submit"]');
        if (searchButton) {
          searchButton.classList.add('btn', 'btn-sm', 'btn-outline-secondary', 'w-100');
        }
      }
    }

  } else {
    console.warn('Devildex Theme: Elemento .sphinxsidebar o .sphinxsidebarwrapper non trovato.');
  }
  // --- FINE CODICE PER LA SIDEBAR ---
});
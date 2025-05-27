document.addEventListener('DOMContentLoaded', function () {
  const bootstrapNavUl = document.querySelector('#devildexNavbarContent .navbar-nav');

  if (!bootstrapNavUl) {
    console.warn('Devildex Theme: Elemento .navbar-nav non trovato in #devildexNavbarContent.');
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
});
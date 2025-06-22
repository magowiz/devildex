// pydoctor_devildex.js

/**
 * Funzione "cecchino": va a caccia di elementi con uno specifico colore di sfondo
 * (il "giallino" di pydoctor) e lo rende trasparente.
 * È una soluzione forzata quando il CSS non collabora.
 */
function removeOffendingBackgrounds() {
    // Il colore esatto che stiamo cercando.
    // getComputedStyle di solito restituisce il formato rgb(), anche se nel CSS è rgba().
    const offendingColor = 'rgb(253, 255, 223)';

    // Seleziona TUTTI gli elementi della pagina.
    const allElements = document.querySelectorAll('*');

    allElements.forEach(element => {
        // Per ogni elemento, otteniamo il suo stile "calcolato" dal browser.
        const style = window.getComputedStyle(element);
        const bgColor = style.backgroundColor;

        // Se il colore di sfondo corrisponde al nostro nemico...
        if (bgColor === offendingColor) {
            // ...lo annientiamo, forzando lo sfondo a essere trasparente.
            // Usiamo setProperty per poter aggiungere '!important' e vincere qualsiasi battaglia.
            element.style.setProperty('background-color', 'transparent', 'important');
        }
    });
}


document.addEventListener('DOMContentLoaded', function() {
    // Codice esistente per i link interni (a.internal-link)
    var internalLinks = document.querySelectorAll('a.internal-link');
    internalLinks.forEach(function(link) {
        link.classList.add('link-primary');
        link.classList.add('link-underline-opacity-75');
        link.classList.add('link-underline-opacity-100-hover');
    });

    // Applica classi Bootstrap alle righe delle tabelle in #splitTables
    // Queste tabelle mostrano moduli, classi, funzioni, ecc.
    const tableRows = document.querySelectorAll('#splitTables > table tr');
    tableRows.forEach(function(row) {
        // Rimuovi le classi di sfondo predefinite di pydoctor per evitare conflitti.
        // Queste classi sono specifiche e verranno sovrascritte dal CSS in extra.css.
        row.classList.remove('package', 'module', 'class', 'classvariable', 'baseclassvariable', 'exception',
            'instancevariable', 'baseinstancevariable', 'variable', 'attribute', 'property',
            'interface', 'method', 'function', 'basemethod', 'baseclassmethod', 'classmethod', 'private');

        // Aggiungi classi Bootstrap per un bordo generale (il colore verrà sovrascritto da extra.css)
        row.classList.add('border-bottom', 'border-secondary'); // border-secondary per un bordo sottile scuro
        // Aggiungi padding se necessario (apidocs.css ha già 5px, ma puoi aumentarlo)
        // row.classList.add('p-2');
    });

    // Applica classi Bootstrap ai blocchi con classe 'basefunction'
    // Questi sono i riquadri per le definizioni di funzioni/attributi.
    const baseFunctionBlocks = document.querySelectorAll('#childList > div.basefunction');
    baseFunctionBlocks.forEach(function(block) {
        // Aggiungi classi Bootstrap per un bordo generale, angoli arrotondati, padding e margine
        block.classList.add('border', 'border-secondary', 'rounded', 'p-3', 'mb-3');
        // Aggiungi un bordo sinistro più spesso e colorato come accento
        // Il colore e lo spessore verranno sovrascritti da extra.css per garantire la precedenza.
        block.classList.add('border-start', 'border-primary', 'border-5');
    });

    // Codice per i tag <code> inline (già presente e corretto)
    // Non è necessario duplicarlo qui se è già in extra.css

    // --- NUOVA CHIAMATA ---
    // Esegui la nostra funzione "cecchino" per eliminare il giallo residuo.
    removeOffendingBackgrounds();
});
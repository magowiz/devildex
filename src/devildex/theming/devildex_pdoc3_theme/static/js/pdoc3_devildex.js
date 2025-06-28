/**
 * Trova tutti i blocchi <pre> e aggiunge la classe 'highlight'
 * per attivare la colorazione della sintassi di Pygments.
 */



document.addEventListener('DOMContentLoaded', () => {

    const pdocClasses = [
        'ident'
    ];

    const pdocToPygmentsMap = {
        'ident': 'nv',
        'name':
    };

    pdocClasses.forEach(pdocClass => {
        const elementsToEdit = document.querySelectorAll(`.${pdocClass}`);

        elementsToEdit.forEach(element => {
            const pygmentsClass = pdocToPygmentsMap[pdocClass];

            if (pygmentsClass) {
                element.classList.remove(pdocClass);
                element.classList.add(pygmentsClass);
            }
        });
    });
    const tuttiIBlocchiDiCodice = document.querySelectorAll('article pre');
    tuttiIBlocchiDiCodice.forEach(blocco => {
        blocco.classList.add('highlight');
    });

});
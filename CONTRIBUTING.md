# Guida per i Contributori

Siamo entusiasti che tu voglia contribuire a DevilDex! Questa guida ti aiuterà a iniziare.

## Codice di Condotta

Partecipando a questo progetto, accetti di rispettare il nostro [Codice di Condotta](CODE_OF_CONDUCT.md) (se ne creeremo uno).

## Come Contribuire

Il processo di contributo generale è il seguente:

1.  **Fork** il repository.
2.  **Clona** il tuo fork localmente.
3.  **Crea un branch** per le tue modifiche (`git checkout -b feature/nome-funzionalita` o `bugfix/descrizione-bug`).
4.  **Implementa** le tue modifiche, assicurandoti di seguire le linee guida di stile e di includere test appropriati.
5.  **Esegui i test** per assicurarti che tutto funzioni come previsto.
6.  **Effettua il commit** delle tue modifiche con un messaggio di commit chiaro e descrittivo.
7.  **Esegui il push** del tuo branch al tuo fork.
8.  **Apri una Pull Request** (PR) al repository principale.

## Configurazione dell'Ambiente di Sviluppo

Per iniziare a sviluppare su DevilDex:

1.  **Prerequisiti**: Assicurati di avere Python (versione 3.13 raccomandata) e [Poetry](https://python-poetry.org/) installati.
2.  **Clona il repository**:
    ```bash
    git clone https://github.com/magowiz/devildex.git
    cd devildex
    ```
3.  **Installa le dipendenze**:
    ```bash
    poetry install
    ```
4.  **Esegui l'applicazione**:
    ```bash
    poetry run devildex
    ```

## Esecuzione dei Test

È fondamentale che tutte le modifiche passino i test esistenti e che vengano aggiunti nuovi test per le nuove funzionalità o le correzioni di bug.

*   **Eseguire tutti i test**:
    ```bash
    poetry run pytest
    ```
*   **Eseguire i test UI in modalità headless (richiede Xvfb su Linux)**:
    ```bash
    xvfb-run poetry run pytest
    ```
    *Nota*: I test che coinvolgono la logica del core dell'applicazione dovrebbero istanziare `DevilDexCore` con un database SQLite in memoria per l'isolamento: `core = DevilDexCore(database_url='sqlite:///:memory:')`.

## Stile del Codice e Linee Guida

*   Segui lo stile di codice esistente nel progetto.
*   Utilizziamo `ruff` per il linting e la formattazione. Assicurati che il tuo codice sia conforme.
*   Aggiungi commenti solo quando necessario per spiegare il *perché* di una scelta complessa, non il *cosa*.

## Invio delle Modifiche (Pull Request)

Quando apri una Pull Request:

*   Fornisci una descrizione chiara e concisa delle modifiche.
*   Fai riferimento a qualsiasi issue correlata (es. `Fixes #123`, `Closes #456`).
*   Assicurati che i test passino e che il codice sia formattato correttamente.

## Segnalazione di Bug e Suggerimento di Funzionalità

Se trovi un bug o hai un'idea per una nuova funzionalità, per favore apri un'issue sul nostro [tracker di issue](https://github.com/magowiz/devildex/issues).

Grazie per il tuo contributo!

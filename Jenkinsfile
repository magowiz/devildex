// Jenkinsfile
// Pipeline per il progetto DevilDex per testare i tool di bundling

pipeline {
    // Definiamo l'agente di default. Qui diciamo che nessun agente globale è necessario,
    // perché useremo agenti Docker specifici all'interno degli stage di build/test.
    agent none

    stages {
        stage('Checkout') {
            agent any // Questo stage può girare su qualsiasi agente disponibile
            steps {
                // Scarica il codice sorgente dal repository Git (Gitea).
                // Jenkins lo fa automaticamente se la pipeline è configurata correttamente nel job.
                // La configurazione nel job Jenkins specificherà l'URL del tuo repo Gitea.
                script {
                    checkout scm
                }
            }
        }

        stage('Build Docker Image') {
            agent any // Anche questo stage può girare su qualsiasi agente
            steps {
                script {
                    // Costruisce l'immagine Docker che useremo per le build
                    // Il Dockerfile dovrà essere nella root del progetto
                    // Diamo all'immagine un tag che possiamo usare negli stage successivi
                    // (Ad esempio, 'devil-dex-build:latest' o un tag basato sul numero di build Jenkins)
                    sh 'docker build -t devil-dex-build:latest .'
                    // Oppure usa la sintassi più Jenkins-friendly:
                    // docker.build('devil-dex-build:latest', '.')
                }
            }
        }

        stage('Test cx_Freeze') {
            // Esegue questo stage all'interno di un container basato sull'immagine appena costruita
            agent {
                docker {
                    image 'devil-dex-build:latest' // Usa l'immagine costruita prima
                    // Potresti voler specificare l'utente o altre opzioni Docker qui
                    // args '-u 0' // Esempio: esegui come root nel container (spesso utile per build)
                }
            }
            steps {
                script {
                    echo 'Testing cx_Freeze build for Linux and Windows...'

                    // I comandi 'sh' qui verranno eseguiti *dentro* il container Docker

                    // Passo 1: Installare cx_Freeze e le sue dipendenze usando Poetry dentro il container
                    // (Assumiamo che il container abbia già Python e Poetry)
                    sh 'poetry run pip install cx_Freeze' // Installa nel venv Poetry del progetto

                    // Passo 2: Eseguire la build Linux con cx_Freeze
                    // Dovrai creare uno script Python o un file setup.py specifico per cx_Freeze
                    // Questo script dovrà usare cx_Freeze per impacchettare l'app
                    // Esempio di comando:
                    sh 'poetry run python path/to/your/cxfreeze_build_script.py build --target-dir /app/dist/linux/cxfreeze'

                    // Passo 3: Eseguire la build Windows con cx_Freeze (Cross-compile)
                    // Questo richiede che il container Docker sia configurato per la cross-compilazione Windows (es. con mingw-w64)
                    sh 'poetry run python path/to/your/cxfreeze_build_script.py build_exe --platforms=win64 --target-dir /app/dist/windows/cxfreeze' // Esempio con unipotente script

                    // Potresti dover gestire i file generati per renderli persistenti fuori dal container
                    // o salvarli come artefatti negli stage successivi. Spesso si generano in una cartella
                    // mappata dal volume o si copiano in una cartella accessibile dall'agente host.
                    // Per ora, assumiamo che vengano generati sotto /app/dist
                }
            }
        }

        // Ripeti stage simili per Nuitka e PyOxidizer
        stage('Test Nuitka') {
             agent {
                docker {
                    image 'devil-dex-build:latest' // Usa l'immagine costruita prima
                    // args '-u 0' // Esempio: esegui come root nel container
                }
            }
            steps {
                script {
                    echo 'Testing Nuitka build for Linux and Windows...'
                    sh 'poetry run pip install nuitka' // Installa nel venv Poetry del progetto
                    // Esegui qui i comandi Nuitka per Linux e Windows
                    // sh 'poetry run nuitka ...' // Comandi Nuitka specifici
                     sh 'echo "Run Nuitka build here"' # Placeholder
                }
            }
        }

         stage('Test PyOxidizer') {
             agent {
                docker {
                    image 'devil-dex-build:latest' // Usa l'immagine costruita prima
                    // args '-u 0' // Esempio: esegui come root nel container
                }
            }
            steps {
                script {
                    echo 'Testing PyOxidizer build for Linux and Windows...'
                    sh 'poetry run pip install pyoxidizer' # Installa nel venv Poetry del progetto
                    // Esegui qui i comandi PyOxidizer per Linux e Windows
                    // sh 'poetry run pyoxidizer build ...' # Comandi PyOxidizer specifici
                     sh 'echo "Run PyOxidizer build here"' # Placeholder
                }
            }
        }


        stage('Archive Artifacts') {
            agent any // Questo stage può girare su qualsiasi agente disponibile
            steps {
                script {
                    echo 'Archiving build artifacts...'
                    // Salva i file generati dagli stage precedenti come artefatti della build Jenkins
                    // I percorsi devono corrispondere a dove i tool di bundling salvano i loro output nel workspace di Jenkins
                    // Esempio:
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/linux/**/*', allowEmptyArchive: true // Per cartelle
                    archiveArtifacts artifacts: 'dist/windows/**/*', allowEmptyArchive: true // Per cartelle
                     echo "Artifacts archived from dist/" # Placeholder
                }
            }
        }

        // Placeholder per la build macOS (richiede un agente macOS separato)
        stage('Build macOS Package (Requires macOS Agent)') {
             // Questo stage dovrebbe essere limitato a un agente con etichetta 'macos' o simile
            agent {
                label 'macos' // Esempio: esegui solo su agenti etichettati 'macos'
                // Potrebbe usare un container Docker macOS se disponibile e sensato, ma spesso si lancia direttamente lo script sull'host macOS
            }
            steps {
                 script {
                     echo 'This stage runs on a macOS agent to build the macOS package.'
                     echo 'Setup and commands for macOS build go here (e.g., using one of the tools).'
                     // sh 'poetry run pip install ...' // Installa tool su macOS
                     // sh 'poetry run ...' // Esegui comando di build per macOS
                     echo "macOS build stage - Placeholder" # Placeholder
                 }
            }
        }
    }
}
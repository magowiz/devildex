@Library('shared-library') _

pipeline {
    agent none // Agente definito a livello di stage o matrix
    options {
        ansiColor('xterm')
        disableConcurrentBuilds(abortPrevious: true)
    }
    environment {
        // Variabili globali
        VERSION = '0.1'
        PIP_INDEX_URL = 'http://hephaestus.local:5000/index/'
        PIP_TRUSTED_HOST = 'hephaestus.local'
        PROJECT_NAME = 'devildex'
        IP_TRUSTED_HOST = '192.168.2.11' // Assicurati che sia raggiungibile dagli agent
        IP_INDEX_URL = 'http://192.168.2.11:5000/index/' // Assicurati che sia raggiungibile dagli agent
        LINT_TAG_REGEX = '.*\\[lint\\].*'
    }
    stages {
        stage('Checkout') {
            agent any // Esegue su un qualsiasi agente disponibile
            steps {
                script {
                    checkout scm
                }
            }
        }

        // Stage per costruire l'immagine Docker base (se necessario separatamente)
        stage('Build Docker Image') {
            agent any // Esegue su un qualsiasi agente disponibile con Docker
            steps {
                script {
                    // Potresti voler usare un tag più specifico, es: ${PROJECT_NAME}-build:${VERSION}
                    sh 'docker build -t devil-dex-build:latest .'
                }
                // CleanWs è opzionale qui, dipende se vuoi mantenere lo workspace per il prossimo stage
                // cleanWs()
            }
        }

        stage('megalinter') {
            agent {
                // Assicurati che 'heracles' sia un nodo agente valido dove eseguire questo container
                docker {
                    label 'heracles'
                    image 'oxsecurity/megalinter-python:v8.4.0'
                    args "-u root -e VALIDATE_ALL_CODEBASE=true -v \${WORKSPACE}:/tmp/lint --entrypoint=''\
                          -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket" // Verifica se il mount avahi è necessario
                    reuseNode true
                }
            }
            environment {
                // Usa le variabili IP definite globalmente (assicurati che l'agent 'heracles' possa raggiungerle)
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                DISABLE_ERRORS = true // Per megalinter, potrebbe essere diverso da quello per le build
            }
            steps {
                    sh 'rm -fr megalinter-reports'
                    sh '/entrypoint.sh'
            }
            post {
                always {
                    archiveArtifacts(allowEmptyArchive: true,
                                     artifacts: 'mega-linter.log,megalinter-reports/**/*',
                                     defaultExcludes: false, followSymlinks: false)
                    publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false,
                                 reportDir: 'megalinter-reports/linters_logs', reportFiles: 'WARNING*.log',
                                 reportName: 'Megalinter-Reports'])
                    cleanWs()
                }
            }
        }

        // Stage che usa Matrix per eseguire build multiple su diverse architetture
        stage('Build Packages Multi-Arch') {
            matrix {
                axes {
                    axis {
                        name 'ARCHITECTURE'
                        // Definisci le label dei tuoi nodi agent (devono esistere in Jenkins!)
                        values 'amd64', 'arm64'
                    }
                    // Puoi aggiungere altri assi qui se necessario in futuro
                }
                // Gli stage seguenti verranno eseguiti per ogni ARCHITECTURE definita nell'asse
                stages {
                    // --- Stage cx_Freeze eseguito per amd64 e arm64 ---
                    stage('Build cx_Freeze') {
                        agent {
                            dockerfile {
                                filename 'Dockerfile' // Usa il Dockerfile nella root del progetto
                                args '-u root'
                                // Seleziona un nodo agente con la label corrispondente all'architettura corrente
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            // Rende l'architettura corrente disponibile come variabile d'ambiente
                            ARCH = "${ARCHITECTURE}"
                            // Usa gli URL/Host IP perché il container potrebbe non risolvere i nomi .local
                            PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                            PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                            DISABLE_ERRORS = true // O qualsiasi altra variabile specifica per questo stage
                        }
                        steps {
                            script {
                                echo "--- Inizio Build cx_Freeze per ${env.ARCH} ---"
                                // Assicurati che withPythonEnv provenga dalla tua shared library o plugin
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt' // Rimuove 'packaging' se dà problemi
                                    sh "python -m pip install --break-system-packages -r requirements.txt"
                                    // Crea directory specifica per l'architettura
                                    sh "mkdir -p dist/${env.ARCH}/cxfreeze"
                                    sh "python -m pip install --break-system-packages cx_Freeze"
                                    // Specifica la directory di build specifica per l'architettura
                                    sh "python setup_cxfreeze.py build_exe --build-exe dist/${env.ARCH}/cxfreeze"
                                    // Rinomina l'artefatto per includere l'architettura
                                    sh "mv ./dist/${env.ARCH}/cxfreeze/main ${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                                }
                                echo "--- Fine Build cx_Freeze per ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                // Archivia l'artefatto con il nome specifico per l'architettura
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                                cleanWs()
                            }
                            failure {
                                echo "Build cx_Freeze fallita per ${env.ARCH}"
                                // Potresti voler archiviare log specifici in caso di fallimento
                                cleanWs()
                            }
                        }
                    } // Fine stage Build cx_Freeze per questa architettura

                    // --- Stage Nuitka eseguito per amd64 e arm64 ---
                    stage('Build Nuitka') {
                        agent {
                            dockerfile {
                                filename 'Dockerfile'
                                args '-u root'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                            PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                            DISABLE_ERRORS = true
                        }
                        steps {
                            script {
                                echo "--- Inizio Build Nuitka per ${env.ARCH} ---"
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt'
                                    sh "python -m pip install --break-system-packages -r requirements.txt"
                                    sh "python -m pip install --break-system-packages nuitka"
                                    // Crea directory specifiche
                                    sh "mkdir -p dist/${env.ARCH}/linux/nuitka dist/${env.ARCH}/windows/nuitka"

                                    // Build Linux (eseguita su host nativo ARCH)
                                    echo "Avvio Nuitka per Linux su host ${env.ARCH}"
                                    sh "python -m nuitka main.py --standalone --onefile --output-dir=dist/${env.ARCH}/linux/nuitka --enable-plugin=pyside6"
                                    // Rinomina artefatto Linux includendo l'architettura HOST
                                    sh "mv dist/${env.ARCH}/linux/nuitka/main.bin ${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"

                                    // Build Windows (cross-compilazione da host ARCH usando MinGW)
                                    // ATTENZIONE: La cross-compilazione per Windows con MinGW potrebbe funzionare
                                    // in modo affidabile solo da un host amd64. Considera di renderla condizionale:
                                    // if (env.ARCH == 'amd64') { ... }
                                    echo "Avvio Nuitka per Windows (cross-compile) su host ${env.ARCH}"
                                    sh "python -m nuitka main.py --standalone --onefile --windows-disable-console --mingw64 --output-dir=dist/${env.ARCH}/windows/nuitka --enable-plugin=pyside6"
                                    // Rinomina artefatto Windows includendo l'architettura HOST
                                    sh "mv dist/${env.ARCH}/windows/nuitka/main.bin ${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-win-nui.bin"
                                }
                                echo "--- Fine Build Nuitka per ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                // Archivia entrambi gli artefatti con nomi specifici per architettura HOST
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"
                                // Archivia l'artefatto windows solo se esiste (potrebbe fallire su arm64)
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-win-nui.bin", allowEmptyArchive: true
                                cleanWs()
                            }
                            failure {
                                echo "Build Nuitka fallita per ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    } // Fine stage Build Nuitka per questa architettura

                    // --- Stage PyOxidizer eseguito per amd64 e arm64 ---
                    stage('Build PyOxidizer') {
                        agent {
                            dockerfile {
                                filename 'Dockerfile'
                                args '-u root'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                            PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                            DISABLE_ERRORS = true
                        }
                        steps {
                            script {
                                echo "--- Inizio Build PyOxidizer per ${env.ARCH} ---"
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt'
                                    sh "python -m pip install --break-system-packages -r requirements.txt"
                                    sh "python -m pip install --break-system-packages pyoxidizer"
                                    // Crea directory specifica (potrebbe non essere necessaria)
                                    sh "mkdir -p dist/${env.ARCH}/pyoxidizer"

                                    // Esegui build PyOxidizer
                                    // Potrebbe essere necessario configurare pyoxidizer.bzl per target diversi (es. aarch64-unknown-linux-gnu)
                                    sh 'pyoxidizer build'

                                    // Determina il path sorgente dell'artefatto basato sull'architettura
                                    // *** IMPORTANTE: VERIFICA IL PATH CORRETTO PER ARM64! ***
                                    // Questo è un esempio basato su convenzioni comuni.
                                    def sourceBuildPath = "build/x86_64-unknown-linux-gnu/debug/install/${PROJECT_NAME}_app" // Nome definito in pyoxidizer.bzl?
                                    if (env.ARCH == 'arm64') {
                                        // Ipotesi comune per ARM64 Linux - VERIFICA QUESTO PATH!
                                        sourceBuildPath = "build/aarch64-unknown-linux-gnu/debug/install/${PROJECT_NAME}_app"
                                    } else if (env.ARCH != 'amd64') {
                                        // Gestione di altre architetture se necessario
                                        error("Architettura ${env.ARCH} non supportata per determinare il path di PyOxidizer")
                                    }

                                    echo "Cerco artefatto PyOxidizer in: ${sourceBuildPath}"
                                    // Verifica se il file sorgente esiste prima di copiare
                                    sh "ls -l ${sourceBuildPath}"

                                    // Copia e rinomina l'artefatto includendo l'architettura
                                    // Il nome finale dell'artefatto è definito in pyoxidizer.bzl, usa quello o rinominalo
                                    def finalArtifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin"
                                    sh "cp '${sourceBuildPath}' '${finalArtifactName}'" // Usa virgolette per sicurezza
                                    sh "chmod +r '${finalArtifactName}'" // Permesso lettura
                                }
                                echo "--- Fine Build PyOxidizer per ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                // Archivia l'artefatto con nome specifico per architettura
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin", fingerprint: true
                                cleanWs()
                            }
                            failure {
                                echo "Build PyOxidizer fallita per ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    } // Fine stage Build PyOxidizer per questa architettura

                } // Fine stages dentro matrix
            } // Fine matrix block

            // Azioni post eseguite dopo che *tutte* le combinazioni della matrix sono terminate
            // post { ... }

        } // Fine stage Build Packages Multi-Arch

        // Stage separato per la build macOS (attualmente solo su un agent amd64)
        stage('Build macOS Package (Requires macOS Agent)') {
            agent {
                // Assicurati che esista un nodo macOS con questa label in Jenkins
                label 'macos-amd64' // Esempio di label; adattala alla tua configurazione
            }
            environment {
                 // Definisci ARCH anche qui se serve per la build macOS
                 ARCH = "amd64"
            }
            steps {
                script {
                    echo "--- Inizio Build macOS Package su ${env.ARCH} ---"
                    // Qui inserisci i comandi specifici per la build macOS
                    // Potrebbe usare cx_Freeze, Nuitka, PyOxidizer o un altro tool (es. py2app)
                    // Assicurati che le dipendenze e Python siano configurati sull'agente macOS

                    // Esempio placeholder:
                    echo "Configurazione ambiente macOS..."
                    // sh 'source /path/to/venv/bin/activate' // Se usi venv
                    echo "Esecuzione comandi di build macOS..."
                    // sh 'python setup_py2app.py py2app' // Esempio con py2app

                    // Esempio ipotetico rinomina/archiviazione artefatto macOS
                    // def macArtifactName = "${PROJECT_NAME}_${VERSION}-macos-${env.ARCH}.dmg" // o .app, .pkg
                    // sh "mv ./dist/MyApp.dmg '${macArtifactName}'"
                    // archiveArtifacts artifacts: "${macArtifactName}"

                    echo "Placeholder: Comandi build macOS completati."
                    echo "--- Fine Build macOS Package su ${env.ARCH} ---"
                }
            }
             post {
                always {
                    cleanWs()
                }
             }
        } // Fine stage Build macOS Package

    } // Fine stages principali pipeline
} // Fine pipeline
@Library('shared-library') _

pipeline {
    agent none
    options {
        ansiColor('xterm')
        disableConcurrentBuilds(abortPrevious: true)
    }
    environment {
        VERSION = '0.1'
        PIP_INDEX_URL = 'http://hephaestus.local:5000/index/'
        PIP_TRUSTED_HOST = 'hephaestus.local'
        PROJECT_NAME = 'devildex'
        IP_TRUSTED_HOST = '192.168.2.11'
        IP_INDEX_URL = 'http://192.168.2.11:5000/index/'
        LINT_TAG_REGEX = '.*\\[lint\\].*'
    }
    stages {
        stage('Checkout') {
            agent any
            steps {
                script {
                    checkout scm
                }
            }
        }
        stage('Build Docker Image') {
            agent any
            steps {
                script {
                    sh 'docker build -t devil-dex-build:latest .'
                }
            }
        }
        stage('generate documentation') {
            when {
                not {
                            changelog "$LINT_TAG_REGEX"
                }
            }
            environment {
                        JENKINS_USER_NAME = sh(script: 'id -un', returnStdout: true)
                        JENKINS_USER_ID = sh(script: 'id -u', returnStdout: true)
                        JENKINS_GROUP_ID = sh(script: 'id -g', returnStdout: true)
            }
            agent {
                    dockerfile {
                            label 'general'
                            reuseNode true
                            args '-u root -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group \
                                  -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket'
                            filename 'Dockerfile'
                            dir 'ci_dockerfiles/generate_doc'
                    }
            }
            steps {
                        pythonGenerateDocsSphinx(packager: 'poetry')
            }
            post {
                        always {
                            publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false,
                                         reportDir: 'build/html', reportFiles: 'index.html',
                                         reportName: 'Documentation', reportTitles: '',
                                         useWrapperFileDirectly: true])
                        }
            }
        }
        stage('megalinter') {
            agent {
                docker {
                    label 'heracles'
                    image 'oxsecurity/megalinter-python:v8'
                    args "-u root -e VALIDATE_ALL_CODEBASE=true -v \${WORKSPACE}:/tmp/lint --entrypoint=''\
                          -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket"
                    reuseNode true
                }
            }
            environment {
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                DISABLE_ERRORS = true
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
        stage('test code') {
                    when {
                        not {
                            changelog "$LINT_TAG_REGEX"
                        }
                    }
                    agent {
                        dockerfile {
                            reuseNode true
                            args '-u root --privileged -v tmp-volume:/tmp -p 9901:9901'
                            filename 'Dockerfile'
                            dir 'ci_dockerfiles/pytest_x11'
                        }
                    }
                    environment {
                        PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                        PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                        LP_USER_ID = credentials('launchpad_id_conf_file')
                        PATH = "/root/.local/bin:${env.PATH}"
                        //PIP_FIND_LINKS = "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/fedora-38/"
                        PIP_FIND_LINKS = "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/"
                    }
                    options {
                        throttle(['pytest_telenium'])
                        retry(2)
                    }
                    steps {
                        sh 'echo "Variabile SHELL: $SHELL"'
                        sh 'mkdir -p ~/.bazaar/'
                        withCredentials([file(credentialsId: 'launchpad_id_conf_file', variable: 'LAUNCHPAD_CONFIG_FILE_PATH')])
                        {
                            sh 'cp "${LAUNCHPAD_CONFIG_FILE_PATH}" ~/.bazaar/launchpad.conf'
                        }
                        sh 'echo $PATH'
                        withPythonEnv('python3.13') {
                            sh 'mkdir -p /usr/local/bin/'
                            sh 'ln -s $(which python3.13) /usr/local/bin/python3.13'
                            sh 'mkdir -p /root/.config/pip/'
                            sh 'cp pip.conf /root/.config/pip/pip.conf'
                            sh 'python -m pip install -e . --timeout 10000'
                            sh 'touch app.log'
                            sh 'echo $PWD > pwd.log'
                            sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                            sh 'poetry export --without-hashes --format=requirements.txt --only test > requirements-test.txt'
                            sh 'sed -i /^packaging/d requirements.txt'
                            sh 'sed -i /^packaging/d requirements-test.txt'
                            sh 'sed -i /^typing_extensions/d requirements.txt'
                            pyTestXvfb(buildType: 'pip', pythonInterpreter: '/usr/local/bin/python3.13',
                                   skipMarkers: 'focus')
                            script {
                                def exists = fileExists 'core'
                                if (exists) {
                            echo 'core found'
                            sh 'pip install pystack'
                            sh 'pystack core core /usr/local/bin/python'
                            sh 'mv core oldcore'
                            sh 'pip list | grep pytest'
                                }
                                stash includes: 'coverage_report_xml/coverage.xml',
                                      name: 'coverageReportXML', allowEmpty: true
                            }
                        }
                    }
                    post {
                        always {
                            publishHTML([allowMissing: true, alwaysLinkToLastBuild: false, keepAll: false,
                                         reportDir: 'test_report', reportFiles: 'index.html',
                                         reportName: 'Test Report', reportTitles: '', useWrapperFileDirectly: true])
                            publishHTML([allowMissing: true, alwaysLinkToLastBuild: false, keepAll: false,
                                         reportDir: 'coverage_report', reportFiles: 'index.html',
                                         reportName: 'Coverage Report', reportTitles: '',
                                         useWrapperFileDirectly: true])
                            archiveArtifacts artifacts: 'errorxvfb.log', fingerprint: true, allowEmptyArchive: true
                            archiveArtifacts artifacts: 'screenshots/*.png', fingerprint: true, allowEmptyArchive: true
                            archiveArtifacts artifacts: 'pwd.log', fingerprint: true, allowEmptyArchive: true
                            archiveArtifacts artifacts: 'app.log', fingerprint: true, allowEmptyArchive: true
                            cleanWs()
                        }
                    }
        }
        stage('SonarQube analysis') {
            environment {
                SONAR_SCANNER_OPTS = '--add-opens java.base/sun.nio.ch=ALL-UNNAMED \
                                      --add-opens java.base/java.io=ALL-UNNAMED'
            }
            agent {
                docker {
                    label 'amd64'
                    image 'sonarsource/sonar-scanner-cli'
                    reuseNode true
                    args '-u root'
                }
            }
            steps {
                sh 'rm  *.html || true'
                script {
                    unstash 'coverageReportXML'
                    withSonarQubeEnv('sonarqube') {
                        sh 'sonar-scanner'
                    }
                }
            }
        }
                stage('Build Python Wheel') {
            agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                    label 'amd64'
                    reuseNode true
                }
            }
            environment {
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
            }
            steps {
                script {
                    echo '--- Starting Python Wheel Build ---'
                    withPythonEnv('python3.13') {
                        sh 'poetry build --format wheel'
                    }
                    echo '--- Python Wheel Build Finished ---'
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'dist/*.whl', followSymlinks: false, allowEmptyArchive: false
                    cleanWs()
                }
                failure {
                    echo 'Python Wheel Build Failed'
                    cleanWs()
                }
            }
                }
        stage('Build Packages Multi-Arch') {
            environment {
                PIP_FIND_LINKS = "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/"
            }
            matrix {
                axes {
                    axis {
                        name 'ARCHITECTURE'
                        values 'amd64', 'arm64'
                    }
                }
                stages {
                    stage('Build cx_Freeze') {
                        options {
                            retry(2)
                        }
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
                                echo "--- Start Build cx_Freeze for ${env.ARCH} ---"

                                def venvPath = "/tmp/devildex_cx_freeze_venv_${env.ARCH}"
                                sh """
                                    echo "[INFO] Initializing Conda and activating environment (conda_env)..."
                                    rm -rf "${venvPath}"

                                    echo "[INFO] Creating Python venv with system-site-packages at ${venvPath} using system python3..."

                                    /usr/bin/python3 -m venv --system-site-packages "${venvPath}"
                                    echo "[INFO] Activating Python venv (${venvPath})..."
                                    . "${venvPath}/bin/activate"
                                """
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for requirements export..."
            . "${venvPath}/bin/activate"

            echo "[INFO] Exporting requirements.txt using globally installed poetry..."
            # Poetry è installato globalmente nel Dockerfile e dovrebbe essere nel PATH
            poetry export -f requirements.txt --output requirements.txt --without-hashes

                                """
                                sh """
                                    if [ "${env.ARCH}" = "arm64" ]; then
                                        sed -i '/wxpython/d' requirements.txt
                                    fi
                                """
                             sh """
                                echo "[INFO] Activating Python venv (${venvPath}) for installing dependencies..."
            . "${venvPath}/bin/activate"

            echo "[INFO] Installing requirements.txt using venv pip..."
            # Con --system-site-packages, pip dovrebbe vedere wxPython (se listato in requirements.txt)
            # come già soddisfatto dalla versione di sistema e non tentare di compilarlo/reinstallarlo,
            # specialmente su arm64 dove PIP_FIND_LINKS non fornirà un wheel.
            # Su amd64, PIP_FIND_LINKS potrebbe comunque fornire un wheel che pip potrebbe preferire.
            pip install -r requirements.txt

            echo "[INFO] Installing cx_Freeze using venv pip..."
            pip install cx_Freeze
                            """
                            sh """
                                echo '[INFO] Activating Python venv (${venvPath}) for cx_Freeze build...'
            . "${venvPath}/bin/activate"

            mkdir -p dist/${env.ARCH}/cxfreeze

            echo '[INFO] Running cx_Freeze build using venv python...'
            python setup_cxfreeze.py build_exe --build-exe dist/${env.ARCH}/cxfreeze

            echo '[INFO] Moving built artifact...'
            mv ./dist/${env.ARCH}/cxfreeze/main \\
               "${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                            """
                            }
                        }
                        post {
                            success {
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                                cleanWs()
                            }
                            failure {
                                echo "Failed Build cx_Freeze for ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    }

                                        stage('Build Nuitka') {
                        options {
                            retry(2)
                        }
                        agent {
                            dockerfile {
                                filename 'Dockerfile' // Questo usa l'immagine ubuntu:plucky
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
                                echo "--- Starting Build Nuitka for ${env.ARCH} ---"
                                def venvPath = "/tmp/devildex_nuitka_venv_${env.ARCH}"

                                // Blocco 1: Crea il venv, attivalo e verifica
                                sh """
                                    echo "[INFO] Preparing Python virtual environment (venv) for Nuitka..."
                                    rm -rf "${venvPath}"

                                    echo "[INFO] Creating Python venv with system-site-packages at ${venvPath} using system python3..."
                                    /usr/bin/python3 -m venv --system-site-packages "${venvPath}"

                                    echo "[INFO] Activating Python venv (${venvPath})..."
                                    . "${venvPath}/bin/activate"

                                    echo "[DEBUG] Verifying Python and Pip from venv:"
                                    which python
                                    python --version
                                    which pip
                                    pip --version

                                    echo "[INFO] Upgrading pip in venv..."
                                    python -m pip install --upgrade pip
                                """

                                // Blocco 2: Esporta requirements.txt e gestisci wxPython per arm64
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for Nuitka requirements management..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Exporting requirements.txt using globally installed poetry..."
                                    poetry export -f requirements.txt --output requirements.txt --without-hashes

                                    if [ "${env.ARCH}" = "arm64" ]; then
                                        echo "[INFO] ARM64: Verifying system wxPython importability in venv for Nuitka..."
                                        if python -c "import wx; print(f'[DEBUG] ARM64: wxPython (system) version in venv: {wx.version()}; Path: {wx.__file__}')"; then
                                            echo "[INFO] ARM64: Successfully imported wxPython from system path into venv for Nuitka."
                                            echo "[INFO] ARM64: Content of requirements.txt BEFORE wxPython removal (Nuitka):"
                                            cat requirements.txt
                                            echo "[INFO] ARM64: Removing wxPython from requirements.txt to rely on system version for Nuitka."
                                            sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            echo "[INFO] ARM64: Content of requirements.txt AFTER wxPython removal (Nuitka):"
                                            cat requirements.txt
                                        else
                                            echo "[ERROR] ARM64: FAILED to import wxPython from system path into venv for Nuitka. Build will likely fail."
                                            exit 1
                                        fi
                                    fi
                                """

                                // Blocco 3: Installa dipendenze, Nuitka ed esegui la build
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for Nuitka build..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Installing requirements.txt for Nuitka using venv pip..."
                                    python -m pip install -r requirements.txt

                                    echo "[INFO] Installing Nuitka using venv pip..."
                                    python -m pip install nuitka

                                    mkdir -p dist/${env.ARCH}/linux/nuitka
                                    echo "Starting Nuitka build for Linux on host ${env.ARCH} using venv python..."
                                    python -m nuitka src/devildex/main.py --standalone --onefile \
                                        --output-dir=dist/${env.ARCH}/linux/nuitka
                                """
                                sh "mv dist/${env.ARCH}/linux/nuitka/main.bin \
                                        ${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"
                                echo "--- Build Nuitka finished for ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"
                                cleanWs()
                            }
                            failure {
                                echo "Build Nuitka failed for ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    }


                                       stage('Build PyOxidizer') {
                        options {
                            retry(2)
                        }
                        agent {
                            dockerfile {
                                filename 'Dockerfile' // Questo usa l'immagine ubuntu:plucky
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
                            // PYTHON_VERSION è implicitamente 3.13 dal Dockerfile
                        }
                        steps {
                            script {
                                echo "--- Start Build PyOxidizer for ${env.ARCH} ---"
                                def venvPath = "/tmp/devildex_pyoxidizer_venv_${env.ARCH}"

                                // Blocco 1: Crea il venv, attivalo e verifica
                                sh """
                                    echo "[INFO] Preparing Python virtual environment (venv) for PyOxidizer..."
                                    rm -rf "${venvPath}"

                                    echo "[INFO] Creating Python venv with system-site-packages at ${venvPath} using system python3..."
                                    /usr/bin/python3 -m venv --system-site-packages "${venvPath}"

                                    echo "[INFO] Activating Python venv (${venvPath})..."
                                    . "${venvPath}/bin/activate"

                                    echo "[DEBUG] Verifying Python and Pip from venv:"
                                    which python
                                    python --version
                                    which pip
                                    pip --version

                                    echo "[INFO] Upgrading pip in venv..."
                                    python -m pip install --upgrade pip
                                """

                                // Blocco 2: Esporta requirements.txt e gestisci wxPython per arm64
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for PyOxidizer requirements management..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Exporting requirements.txt using globally installed poetry..."
                                    poetry export -f requirements.txt --output requirements.txt --without-hashes

                                    if [ "${env.ARCH}" = "arm64" ]; then
                                        echo "[INFO] ARM64: Verifying system wxPython importability in venv for PyOxidizer..."
                                        if python -c "import wx; print(f'[DEBUG] ARM64: wxPython (system) version in venv: {wx.version()}; Path: {wx.__file__}')"; then
                                            echo "[INFO] ARM64: Successfully imported wxPython from system path into venv for PyOxidizer."
                                            echo "[INFO] ARM64: Content of requirements.txt BEFORE wxPython removal (PyOxidizer):"
                                            cat requirements.txt
                                            echo "[INFO] ARM64: Removing wxPython from requirements.txt to rely on system version for PyOxidizer."
                                            sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            echo "[INFO] ARM64: Content of requirements.txt AFTER wxPython removal (PyOxidizer):"
                                            cat requirements.txt
                                        else
                                            echo "[ERROR] ARM64: FAILED to import wxPython from system path into venv for PyOxidizer. Build will likely fail."
                                            echo "[ERROR] Ensure 'python3-wxgtk4.0' is correctly installed via apt and compatible with system Python."
                                            exit 1
                                        fi
                                    fi
                                """

                                // Blocco 3: Installa dipendenze, PyOxidizer ed esegui la build
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for PyOxidizer build..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Installing requirements.txt for PyOxidizer using venv pip..."
                                    python -m pip install -r requirements.txt

                                    echo "[INFO] Installing PyOxidizer using venv pip..."
                                    python -m pip install pyoxidizer

                                    echo "[INFO] Running PyOxidizer build using venv..."
                                    # mkdir -p dist/${env.ARCH}/pyoxidizer # Questa riga potrebbe non essere necessaria
                                                                        # se PyOxidizer crea la sua struttura in 'build/'
                                    pyoxidizer build
                                """

                                // Blocco 4: Gestione artefatti (invariato, ma ora opera dopo i passaggi nel venv)
                                def sourceFolder = '-unknown-linux-gnu/debug/install/'
                                // Assicurati che PYTHON_VERSION sia disponibile o definito se usato qui,
                                // ma il path di PyOxidizer di solito non dipende dalla versione Python nel nome della cartella build
                                def sourceBuildPath = "build/x86_64${sourceFolder}${PROJECT_NAME}_app"
                                if (env.ARCH == 'arm64') {
                                    sourceBuildPath = "build/aarch64${sourceFolder}${PROJECT_NAME}_app"
                                } else if (env.ARCH != 'amd64') {
                                    error("Architecture ${env.ARCH} not supported for determining PyOxidizer path")
                                }
                                echo "Searching for PyOxidizer artifact in: ${sourceBuildPath}"
                                def finalArtifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin"
                                sh "cp '${sourceBuildPath}' '${finalArtifactName}'"
                                sh "chmod +r '${finalArtifactName}'"
                                echo "--- End Build PyOxidizer for ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin",
                                                 fingerprint: true
                                cleanWs()
                            }
                            failure {
                                echo "Failed Build PyOxidizer for ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    }


                                        stage('Build PyInstaller') {
                        options {
                            retry(2)
                        }
                        agent {
                            dockerfile {
                                filename 'Dockerfile' // Questo usa l'immagine ubuntu:plucky
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
                                echo "--- Start Build PyInstaller for ${env.ARCH} ---"
                                def venvPath = "/tmp/devildex_pyinstaller_venv_${env.ARCH}"

                                // Blocco 1: Crea il venv, attivalo e verifica
                                sh """
                                    echo "[INFO] Preparing Python virtual environment (venv) for PyInstaller..."
                                    rm -rf "${venvPath}"

                                    echo "[INFO] Creating Python venv with system-site-packages at ${venvPath} using system python3..."
                                    /usr/bin/python3 -m venv --system-site-packages "${venvPath}"

                                    echo "[INFO] Activating Python venv (${venvPath})..."
                                    . "${venvPath}/bin/activate"

                                    echo "[DEBUG] Verifying Python and Pip from venv:"
                                    which python
                                    python --version
                                    which pip
                                    pip --version

                                    echo "[INFO] Upgrading pip in venv..."
                                    python -m pip install --upgrade pip
                                """

                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for PyInstaller requirements management..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Exporting requirements.txt using globally installed poetry..."
                                    poetry export -f requirements.txt --output requirements.txt --without-hashes

                                    if [ "${env.ARCH}" = "arm64" ]; then
                                        echo "[INFO] ARM64: Verifying system wxPython importability in venv for PyInstaller..."
                                        if python -c "import wx; print(f'[DEBUG] ARM64: wxPython (system) version in venv: {wx.version()}; Path: {wx.__file__}')"; then
                                            echo "[INFO] ARM64: Successfully imported wxPython from system path into venv for PyInstaller."
                                            echo "[INFO] ARM64: Content of requirements.txt BEFORE wxPython removal (PyInstaller):"
                                            cat requirements.txt
                                            echo "[INFO] ARM64: Removing wxPython from requirements.txt to rely on system version for PyInstaller."
                                            sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            echo "[INFO] ARM64: Content of requirements.txt AFTER wxPython removal (PyInstaller):"
                                            cat requirements.txt
                                        else
                                            echo "[ERROR] ARM64: FAILED to import wxPython from system path into venv for PyInstaller. Build will likely fail."
                                            echo "[ERROR] Ensure 'python3-wxgtk4.0' is correctly installed via apt and compatible with system Python."
                                            exit 1
                                        fi
                                    fi
                                """

                                // Blocco 3: Installa dipendenze, PyInstaller ed esegui la build
                                sh """
                                    echo "[INFO] Activating Python venv (${venvPath}) for PyInstaller build..."
                                    . "${venvPath}/bin/activate"

                                    echo "[INFO] Installing requirements.txt for PyInstaller using venv pip..."
                                    python -m pip install -r requirements.txt

                                    echo "[INFO] Installing PyInstaller using venv pip..."
                                    python -m pip install pyinstaller

                                    echo "[INFO] Running PyInstaller build using venv..."
                                    mkdir -p dist/${env.ARCH}/pyinstaller // Assicura che la directory esista
                                    pyinstaller --noconfirm --onefile --console src/devildex/main.py \
                                        --distpath dist/${env.ARCH}/pyinstaller \
                                        --workpath build/pyinstaller_work_${env.ARCH} --name ${PROJECT_NAME}
                                """
                                // Blocco 4: Sposta l'artefatto (separato per chiarezza, ma potrebbe essere unito al precedente)
                                sh """
                                    echo "[INFO] Moving PyInstaller artifact..."
                                    mv dist/${env.ARCH}/pyinstaller/${PROJECT_NAME} \
                                        ${PROJECT_NAME}_${VERSION}-${env.ARCH}-pyi.bin
                                """
                                echo "--- End Build PyInstaller for ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-pyi.bin"
                                cleanWs()
                            }
                            failure {
                                echo "Failed Build PyInstaller for ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    }
                }
            }
        }
    }
}

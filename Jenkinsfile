@Library('shared-library') _

pipeline {
    agent none
    options {
        ansiColor('xterm')
        disableConcurrentBuilds(abortPrevious: true)
    }
    environment {
        VERSION = '0.1'
        PROJECT_NAME = 'devildex'
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
        stage('Build Python Wheel') {
            agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                    label 'amd64'
                    reuseNode true
                }
            }
            steps {
                script {
                    echo '--- Starting Python Wheel Build ---'
                    withPythonEnv('python3.13') {
                        withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                         string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                            withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                                sh 'poetry build --format wheel --no-interaction --no-ansi --verbose'
                            }
                        }
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
                    dir 'ci_dockerfiles/pytest_ubuntu_x11'
                    label 'amd64'
                }
            }
            environment {
                LP_USER_ID = credentials('launchpad_id_conf_file')
                PATH = "/root/.local/bin:${env.PATH}"
                PIP_FIND_LINKS = 'https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/'
            }
            options {
                throttle(['pytest_telenium'])
                retry(2)
            }
            steps {
                sh 'echo "Variable SHELL: $SHELL"'
                sh 'mkdir -p ~/.bazaar/'
                withCredentials([file(credentialsId: 'launchpad_id_conf_file', variable: 'LAUNCHPAD_CONFIG_FILE_PATH')]) {
                    sh 'cp "${LAUNCHPAD_CONFIG_FILE_PATH}" ~/.bazaar/launchpad.conf'
                }
                sh 'echo $PATH'
                withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                 string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                    withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                        sh 'poetry export --with test -f requirements.txt --output requirements.txt --without-hashes'
                        sh 'poetry export --without-hashes --format=requirements.txt --only test > requirements-test.txt'
                        sh 'pip install -r requirements.txt --index-url $IP_INDEX_URL --trusted-host $IP_TRUSTED_HOST'
                        sh 'pip install --no-deps -e . --index-url $IP_INDEX_URL --trusted-host $IP_TRUSTED_HOST'
                    }
                }

                pyTestXvfb(buildType: 'pip', pythonInterpreter: 'python', skipMarkers: '')
                script {
                    def exists = fileExists 'core'
                    if (exists) {
                        echo 'core found'
                        sh 'pip install pystack'
                        sh 'pystack core core python'
                        sh 'mv core oldcore'
                        sh 'pip list | grep pytest'
                    }
                    stash includes: 'coverage_report_xml/coverage.xml',
                          name: 'coverageReportXML', allowEmpty: true
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
                SONAR_TOKEN = credentials('SONAR_TOKEN')
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
                sh 'rm *.html || true'
                script {
                    unstash 'coverageReportXML'
                    withSonarQubeEnv('sonarqube') {
                        sh 'sonar-scanner'
                    }
                }
            }
        }

        stage('Build Packages Multi-Arch') {
            when {
                expression { false }
            }
            environment {
                PIP_FIND_LINKS = 'https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/'
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
                            DISABLE_ERRORS = true
                        }
                        steps {
                            withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                             string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                                withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                                    script {
                                        echo "--- Start Build cx_Freeze for ${env.ARCH} ---"
                                        def venvPath = "/tmp/devildex_cx_freeze_venv_${env.ARCH}"

                                        sh """
                                            echo "[INFO] Initializing Conda and activating environment (conda_env)..."
                                            rm -rf "${venvPath}"
                                            echo "[INFO] Creating venv with system-site-packages at ${venvPath}"
                                            python -m venv --system-site-packages "${venvPath}"
                                            echo "[INFO] Activating Python venv (${venvPath})..."
                                            . "${venvPath}/bin/activate"

                                            echo "[INFO] Exporting requirements.txt using globally installed poetry..."
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
                                            pip install -r requirements.txt --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST

                                            echo "[INFO] Installing cx_Freeze using venv pip..."
                                            pip install cx_Freeze --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
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
                            }
                        }
                        post {
                            success {
                                script {
                                    def artifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                                    stash name: "executable-cx_Freeze-${env.ARCH}", includes: artifactName
                                }
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
                                filename 'Dockerfile'
                                args '-u root'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            DISABLE_ERRORS = true
                        }
                        steps {
                             withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                             string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                                withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                                    script {
                                        echo "--- Starting Build Nuitka for ${env.ARCH} ---"
                                        def venvPath = "/tmp/devildex_nuitka_venv_${env.ARCH}"

                                        sh """
                                            echo "[INFO] Preparing Python virtual environment (venv) for Nuitka..."
                                            rm -rf "${venvPath}"
                                            python -m venv --system-site-packages "${venvPath}"
                                            . "${venvPath}/bin/activate"
                                            python -m pip install --upgrade pip
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            poetry export -f requirements.txt --output requirements.txt --without-hashes
                                            if [ "${env.ARCH}" = "arm64" ]; then
                                                    sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            fi
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            echo "[INFO] Installing requirements.txt for Nuitka using venv pip..."
                                            python -m pip install -r requirements.txt --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                            echo "[INFO] Installing Nuitka using venv pip..."
                                            python -m pip install nuitka --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                        """

                                        sh """
                                            mv dist/${env.ARCH}/linux/nuitka/main.bin \\
                                                ${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin
                                        """
                                        echo "--- Build Nuitka finished for ${env.ARCH} ---"
                                    }
                                }
                            }
                        }
                        post {
                            success {
                                script {
                                    def artifactName = "${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"
                                    stash name: "executable-Nuitka-${env.ARCH}", includes: artifactName
                                }
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
                                filename 'Dockerfile'
                                args '-u root'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            DISABLE_ERRORS = true
                        }
                        steps {
                            withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                             string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                                withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                                    script {
                                        echo "--- Start Build PyOxidizer for ${env.ARCH} ---"
                                        def venvPath = "/tmp/devildex_pyoxidizer_venv_${env.ARCH}"

                                        sh """
                                            rm -rf "${venvPath}"
                                            python -m venv --system-site-packages "${venvPath}"
                                            . "${venvPath}/bin/activate"
                                            python -m pip install --upgrade pip
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            poetry export -f requirements.txt --output requirements.txt --without-hashes
                                            if [ "${env.ARCH}" = "arm64" ]; then
                                                    sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            fi
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            python -m pip install -r requirements.txt --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                            python -m pip install pyoxidizer --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                        """

                                        def sourceFolder = '-unknown-linux-gnu/debug/install/'
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
                            }
                        }
                        post {
                            success {
                                script {
                                    def artifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin"
                                    stash name: "executable-PyOxidizer-${env.ARCH}", includes: artifactName
                                }
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
                                filename 'Dockerfile'
                                args '-u root'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            DISABLE_ERRORS = true
                        }
                        steps {
                            withCredentials([string(credentialsId: 'INTERNAL_PIP_INDEX_URL_IP', variable: 'PIP_INDEX_URL_VAR'),
                                             string(credentialsId: 'HEPHAESTUS_IP', variable: 'PIP_TRUSTED_HOST_VAR')]) {
                                withEnv(["IP_INDEX_URL=${PIP_INDEX_URL_VAR}", "IP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VAR}"]) {
                                    script {
                                        echo "--- Start Build PyInstaller for ${env.ARCH} ---"
                                        def venvPath = "/tmp/devildex_pyinstaller_venv_${env.ARCH}"

                                        sh """
                                            rm -rf "${venvPath}"
                                            python -m venv --system-site-packages "${venvPath}"
                                            . "${venvPath}/bin/activate"
                                            python -m pip install --upgrade pip
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            poetry export -f requirements.txt --output requirements.txt --without-hashes
                                            if [ "${env.ARCH}" = "arm64" ]; then
                                                    sed -i '/^[wW][xX][pP][yY][tT][hH][oO][nN]/d' requirements.txt
                                            fi
                                        """

                                        sh """
                                            . "${venvPath}/bin/activate"
                                            python -m pip install -r requirements.txt --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                            python -m pip install pyinstaller --index-url \$IP_INDEX_URL --trusted-host \$IP_TRUSTED_HOST
                                            mkdir -p dist/${env.ARCH}/pyinstaller
                                            pyinstaller --noconfirm --onefile --console src/devildex/main.py \\
                                                --distpath dist/${env.ARCH}/pyinstaller \\
                                                --workpath build/pyinstaller_work_${env.ARCH} --name ${PROJECT_NAME}
                                        """

                                        sh """
                                            mv dist/${env.ARCH}/pyinstaller/${PROJECT_NAME} \\
                                                ${PROJECT_NAME}_${VERSION}-${env.ARCH}-pyi.bin
                                        """
                                        echo "--- End Build PyInstaller for ${env.ARCH} ---"
                                    }
                                }
                            }
                        }
                        post {
                            success {
                                script {
                                    def artifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-pyi.bin"
                                    stash name: "executable-PyInstaller-${env.ARCH}", includes: artifactName
                                }
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
        stage('Smoke Test and Archive Executables') {
            when {
                expression { false }
            }
            matrix {
                axes {
                    axis {
                        name 'ARCHITECTURE'
                        values 'amd64', 'arm64'
                    }
                    axis {
                        name 'TOOL'
                        values 'cx_Freeze', 'Nuitka', 'PyOxidizer', 'PyInstaller'
                    }
                }
                stages {
                    stage('Run Smoke Test') {
                        agent {
                            dockerfile {
                                filename 'Dockerfile'
                                dir 'ci_dockerfiles/smoke_runner'
                                label "${ARCHITECTURE}"
                                reuseNode true
                            }
                        }
                        environment {
                            ARCH = "${ARCHITECTURE}"
                            BUILD_TOOL = "${TOOL}"
                            STASHED_EXECUTABLE_NAME_PATTERN = "executable-${TOOL}-${ARCH}"
                        }
                        steps {
                            script {
                                def artifactFileName
                                switch (BUILD_TOOL) {
                                    case 'cx_Freeze':
                                        artifactFileName = "${PROJECT_NAME}_${VERSION}-${ARCH}-cx.bin"
                                        break
                                    case 'Nuitka':
                                        artifactFileName = "${PROJECT_NAME}_${VERSION}-host_${ARCH}-lin-nui.bin"
                                        break
                                    case 'PyOxidizer':
                                        artifactFileName = "${PROJECT_NAME}_${VERSION}-${ARCH}-oxi.bin"
                                        break
                                    case 'PyInstaller':
                                        artifactFileName = "${PROJECT_NAME}_${VERSION}-${ARCH}-pyi.bin"
                                        break
                                    default:
                                        error("Unknown build tool for smoke test: ${BUILD_TOOL}")
                                        return
                                }

                                def smokeTestPassed = false
                                def testLogContent = "Smoke test log for ${artifactFileName} (${BUILD_TOOL}, ${ARCH}):\n"
                                def smokeTestStatus = 'UNKNOWN'
                                def reportLine = "Tool: ${BUILD_TOOL}, Arch: ${ARCH}, Artifact: ${artifactFileName}, Status: "
                                def workspace = pwd()
                                def smokeResultsDir = "${workspace}/smoke_results_${BUILD_TOOL}_${ARCH}"
                                def detailedLogFile = "smoke_test_logs/${BUILD_TOOL}-${ARCH}-${artifactFileName}.log"
                                def smokeTestScriptPath = 'ci_scripts/smoke_test_agent.sh'

                                try {
                                    echo "Attempting to unstash ${STASHED_EXECUTABLE_NAME_PATTERN} (expected file: ${artifactFileName})"
                                    unstash name: STASHED_EXECUTABLE_NAME_PATTERN

                                    if (!fileExists(artifactFileName)) {
                                        error("Stashed artifact ${artifactFileName} not found after unstash for ${STASHED_EXECUTABLE_NAME_PATTERN}.")
                                    }
                                    sh "mkdir -p ${smokeResultsDir}"
                                    sh 'mkdir -p smoke_test_logs'
                                    sh "touch ${smokeResultsDir}/smoke_test_status.txt"
                                    sh "chmod +x ${smokeTestScriptPath}"

                                    sh "${smokeTestScriptPath} \"${artifactFileName}\" \"${smokeResultsDir}\""

                                    if (fileExists("${smokeResultsDir}/smoke_test_status.txt")) {
                                        smokeTestStatus = readFile("${smokeResultsDir}/smoke_test_status.txt").trim()
                                        if (fileExists("${smokeResultsDir}/smoke_test_run.log")) {
                                            testLogContent += readFile("${smokeResultsDir}/smoke_test_run.log")
                                        }
                                        if (smokeTestStatus.startsWith('PASS')) {
                                            smokeTestPassed = true
                                        }
                                    } else {
                                        echo "Smoke test FAILED for ${artifactFileName}. Archiving to 'failed/' directory."
                                        sh 'mkdir -p failed'
                                        sh "mv '${artifactFileName}' failed/"
                                        archiveArtifacts artifacts: "failed/${artifactFileName}", allowEmptyArchive: true
                                    }
                                } catch (Exception e) {
                                    echo "Smoke test Jenkins script execution failed for ${artifactFileName}: ${e}"
                                    testLogContent += "\\nJenkins-level Exception: ${e}"
                                    smokeTestStatus = 'JENKINS_ERROR'
                                    smokeTestPassed = false
                                }

                                writeFile file: detailedLogFile, text: testLogContent
                                reportLine += smokeTestStatus
                                def individualReportFragmentFile = "report_fragment_${BUILD_TOOL}_${ARCH}.txt"
                                writeFile file: individualReportFragmentFile, text: "${reportLine}\n"
                                stash name: "smoke_report_fragment_${BUILD_TOOL}_${ARCH}", includes: individualReportFragmentFile

                                if (smokeTestPassed) {
                                    echo "Smoke test PASSED for ${artifactFileName}. Archiving to standard location (root of artifacts)."
                                    archiveArtifacts artifacts: artifactFileName, allowEmptyArchive: true
                                } else {
                                    echo "Smoke test FAILED for ${artifactFileName}. Archiving to 'failed/' directory."
                                    sh 'mkdir -p failed'
                                    sh "mv '${artifactFileName}' failed/"
                                    archiveArtifacts artifacts: "failed/${artifactFileName}", allowEmptyArchive: true
                                }

                                sh "rm -f ${artifactFileName}"
                                sh "rm -rf ${smokeResultsDir}"
                            }
                        }
                        post {
                            always {
                                archiveArtifacts artifacts: 'smoke_test_logs/**/*.log', allowEmptyArchive: true
                                cleanWs()
                            }
                        }
                    }
                }
            }
        }
    }
}
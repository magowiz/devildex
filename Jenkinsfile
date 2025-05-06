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

        stage('megalinter') {
            agent {
                docker {
                    label 'heracles'
                    image 'oxsecurity/megalinter-python:v8.4.0'
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

        stage('Build Packages Multi-Arch') {
            matrix {
                axes {
                    axis {
                        name 'ARCHITECTURE'
                        values 'amd64', 'arm64'
                    }
                }
                stages {
                    stage('Build cx_Freeze') {
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
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt'
                                    sh 'python -m pip install --break-system-packages -r requirements.txt'
                                    sh "mkdir -p dist/${env.ARCH}/cxfreeze"
                                    sh 'python -m pip install --break-system-packages cx_Freeze'
                                    sh "python setup_cxfreeze.py build_exe --build-exe dist/${env.ARCH}/cxfreeze"
                                    sh "mv ./dist/${env.ARCH}/cxfreeze/main \
                                        ${PROJECT_NAME}_${VERSION}-${env.ARCH}-cx.bin"
                                }
                                echo "--- End Build cx_Freeze for ${env.ARCH} ---"
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
                                echo "--- Starting Build Nuitka for ${env.ARCH} ---"
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt'
                                    sh "python -m pip install --break-system-packages -r requirements.txt"
                                    sh "python -m pip install --break-system-packages nuitka"

                                    sh "mkdir -p dist/${env.ARCH}/linux/nuitka dist/${env.ARCH}/windows/nuitka"

                                    echo "Starting Nuitka build for Linux on host ${env.ARCH}"
                                    sh "python -m nuitka src/devildex/main.py --standalone --onefile --output-dir=dist/${env.ARCH}/linux/nuitka --enable-plugin=pyside6"
                                    sh "mv dist/${env.ARCH}/linux/nuitka/main.bin ${PROJECT_NAME}_${VERSION}-host_${env.ARCH}-lin-nui.bin"
                                }
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
                                echo "--- Start Build PyOxidizer for ${env.ARCH} ---"
                                withPythonEnv('python3.13') {
                                    sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                                    sh 'sed -i /^packaging/d requirements.txt'
                                    sh "python -m pip install --break-system-packages -r requirements.txt"
                                    sh "python -m pip install --break-system-packages pyoxidizer"
                                    sh "mkdir -p dist/${env.ARCH}/pyoxidizer"

                                    sh 'pyoxidizer build'

                                    def sourceBuildPath = "build/x86_64-unknown-linux-gnu/debug/install/${PROJECT_NAME}_app"
                                    if (env.ARCH == 'arm64') {
                                        sourceBuildPath = "build/aarch64-unknown-linux-gnu/debug/install/${PROJECT_NAME}_app"
                                    } else if (env.ARCH != 'amd64') {
                                        error("Architecture ${env.ARCH} not supported for determining PyOxidizer path")
                                    }

                                    echo "Searching for PyOxidizer artifact in: ${sourceBuildPath}"
                                    sh "ls -l ${sourceBuildPath}"

                                    def finalArtifactName = "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin"
                                    sh "cp '${sourceBuildPath}' '${finalArtifactName}'"
                                    sh "chmod +r '${finalArtifactName}'"
                                }
                                echo "--- End Build PyOxidizer for ${env.ARCH} ---"
                            }
                        }
                        post {
                            success {
                                archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-${env.ARCH}-oxi.bin", fingerprint: true
                                cleanWs()
                            }
                            failure {
                                echo "Failed Build PyOxidizer for ${env.ARCH}"
                                cleanWs()
                            }
                        }
                    }

                }
            }

        }

        stage('Build macOS Package (Requires macOS Agent)') {
            agent {
                label 'amd64'
            }
            environment {
                 ARCH = "amd64"
            }
            steps {
                script {
                    echo "--- Start Build macOS Package on ${env.ARCH} ---"

                    echo "Configuring macOS environment..."
                    echo "Executing macOS build commands ..."

                    echo 'Placeholder: build macOS Commands completed.'
                    echo "--- End Build macOS Package on ${env.ARCH} ---"
                }
            }
            post {
                always {
                    cleanWs()
                }
             }
        }
    }
}

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
                cleanWs()
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
        stage('Test cx_Freeze') {
                    environment {
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                DISABLE_ERRORS = true
            }
            agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                }
            }
            steps {
                script {
                    catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                    echo 'Setting up Python env and testing cx_Freeze build...'
                    withPythonEnv('python3.13') {
                        echo "Python environment activated."
                        sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                        echo "requirements.txt generated."

                        sh 'python -m pip install --break-system-packages -r requirements.txt'
                        echo "Project dependencies installed with pip."
                        sh 'mkdir -p dist/linux/cxfreeze dist/windows/cxfreeze'
                        echo "Output directories created."
                        sh "python -m pip install --break-system-packages cx_Freeze"
                        sh 'python setup_cxfreeze.py build_exe --build-exe dist/linux/cxfreeze'
                        echo "cx_Freeze Linux build attempted."

                        sh 'python setup_cxfreeze.py build_exe --build-exe dist/windows/cxfreeze'
                        echo "cx_Freeze Windows build attempted."
                    }
                }}
            }
            post {
                success {
                    echo 'Archiving build artifacts...'
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/linux/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/windows/**/*', allowEmptyArchive: true
                }
                always {
                    cleanWs()
                }
            }
        }
        stage('Test Nuitka') {
                        environment {
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                DISABLE_ERRORS = true
            }
             agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                }
            }
            steps {
                script {
                    catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                    echo 'Setting up Python env and testing Nuitka build...'

                        withPythonEnv('python3.13') {
                            echo "Python environment activated."

                            sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                            echo "requirements.txt generated."

                            sh 'python -m pip install --break-system-packages -r requirements.txt'
                            echo "Project dependencies installed with pip."

                            sh 'python -m pip install --break-system-packages nuitka'
                            echo "Nuitka installed in venv."

                            sh 'mkdir -p dist/linux/nuitka dist/windows/nuitka'
                            echo "Output directories created."

                            sh 'python -m nuitka main.py --standalone --output-dir=dist/linux/nuitka --enable-plugin=pyside6'
                            echo "Nuitka Linux build attempted."

                            sh 'python -m nuitka main.py --standalone --windows-disable-console --mingw64 --output-dir=dist/windows/nuitka --enable-plugin=pyside6'
                            echo "Nuitka Windows build attempted."
                        }
                    }
                }
            post {
                success {
                    echo 'Archiving build artifacts...'
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/linux/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/windows/**/*', allowEmptyArchive: true
                }
                always {
                    cleanWs()
                }
            }
            }
        }

         stage('Test PyOxidizer') {
                     environment {
                PIP_INDEX_URL = "${env.IP_INDEX_URL}"
                PIP_TRUSTED_HOST = "${env.IP_TRUSTED_HOST}"
                DISABLE_ERRORS = true
            }

             agent {
                dockerfile {
                     filename 'Dockerfile'
                     args '-u root'
                }
            }
            steps {
                script {
                    catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                    echo 'Setting up Python env and testing PyOxidizer build...'

                        withPythonEnv('python3.13') {
                            echo "Python environment activated."

                            sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                            echo "requirements.txt generated."

                            sh 'python -m pip install --break-system-packages -r requirements.txt'
                            echo "Project dependencies installed with pip."

                            sh 'python -m pip install --break-system-packages pyoxidizer'
                            echo "PyOxidizer installed in venv."

                            sh 'mkdir -p dist/linux/pyoxidizer dist/windows/pyoxidizer'
                            echo "Output directories prepared (build output will be in ./build/ by default)."

                            sh 'pyoxidizer build'
                            echo "PyOxidizer build attempted."

                            sh 'cp -r build/x86_64-unknown-linux-gnu/debug/install/* dist/linux/pyoxidizer/'
                            sh 'cp -r build/x86_64-pc-windows-gnu/debug/install/* dist/windows/pyoxidizer/'
                            echo "PyOxidizer artifacts copied to dist/."
                        }
                    }
                }
            }
            post {
                success {
                    echo 'Archiving build artifacts...'
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/linux/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/windows/**/*', allowEmptyArchive: true
                }
                always {
                    cleanWs()
                }
            }
        }

        stage('Build macOS Package (Requires macOS Agent)') {
            agent {
                label 'amd64'
            }
            steps {
                 script {
                     echo 'This stage runs on a macOS agent to build the macOS package.'
                     echo 'Setup and commands for macOS build go here (e.g., using one of the tools).'
                     echo "macOS build stage - Placeholder"
                 }
            }
        }
    }
}
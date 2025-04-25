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
        stage('build packages')
        {
            parallel {
        stage('Build cx_Freeze') {
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
                    withPythonEnv('python3.13') {
                        sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                        sh 'python -m pip install --break-system-packages -r requirements.txt'
                        sh 'mkdir -p dist/linux/cxfreeze'
                        sh "python -m pip install --break-system-packages cx_Freeze"
                        sh 'python setup_cxfreeze.py build_exe --build-exe dist/linux/cxfreeze'
                        sh "mv ./dist/linux/cxfreeze/main ${PROJECT_NAME}_${VERSION}-cx.bin"
                    }
                }
            }
            post {
                success {
                    echo 'Archiving build artifacts...'
                    archiveArtifacts artifacts: "${PROJECT_NAME}_${VERSION}-cx.bin"
                    cleanWs()
                }
                failure {
                    cleanWs()
                }
            }
        }
        stage('Build Nuitka') {
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
                        withPythonEnv('python3.13') {
                            sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                            sh 'python -m pip install --break-system-packages -r requirements.txt'
                            sh 'python -m pip install --break-system-packages nuitka'
                            sh 'mkdir -p dist/linux/nuitka dist/windows/nuitka'
                            sh 'python -m nuitka main.py --standalone --onefile --output-dir=dist/linux/nuitka --enable-plugin=pyside6'
                            sh 'python -m nuitka main.py --standalone --onefile --windows-disable-console --mingw64 --output-dir=dist/windows/nuitka --enable-plugin=pyside6'
                            sh 'find'
                        }
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip'
                    archiveArtifacts artifacts: 'dist/linux/**/*'
                    archiveArtifacts artifacts: 'dist/windows/**/*'
                }
                always {
                    cleanWs()
                }
            }
        }

         stage('Build PyOxidizer') {
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

                        withPythonEnv('python3.13') {
                            sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                            sh 'python -m pip install --break-system-packages -r requirements.txt'
                            sh 'python -m pip install --break-system-packages pyoxidizer'
                            sh 'mkdir -p dist/linux/pyoxidizer dist/windows/pyoxidizer'
                            sh 'pyoxidizer build'
                            sh 'find'
                            //sh 'cp -r build/x86_64-unknown-linux-gnu/debug/install/* .'
                        }
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip'
                    archiveArtifacts artifacts: 'dist/linux/**/*'
                    archiveArtifacts artifacts: 'dist/windows/**/*'
                }
                always {
                    cleanWs()
                }
            }
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

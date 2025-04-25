pipeline {
    agent none

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

        stage('Test cx_Freeze') {
            agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                }
            }
            steps {
                script {
                    echo 'Setting up Python env and testing cx_Freeze build...'

                    withPythonEnv('python3.13') {
                        echo "Python environment activated."

                        sh 'poetry export -f requirements.txt --output requirements.txt --without-hashes'
                        echo "requirements.txt generated."

                        sh 'pip install --break-system-packages -r requirements.txt'
                        echo "Project dependencies installed with pip."

                        sh 'mkdir -p dist/linux/cxfreeze dist/windows/cxfreeze'
                        echo "Output directories created."
                        sh "pip install cx_Freeze"
                        sh 'python3 setup_cxfreeze.py build_exe --build-exe dist/linux/cxfreeze'
                        echo "cx_Freeze Linux build attempted."

                        sh 'python setup_cxfreeze.py build_exe --platforms=win64 --build-exe dist/windows/cxfreeze'
                        echo "cx_Freeze Windows build attempted."

                    }
                }
            }
        }
        stage('Test Nuitka') {
             agent {
                dockerfile {
                    filename 'Dockerfile'
                    args '-u root'
                }
            }
            steps {
                script {
                    echo 'Testing Nuitka build for Linux and Windows...'
                    sh 'poetry run pip install nuitka'
                     sh 'echo "Run Nuitka build here"'
                }
            }
        }

         stage('Test PyOxidizer') {
             agent {
                dockerfile {
                     filename 'Dockerfile'
                     args '-u root'
                }
            }
            steps {
                script {
                    echo 'Testing PyOxidizer build for Linux and Windows...'
                    sh 'poetry run pip install pyoxidizer'
                    sh 'echo "Run PyOxidizer build here"'
                }
            }
        }


        stage('Archive Artifacts') {
            agent any
            steps {
                script {
                    echo 'Archiving build artifacts...'
                    archiveArtifacts artifacts: 'dist/linux/**/*.tar.gz, dist/windows/**/*.zip', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/linux/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'dist/windows/**/*', allowEmptyArchive: true
                     echo "Artifacts archived from dist/"
                }
            }
        }

        stage('Build macOS Package (Requires macOS Agent)') {
            agent {
                label 'macos'
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
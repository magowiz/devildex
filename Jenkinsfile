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
        when { expression { return true } }
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

                        sh 'pip install --break-system-packages -r requirements.txt'
                        echo "Project dependencies installed with pip."
                        sh 'find  > out.txt'
                        sh 'cat out.txt | grep  "QtCore" && exit 1'
                        sh 'mkdir -p dist/linux/cxfreeze dist/windows/cxfreeze'
                        echo "Output directories created."
                        sh "pip install --break-system-packages cx_Freeze"
                        sh 'python3 setup_cxfreeze.py build_exe --build-exe dist/linux/cxfreeze'
                        echo "cx_Freeze Linux build attempted."

                        sh 'python setup_cxfreeze.py build_exe --platforms=win64 --build-exe dist/windows/cxfreeze'
                        echo "cx_Freeze Windows build attempted."

                    }
                }}
            }
        }
        stage('Test Nuitka') {
            when { expression { return true } }
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

                            sh 'pip install --break-system-packages -r requirements.txt'
                            echo "Project dependencies installed with pip."

                            sh 'pip install --break-system-packages nuitka'
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
            }
        }

         stage('Test PyOxidizer') {
         when { expression { return true } }
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

                            sh 'pip install --break-system-packages -r requirements.txt'
                            echo "Project dependencies installed with pip."

                            sh 'pip install --break-system-packages pyoxidizer'
                            echo "PyOxidizer installed in venv."

                            sh 'mkdir -p dist/linux/pyoxidizer dist/windows/pyoxidizer'
                            echo "Output directories prepared (build output will be in ./build/ by default)."

                            sh 'pyoxidizer build --release'
                            echo "PyOxidizer build attempted."

                            sh 'cp -r build/x86_64-unknown-linux-gnu/release/* dist/linux/pyoxidizer/'
                            sh 'cp -r build/x86_64-pc-windows-gnu/release/* dist/windows/pyoxidizer/'
                            echo "PyOxidizer artifacts copied to dist/."


                        }
                    }
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
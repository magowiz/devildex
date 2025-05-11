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
                    }
                    options {
                        throttle(['pytest_telenium'])
                    }
                    steps {
                        sh 'pip install -e . --timeout 10000'
                        sh 'touch app.log'
                        sh 'echo $PWD > pwd.log'
                        pyTestXvfb(buildType: 'poetry', pythonInterpreter: '/usr/local/bin/python3.12',
                               skipMarkers: '')
                        script {
                            def exists = fileExists 'core'
                            if (exists) {
                                    echo 'core found'
                                    sh 'pip install pystack'
                                    sh 'pystack core core /usr/local/bin/python'
                                    sh 'mv core oldcore'
                                    sh 'pip list | grep pytest'
                            }
                            stash includes: 'coverage_report_xml/coverage.xml', name: 'coverageReportXML', allowEmpty: true
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
                        }
                    }

        }

    }
}
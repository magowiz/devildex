
import os
import subprocess
import shutil

config_file = "../../../devildex_config.ini"


def git_clone(repo_url, clone_dir_path, default_branch='master'):
    if os.path.isdir(clone_dir_path):
        shutil.rmtree(clone_dir_path)
    try:
        subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--branch",
                        default_branch,
                        repo_url,
                        clone_dir_path,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
    except Exception:
        subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--branch",
                        "main",
                        repo_url,
                        clone_dir_path,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
    run_pdoc()

def run(url, project_name, version=""):
    final_output_dir = os.path.join("../../../docset", project_name, version)
    git_clone(url, project_name)


if __name__ == "__main__":
    url = "https://github.com/psf/black"
    project_name = url.split('/')[-1]
    run(url, project_name)
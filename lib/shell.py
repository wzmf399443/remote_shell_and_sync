import logging
import os
import re
import subprocess
import fire
logging.basicConfig(level=logging.INFO)


class shellScript:
    def shell_caller(self, cmd: str) -> str:
        resp = subprocess.Popen(cmd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding="utf-8")
        out, err = resp.communicate()
        logging.info(out if resp.poll() == 0 else err)
        return out if resp.poll() == 0 else err

    def git_status(self, path: str, status: str) -> str:
        if not path:
            path = os.getcwd()
        r = self.shell_caller(f"git -C {path} status -s")
        lines = []
        for line in r.splitlines():
            if re.match(rf'({status}) (?P<file>\w+)', line):
                lines.append(re.match(rf'({status}) (?P<file>.+)', line).group("file"))
        return lines

    def git_local_file_diff(self, local_path, first, second):
        cmd = f"git -C {local_path} diff --name-only {first} {second}"
        resp = self.shell_caller(cmd)
        diff_file = list(filter(None, resp.split("\n")))
        # use class
        status_string = ["M ", "A ", "\?\?", " R", " M", "MM"]
        status_list = list(filter(None,
                                  [self.git_status(f"{local_path}", status) for status in status_string]))
        diff_file += status_list
        logging.info("---------* Diff Files: *---------")
        logging.info(diff_file)
        return diff_file

    def git_current_commit(self, project, branch, remote=False):
        if remote:
            out = self.ssh_shell_caller(
                f"git -C {REMOTE_BASE_PATH}/{project} pull && git -C {LOCAL_PATH}/{project} checkout {branch}")
            out = self.ssh_shell_caller("git -C {}/{project} rev-parse HEAD".format(
                REMOTE_BASE_PATH, **locals()))
            commit = out
        else:
            self.shell_caller(
                "git -C {}/{project} checkout {branch}"
                .format(LOCAL_PATH, LOCAL_PATH, **locals()))
            out = shell_caller("git -C {}/{project} rev-parse HEAD".format(
                LOCAL_PATH, **locals()))
            commit = "".join(out.split("\n"))
        logging.info("Remote Commit: " +
                     commit if remote else "Local Commit: " + commit)
        return commit

    # def git_clean_and_back_to_branch(project, delete_branch, branch="master", remote=False):
    #     path = REMOTE_BASE_PATH if remote else LOCAL_PATH
    #     ssh_shell_caller("git -C {}/{project} checkout -- .".format(
    #         path, **locals()))
    #     ssh_shell_caller("git -C {}/{project} clean -f".format(
    #         path, **locals()))
    #     ssh_shell_caller("git -C {}/{project} checkout master".format(
    #         path, **locals()))
    #     ssh_shell_caller("git -C {}/{project} branch -D {delete_branch}".format(
    #         path, **locals()))
if __name__ == "__main__":
    fire.Fire(shellScript)

import click
import logging
import os
import paramiko
import re
import subprocess
from env import *
from scp import SCPClient
logging.basicConfig(level=logging.INFO)


def ssh_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(IP_HOST, 22, USER, PWD)
    return ssh


def get_remote_report_folder(project):
    try:
        ssh = ssh_connect()
        remotepath = REMOTE_BASE_PATH + \
            "/report/{project}/general_report".format(**locals())
        # socket_timeout=120
        with SCPClient(ssh.get_transport(), socket_timeout=30) as scp:
            scp.get(remotepath, LOCAL_PATH +
                    "/remote_report/{project}/".format(**locals()), recursive=True)
            logging.info("----log file----")
            logging.info(LOCAL_PATH +
                        "/remote_report/{project}/general_report/log.html".format(**locals()))
        ssh_shell_caller(f"sudo rm -rf {remotepath[:-14]}")
    finally:
        ssh.close()

def sync_remote_file(localpath, remotepath):
    ssh = ssh_connect()
    with SCPClient(ssh.get_transport()) as scp:
        for local, remote in zip(localpath, remotepath):
            logging.info("---Sync File---\n {} to {}".format(local, remote))
            scp.put(local, remote)
        logging.info("---Sync complete---")


def git_status(path, status):
    if not path:
        path = os.getcwd()
    r = shell_caller("git -C {} status -s".format(path))
    lines = []
    for line in r.splitlines():
        if re.match(r'(%s) (?P<file>\w+)' % (status), line):
            lines.append(re.match(r'(%s) (?P<file>.+)' %
                                  (status), line).group("file"))
    return lines


def scp_file(method, local, remote):
    ssh = ssh_connect()
    with SCPClient(ssh.get_transport()) as scp:
        logging.info("---Sync File---\n {} to {}".format(local, remote))
        if method=="put":
            scp.put(local, remote)
        elif method=="get":
            scp.get(remote,local)
        logging.info("---Sync complete---")


def shell_caller(cmd):
    resp = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            encoding="utf-8")
    out, err = resp.communicate()
    logging.info(out if resp.poll() == 0 else err)
    return out if resp.poll() == 0 else err


def ssh_shell_caller(cmd, robot=False):
    try:
        ssh = ssh_connect()
        if re.match(r'sudo', cmd):
            logging.info("-----Run sudo------")
            logging.info(cmd)
            if robot:
                stdin, stdout, stderr = ssh.exec_command(
                    "cd %s && %s" % (REMOTE_BASE_PATH, cmd), get_pty=True)
            else:
                stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            stdin.write('%s\n' % PWD)
            stdin.flush()
        else:
            stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        logging.info(out if stdout.channel.recv_exit_status(
        ) == 0 else err)
        return out if stdout.channel.recv_exit_status() == 0 else err
    finally:
        ssh.close()


def git_local_file_diff(project, first, second):
    cmd = "git -C {}/{project} diff --name-only {first} {second}".format(
        LOCAL_PATH, **locals())
    resp = shell_caller(cmd)
    diff_file = list(filter(None, resp.split("\n")))
    # use class
    status_string = ["M ", "A ", "\?\?", " R"," M", "MM"]
    status_list = list(filter(None, [git_status(
        "{}/{}".format(LOCAL_PATH, project), status) for status in status_string]))
    [diff_file.extend(x) for x in status_list]
    logging.info("---------* Diff Files: *---------")
    logging.info(diff_file)
    return diff_file
    # -------------------------


def git_current_commit(project, branch, remote=False):
    if remote:
        out = ssh_shell_caller("git -C {}/{project} pull && git -C {}/{project} checkout {branch}".format(
            REMOTE_BASE_PATH, REMOTE_BASE_PATH, LOCAL_PATH, **locals()))
        out = ssh_shell_caller("git -C {}/{project} rev-parse HEAD".format(
            REMOTE_BASE_PATH, **locals()))
        commit = out
    else:
        shell_caller(
            "git -C {}/{project} checkout {branch}"
            .format(LOCAL_PATH, LOCAL_PATH, **locals()))
        out = shell_caller("git -C {}/{project} rev-parse HEAD".format(
            LOCAL_PATH, **locals()))
        commit = "".join(out.split("\n"))
    logging.info("Remote Commit: " +
                 commit if remote else "Local Commit: "+commit)
    return commit


def git_clean_and_back_to_branch(project, delete_branch, branch="master", remote=False):
    path = REMOTE_BASE_PATH if remote else LOCAL_PATH
    ssh_shell_caller("git -C {}/{project} checkout -- .".format(
        path, **locals()))
    ssh_shell_caller("git -C {}/{project} clean -f".format(
        path, **locals()))
    ssh_shell_caller("git -C {}/{project} checkout master".format(
        path, **locals()))
    ssh_shell_caller("git -C {}/{project} branch -D {delete_branch}".format(
        path, **locals()))


@click.group()
def cli():
    pass


@click.command("test", help="test option")
@click.option("-r", "--remote", help="The remote need to run")
@click.option("-l", "--local", help="The local need to run")
@click.option("-m", "--method", help="The method need to run")
def test(remote, local, method):
    scp_file(method, local, remote)


@click.command("robot", help="Remote the robot command by ssh")
@click.option("-c", "--command", help="The command need to run")
@click.option("-b", "--branch", help="The branch need to run")
def remote_robot(command, branch):
    try:
        project = re.search(r'(-I) (?P<project>dqa-\w+)',
                            command).group("project")
        shell_caller(
            "mkdir -p remote_report/{}/".format(project))
        first = git_current_commit(project, branch)
        second = git_current_commit(project, branch, remote=True)
        logging.info("local commit: "+first+"remote commit: "+second)
        resp = git_local_file_diff(project, first, second)
        local_files = list(map(lambda file: LOCAL_PATH +
                               "/"+str(project)+"/"+file, resp))
        remote_files = list(
            map(lambda file: REMOTE_BASE_PATH+"/"+str(project)+"/"+file, resp))
        logging.info(local_files)
        logging.info(remote_files)
        sync_remote_file(local_files, remote_files)
        ssh_shell_caller(command, True)
        get_remote_report_folder(project)

    finally:
        git_clean_and_back_to_branch(project, branch, remote=True)


cli.add_command(test)
cli.add_command(remote_robot)

if __name__ == "__main__":
    USER = input("User name: ") if USER == "" else USER
    PWD = input("Password: ") if PWD == "" else PWD
    cli()

# ssh.close()

# stdin, stdout, stderr = ssh.exec_command("")
# print(stdout.readlines())

# python dqa-script/exo-robot-runner run -I dqa-exosense -i api \
# -O --suite=request_removal \
# --docker_skip

# p=subprocess.Popen("dir", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
# (stdoutput,erroutput) = p.communicate()

# all_files = list()
#     if dir_path[-1] == '/':
#         dir_path = dir_path[0:-1]
#     files = sftp.listdir_attr(dir_path)
#     for x in files:
#         # find subdir if there is
#         filename = dir_path + '/' + x.filename
#         if stat.S_ISDIR(x.st_mode):
#             all_files.extend(get_remote_folder_files(sftp, filename))
#         else:
#             all_files.append(filename)
#     return all_files

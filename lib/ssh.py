import logging
import paramiko
import re
from scp import SCPClient


class sshConnect:
    def __init__(self, ip: str, username: str, password: str, port: int = 22) -> None:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, 22, username, password)
        self.ssh = ssh

    def get_remote_report_folder(self):
        try:
            ssh = self.ssh
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

    def sync_remote_file(self, localpath, remotepath):
        ssh = self.ssh
        with SCPClient(ssh.get_transport()) as scp:
            for local, remote in zip(localpath, remotepath):
                logging.info("---Sync File---\n {} to {}".format(local, remote))
                scp.put(local, remote)
            logging.info("---Sync complete---")

    def scp_file(self, method, local, remote):
        ssh = self.ssh
        with SCPClient(ssh.get_transport()) as scp:
            logging.info("---Sync File---\n {} to {}".format(local, remote))
            if method == "put":
                scp.put(local, remote)
            elif method == "get":
                scp.get(remote, local)
            logging.info("---Sync complete---")

    def ssh_shell_caller(self, cmd, robot=False):
        ssh = self.ssh
        try:
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

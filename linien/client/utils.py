import os
import paramiko
from plumbum import colors

import linien
from linien.config import REMOTE_BASE_PATH
from linien.client.exceptions import InvalidServerVersionException, \
    ServerNotInstalledException


def connect_ssh(host, user, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, username=user, password=password)
    return ssh


def run_server(host, user, password):
    ssh = connect_ssh(host, user, password)

    version = linien.__version__

    if version == 'dev':
        # if we are in a development version, we upload the files from source
        # directory directly to the RP.
        upload_source_code(ssh)

        # start the development code that was just uploaded.
        # For that, go to the parent directory; an import of "linien" then
        # points to that directory instead of any globally installed release
        # version.
        stdin, stdout, stderr = ssh.exec_command(
            ('cd %s/../;' % REMOTE_BASE_PATH) +
            ('bash %s/server/linien_start_server' % REMOTE_BASE_PATH)
        )
        err = stderr.read()
        if err:
            print(colors.red | 'Error starting the server')
            print(err)
    else:
        # it is a release and not a dev version.

        # read out version number of the server
        remote_version = read_remote_version(ssh)
        print('remote version', remote_version, 'local version', version)

        if version != remote_version:
            raise InvalidServerVersionException(version, remote_version)

        # start the server process using the global command
        ssh.exec_command('linien_start_server')
        ssh.close()


def read_remote_version(ssh):
    """Reads the remote version of linien using SSH."""
    stdin, stdout, stderr = ssh.exec_command(
        'python3 -c "import linien; print(linien.__version__);"'
    )
    lines = stdout.readlines()

    if not lines:
        raise ServerNotInstalledException()

    remote_version = lines[0].strip()
    return remote_version


def upload_source_code(ssh):
    """Uploads the application's source code to the remote server using SFTP."""
    print('uploading dev source code...')

    ftp = ssh.open_sftp()

    directory = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..'
        )
    )

    if not os.path.exists(os.path.join(directory, 'server', 'linien.bin')):
        print(colors.red | 'Error: In order to run the development version, '
                           'you need the FPGA bitstream in server/linien.bin! '
                           'Consult README to see how you can get one.')
        raise Exception('FPGA bitstream missing')

    # upload the code required for running the server
    for dirpath, dirnames, filenames in os.walk(directory):
        dirpath_rel = dirpath.replace(directory, '').lstrip('/')
        remote_path = os.path.join(REMOTE_BASE_PATH, dirpath_rel)

        if '.' in dirpath_rel or '__' in dirpath_rel:
            continue

        try:
            ftp.lstat(remote_path)
        except IOError:
            ftp.mkdir(os.path.join(remote_path.rstrip('/')))

        for filename in filenames:
            local_path = os.path.join(dirpath, filename)
            remote_filepath = os.path.join(remote_path, filename)
            # put file
            ftp.put(local_path, remote_filepath)

    ftp.close()

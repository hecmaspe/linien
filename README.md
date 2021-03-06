LINIEN
======

<img align="right" src="https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/icon.png" width="20%">

Spectroscopy locking of lasers using RedPitaya (STEMlab 125-14) that
just works. Linien aims to follow the UNIX philosophy of doing one thing
very well. It is built with Python and
[Migen](https://github.com/m-labs/migen) and is based on [RED
PID](https://github.com/quartiq/redpid).

Features
--------

-   **All included**: Sinusoidal modulation (up to 50 MHz), demodulation, filtering
    and servo implemented on the FPGA.
-   **Client-server architecture**: Autonomous operation on RedPitaya.
    One or multiple GUI clients or scripts can connect to the server.
-   **Autolock**: Click and drag over a line, and linien will
    automatically approach it and lock to it.
-   **Lock detection**: linien is capable of detecting loss of lock.
-   **Automatic relocking**: in that case, it can relock automatically
    using the autolock.
-   **Automatic Optimization**: linien uses machine learning to optimize
    spectroscopy parameters
-   **Remote-controllable**: The client libraries can be used to control
    or monitor the spectroscopy lock with python.
-   **Combined FMS+MTS**: Supports dual-channel spectroscopy that can be
    used to implement [combined
    FMS+MTS](https://arxiv.org/pdf/1701.01918.pdf)
-   **Logging**: Use
    [linien-influxdb](https://github.com/hermitdemschoenenleben/linien-influxdb)
    to log the lock status to influxdb.
-   **TTL status**: Outputs the lock status via TTL

![image](https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/screencast.gif)

Getting started
---------------

Linien runs on Windows and Linux. For most users the [standalone
binaries](#standalone-binary) containing the graphical user interface
are recommended. If you want to use the python interface you should [install it using pip](#installation-with-pip).

### Standalone binary

You can download standalone binaries for windows and linux on [the
releases
page](https://github.com/hermitdemschoenenleben/linien/releases). On
linux you have to mark it as executable before executing:

```bash
chmod +x linien-linux*
./linien-linux*
```

### Installation with pip

Linien is written for python 3 and can be installed using python\'s
package manager pip:

```bash
pip3 install linien
```

Run the application by calling

```bash
linien
```

If this doesn\'t work, your local bin directory (e.g. \~/.local/bin) is
probably missing in your PATH. Alternatively you can open linien using
python:

```python
from linien.client.client import run_application
run_application()
```

Then, you can enter your RedPitaya\'s credentials and connect. If you
agree, linien\'s server component is automatically installed.

Physical setup
--------------

The default setup looks like this:

![image](https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/setup.png)

You can also configure linien for different setups, e.g. if you want to
have the modulation frequency and the control on the same output. Additionally, it is possible to set up a slow integrator on ANALOG OUT 0 (0 V to 1.8 V).

![image](https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/explain-pins.png)

Using the application
---------------------

### Connecting to the RedPitaya

After launching the application you have to set up a new device. The host address is given by <pre>rp-<b>XXXXXX.local</b></pre>, where **XXXXXX** are the last 6 digits of the device's MAC address. You will find them on a sticker on the ethernet port:

![image](https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/mac.jpg)

Default value for user name and password is `root`.

When connecting to a RedPitaya for the first time, the application will ask you whether you want to install the server component on the device. In order to do so, the RedPitaya has to have access to the internet.

After installation of the server libraries, Linien will start the server and connect to it. You never need to start or stop anything on the server manually as the client automatically takes care of this.

### Setting things up

### Using the autolock

In order to use the autolock, you should enter some PID parameters first. Note that the sign of the parameters is determined automatically. After clicking the green button, you can select the line you want to lock to by clicking and dragging over it. The autolock will then center this line, decrease the scan range and try to lock to the middle between minimum and maximum contained in your selection.

![image](https://raw.githubusercontent.com/hermitdemschoenenleben/linien/master/docs/screencast.gif)

The following options are available:
 * **Determine signal offset**: If this checkbox is ticked, the autolock will adapt the y-offset of the signal such that the middle between minimum and maximum is at the zero crossing. This is especially useful if you have a large background signal (e.g. the Doppler background in FMS spectroscopy).
 * **Check lock**: Directly after turning on the lock, the control signal is investigated. If it shifts too much, the lock is assumed to have failed.
 * **Watch lock**: This option tells the Linien to continuously watch the control signal when the laser is locked. If steep changes are detected, a relock is initiated.

If you experience trouble with the autolock, this is most likely due to a bad signal to noise ratio or strong laser jitter.

### Using the manual lock

If you have problems with the autolock, you can also lock manually. For that, use the manual controls in the top (`Zoom` and `Position`) to center the line you want to lock to. Then, select whether the target slope is rising or falling and click the green button.

### Optimization of spectroscopy parameters using machine learning

Linien may use machine learning to maximize the slope of a line. As for the autolock, you have to click and drag over the line you want to optimize. Then, the line is centered and the optimization starts. Please note that this only works if initially a distinguished zero-crossing is visible.

Scripting interface
-------------------

In addition to the GUI, Linien can also be controlled using python
scripts. For that purpose, installation via pip is required (see above).

```python
from linien.client.connection import BaseClient, MHz, Vpp
c = BaseClient(host, 18862, False)

# read out the modulation frequency
print(c.parameters.modulation_frequency.value / MHz)

# set modulation amplitude
c.parameters.modulation_amplitude.value = 1 * Vpp
# in the line above, we set a parameter. This is not written directly to the
# FPGA, though. In order to do this, we have to call write_data():
c.connection.root.write_data()

# plot control and error signal
import pickle
from matplotlib import pyplot as plt
plot_data = pickle.loads(c.parameters.to_plot.value)

# depending on the status (locked / unlocked), different signals are available
print(plot_data.keys())

# if unlocked, signal1 and signal2 contain the error signal of channel 1 and 2
# if the laser is locked, they contain error signal and control signal.
if c.parameters.lock.value:
    plt.plot(plot_data['control_signal'], label='control')
    plt.plot(plot_data['error_signal'], label='error')
else:
    plt.plot(plot_data['error_signal_1'], label='error 1')
    plt.plot(plot_data['error_signal_2'], label='error 2')

plt.legend()
plt.show()
```

For a full list of parameters that can be controlled or accessed have a
look at
[parameters.py](https://github.com/hermitdemschoenenleben/linien/blob/master/linien/server/parameters.py).

Development
-----------

As linien uses a git submodule, you should check it out like this:

```bash
git clone https://github.com/hermitdemschoenenleben/linien.git --recursive
```

Then, create a file named `checked_out_repo/linien/VERSION` with contents

```
dev
```
(no newlines).

This ensures that changes you made to the server component are automatically uploaded to the RedPitaya when you launch the client.

### Architecture

Linien contains three components:
* The client: Connects to the server, runs the GUI, etc.
* The server: Handles connections from the client, runs long-running tasks like the autolock or the optimization algorithm. Connects to the acquisition process for communication with the FPGA.
* The acquisition process: Handles the low-level communication with the FPGA (reading / writing registers)

The communication between the components takes place using [rpyc](https://rpyc.readthedocs.io/en/latest/).

For development purposes, you can run the first two components on your local machine to simplify debugging. Only the acquisition process has to run on the RedPitaya. In a production version of linien, server and acquisition process run on RedPitaya.

### Running the code

Before running the development version check that no production version of the server is running on the RedPitaya by executing `linien_stop_server` on the RedPitaya. Now you need to have an FPGA bitstream at `linien/server/linien.bin`. You have two choices:
* [Build the gateware](#building-the-fpga-image): this makes sense if you want to change the FPGA programming.
* Use the gateware of the latest release: if you just want to work on the python client or server code without touching the FPGA gateware, this approach is right for you as it is way easier:
    * Install linien-server using pip: `pip3 install linien-server`
    * Find out where it was installed to: `python3 -c "import linien; print(linien.__path__)"`
    * In that folder go to linien/server and copy this file to your development server folder.

Now you can launch the client

```
python3 linien/client/client.py
```

and you can connect to your RedPitaya.
If you have set `checked_out_repo/linien/VERSION` to dev ([see above](#development)), this automatically uploads your local code to the RedPitaya and starts the server.
The FPGA bitstream will also be transferred to the RedPitaya and loaded on the FPGA.

### Run server locally

For debugging it may be helpful to execute the server component on
your machine (e.g. if you want to work on the autolock and want to plot the spectra). In order to make this work, you have to start `/linien/server/acquisition_process.py` on your RedPitaya using SSH. This process provides remote access to the FPGA registers. Then, you can run the server locally and connect to the FPGA registers:

```
python3 server/server.py --remote-rp=root:password@rp-f0xxxx.local
```

Now, you can start the client. **Important**: Be sure not to connect your client to the RedPitaya, but to "localhost" instead.

### Fake server

If you just want to test the GUI, there is also a fake server that you can run locally on your machine:

```bash
python3 server/server.py --fake
```

This fake server just outputs random data. Then you can connect to \"localhost\" using the client.

### Building the FPGA image

For building the FPGA image, you need to install Xilinx Vivado first. Then, call `scripts/build_gateware.sh`. In the end, the bitstream is located at `linien/server/linien.bin`. **Note**: So far, this was tested only with Linux. It should work on Windows 10, though, when calling the script inside Windows Powershell.

### Releasing a new version

First, update the version number in the `checked_out_repo/linien/VERSION` file. Then you can build and upload the package to pypi using `scripts/upload_pypi.sh`. Finally, build the standalone client using `build_standalone_client.sh` (you have
to do this on the platform you want to build the standalone client for). When on Windows 10, both scripts have to be started in Windows Powershell.
In the end, the standalone client should be uploaded to a github release.

Troubleshooting
---------------

### Connection problems

If the client fails to connect to a RedPitaya, first check whether you
can ping it by executing

```bash
ping rp-f0xxxx.local
```

in a command line. If this works, check whether you can connect via SSH.
On Windows, you have to [install a SSH client](https://www.putty.org),
on linux you can execute

```bash
ssh rp-f0xxxx.local
```

on the command line.

FAQs
----

### Can I run linien and the RedPitaya web application / scpi interface at the same time

No, this is not possible as linien relies on a customized FPGA bitstream.

### What control bandwidth is achievable with linien?

The propagation delay is roughly 300 ns, thus approximately 3 MHz bandwidth are possible.

See Also
--------

-   [RedPID](https://github.com/quartiq/redpid): the basis of linien

#!/usr/bin/python3
# this code is based on redpid. See LICENSE for details.

from migen import *

from gateware.platform import Platform
from gateware.linien import Linien
from bit2bin import bit2bin


def py_csrconstants(map, fil):
    fil.write("csr_constants = {\n")
    for k, v in linien.pid.csrbanks.constants:
        fil.write("    '{}_{}': {},\n".format(k, v.name, v.value.value))
    fil.write("}\n\n")


def get_csrmap(banks):
    for name, csrs, map_addr, rmap in banks:
        reg_addr = 0
        for csr in csrs:
            yield [name, csr.name, map_addr, reg_addr, csr.size,
                   not hasattr(csr, "status")]
            reg_addr += (csr.size + 8 - 1)//8


def py_csrmap(it, fil):
    fil.write("csr = {\n")
    for reg in it:
        fil.write("    '{}_{}': ({}, 0x{:03x}, {}, {}),\n".format(*reg))
    fil.write("}\n")


if __name__ == "__main__":
    platform = Platform()
    linien = Linien(platform)

    fil = open("linien/server/csrmap.py", "w")
    py_csrconstants(linien.pid.csrbanks.constants, fil)
    csr = get_csrmap(linien.pid.csrbanks.banks)
    py_csrmap(csr, fil)
    fil.write("states = {}\n".format(repr(linien.pid.state_names)))
    fil.write("signals = {}\n".format(repr(linien.pid.signal_names)))
    fil.close()

    platform.add_source_dir("verilog")
    build_dir = 'fpga_build'
    platform.build(linien, build_name="top", build_dir=build_dir)
    bit2bin("%s/top.bit" % build_dir, "%s/linien.bin" % build_dir, flip=True)

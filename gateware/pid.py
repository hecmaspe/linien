from migen import Module, If, Signal
from misoc.interconnect.csr import CSRStorage, AutoCSR


class PID(Module, AutoCSR):
    def __init__(self, width=14, coeff_width=14):
        self.width = width
        self.coeff_width = coeff_width

        self.input = Signal((width, True))

        self.max_pos = (1 << (width - 1)) - 1
        self.max_neg = (-1 * self.max_pos) - 1

        self.calculate_error_signal()
        self.calculate_p()
        self.calculate_i()
        self.calculate_d()
        self.calculate_sum()

    def calculate_error_signal(self):
        self.setpoint = CSRStorage(self.width)
        setpoint_signed = Signal((self.width, True))
        self.comb += [
            setpoint_signed.eq(self.setpoint.storage)
        ]

        self.error = Signal((self.width + 1, True))

        self.comb += [
            self.error.eq(
                self.input - self.setpoint.storage
            )
        ]

    def calculate_p(self):
        self.kp = CSRStorage(self.coeff_width)
        kp_signed = Signal((self.coeff_width, True))
        self.comb += [
            kp_signed.eq(self.kp.storage)
        ]

        kp_mult = Signal((self.width + self.coeff_width, True))
        self.comb += [
            kp_mult.eq(self.error * kp_signed)
        ]

        self.output_p = Signal((self.width, True))
        self.comb += [
            self.output_p.eq(
                kp_mult >> (self.coeff_width - 2)
            )
        ]

        self.kp_mult = kp_mult

    def calculate_i(self):
        self.ki = CSRStorage(self.coeff_width)
        self.reset = CSRStorage()

        ki_signed = Signal((self.coeff_width, True))
        self.comb += [
            ki_signed.eq(self.ki.storage)
        ]

        self.ki_mult = Signal((1 + self.width + self.coeff_width, True))

        self.comb += [
            self.ki_mult.eq(
                (self.error * ki_signed) >> 4
            )
        ]

        int_reg_width = self.width + self.coeff_width + 4
        extra_width = int_reg_width - self.width
        self.int_reg = Signal((int_reg_width, True))
        self.int_sum = Signal((int_reg_width + 1, True))
        self.int_out = Signal((self.width, True))

        self.comb += [
            self.int_sum.eq(
                self.ki_mult + self.int_reg
            ),
            self.int_out.eq(
                self.int_reg >> extra_width
            )
        ]

        max_pos_extra = (self.max_pos << extra_width)
        max_neg_extra = (-1 * max_pos_extra) - 1

        self.sync += [
            If(self.reset.storage,
                self.int_reg.eq(0)
            ).Elif(self.int_sum > max_pos_extra, # positive saturation
                self.int_reg.eq(max_pos_extra)
            ).Elif(self.int_sum < max_neg_extra, # negative saturation
                self.int_reg.eq(max_neg_extra)
            ).Else(
                self.int_reg.eq(self.int_sum)
            )
        ]

    def calculate_d(self):
        self.kd = CSRStorage(self.coeff_width)
        kd_mult = Signal((29, True))
        kd_reg = Signal((19, True))
        kd_reg_r = Signal((19, True))
        self.kd_reg_s = Signal((20, True))
        kd_signed = Signal((self.coeff_width, True))

        self.comb += [
            kd_signed.eq(self.kd.storage),
            kd_mult.eq(self.error * kd_signed)
        ]

        self.sync += [
            kd_reg.eq(kd_mult[10:29]),
            kd_reg_r.eq(kd_reg),
            self.kd_reg_s.eq(kd_reg - kd_reg_r)
        ]

    def calculate_sum(self):
        self.pid_sum = Signal((self.width + 3, True))
        self.pid_out = Signal((self.width, True))

        self.comb += [
            If(self.pid_sum > self.max_pos, # positive overflow
                self.pid_out.eq(self.max_pos)
            ).Elif(self.pid_sum < self.max_neg, # negative overflow
                self.pid_out.eq(self.max_neg)
            ).Else(
                self.pid_out.eq(self.pid_sum[:self.width])
            )
        ]

        self.comb += [
            self.pid_sum.eq(
                self.output_p + self.int_out # FIXME: kd disabled + self.kd_reg_s
            )
        ]
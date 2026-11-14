"""A 48K floating bus for SkoolKit's simulator: a read of a port the
hardware leaves undriven (FF here; odd ports nothing else answers) returns
the byte the ULA is fetching for the display at that moment, or FF in the
borders and between fetches.

Timing (48K): frames of 69,888 T-states, lines of 224; the ULA's first
fetch for the screen's top line is at T 14,338 after the interrupt, then
each 8 T-states: bitmap byte, its attribute, the next bitmap byte, its
attribute, four idle (FF), for 16 such groups (128 T-states), then the
rest of the line (96) idle.  The port is read 7 T-states into IN A,(n).

The game does not use the floating bus (only the declined Z48_VSYNC trial
did); z48tap.py uses this so that ports nothing answers, such as the
Kempston port when no interface is fitted, read as on a real 48K."""
from skoolkit.trace import Tracer

FRAME = 69888; FETCH0 = 14338; LINE = 224

class FloatingBusTracer(Tracer):
    def read_port(self, registers, port):
        if port & 0xFF == 0xFF:
            t = (registers[25] + 7) % FRAME - FETCH0
            if t < 0: return 0xFF
            y, x = divmod(t, LINE)
            if y >= 192 or x >= 128: return 0xFF
            g, p = divmod(x, 8)
            if p >= 4: return 0xFF
            col = 2 * g + (p >> 1)
            m = self.simulator.memory
            if p & 1:
                return m[0x5800 + (y >> 3) * 32 + col]
            return m[0x4000 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + col]
        return super().read_port(registers, port)

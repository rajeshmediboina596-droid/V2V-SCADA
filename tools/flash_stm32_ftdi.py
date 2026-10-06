#!/usr/bin/env python3
"""
=======================================================================================
 FTDI / USB-to-UART Firmware Flasher & Serial Tool for STM32 V2V System
 Supports: FTDI (FT232RL, FT2232), CP2102, CH340, and Standard USB-Serial Adapters
 Protocol: STMicroelectronics USART Bootloader Protocol (AN3155)
 Target:   STM32F103C8T6 (Blue Pill), STM32F411 (Black Pill), and STM32 Family
=======================================================================================

Wiring Guide for FTDI (FT232RL) to STM32F103:
---------------------------------------------------------------------------------------
  FTDI Pin           STM32 Blue Pill Pin    Description / Function
---------------------------------------------------------------------------------------
  TXD                PA10 (USART1 RX)       Firmware upload and telemetry
  RXD                PA9  (USART1 TX)       Firmware upload and telemetry
  GND                GND                    Common ground reference
  VCC (Set to 3.3V)  3.3V (or 5V to 5V)     Power rail (set jumper to 3.3V!)
  DTR (Optional)     NRST / RESET           Hardware Auto-Reset (hands-free)
  RTS (Optional)     BOOT0                  Hardware Auto-BOOT0 Mode (hands-free)
---------------------------------------------------------------------------------------

Manual Jumper Flashing Procedure (if DTR/RTS not connected):
  1. Set yellow jumper BOOT0 = 1 (towards 3.3V), leave BOOT1 = 0 (towards GND).
  2. Press the RESET button on the STM32 board once.
  3. Run this script to upload your .bin or .hex firmware.
  4. Move yellow jumper BOOT0 = 0 (towards GND) and press RESET to run!
=======================================================================================
"""

import sys
import os
import time
import argparse
import struct
from typing import Optional, List, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] 'pyserial' library is required. Install it using: pip install pyserial")
    sys.exit(1)

# Protocol Constants (STM32 AN3155)
ACK = 0x79
NACK = 0x1F
INIT_BYTE = 0x7F

CMD_GET = 0x00
CMD_GET_VERSION = 0x01
CMD_GET_ID = 0x02
CMD_READ_MEMORY = 0x11
CMD_GO = 0x21
CMD_WRITE_MEMORY = 0x31
CMD_ERASE = 0x43
CMD_EXTENDED_ERASE = 0x44
CMD_WRITE_PROTECT = 0x73
CMD_WRITE_UNPROTECT = 0x82
CMD_READOUT_PROTECT = 0x91
CMD_READOUT_UNPROTECT = 0x92

FLASH_BASE_ADDRESS = 0x08000000

# Known STM32 Device IDs
STM32_CHIP_NAMES = {
    0x0410: "STM32F103 Medium-Density (64KB/128KB Flash, 20KB RAM - Classic Blue Pill)",
    0x0412: "STM32F103 Low-Density (16KB/32KB Flash)",
    0x0414: "STM32F103 High-Density (256KB/512KB Flash)",
    0x0418: "STM32F103 Connectivity Line (USB/CAN/Ethernet)",
    0x0420: "STM32F100 Value Line",
    0x0430: "STM32F103 XL-Density (768KB/1MB Flash)",
    0x0411: "STM32F20x / F21x",
    0x0413: "STM32F405 / F407 / F415 / F417",
    0x0419: "STM32F427 / F429 / F437 / F439",
    0x0423: "STM32F401xB/C",
    0x0431: "STM32F411xC/E (Black Pill 100MHz)",
    0x0433: "STM32F401xD/E",
    0x0440: "STM32F051xx",
    0x0444: "STM32F030x4/x6",
    0x0448: "STM32F070xB / F072xB",
}

class STM32Flasher:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0, auto_reset: bool = False):
        self.port_name = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.auto_reset = auto_reset
        self.ser: Optional[serial.Serial] = None
        self.supported_cmds: List[int] = []
        self.bootloader_version = 0x00
        self.chip_id = 0x0000

    def open(self):
        """Open serial port with 8E1 (Even Parity) configuration required by STM32 ROM bootloader."""
        if self.ser and self.ser.is_open:
            self.ser.close()

        self.ser = serial.Serial(
            port=self.port_name,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout
        )

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def hardware_reset(self, enter_bootloader: bool = True):
        """
        Uses FTDI DTR (NRST) and RTS (BOOT0) to automatically reboot STM32 into bootloader or user code.
        """
        if not self.ser:
            return

        print(f"[FTDI] Triggering Hardware {'Bootloader' if enter_bootloader else 'Run'} Reset via DTR/RTS...")
        # RTS controls BOOT0: True = Logic High (3.3V), False = Logic Low (GND)
        self.ser.rts = enter_bootloader
        time.sleep(0.05)

        # DTR controls NRST (Active-Low): True = Pull low (Assert Reset), False = High (De-assert)
        self.ser.dtr = True
        time.sleep(0.1)
        self.ser.dtr = False
        time.sleep(0.15)

    def synchronize(self) -> bool:
        """Sends INIT_BYTE (0x7F) and waits for ACK (0x79) to establish communication."""
        if not self.ser:
            return False

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        for attempt in range(1, 6):
            self.ser.write(bytes([INIT_BYTE]))
            self.ser.flush()
            resp = self.ser.read(1)

            if len(resp) == 1 and resp[0] == ACK:
                return True
            elif len(resp) == 1 and resp[0] == NACK:
                # If NACK, chip might already be synchronized
                return True
            time.sleep(0.05)

        return False

    def send_command(self, cmd: int) -> bool:
        """Sends a command byte along with its bitwise inverted complement (cmd ^ 0xFF)."""
        if not self.ser:
            return False
        self.ser.write(bytes([cmd, cmd ^ 0xFF]))
        self.ser.flush()
        resp = self.ser.read(1)
        return len(resp) == 1 and resp[0] == ACK

    def read_chip_info(self) -> Tuple[int, int, List[int]]:
        """Reads Bootloader Version, Chip ID, and Supported Commands."""
        # 1. GET command (0x00)
        if not self.send_command(CMD_GET):
            raise RuntimeError("Failed to send CMD_GET")

        num_bytes = self.ser.read(1)
        if not num_bytes:
            raise RuntimeError("Timeout reading command count")
        count = num_bytes[0]

        data = self.ser.read(count + 1)
        ack = self.ser.read(1)
        if not ack or ack[0] != ACK:
            raise RuntimeError("Invalid ACK received during GET")

        self.bootloader_version = data[0]
        self.supported_cmds = list(data[1:])

        # 2. GET ID command (0x02)
        if not self.send_command(CMD_GET_ID):
            raise RuntimeError("Failed to send CMD_GET_ID")

        num_bytes = self.ser.read(1)
        if not num_bytes:
            raise RuntimeError("Timeout reading ID length")
        id_len = num_bytes[0] + 1

        id_data = self.ser.read(id_len)
        ack = self.ser.read(1)
        if not ack or ack[0] != ACK:
            raise RuntimeError("Invalid ACK received during GET_ID")

        if len(id_data) >= 2:
            self.chip_id = (id_data[0] << 8) | id_data[1]

        return self.chip_id, self.bootloader_version, self.supported_cmds

    def erase_chip(self) -> bool:
        """Performs global mass erase on the STM32 Flash memory."""
        print("[FTDI] Erasing Flash Memory...")

        if CMD_EXTENDED_ERASE in self.supported_cmds:
            # Extended Erase (for high/connectivity density devices)
            if not self.send_command(CMD_EXTENDED_ERASE):
                return False
            # 0xFFFF = Global Mass Erase
            self.ser.write(bytes([0xFF, 0xFF, 0x00]))
            self.ser.flush()
        elif CMD_ERASE in self.supported_cmds:
            # Standard Erase (STM32F103 medium-density)
            if not self.send_command(CMD_ERASE):
                return False
            # 0xFF = Global Mass Erase
            self.ser.write(bytes([0xFF, 0x00]))
            self.ser.flush()
        else:
            raise RuntimeError("Erase command not supported by target device!")

        # Erasing flash can take up to 3-5 seconds
        old_timeout = self.ser.timeout
        self.ser.timeout = 10.0
        ack = self.ser.read(1)
        self.ser.timeout = old_timeout

        if len(ack) == 1 and ack[0] == ACK:
            print("[FTDI] Mass erase completed successfully!")
            return True
        return False

    def write_block(self, address: int, data: bytes) -> bool:
        """Writes up to 256 bytes to Flash memory at the specified address."""
        if len(data) > 256:
            raise ValueError("Block size cannot exceed 256 bytes")

        # 1. Send Write Memory Command
        if not self.send_command(CMD_WRITE_MEMORY):
            return False

        # 2. Send 4-byte address + address checksum
        addr_bytes = struct.pack('>I', address)
        addr_csum = addr_bytes[0] ^ addr_bytes[1] ^ addr_bytes[2] ^ addr_bytes[3]
        self.ser.write(addr_bytes + bytes([addr_csum]))
        self.ser.flush()

        ack = self.ser.read(1)
        if len(ack) != 1 or ack[0] != ACK:
            return False

        # 3. Send length (N-1) + data + checksum
        length_byte = len(data) - 1
        csum = length_byte
        for b in data:
            csum ^= b

        payload = bytes([length_byte]) + data + bytes([csum])
        self.ser.write(payload)
        self.ser.flush()

        ack = self.ser.read(1)
        return len(ack) == 1 and ack[0] == ACK

    def read_block(self, address: int, length: int) -> bytes:
        """Reads up to 256 bytes from memory at the specified address."""
        if length > 256:
            raise ValueError("Read length cannot exceed 256 bytes")

        if not self.send_command(CMD_READ_MEMORY):
            raise RuntimeError("Failed to send CMD_READ_MEMORY")

        addr_bytes = struct.pack('>I', address)
        addr_csum = addr_bytes[0] ^ addr_bytes[1] ^ addr_bytes[2] ^ addr_bytes[3]
        self.ser.write(addr_bytes + bytes([addr_csum]))
        self.ser.flush()

        ack = self.ser.read(1)
        if len(ack) != 1 or ack[0] != ACK:
            raise RuntimeError("Address ACK failed during read")

        len_byte = length - 1
        self.ser.write(bytes([len_byte, len_byte ^ 0xFF]))
        self.ser.flush()

        ack = self.ser.read(1)
        if len(ack) != 1 or ack[0] != ACK:
            raise RuntimeError("Length ACK failed during read")

        return self.ser.read(length)

    def jump_to_application(self, address: int = FLASH_BASE_ADDRESS) -> bool:
        """Sends GO command to jump and execute firmware directly from Flash."""
        print(f"[FTDI] Jumping to application entry point at 0x{address:08X}...")
        if not self.send_command(CMD_GO):
            return False

        addr_bytes = struct.pack('>I', address)
        addr_csum = addr_bytes[0] ^ addr_bytes[1] ^ addr_bytes[2] ^ addr_bytes[3]
        self.ser.write(addr_bytes + bytes([addr_csum]))
        self.ser.flush()

        ack = self.ser.read(1)
        return len(ack) == 1 and ack[0] == ACK

    def flash_binary(self, binary_data: bytes, start_address: int = FLASH_BASE_ADDRESS, verify: bool = True) -> bool:
        """Flashes binary image to Flash memory with visual progress indicator."""
        total_size = len(binary_data)
        block_size = 256
        num_blocks = (total_size + block_size - 1) // block_size

        print(f"[FTDI] Programming {total_size} bytes ({num_blocks} blocks) at 0x{start_address:08X}...")

        start_time = time.time()
        for i in range(num_blocks):
            offset = i * block_size
            chunk = binary_data[offset:offset + block_size]
            current_addr = start_address + offset

            # Pad last chunk with 0xFF to 4-byte alignment
            if len(chunk) % 4 != 0:
                pad_len = 4 - (len(chunk) % 4)
                chunk += b'\xFF' * pad_len

            if not self.write_block(current_addr, chunk):
                print(f"\n[ERROR] Write failed at block {i+1}/{num_blocks} (Address 0x{current_addr:08X})")
                return False

            # Progress bar
            progress = (i + 1) / num_blocks
            bar_len = 30
            filled = int(bar_len * progress)
            bar = '█' * filled + '-' * (bar_len - filled)
            pct = progress * 100
            sys.stdout.write(f"\r[FTDI] Writing: |{bar}| {pct:5.1f}% ({offset + len(chunk)}/{total_size} bytes)")
            sys.stdout.flush()

        elapsed = time.time() - start_time
        speed_kbps = (total_size / 1024.0) / elapsed if elapsed > 0 else 0
        print(f"\n[FTDI] Write complete! Elapsed: {elapsed:.2f}s ({speed_kbps:.1f} KB/s)")

        if verify:
            print("[FTDI] Verifying Flash Integrity...")
            verify_start = time.time()
            for i in range(num_blocks):
                offset = i * block_size
                chunk = binary_data[offset:offset + block_size]
                current_addr = start_address + offset

                read_back = self.read_block(current_addr, len(chunk))
                if read_back != chunk:
                    print(f"\n[ERROR] Verification mismatch at address 0x{current_addr:08X}!")
                    return False

                progress = (i + 1) / num_blocks
                pct = progress * 100
                sys.stdout.write(f"\r[FTDI] Verifying: {pct:5.1f}%")
                sys.stdout.flush()

            print(f"\n[FTDI] Verification Successful! 100% data integrity confirmed in {time.time() - verify_start:.2f}s.")

        return True


def parse_hex_file(filepath: str) -> Tuple[int, bytes]:
    """Parses an Intel HEX file into base address and contiguous binary payload."""
    data_dict = {}
    base_upper = 0

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line.startswith(':'):
                continue
            byte_count = int(line[1:3], 16)
            address = int(line[3:7], 16)
            record_type = int(line[7:9], 16)
            data_str = line[9:9 + byte_count * 2]

            if record_type == 0x00: # Data Record
                full_addr = (base_upper << 16) | address
                for i in range(byte_count):
                    val = int(data_str[i*2:i*2+2], 16)
                    data_dict[full_addr + i] = val
            elif record_type == 0x01: # EOF
                break
            elif record_type == 0x04: # Extended Linear Address
                base_upper = int(data_str, 16)

    if not data_dict:
        raise ValueError("No data found in HEX file")

    min_addr = min(data_dict.keys())
    max_addr = max(data_dict.keys())
    size = max_addr - min_addr + 1

    binary_array = bytearray([0xFF] * size)
    for addr, val in data_dict.items():
        binary_array[addr - min_addr] = val

    return min_addr, bytes(binary_array)


def list_serial_ports() -> List[str]:
    """Lists available system COM ports with hardware descriptions."""
    ports = list(serial.tools.list_ports.comports())
    candidates = []
    print("\n--- Available Serial Ports ---")
    for p in ports:
        desc = p.description or ""
        hwid = p.hwid or ""
        is_ftdi = any(name in desc.lower() or name in hwid.lower() for name in ["ftdi", "ft232", "cp210", "ch340", "uart", "serial"])
        mark = " [RECOMMENDED: FTDI / USB-UART]" if is_ftdi else ""
        print(f"  • {p.device}: {desc}{mark}")
        if is_ftdi:
            candidates.append(p.device)

    if not candidates and ports:
        candidates.append(ports[0].device)
    return candidates


def run_serial_monitor(port: str, baud: int = 115200):
    """Launches an interactive live serial telemetry monitor."""
    print(f"\n=======================================================")
    print(f" Starting Live Serial Telemetry Monitor on {port} @ {baud}")
    print(f" Press Ctrl+C to exit monitor.")
    print(f"=======================================================\n")

    try:
        ser = serial.Serial(port, baud, timeout=1.0)
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    if line.startswith('{') and line.endswith('}'):
                        print(f"[V2V SCADA JSON] {line}")
                    else:
                        print(f"[STM32 Node] {line}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\n[Monitor] Stopped by user.")
    except Exception as e:
        print(f"[Monitor Error] {e}")


def main():
    parser = argparse.ArgumentParser(
        description="FTDI / USB-to-UART Firmware Flasher & Diagnostics for STM32 V2V System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/flash_stm32_ftdi.py --info
  python tools/flash_stm32_ftdi.py --port COM4 --info
  python tools/flash_stm32_ftdi.py --port COM4 --file build/main.bin
  python tools/flash_stm32_ftdi.py --port COM4 --file build/main.hex --verify --monitor
  python tools/flash_stm32_ftdi.py --monitor --port COM4
        """
    )
    parser.add_argument("--port", "-p", help="Serial port (e.g. COM3, COM4, /dev/ttyUSB0). If omitted, auto-detected.")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Flashing baud rate (default: 115200, or 57600)")
    parser.add_argument("--file", "-f", help="Path to firmware file (.bin or .hex)")
    parser.add_argument("--info", "-i", action="store_true", help="Connect and display STM32 chip ID & info without flashing")
    parser.add_argument("--erase", "-e", action="store_true", help="Perform mass erase on Flash memory")
    parser.add_argument("--no-verify", action="store_true", help="Skip checksum verification after write")
    parser.add_argument("--auto-reset", "-a", action="store_true", help="Use FTDI DTR/RTS lines for hands-free auto-reset into bootloader")
    parser.add_argument("--monitor", "-m", action="store_true", help="Open live serial monitor after operation")

    args = parser.parse_args()

    # Step 1: Detect or select COM Port
    target_port = args.port
    if not target_port:
        detected = list_serial_ports()
        if detected:
            target_port = detected[0]
            print(f"[FTDI] Automatically selected port: {target_port}")
        else:
            print("[ERROR] No USB serial ports detected. Please plug in your FTDI / USB-to-UART adapter.")
            sys.exit(1)

    # If only monitor requested:
    if args.monitor and not args.file and not args.info and not args.erase:
        run_serial_monitor(target_port, 115200)
        return

    flasher = STM32Flasher(target_port, baudrate=args.baud, auto_reset=args.auto_reset)

    try:
        print(f"\n[FTDI] Connecting to STM32 on {target_port} @ {args.baud} baud (8E1)...")
        flasher.open()

        if args.auto_reset:
            flasher.hardware_reset(enter_bootloader=True)
        else:
            print("[INFO] If not using DTR/RTS auto-reset, ensure yellow jumper BOOT0=1 and press RESET.")

        # Step 2: Establish Bootloader Handshake
        print("[FTDI] Synchronizing with STM32 ROM Bootloader (sending 0x7F)...")
        if not flasher.synchronize():
            print("\n[ERROR] Synchronization failed!")
            print("Troubleshooting Steps:")
            print("  1. Verify wiring:")
            print(f"     • FTDI TXD  -> STM32 PA10 (USART1 RX)")
            print(f"     • FTDI RXD  -> STM32 PA9  (USART1 TX)")
            print(f"     • FTDI GND  -> STM32 GND")
            print("  2. Verify jumper configuration:")
            print("     • Set BOOT0 jumper to '1' (3.3V)")
            print("     • Set BOOT1 jumper to '0' (GND)")
            print("  3. Press the physical RESET button on the Blue Pill, then run this tool again.")
            flasher.close()
            sys.exit(1)

        print("[FTDI] Handshake SUCCESS! STM32 ROM Bootloader acknowledged.")

        # Step 3: Read Chip Info
        chip_id, version, cmds = flasher.read_chip_info()
        chip_desc = STM32_CHIP_NAMES.get(chip_id, "Unknown STM32 Device")
        print(f"\n================ Target Microcontroller Detected ================")
        print(f"  Chip ID:            0x{chip_id:04X} -> {chip_desc}")
        print(f"  Bootloader Version: v{(version >> 4)}.{(version & 0x0F)}")
        print(f"  Supported Commands: {len(cmds)} commands available")
        print(f"=================================================================\n")

        # Step 4: Erase if requested or before flashing
        if args.erase or args.file:
            if not flasher.erase_chip():
                print("[ERROR] Flash erase failed!")
                flasher.close()
                sys.exit(1)

        # Step 5: Flash firmware if file specified
        if args.file:
            filepath = os.path.abspath(args.file)
            if not os.path.isfile(filepath):
                print(f"[ERROR] File not found: {filepath}")
                flasher.close()
                sys.exit(1)

            if filepath.lower().endswith(".hex"):
                base_addr, bin_data = parse_hex_file(filepath)
            else:
                base_addr = FLASH_BASE_ADDRESS
                with open(filepath, "rb") as f:
                    bin_data = f.read()

            success = flasher.flash_binary(bin_data, start_address=base_addr, verify=(not args.no_verify))
            if not success:
                print("[ERROR] Firmware flashing failed!")
                flasher.close()
                sys.exit(1)

            print("\n[SUCCESS] Firmware programmed successfully!")

            if args.auto_reset:
                flasher.hardware_reset(enter_bootloader=False)
            else:
                print("\n[NEXT STEP] To execute your firmware:")
                print("  1. Move yellow jumper BOOT0 back to '0' (GND).")
                print("  2. Press the physical RESET button on your STM32.")

        flasher.close()

        # Step 6: Launch live monitor if requested
        if args.monitor:
            time.sleep(1.0)
            run_serial_monitor(target_port, 115200)

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        if flasher:
            flasher.close()
        sys.exit(1)

if __name__ == "__main__":
    main()

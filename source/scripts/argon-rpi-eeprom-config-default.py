#!/usr/bin/env python3

# Based on /usr/bin/rpi-eeprom-config of bookworm
"""
rpi-eeprom-config
"""

import argparse
import atexit
import os
import subprocess
import string
import struct
import sys
import tempfile
import time

VALID_IMAGE_SIZES = [512 * 1024, 2 * 1024 * 1024]

BOOTCONF_TXT = 'bootconf.txt'
BOOTCONF_SIG = 'bootconf.sig'
PUBKEY_BIN = 'pubkey.bin'

# Each section starts with a magic number followed by a 32 bit offset to the
# next section (big-endian).
# The number, order and size of the sections depends on the bootloader version
# but the following mask can be used to test for section headers and skip
# unknown data.
#
# The last 4KB of the EEPROM image is reserved for internal use by the
# bootloader and may be overwritten during the update process.
MAGIC = 0x55aaf00f
PAD_MAGIC = 0x55aafeef
MAGIC_MASK = 0xfffff00f
FILE_MAGIC = 0x55aaf11f # id for modifiable files
FILE_HDR_LEN = 20
FILENAME_LEN = 12
TEMP_DIR = None

# Modifiable files are stored in a single 4K erasable sector.
# The max content 4076 bytes because of the file header.
ERASE_ALIGN_SIZE = 4096
MAX_FILE_SIZE = ERASE_ALIGN_SIZE - FILE_HDR_LEN

DEBUG = False

# BEGIN: Argon40 added methods
def argon_rpisupported():
    # bcm2711 = pi4, bcm2712 = pi5
    return rpi5()

def argon_edit_config():
    # modified/stripped version of edit_config

    config_src = ''
    # If there is a pending update then use the configuration from
    # that in order to support incremental updates. Otherwise,
    # use the current EEPROM configuration.
    bootfs = shell_cmd(['rpi-eeprom-update', '-b']).rstrip()
    pending = os.path.join(bootfs, 'pieeprom.upd')
    if os.path.exists(pending):
        config_src = pending
        image = BootloaderImage(pending)
        current_config = image.get_file(BOOTCONF_TXT).decode('utf-8')
    else:
        current_config, config_src = read_current_config()

    # Add NVMe boot priority etc if not yet set
    foundnewsetting = 0
    addsetting="\nBOOT_UART=1\nWAKE_ON_GPIO=0\nPOWER_OFF_ON_HALT=1\nBOOT_ORDER=0xf416\nPCIE_PROBE=1"
    current_config_lines = current_config.splitlines()
    new_config = current_config
    lineidx = 0
    while lineidx < len(current_config_lines):
        current_config_pair = current_config_lines[lineidx].split("=")
        newsetting = ""
        if current_config_pair[0] == "BOOT_UART":
            newsetting = "BOOT_UART=1"
        elif current_config_pair[0] == "WAKE_ON_GPIO":
            newsetting = "WAKE_ON_GPIO=0"
        elif current_config_pair[0] == "POWER_OFF_ON_HALT":
            newsetting = "POWER_OFF_ON_HALT=1"
        elif current_config_pair[0] == "BOOT_ORDER":
            newsetting = "BOOT_ORDER=0xf416"
        elif current_config_pair[0] == "PCIE_PROBE":
            newsetting = "PCIE_PROBE=1"

        if newsetting != "":
            addsetting = addsetting.replace("\n"+newsetting,"",1)
            if current_config_lines[lineidx] != newsetting:
                foundnewsetting = foundnewsetting + 1
                new_config = new_config.replace(current_config_lines[lineidx], newsetting, 1)

        lineidx = lineidx + 1

    if addsetting != "":
        # Append additional settings after [all]
        new_config = new_config.replace("[all]", "[all]"+addsetting, 1)
        foundnewsetting = foundnewsetting + 1

    if foundnewsetting == 0:
        # Already configured
        print("EEPROM settings up to date")
        sys.exit(0)

    # Skipped editor and write new config to temp file
    create_tempdir()
    tmp_conf = os.path.join(TEMP_DIR, 'boot.conf')
    out = open(tmp_conf, 'w')
    out.write(new_config)
    out.close()

    # Apply updates

    apply_update(tmp_conf, None, config_src)

# END: Argon40 added methods


def debug(s):
    if DEBUG:
        sys.stderr.write(s + '\n')


def rpi4():
    compatible_path = "/sys/firmware/devicetree/base/compatible"
    if os.path.exists(compatible_path):
        with open(compatible_path, "rb") as f:
            compatible = f.read().decode('utf-8')
            if "bcm2711" in compatible:
                return True
    return False

def rpi5():
    compatible_path = "/sys/firmware/devicetree/base/compatible"
    if os.path.exists(compatible_path):
        with open(compatible_path, "rb") as f:
            compatible = f.read().decode('utf-8')
            if "bcm2712" in compatible:
                return True
    return False

def exit_handler():
    """
    Delete any temporary files.
    """
    if TEMP_DIR is not None and os.path.exists(TEMP_DIR):
        tmp_image = os.path.join(TEMP_DIR, 'pieeprom.upd')
        if os.path.exists(tmp_image):
            os.remove(tmp_image)
        tmp_conf = os.path.join(TEMP_DIR, 'boot.conf')
        if os.path.exists(tmp_conf):
            os.remove(tmp_conf)
        os.rmdir(TEMP_DIR)

def create_tempdir():
    global TEMP_DIR
    if TEMP_DIR is None:
        TEMP_DIR = tempfile.mkdtemp()

def pemtobin(infile):
    """
    Converts an RSA public key into the format expected by the bootloader.
    """
    # Import the package here to make this a weak dependency.
    from Cryptodome.PublicKey import RSA

    arr = bytearray()
    f = open(infile,'r')
    key = RSA.importKey(f.read())

    if key.size_in_bits() != 2048:
        raise Exception("RSA key size must be 2048")

    # Export N and E in little endian format
    arr.extend(key.n.to_bytes(256, byteorder='little'))
    arr.extend(key.e.to_bytes(8, byteorder='little'))
    return arr

def exit_error(msg):
    """
    Trapped a fatal error, output message to stderr and exit with non-zero
    return code.
    """
    sys.stderr.write("ERROR: %s\n" % msg)
    sys.exit(1)

def shell_cmd(args):
    """
    Executes a shell command waits for completion returning STDOUT. If an
    error occurs then exit and output the subprocess stdout, stderr messages
    for debug.
    """
    start = time.time()
    arg_str = ' '.join(args)
    result = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    while time.time() - start < 5:
        if result.poll() is not None:
            break

    if result.poll() is None:
        exit_error("%s timeout" % arg_str)

    if result.returncode != 0:
        exit_error("%s failed: %d\n %s\n %s\n" %
                   (arg_str, result.returncode, result.stdout.read(), result.stderr.read()))
    else:
        return result.stdout.read().decode('utf-8')

def get_latest_eeprom():
    """
    Returns the path of the latest EEPROM image file if it exists.
    """
    latest = shell_cmd(['rpi-eeprom-update', '-l']).rstrip()
    if not os.path.exists(latest):
        exit_error("EEPROM image '%s' not found" % latest)
    return latest

def apply_update(config, eeprom=None, config_src=None):
    """
    Applies the config file to the latest available EEPROM image and spawns
    rpi-eeprom-update to schedule the update at the next reboot.
    """
    if eeprom is not None:
        eeprom_image = eeprom
    else:
        eeprom_image = get_latest_eeprom()
    create_tempdir()

    # Replace the contents of bootconf.txt with the contents of the config file
    tmp_update = os.path.join(TEMP_DIR, 'pieeprom.upd')
    image = BootloaderImage(eeprom_image, tmp_update)
    image.update_file(config, BOOTCONF_TXT)
    image.write()

    config_str = open(config).read()
    if config_src is None:
        config_src = ''
    sys.stdout.write("Updating bootloader EEPROM\n image: %s\nconfig_src: %s\nconfig: %s\n%s\n%s\n%s\n" %
                     (eeprom_image, config_src, config, '#' * 80, config_str, '#' * 80))

    sys.stdout.write("\n*** To cancel this update run 'sudo rpi-eeprom-update -r' ***\n\n")

    # Ignore APT package checksums so that this doesn't fail when used
    # with EEPROMs with configs delivered outside of APT.
    # The checksums are really just a safety check for automatic updates.
    args = ['rpi-eeprom-update', '-d', '-i', '-f', tmp_update]
    resp = shell_cmd(args)
    sys.stdout.write(resp)

def edit_config(eeprom=None):
    """
    Implements something like 'git commit' for editing EEPROM configs.
    """
    # Default to nano if $EDITOR is not defined.
    editor = 'nano'
    if 'EDITOR' in os.environ:
        editor = os.environ['EDITOR']

    config_src = ''
    # If there is a pending update then use the configuration from
    # that in order to support incremental updates. Otherwise,
    # use the current EEPROM configuration.
    bootfs = shell_cmd(['rpi-eeprom-update', '-b']).rstrip()
    pending = os.path.join(bootfs, 'pieeprom.upd')
    if os.path.exists(pending):
        config_src = pending
        image = BootloaderImage(pending)
        current_config = image.get_file(BOOTCONF_TXT).decode('utf-8')
    else:
        current_config, config_src = read_current_config()

    create_tempdir()
    tmp_conf = os.path.join(TEMP_DIR, 'boot.conf')
    out = open(tmp_conf, 'w')
    out.write(current_config)
    out.close()
    cmd = "\'%s\' \'%s\'" % (editor, tmp_conf)
    result = os.system(cmd)
    if result != 0:
        exit_error("Aborting update because \'%s\' exited with code %d." % (cmd, result))

    new_config = open(tmp_conf, 'r').read()
    if len(new_config.splitlines()) < 2:
        exit_error("Aborting update because \'%s\' appears to be empty." % tmp_conf)
    apply_update(tmp_conf, eeprom, config_src)

def read_current_config():
    """
    Reads the configuration used by the current bootloader.
    """
    fw_base = "/sys/firmware/devicetree/base/"
    nvmem_base = "/sys/bus/nvmem/devices/"

    if os.path.exists(fw_base + "/aliases/blconfig"):
        with open(fw_base + "/aliases/blconfig", "rb") as f:
            nvmem_ofnode_path = fw_base + f.read().decode('utf-8')
            for d in os.listdir(nvmem_base):
                if os.path.realpath(nvmem_base + d + "/of_node") in os.path.normpath(nvmem_ofnode_path):
                    return (open(nvmem_base + d + "/nvmem", "rb").read().decode('utf-8'), "blconfig device")

    return (shell_cmd(['vcgencmd', 'bootloader_config']), "vcgencmd bootloader_config")

class ImageSection:
    def __init__(self, magic, offset, length, filename=''):
        self.magic = magic
        self.offset = offset
        self.length = length
        self.filename = filename
        debug("ImageSection %x offset %d length %d %s" % (magic, offset, length, filename))

class BootloaderImage(object):
    def __init__(self, filename, output=None):
        """
        Instantiates a Bootloader image writer with a source eeprom (filename)
        and optionally an output filename.
        """
        self._filename = filename
        self._sections = []
        self._image_size = 0
        try:
            self._bytes = bytearray(open(filename, 'rb').read())
        except IOError as err:
            exit_error("Failed to read \'%s\'\n%s\n" % (filename, str(err)))
        self._out = None
        if output is not None:
            self._out = open(output, 'wb')

        self._image_size = len(self._bytes)
        if self._image_size not in VALID_IMAGE_SIZES:
            exit_error("%s: Expected size %d bytes actual size %d bytes" %
                       (filename, self._image_size, len(self._bytes)))
        self.parse()

    def parse(self):
        """
        Builds a table of offsets to the different sections in the EEPROM.
        """
        offset = 0
        magic = 0
        while offset < self._image_size:
            magic, length = struct.unpack_from('>LL', self._bytes, offset)
            if magic == 0x0 or magic == 0xffffffff:
                break # EOF
            elif (magic & MAGIC_MASK) != MAGIC:
                raise Exception('EEPROM is corrupted %x %x %x' % (magic, magic & MAGIC_MASK, MAGIC))

            filename = ''
            if magic == FILE_MAGIC: # Found a file
                # Discard trailing null characters used to pad filename
                filename = self._bytes[offset + 8: offset + FILE_HDR_LEN].decode('utf-8').replace('\0', '')
            debug("section at %d length %d magic %08x %s" % (offset, length, magic, filename))
            self._sections.append(ImageSection(magic, offset, length, filename))

            offset += 8 + length # length + type
            offset = (offset + 7) & ~7

    def find_file(self, filename):
        """
        Returns the offset, length and whether this is the last section in the
        EEPROM for a modifiable file within the image.
        """
        offset = -1
        length = -1
        is_last = False

        next_offset = self._image_size - ERASE_ALIGN_SIZE # Don't create padding inside the bootloader scratch page
        for i in range(0, len(self._sections)):
            s = self._sections[i]
            if s.magic == FILE_MAGIC and s.filename == filename:
                is_last = (i == len(self._sections) - 1)
                offset = s.offset
                length = s.length
                break

        # Find the start of the next non padding section
        i += 1
        while i < len(self._sections):
            if self._sections[i].magic == PAD_MAGIC:
                i += 1
            else:
                next_offset = self._sections[i].offset
                break
        ret = (offset, length, is_last, next_offset)
        debug('%s offset %d length %d is-last %d next %d' % (filename, ret[0], ret[1], ret[2], ret[3]))
        return ret

    def update(self, src_bytes, dst_filename):
        """
        Replaces a modifiable file with specified byte array.
        """
        hdr_offset, length, is_last, next_offset = self.find_file(dst_filename)
        update_len = len(src_bytes) + FILE_HDR_LEN

        if hdr_offset + update_len > self._image_size - ERASE_ALIGN_SIZE:
            raise Exception('No space available - image past EOF.')

        if hdr_offset < 0:
            raise Exception('Update target %s not found' % dst_filename)

        if hdr_offset + update_len > next_offset:
            raise Exception('Update %d bytes is larger than section size %d' % (update_len, next_offset - hdr_offset))

        new_len = len(src_bytes) + FILENAME_LEN + 4
        struct.pack_into('>L', self._bytes, hdr_offset + 4, new_len)
        struct.pack_into(("%ds" % len(src_bytes)), self._bytes,
                         hdr_offset + 4 + FILE_HDR_LEN, src_bytes)

        # If the new file is smaller than the old file then set any old
        # data which is now unused to all ones (erase value)
        pad_start = hdr_offset + 4 + FILE_HDR_LEN + len(src_bytes)

        # Add padding up to 8-byte boundary
        while pad_start % 8 != 0:
            struct.pack_into('B', self._bytes, pad_start, 0xff)
            pad_start += 1

        # Create a padding section unless the padding size is smaller than the
        # size of a section head. Padding is allowed in the last section but
        # by convention bootconf.txt is the last section and there's no need to
        # pad to the end of the sector. This also ensures that the loopback
        # config read/write tests produce identical binaries.
        pad_bytes = next_offset - pad_start
        if pad_bytes > 8 and not is_last:
            pad_bytes -= 8
            struct.pack_into('>i', self._bytes, pad_start, PAD_MAGIC)
            pad_start += 4
            struct.pack_into('>i', self._bytes, pad_start, pad_bytes)
            pad_start += 4

        debug("pad %d" % pad_bytes)
        pad = 0
        while pad < pad_bytes:
            struct.pack_into('B', self._bytes, pad_start + pad, 0xff)
            pad = pad + 1

    def update_key(self, src_pem, dst_filename):
        """
        Replaces the specified public key entry with the public key values extracted
        from the source PEM file.
        """
        pubkey_bytes = pemtobin(src_pem)
        self.update(pubkey_bytes, dst_filename)

    def update_file(self, src_filename, dst_filename):
        """
        Replaces the contents of dst_filename in the EEPROM with the contents of src_file.
        """
        src_bytes = open(src_filename, 'rb').read()
        if len(src_bytes) > MAX_FILE_SIZE:
            raise Exception("src file %s is too large (%d bytes). The maximum size is %d bytes."
                            % (src_filename, len(src_bytes), MAX_FILE_SIZE))
        self.update(src_bytes, dst_filename)

    def write(self):
        """
        Writes the updated EEPROM image to stdout or the specified output file.
        """
        if self._out is not None:
            self._out.write(self._bytes)
            self._out.close()
        else:
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write(self._bytes)
            else:
                sys.stdout.write(self._bytes)

    def get_file(self, filename):
        hdr_offset, length, is_last, next_offset = self.find_file(filename)
        offset = hdr_offset + 4 + FILE_HDR_LEN
        file_bytes = self._bytes[offset:offset+length-FILENAME_LEN-4]
        return file_bytes

    def extract_files(self):
        for i in range(0, len(self._sections)):
            s = self._sections[i]
            if s.magic == FILE_MAGIC:
                file_bytes = self.get_file(s.filename)
                open(s.filename, 'wb').write(file_bytes)

    def read(self):
        config_bytes = self.get_file('bootconf.txt')
        if self._out is not None:
            self._out.write(config_bytes)
            self._out.close()
        else:
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write(config_bytes)
            else:
                sys.stdout.write(config_bytes)

def main():
    """
    Utility for reading and writing the configuration file in the
    Raspberry Pi bootloader EEPROM image.
    """
    description = """\
Bootloader EEPROM configuration tool for the Raspberry Pi 4 and Raspberry Pi 5.
Operating modes:

1. Outputs the current bootloader configuration to STDOUT if no arguments are
   specified OR the given output file if --out is specified.

   rpi-eeprom-config [--out boot.conf]

2. Extracts the configuration file from the given 'eeprom' file and outputs
   the result to STDOUT or the output file if --output is specified.

   rpi-eeprom-config pieeprom.bin [--out boot.conf]

3. Writes a new EEPROM image replacing the configuration file with the contents
   of the file specified by --config.

   rpi-eeprom-config --config boot.conf --out newimage.bin pieeprom.bin

   The new image file can be installed via rpi-eeprom-update
   rpi-eeprom-update -d -f newimage.bin

4. Applies a given config file to an EEPROM image and invokes rpi-eeprom-update
   to schedule an update of the bootloader when the system is rebooted.

   Since this command launches rpi-eeprom-update to schedule the EEPROM update
   it must be run as root.

   sudo rpi-eeprom-config --apply boot.conf [pieeprom.bin]

   If the 'eeprom' argument is not specified then the latest available image
   is selected by calling 'rpi-eeprom-update -l'.

5. The '--edit' parameter behaves the same as '--apply' except that instead of
   applying a predefined configuration file a text editor is launched with the
   contents of the current EEPROM configuration.

   Since this command launches rpi-eeprom-update to schedule the EEPROM update
   it must be run as root.

   The configuration file will be taken from:
       * The blconfig reserved memory nvmem device
       * The cached bootloader configuration 'vcgencmd bootloader_config'
       * The current pending update - typically /boot/pieeprom.upd

   sudo -E rpi-eeprom-config --edit [pieeprom.bin]

   To cancel the pending update run 'sudo rpi-eeprom-update -r'

   The default text editor is nano and may be overridden by setting the 'EDITOR'
   environment variable and passing '-E' to 'sudo' to preserve the environment.

6. Signing the bootloader config file.
   Updates an EEPROM binary with a signed config file (created by rpi-eeprom-digest) plus
   the corresponding RSA public key.

   Requires Python Cryptodomex libraries and OpenSSL. To install on Raspberry Pi OS run:-
   sudo apt install openssl python-pip
   sudo python3 -m pip install cryptodomex

   rpi-eeprom-digest -k private.pem -i bootconf.txt -o bootconf.sig
   rpi-eeprom-config --config bootconf.txt --digest bootconf.sig --pubkey public.pem --out pieeprom-signed.bin pieeprom.bin

   Currently, the signing process is a separate step so can't be used with the --edit or --apply modes.


See 'rpi-eeprom-update -h' for more information about the available EEPROM images.
"""

    if os.getuid() != 0:
        exit_error("Please run as root")
    elif not argon_rpisupported():
        # Skip
        sys.exit(0)
    argon_edit_config()

if __name__ == '__main__':
    atexit.register(exit_handler)
    main()

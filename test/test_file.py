"""File tests"""

from contextlib import nullcontext
from io import IOBase
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile, TemporaryFile
import unittest
from uuid import UUID
from pihat.eeprom import (EepromFile, EepromGpioDrive, EepromGpioFunction,
                          EepromGpioSlew, EepromGpioHysteresis,
                          EepromGpioBackPower, EepromGpioPull)


class FileTestBase(unittest.TestCase):
    """File tests base class"""

    @classmethod
    def setUpClass(cls):
        """Initialise test suite"""
        module = sys.modules[cls.__module__]
        cls.files = Path(module.__file__).parent / 'files'

    def assertFilesEqual(self, file1, file2):
        """Assert that files have identical content"""
        def filecontext(file):
            if isinstance(file, IOBase):
                file.seek(0)
                return nullcontext(file)
            return open(file, 'rb')
        with filecontext(file1) as fh1, filecontext(file2) as fh2:
            self.assertEqual(fh1.read(), fh2.read())


class FileTest(FileTestBase):
    """File tests"""

    def test_load(self):
        """Test loading EEPROM generated by eepmake"""
        eeprom = EepromFile(self.files / 'sample.eep').load()
        self.assertEqual(eeprom.uuid,
                         UUID('23872014-7f74-46f9-b521-02456d9c8261'))
        self.assertEqual(eeprom.pid, 0xcafe)
        self.assertEqual(eeprom.pver, 0x0007)
        self.assertEqual(eeprom.vstr, b'The Factory')
        self.assertEqual(eeprom.pstr, b'Sample Board')
        self.assertEqual(eeprom.bank.drive, EepromGpioDrive.MA_14)
        self.assertEqual(eeprom.bank.slew, EepromGpioSlew.LIMITED)
        self.assertEqual(eeprom.bank.hysteresis, EepromGpioHysteresis.DEFAULT)
        self.assertEqual(eeprom.power.back_power, EepromGpioBackPower.MA_2000)
        self.assertFalse(eeprom.pins[1].used)
        self.assertTrue(eeprom.pins[2].used)
        self.assertEqual(eeprom.pins[2].function, EepromGpioFunction.INPUT)
        self.assertEqual(eeprom.pins[2].pull, EepromGpioPull.DEFAULT)
        self.assertEqual(eeprom.pins[3].pull, EepromGpioPull.DOWN)
        self.assertEqual(eeprom.pins[8].function, EepromGpioFunction.ALT3)
        self.assertEqual(
            eeprom.fdt.get_property('status', 'fragment@0/__overlay__').value,
            'okay'
        )
        self.assertEqual(
            eeprom.fdt.get_property('i2c0', '__fixups__').value,
            '/fragment@0:target:0',
        )

    def test_load_init_name(self):
        """Test loading EEPROM from constructor filename"""
        eeprom = EepromFile(self.files / 'spidev.eep').load()
        self.assertEqual(eeprom.pid, 0xfeed)
        self.assertFalse(eeprom.pins[7].used)

    def test_load_explicit_name(self):
        """Test loading EEPROM from explicit filename"""
        eeprom = EepromFile().load(self.files / 'sample.eep')
        self.assertEqual(eeprom.pver, 0x0007)
        self.assertTrue(eeprom.pins[3].used)
        self.assertFalse(eeprom.pins[4].used)

    def test_load_init_fh(self):
        """Test loading EEPROM from constructor filehandle"""
        with open(self.files / 'sample.eep', 'rb') as fh:
            eeprom = EepromFile(fh).load()
            self.assertFalse(fh.closed)
            self.assertEqual(eeprom.pver, 0x0007)
            self.assertEqual(eeprom.pstr, b'Sample Board')

    def test_load_explicit_fh(self):
        """Test loading EEPROM from explicit filehandle"""
        with open(self.files / 'spidev.eep', 'rb') as fh:
            eeprom = EepromFile().load(fh)
            self.assertFalse(fh.closed)
            self.assertEqual(eeprom.pstr, b'SPI Thing')
            self.assertEqual(eeprom.pins[10].function, EepromGpioFunction.ALT0)

    def test_save_init_name(self):
        """Test saving EEPROM to constructor filename"""
        with NamedTemporaryFile() as temp:
            eeprom = EepromFile(temp.name)
            eeprom.load(self.files / 'spidev.eep')
            eeprom.save()
            self.assertFilesEqual(temp.name, self.files / 'spidev.eep')

    def test_save_explicit_name(self):
        """Test saving EEPROM to explicit filename"""
        eeprom = EepromFile(self.files / 'sample.eep').load()
        with NamedTemporaryFile() as temp:
            eeprom.save(temp.name, verify=True)
            self.assertFilesEqual(temp.file, self.files / 'sample.eep')

    def test_save_init_fh(self):
        """Test saving EEPROM to constructor filehandle"""
        with TemporaryFile() as temp:
            eeprom = EepromFile(temp)
            eeprom.load(self.files / 'spidev.eep')
            eeprom.save()
            self.assertFalse(temp.closed)
            self.assertFilesEqual(temp, self.files / 'spidev.eep')

    def test_save_explicit_fh(self):
        """Test saving EEPROM to explicit filehandle"""
        eeprom = EepromFile(self.files / 'spidev.eep').load()
        with TemporaryFile() as temp:
            eeprom.save(temp)
            self.assertFalse(temp.closed)
            self.assertFilesEqual(temp, self.files / 'spidev.eep')

    def test_open(self):
        """Test opening EEPROM file"""
        with TemporaryFile() as temp:
            eeprom = EepromFile(temp)
            with eeprom.open() as fh:
                self.assertEqual(fh, temp)

    def test_context(self):
        """Test using EEPROM as context manager"""
        with EepromFile(self.files / 'sample.eep') as eeprom:
            self.assertEqual(eeprom.uuid,
                             UUID('23872014-7f74-46f9-b521-02456d9c8261'))
            with TemporaryFile() as temp:
                eeprom.save(temp)
                self.assertFilesEqual(temp, self.files / 'sample.eep')

    def test_no_autoload(self):
        """Test disabling autoload"""
        with TemporaryFile() as temp:
            with EepromFile(temp, autoload=False) as eeprom:
                self.assertEqual(eeprom.vstr, b'')
                eeprom.load(self.files / 'spidev.eep')
                self.assertEqual(eeprom.vstr, b'The Factory')
                eeprom.save()
            self.assertFilesEqual(temp, self.files / 'spidev.eep')

    def test_autosave(self):
        """Test automatic saving of modified EEPROM"""
        with NamedTemporaryFile() as temp:
            with open(self.files / 'sample.eep', 'rb') as original:
                temp.write(original.read())
                temp.flush()
            with EepromFile(temp.name, autosave=True) as eeprom1:
                self.assertEqual(eeprom1.uuid,
                                 UUID('23872014-7f74-46f9-b521-02456d9c8261'))
                self.assertEqual(eeprom1.pstr, b'Sample Board')
                eeprom1.uuid = UUID('5faf992a-2098-496c-a119-46dcb2dc0ddd')
            with EepromFile(temp.name, autosave=False) as eeprom2:
                self.assertEqual(eeprom2.uuid,
                                 UUID('5faf992a-2098-496c-a119-46dcb2dc0ddd'))
                self.assertEqual(eeprom2.pstr, b'Sample Board')
                eeprom2.pstr = b'Nothing'
            with EepromFile(temp.name, autosave=False) as eeprom3:
                self.assertEqual(eeprom3.uuid,
                                 UUID('5faf992a-2098-496c-a119-46dcb2dc0ddd'))
                self.assertEqual(eeprom3.pstr, b'Sample Board')
                eeprom3.pstr = b'Something'
                eeprom3.save()
                eeprom3.pstr = b'Else'
                eeprom3.save()
            with EepromFile(temp.name, autosave=False) as eeprom4:
                self.assertEqual(eeprom4.uuid,
                                 UUID('5faf992a-2098-496c-a119-46dcb2dc0ddd'))
                self.assertEqual(eeprom4.pstr, b'Else')

    def test_autouuid(self):
        """Test automatic generation of UUID"""
        with NamedTemporaryFile() as temp:
            eeprom1 = EepromFile(temp.name, autouuid=True)
            eeprom1.vstr = b'Hello'
            eeprom1.vstr = b'World'
            self.assertEqual(eeprom1.uuid.int, 0)
            eeprom1.save(temp.name)
            self.assertEqual(eeprom1.uuid.int, 0)
            eeprom2 = EepromFile(temp.name).load()
            self.assertNotEqual(eeprom2.uuid.int, 0)
            eeprom1.uuid = eeprom2.uuid
            self.assertEqual(eeprom1, eeprom2)

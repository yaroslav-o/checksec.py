from collections import namedtuple
from pathlib import Path

import lief
from lief.PE import Header, OptionalHeader, Signature
DLL_CHARACTERISTICS = OptionalHeader.DLL_CHARACTERISTICS
HEADER_CHARACTERISTICS = Header.CHARACTERISTICS
MACHINE_TYPES = Header.MACHINE_TYPES


from .binary import BinarySecurity

PEChecksecData = namedtuple(
    "PEChecksecData",
    [
        "machine",
        "nx",
        "canary",
        "aslr",
        "dynamic_base",
        "high_entropy_va",
        "seh",
        "safe_seh",
        "force_integrity",
        "guard_cf",
        "isolation",
        "authenticode",
    ],
)


def is_pe(filepath: Path) -> bool:
    """Tests whether given file is a Portable Executable"""
    return lief.is_pe(str(filepath))


class PESecurity(BinarySecurity):
    """This class allows to get the security state of a PE from a Path object"""

    def __init__(self, pe_path: Path):
        super().__init__(pe_path)

    @property
    def has_canary(self) -> bool:
        """Whether stack security cookie is enabled (/GS)"""
        try:
            return True if self.bin.load_configuration.security_cookie != 0 else False
        except AttributeError:
            # # no load_configuration or no security cookie
            return False

    @property
    def has_dynamic_base(self) -> bool:
        """Whether DYNAMIC_BASE is enabled"""
        return self.bin.optional_header.has(DLL_CHARACTERISTICS.DYNAMIC_BASE)

    @property
    def is_aslr(self) -> bool:
        """Checks whether ASLR is compatible"""
        # https://github.com/trailofbits/winchecksec/blob/v2.0.0/checksec.cpp#L172
        return not self.bin.header.has_characteristic(HEADER_CHARACTERISTICS.RELOCS_STRIPPED) and self.has_dynamic_base

    @property
    def has_high_entropy_va(self) -> bool:
        """Whether HIGH_ENTROPY_VA is enabled"""
        return self.bin.optional_header.has(DLL_CHARACTERISTICS.HIGH_ENTROPY_VA)

    @property
    def has_seh(self) -> bool:
        return not self.bin.optional_header.has(DLL_CHARACTERISTICS.NO_SEH)

    @property
    def has_safe_seh(self) -> bool:
        """Whether the binary has SafeSEH mitigations"""
        # SafeSEH only applies to 32 bits
        # winchecksec implementation:
        # https://github.com/trailofbits/winchecksec/blob/v2.0.0/checksec.cpp#L280
        if not self.bin.header.machine == MACHINE_TYPES.I386:
            return False
        try:
            return (
                self.has_seh
                and self.bin.load_configuration.se_handler_table != 0
                and self.bin.load_configuration.se_handler_count != 0
            )
        except AttributeError:
            # no load_configuration or no se_handler_xx
            return False

    @property
    def is_authenticode_valid(self) -> bool:
        """Whether the binary has a valid Authenticode signature"""
        return self.bin.verify_signature() == Signature.VERIFICATION_FLAGS.OK

    @property
    def has_force_integrity(self) -> bool:
        """Whether FORCE_INTEGRITY is enabled"""
        # /INTEGRITYCHECK
        return self.bin.optional_header.has(DLL_CHARACTERISTICS.FORCE_INTEGRITY)

    @property
    def has_guard_cf(self) -> bool:
        """Whether Control Flow Guard is enabled"""
        # November 2014 (Windows 8.1 Update 3)
        # winchecksec:
        # https://github.com/trailofbits/winchecksec/blob/v2.0.0/checksec.cpp#L238
        return self.is_aslr and self.bin.optional_header.has(DLL_CHARACTERISTICS.GUARD_CF)

    # Return Flow Guard: October 2016 (Windows 10 Redstone 2)

    @property
    def has_isolation(self) -> bool:
        """Whether manifest isolation is enabled"""
        # MSDN doc: https://docs.microsoft.com/en-us/cpp/build/reference/allowisolation-manifest-lookup?view=vs-2019
        # November 2016
        return not self.bin.optional_header.has(DLL_CHARACTERISTICS.NO_ISOLATION)

    @property
    def checksec_state(self) -> PEChecksecData:
        machine: MACHINE_TYPES = self.bin.header.machine
        machine_int = machine.value
        return PEChecksecData(
            machine=machine_int,
            nx=self.has_nx,
            canary=self.has_canary,
            aslr=self.is_aslr,
            dynamic_base=self.has_dynamic_base,
            high_entropy_va=self.has_high_entropy_va,
            seh=self.has_seh,
            safe_seh=self.has_safe_seh,
            force_integrity=self.has_force_integrity,
            guard_cf=self.has_guard_cf,
            isolation=self.has_isolation,
            authenticode=self.is_authenticode_valid,
        )

"""NVMe Get Log Page 指令 CDW 組合器。"""
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class GetLogPageCommand:
    """Get Log Page 指令參數封裝。"""
    lid: int                              # Log Page Identifier (0x00~0xFF)
    length_bytes: Optional[int] = None    # 使用者請求的資料長度 (Bytes)
    numd_val: Optional[int] = None        # 使用者直接指定之 NUMD (0-based, 例如 0x7F)
    nsid: int = 0xFFFFFFFF               # Namespace ID
    rae: int = 0                          # Retain Asynchronous Event
    lsp: int = 0                          # Log Specific Field
    lpo: int = 0                          # Log Page Offset
    
    def __post_init__(self):
        if self.length_bytes is None and self.numd_val is not None:
            self.length_bytes = (self.numd_val + 1) * 4
        elif self.length_bytes is None and self.numd_val is None:
            self.length_bytes = 512
    
    @property
    def aligned_length(self) -> int:
        """計算 Dword 對齊後的實際傳輸長度 (Bytes)。"""
        dwords = math.ceil(self.length_bytes / 4)
        return dwords * 4
    
    @property
    def numd(self) -> int:
        """計算 Number of Dwords (0-based)。"""
        if self.numd_val is not None:
            return self.numd_val
        return math.ceil(self.length_bytes / 4) - 1
    
    @property
    def numdl(self) -> int:
        """NUMD Lower 16-bit。"""
        return self.numd & 0xFFFF
        
    @property
    def numdu(self) -> int:
        """NUMD Upper 16-bit。"""
        return (self.numd >> 16) & 0xFFFF
    
    @property
    def cdw10(self) -> int:
        """組合 CDW10: NUMDL[31:16] | RAE[15] | LSP[11:8] | LID[7:0]。"""
        return (self.numdl << 16) | ((self.rae & 1) << 15) | ((self.lsp & 0xF) << 8) | (self.lid & 0xFF)
    
    @property
    def cdw11(self) -> int:
        """組合 CDW11: NUMDU[15:0]。"""
        return self.numdu
    
    @property
    def cdw12(self) -> int:
        """CDW12: Log Page Offset Lower 32-bit。"""
        return self.lpo & 0xFFFFFFFF
    
    @property
    def cdw13(self) -> int:
        """CDW13: Log Page Offset Upper 32-bit。"""
        return (self.lpo >> 32) & 0xFFFFFFFF

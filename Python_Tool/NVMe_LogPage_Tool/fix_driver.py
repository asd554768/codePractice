import re

with open('core/nvme_driver.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 把被破壞的部分取代回來，順便加入多重策略。
# 目前被破壞的段落：
#         io_buffer = SPC_WITH_BUFFER()
# 
#         return data, nvme_status_code
# 
# 我們直接利用正則表達式把這整段取代掉。

replacement = """        io_buffer = SPC_WITH_BUFFER()
        
        # 多重嘗試策略，用來避開不同驅動程式對於 Length/Flags/NSID 的奇怪限制 (Error 87)
        strategies = [
            # 策略 1: Microsoft 官方 Adapter Request (通常要求 Length=84, NSID=0xFFFFFFFF)
            {"length": 84, "flags": 0x80000000, "nsid": cmd.nsid},
            # 策略 2: 某些驅動將 PhysicalDrive 視為 Device Request (Flags=0)
            {"length": 84, "flags": 0x00000000, "nsid": cmd.nsid},
            # 策略 3: Device Request 且 NSID 為 0 (交由驅動自行填充)
            {"length": 84, "flags": 0x00000000, "nsid": 0},
            # 策略 4: Length 144, Adapter Request (針對舊版驅動可能直接檢查整個 struct size)
            {"length": spc_size, "flags": 0x80000000, "nsid": cmd.nsid},
            # 策略 5: Length 144, Device Request
            {"length": spc_size, "flags": 0x00000000, "nsid": cmd.nsid},
        ]
        
        last_error_code = None
        for strat in strategies:
            import ctypes, struct
            # 每次重設 io_buffer
            ctypes.memset(ctypes.addressof(io_buffer), 0, ctypes.sizeof(io_buffer))
            
            io_buffer.spc.Version = 1
            io_buffer.spc.Length = strat["length"]
            io_buffer.spc.ProtocolType = 1 # PROTOCOL_TYPE_NVME
            io_buffer.spc.Flags = strat["flags"]
            io_buffer.spc.CommandLength = 64
            io_buffer.spc.DataFromDeviceTransferLength = aligned_length
            io_buffer.spc.TimeOutValue = 10
            io_buffer.spc.DataFromDeviceBufferOffset = spc_size
            io_buffer.spc.CommandSpecific = 1  # NVMe Admin Command
            
            # 設定 NVMe SQE (64 bytes)
            io_buffer.spc.Command[0] = 0x02 # OPCODE_GET_LOG_PAGE
            struct.pack_into("<I", io_buffer.spc.Command, 4, strat["nsid"])
            struct.pack_into("<I", io_buffer.spc.Command, 40, cmd.cdw10)
            struct.pack_into("<I", io_buffer.spc.Command, 44, cmd.cdw11)
            struct.pack_into("<I", io_buffer.spc.Command, 48, cmd.cdw12)
            struct.pack_into("<I", io_buffer.spc.Command, 52, cmd.cdw13)

            res, bytes_returned = device_io_control(
                self.handle,
                0x002D5140, # IOCTL_STORAGE_PROTOCOL_COMMAND
                io_buffer,
                total_size,
                io_buffer,
                total_size
            )
            
            if res:
                return_status = io_buffer.spc.ReturnStatus
                error_code = io_buffer.spc.ErrorCode
                nvme_status_code = return_status if return_status != 0 else error_code
                
                data = bytes(io_buffer.buffer)[:cmd.length_bytes]
                return data, nvme_status_code
            else:
                last_error_code = ctypes.GetLastError()
                # 如果是 87 (Invalid Parameter)，我們換下一種策略
                if last_error_code == 87:
                    continue
                else:
                    # 如果是其他錯誤 (例如權限不足 5)，就不繼續嘗試了，直接報錯
                    break
                    
        raise OSError(f"DeviceIoControl (Pass-Through) failed with Windows error {last_error_code}")"""

code = re.sub(r'        io_buffer = SPC_WITH_BUFFER\(\)\s*return data, nvme_status_code', replacement, code)

with open('core/nvme_driver.py', 'w', encoding='utf-8') as f:
    f.write(code)

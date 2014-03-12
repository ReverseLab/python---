import sys
import ctypes
import struct

kernel32 = ctypes.WinDLL('kernel32.dll')

def allocate(handle, size):
	MEM_COMMIT  = 0x1000
	MEM_RESERVE = 0x2000
	PAGE_EXECUTE_READWRITE = 0x40

	count = size

	res = kernel32.VirtualAllocEx(handle, 0x0, count * 0x1000, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
	print "Allocated memory for handle %d at 0x%08x" % (handle, res)

	return res

def writemem(handle, mem, data):

	src = ctypes.c_char_p(data)
	dst = ctypes.cast(mem, ctypes.c_char_p)
	length = ctypes.c_int(len(data))

	res = ctypes.windll.kernel32.WriteProcessMemory(handle, dst, src, length, 0x0)

	return res


def allocate_code(handle, opcodes):

	memory = allocate(handle, 1024)
	addr = writemem(handle, memory, opcodes)

	return (memory, addr)

def get_handle(pid):
	PROCESS_VM_OPERATION = 0x0008  
	PROCESS_VM_READ = 0x0010  
	PROCESS_VM_WRITE = 0x0020  

	PROCESS_SET_INFORMATION = 0x0200  
	PROCESS_QUERY_INFORMATION = 0x0400 
	
	PROCESS_INFO_ALL = PROCESS_QUERY_INFORMATION|PROCESS_SET_INFORMATION
	PROCESS_VM_ALL = PROCESS_VM_OPERATION|PROCESS_VM_READ|PROCESS_VM_WRITE

	res = kernel32.OpenProcess(PROCESS_INFO_ALL | PROCESS_VM_ALL, False, pid)
	print "Returning handle %d" % res
	return res

def vprotect(handle, address):
	PAGE_EXECUTE_READWRITE = 0x40

	crap = ctypes.create_string_buffer("\x00"*4)
	res = kernel32.VirtualProtectEx(handle, address, 0x1000, PAGE_EXECUTE_READWRITE, ctypes.byref(crap))
	print "VirtualProtecEx returned 0x%08x" % res
	return res

def makejump(start, target, length):

	print "Asked to make a jump from 0x%08x to 0x%08x" % (start, target)
	if start < target:
		buf = "\xe9" + struct.pack("L", target-start-5)
		buf += "\x90"*(length-len(buf))
	else:
		buf = "\xe9" + struct.pack("L", target-start-5)
		buf += "\x90"*(length-len(buf))

	return buf

def patchjump(handle, x, y, length):
	opcodes = makejump(x, y, length)

	dst = ctypes.cast(x, ctypes.c_char_p)
	src = ctypes.c_char_p(opcodes)

	print "Patching jump from 0x%08x to 0x%08x" % (x, y)
	res = ctypes.windll.kernel32.WriteProcessMemory(handle, dst, src, length, 0x0)
	print "WriteProcessMemory returned 0x%08x" % res

	return res

pid = int(sys.argv[1])
print "Getting handle to process with PID %d" % pid
handle = get_handle(pid)

print "Allocating code"
addr, res = allocate_code(handle, "ABCDEF")

#hook = int(sys.argv[2], 16)
hook1 = 0x78586eb5
hook2 = 0x78586F35
print "VirtualProtect'ing the hook point 0x%08x" % hook1
res2 = vprotect(handle, hook1)

"""
offset
0x00    our grab args code - 0x17 bytes + 5 byte jump
0x20    our search code - 0x31 bytes + 5 byte jump
0x60    original hook1 code - 0x0c bytes + 5 byte jump
0x80    original hook2 code - 0x07 bytes + 5 byte jump
0x100   2 saved dwords
"""

# .text:78586EB5 8B C8                   mov     ecx, eax
# .text:78586EB7 C1 F9 05                sar     ecx, 5
# .text:78586EBA 8D 1C 8D A0 D6 5B 78    lea     ebx, ___pioinfo[ecx*4]
hook1_orig = "\x8b\xc8\xc1\xf9\x05\x8d\x1c\x8d\xa0\xd6\x5b\x78"

# patch a jump from hook1 to addr
patchjump(handle, hook1, addr+0x00, 12)

# .text:78586F35 C7 45 FC FE FF FF FF    mov     [ebp+ms_exc.disabled], 0FFFFFFFEh
hook2_orig = "\xc7\x45\xfc\xfe\xff\xff\xff"

# patch a jump from hook2 to addr+0x20
patchjump(handle, hook2, addr+0x20, 7)

writemem(handle, addr+0x60, hook1_orig)
writemem(handle, addr+0x80, hook2_orig)

saved_size = struct.pack("L", allocate(handle, 4))
saved_dst  = struct.pack("L", allocate(handle, 4))
bytes = "RIFX"

args_hook = "\x51\x56\x8b\x4c\x24\x10\x8b\x74\x24\x0c\x89\x0d" + saved_size + "\x89\x35" + saved_dst + "\x5e\x59"
search_hook = "\x60\x9c\x8b\x0d" + saved_size + "\x8b\x35" + saved_dst + "\xc1\xe9\x02\xb8" + bytes + "\x39\x06\x75\x02\x74\x08\x8d\x76\x04\x49\x74\x08\xeb\xf2\xcc\xe9\x05\x00\x00\x00\xe9\x00\x00\x00\x00\x9d\x61"
jmp_hook1 = patchjump(handle, addr+0x00+len(args_hook), addr+0x60, 5)
jmp_hook2 = patchjump(handle, addr+0x20+len(search_hook), addr+0x80, 5)

writemem(handle, addr, args_hook)
writemem(handle, addr+0x20, search_hook)

patchjump(handle, addr+0x60+len(hook1_orig), hook1+12, 5)
patchjump(handle, addr+0x80+len(hook2_orig), hook2+7, 5)


raw_input(">>>>>>>>>>>>  ")

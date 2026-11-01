"""ROM-only zero-run codec for Konami's 64 stage sprite patterns."""

def compress(data):
    out=bytearray()
    i=0
    while i<len(data):
        if data[i]==0:
            n=1
            while i+n<len(data) and n<128 and data[i+n]==0:n+=1
            out.append(0x80|(n-1))
            i+=n
        else:
            n=1
            while i+n<len(data) and n<128 and data[i+n]!=0:n+=1
            out.append(n-1)
            out.extend(data[i:i+n])
            i+=n
    return bytes(out)

def decompress(data):
    out=bytearray()
    i=0
    while i<len(data):
        ctl=data[i];i+=1
        n=(ctl&127)+1
        if ctl&128:out.extend(bytes(n))
        else:
            out.extend(data[i:i+n]);i+=n
    return bytes(out)

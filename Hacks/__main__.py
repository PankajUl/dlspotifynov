import os
import multiprocessing
import hashlib

from multiprocessing.managers import BaseManager

from datetime import datetime as Time

from importLogging.loggingBlah import log0, log1

# Some parameters you can tweak
BUFSIZE = 2**25
POOLSIZE = 1

totalFiles = 0

class notify(object):
    def __init__(self, fname):
        self.x = 0
        self.file = open(fname, 'w')
    
    def msPrint(self, filename, digest):
        self.x += 1
        print('%06d > %-125s : %-20s\r' % (self.x, filename[:125], digest[:20]), end='')
        self.file.write('%-175s\t%s\n' % (filename, digest))
    
    def final(self):
        print()
        print('Files Processed:\t%06d' % self.x)
        self.file.close()

class managedNotify(BaseManager): pass
managedNotify.register('notify', notify)

def compute_digest(filename, printer):
    try:
        f = open(filename,"rb")
    except IOError:
        return None

    digest = hashlib.sha512()
    
    while True:
        chunk = f.read(BUFSIZE)
        
        if not chunk:
            log0.info('%s digest calculated' % filename)
            break
        
        log1.info('%s digest being updated' % filename)
        digest.update(chunk)

    f.close()
    
    dValue = digest.digest().hex()
    printer.msPrint(filename, dValue)

    return filename, dValue

def build_digest_map(topdir, fname):
    digest_pool = multiprocessing.Pool(POOLSIZE)

    # Read buffer size
    # Number of workers
    allfiles = (os.path.join(path,name)
        for path, dirs, files in os.walk(topdir)
         for name in files)
    
    argsR = []

    manager = managedNotify()
    manager.start()
    temp = manager.notify(fname)

    for file in allfiles:
        argsR.append((file, temp))


    log0.info('launching the Imaps')
    digest_map = dict(digest_pool.starmap(compute_digest,argsR))
    digest_pool.close()

    temp.final()
    manager.shutdown()
    
    return digest_map

# Try it out. Change the directory name as desired. 

#__name__ = '__main__'

if __name__ == '__main__':
    multiprocessing.freeze_support()

    log1.critical('Inside Main')
 
    print('\n\nUtilizing 1 processes, (1core normal-threading):')

    st = Time.now()
    digest_map = build_digest_map(r"D:\\Software", '1core.txt')
    final = Time.now()
    
    print('Time Taken:\t\t', end='')
    print((final-st))

    print('\n\nUtilizing 16 processes, (8core hyperthreading):')

    POOLSIZE = 16

    st = Time.now()
    digest_map = build_digest_map(r"D:\\Software", '16proc.txt')
    final = Time.now()
    
    print('Time Taken:\t\t', end='')
    print((final-st))

# Utilizing 1 processes, (1core normal-threading):
# 033326 > D:\\Software\VLC\skins\fonts\FreeSansBold.ttf  
# Files Processed:        033326
# Time Taken:             0:17:36.301516
# 
# 
# Utilizing 16 processes, (8core hyperthreading):
# 033326 > D:\\Software\VLC\locale\ml\LC_MESSAGES\vlc.mo
# Files Processed:        033326
# Time Taken:             0:03:26.973040
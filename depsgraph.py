import bpy

import queue
from threading import Lock

runQueue = queue.Queue()
runMap = {}
runQueue2 = []
runMap2 = {}

running=False

__runmaplock = Lock()

depsgraphList =[]

def runLater(fun,key=None):
    if key!=None:
        __runmaplock.acquire()
        if key not in runMap:
            (runMap2 if running else runMap)[key]=fun
        __runmaplock.release()
    else:
        if running:
            runQueue2.append(fun)
        else: 
            runQueue.put(fun)

@bpy.app.handlers.persistent
def queuedRun():
    global running
    running=True
    
    if runMap:
        __runmaplock.acquire()
        for fun in runMap.values():
            fun()
        runMap.clear()
        __runmaplock.release()
    
    while not runQueue.empty():
        fun=runQueue.get()
        try:
            fun()
        except:
            import traceback
            traceback.print_exc()
    
    if runMap2:
        runMap.update(runMap2)
        runMap2.clear()
    
    if runQueue2:
        for i in runQueue2:
            runQueue.put(i)
        runQueue2.clear()
    
    running=False
    return 1/60.0


def onDepsgraph(fun):
    depsgraphList.append(fun)

def offDepsgraph(fun):
    depsgraphList.remove(fun)

@bpy.app.handlers.persistent
def depsgraphRun(ctx):
    for fun in depsgraphList:
        fun(ctx)
    
def reg():
    
    bpy.app.timers.register(queuedRun)
    bpy.app.handlers.depsgraph_update_post.append(depsgraphRun)
    
    

def dereg():
    try:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraphRun)
    except:
        pass
    depsgraphList.clear()
    
    try:
        bpy.app.timers.unregister(queuedRun)
    except:
        pass

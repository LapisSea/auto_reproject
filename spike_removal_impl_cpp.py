import bpy
from .import_properties import *
from . import utils
import numpy as np
import threading
import time
from array import array
import tempfile

def analyse_mesh(mesh, locality, min_derivation, min_length, process_wait):
    import subprocess, os, io
    build="x64"
    
    waiting=[False]
    
    local_path='SpikeDetector/bin/'+build+'/SpikeDetector/SpikeDetector.exe'
    
    from os import listdir
    from os.path import join
    
    proc = subprocess.Popen(join(os.path.dirname(os.path.realpath(__file__)),local_path), encoding="utf8", stdout=subprocess.PIPE, stdin=subprocess.PIPE,stderr=subprocess.STDOUT, shell=False)
    
    chunk_size=1024
    
    folder=tempfile.TemporaryDirectory()
    tmp_path=folder.name
    
    def tmp_file():
        return join(tmp_path,str(sum(1 for f in listdir(tmp_path))))
    
    try:
        stdout = proc.stdout
        stdin = proc.stdin
        
        
        def read_command():
            
            what=read_until(" ")
            args=[]
            while True:
                arg=read_until(";")
                # safe=arg.strip()
                if arg=="":
                    break
                args.append(arg)
            
            return (what, args)
        
        def send_message(data):
            # print("sent message:",data)
            val=str(data)+os.linesep
            stdin.write(val)
            stdin.flush()
        
        def send_raw(data):
            stdin.write(data)
        
        def read_until(delimiter):
            word=""
            while True:
                if proc.poll()!=None:
                    raise Exception("Worker died unexpectedly, code: "+str(proc.returncode))
                
                char = stdout.read(1)
                if char == delimiter:
                    # print("read",'"'+word+delimiter+'"')
                    return word
                word+=char
        
        def signal_file(fil):
            send_message(len(fil))
            send_message(fil)
            
        def make_file(writer):
            fil=tmp_file()
            
            with open(fil, 'w+',encoding="utf8",buffering=chunk_size*2) as f:
                
                def write_chunk(data):
                    f.write(data.hex())
                
                writer(write_chunk)
            
            return fil
        
        def write_co():
            def writer(send_chunk):
                verts=mesh.vertices
                
                siz=len(verts)
                pos=0
                while pos<siz:
                    f=pos
                    t=min(siz, pos+chunk_size)
                    pos=t
                    
                    chunk=[]
                    for i in range(f,t):
                        co=verts[i].co
                        chunk.append(co[0])
                        chunk.append(co[1])
                        chunk.append(co[2])
                    
                    send_chunk(array('f', chunk).tobytes())
            
            return make_file(writer)
        
        def write_ed():
            def writer(send_chunk):
                edges=mesh.edges
                
                siz=len(edges)
                pos=0
                while pos<siz:
                    f=pos
                    t=min(siz, pos+chunk_size)
                    pos=t
                    
                    chunk=[]
                    for i in range(f,t):
                        co=edges[i].vertices
                        chunk.append(co[0])
                        chunk.append(co[1])
                    
                    send_chunk(array('i', chunk).tobytes())
            
            return make_file(writer)
        
        co_fil=[]
        ed_fil=[]
        
        def write_fils():
            ed_fil.append(write_ed())
            co_fil.append(write_co())
        threading.Thread(target=write_fils).start()
        
        
        def wait_n_get(file):
            if not file:
                print("Waiting for file...")
                while not file:
                    time.sleep(0.02)
                
            return file[0]
        
        response_values={
            "mesh.cordinates.size": lambda: len(mesh.vertices),
            "mesh.edge_index.size": lambda: len(mesh.edges),
            "mesh.face_index.size": lambda: len(mesh.loop_triangles),
            "locality": lambda: locality,
            "min_length": lambda: min_length,
            "standard_derivation_treshold": lambda: min_derivation,
            "ping": lambda: True,
            "report_got": lambda: len(mesh.vertices)>50000,
        }
        
        def error_cmd(args):
            raise Exception(args[0])
        
        def rest_cmd(args):
            print("waiting for results...")
            process_wait(True)
            waiting[0]=True
        
        results=[([],[])]
        def feed_results_cmd(args):
            process_wait(False)
            waiting[0]=False
            
            size=int(args[0])
            index, weights=[0]*size, [0.0]*size
            
            for i in range(size):
                index[i]=int(read_until(";"))
                weights[i]=float(read_until(";"))
            
            print("Got", size,"results")
            results[0]=(index, weights)
            
        
        commands={
            "mesh.cordinates": lambda args: signal_file(wait_n_get(co_fil)),
            "mesh.edge_index": lambda args: signal_file(wait_n_get(ed_fil)),
            "log": lambda args: print("Worker:",args[0]),
            "error": error_cmd,
            "rest": rest_cmd,
            "feed-results": feed_results_cmd
        }
        
        while proc.poll()==None:
            stdin.flush()
            stdout.flush()
            
            command_name, args=read_command()
            # print(command_name+"("+(", ".join(args))+")")
            
            if command_name in response_values:
                val=response_values[command_name]()
                if type(val)==bool:val=1 if val else 0
                send_message(val)
                continue
            
            if command_name in commands:
                commands[command_name](args)
                continue
            
            if command_name=="kill":
                return results[0]
            
            raise Exception("Unknown request: "+ command_name+"("+(", ".join(args))+")")
        
        
    finally:
        if waiting[0]:
            process_wait(False)
        
        if proc.poll()==None:
            proc.kill()

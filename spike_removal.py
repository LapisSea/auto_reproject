
import bpy
from .import_properties import *
from . import utils
import numpy as np
import threading
import time

def normalize(dataset):
    data_size=len(dataset)
    
    if data_size<=1:
        return [1]*data_size
    
    min_val=float("inf")
    max_val=0
    
    for avg_dist in dataset:
        if min_val>avg_dist:
            min_val=avg_dist
        if max_val<avg_dist:
            max_val=avg_dist
    
    value_range=max_val-min_val
    
    if value_range<0.000001:
        return [0]*data_size
    
    return [(avg_dist-min_val)/value_range for avg_dist in dataset]

def compute_local_index(edge_data, vertex_index, locality):
    vertex_to_edge_index, edge_lr=edge_data
    
    vertex_ids=set()
    vertex_ids.add(vertex_index)
    
    index_set=set()
    
    for _ in range(locality):
        ids=[]
        for vt_id in vertex_ids:
            for edge_index in vertex_to_edge_index[vt_id]:
                
                if edge_index in index_set:
                    continue
                index_set.add(edge_index)
                
                def add(new_id):
                    if new_id!=vt_id:
                        ids.append(new_id)
                
                lr=edge_lr[edge_index]
                add(lr[0])
                add(lr[1])
        
        vertex_ids.update(ids)
    
    return list(vertex_ids)


def compute_vertex_to_edge_index(mesh):
    index=tuple([] for i in range(len(mesh.vertices)))
    edge_lr=tuple([0,0] for i in range(len(mesh.edges)))
    
    for i, edge in enumerate(mesh.edges):
        lr=edge_lr[i]
        lr[0]=edge.vertices[0]
        lr[1]=edge.vertices[1]
        index[lr[0]].append(i)
        index[lr[1]].append(i)
    
    return (index, edge_lr)

def compute_avarage_vertex_edge_lengths_index_iter(mesh, edge_data):
    vertex_to_edge_index, edge_lr=edge_data
    
    verts=mesh.vertices
    
    dataset=[0.0]*len(vertex_to_edge_index)
    
    for i, index in enumerate(vertex_to_edge_index):
        val_sum=0
        for edge_index in index:
            lr=edge_lr[edge_index]
            val_sum+=(verts[lr[0]].co-verts[lr[1]].co).length
        
        dataset[i]=val_sum/len(index)
    
    return dataset

def compute_avarage_vertex_edge_lengths_self_acum(mesh):
    verts=mesh.vertices
    
    dataset_acum=[[0, 0.0] for i in range(len(verts))]
    
    def log_length(index, le):
        log=dataset_acum[index]
        log[0]+=1
        log[1]+=le
    
    for edge in mesh.edges:
        v0=verts[edge.vertices[0]]
        v1=verts[edge.vertices[1]]
        
        le=(v0.co-v1.co).length
        
        log_length(v0.index, le)
        log_length(v1.index, le)
    
    return [c[1]/c[0] for c in dataset_acum]


def generate_positive_outlier_index(data, standard_derivation_threshold):
    
    mean = np.mean(data)
    std =np.std(data)
    
    if std<0.000001:
        return
    
    for i, y in enumerate(data):
        z_score= (y - mean)/std 
        
        if z_score > standard_derivation_threshold:
            yield i

def analyse_mesh_local_impl(mesh, locality, treshold, process_wait):
    lock = threading.Lock()
    
    inverse_treshold=1-treshold
    
    index_weight=([], [])
    
    def push_raw_dataset(dataset, index_unapper, consume):
        for index in generate_positive_outlier_index(dataset, 5*inverse_treshold):
            consume((index_unapper(index), dataset[index]))
    
    def push_result(data):
        lock.acquire()
        try:
            index_weight[0].append(data[0])
            index_weight[1].append(data[1])
        finally:
            lock.release()
    
    if locality==0:
        print("Computing global avarage edge lengths")
        dataset=compute_avarage_vertex_edge_lengths_self_acum(mesh)
        
        push_raw_dataset(dataset, lambda local_i: local_i, push_result)
    else:
        print("Computing vertex to edge relations")
        
        edge_data=compute_vertex_to_edge_index(mesh)
        vertex_to_edge_index, edge_lr=edge_data
        
        print("Computing avarage edge lengths")
        global_dataset=compute_avarage_vertex_edge_lengths_index_iter(mesh, edge_data)
        
        print("Computing standard derivation")
        
        def get_ms(): return int(round(time.time() * 1000))
        
        millis = [get_ms()]
        
        start_tim = int(millis[0])
        
        vt_len=len(vertex_to_edge_index)
        counter=[0]
        def increment():
            lock.acquire()
            try:
                counter[0]+=1
                val=counter[0]/vt_len
                tim=get_ms()
                diff=tim-millis[0]
                if diff>1000:
                    millis[0]=tim
                    spent_time=tim-start_tim
                    
                    total_time=spent_time/val
                    ms=int(total_time-spent_time)
                    sec=int(ms/1000)
                    ms-=sec*1000
                    minute=int(sec/60)
                    sec-=minute*60
                    print(str(round(val*100,2))+"% remaining: "+str(minute)+":"+str(sec)+":"+str(ms))
            finally:
                lock.release()
        
        def process(vertex_index):
            increment()
            
            local_index=compute_local_index(edge_data, vertex_index, locality)
            
            local_dataset=[global_dataset[index] for index in local_index]
            
            weight=[-1]
            
            def eat(val):
                if val[0]==vertex_index:
                    weight[0]=val[1]
            
            push_raw_dataset(local_dataset, lambda local_i: local_index[local_i], eat)
            
            if weight[0]>=0:
                push_result((vertex_index, weight[0]))
            
        
        thread_num=min(10, int(vt_len/500))
        
        if thread_num<=1:
            for i in range(vt_len):
                process(i)
        else:
            def prod(start,end):
                for i in range(start,end):
                    process(i)
            
            threads = []
            last=0
            step=int(vt_len/thread_num)-1
            for i in range(thread_num-1):
                start=last
                end=start+step
                last+=step
                threads.append(threading.Thread(name="Prod %d" % i, target=prod, args=(start,end)))
            
            threads.append(threading.Thread(name="Prod %d" % thread_num, target=prod, args=(last, vt_len)))
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
    
    normalize(index_weight[1])
    
    return index_weight


def analyse_mesh_CPP_impl(mesh, locality, treshold, process_wait):
    import subprocess, os, io
    
    def gen_writer(args, output):
        dims=-1
        
        for val in args:
            if val.startswith("dim="):
                dims=int(val[4:])
                break
        
        if dims==-1:
            raise Exception("Unknown dimensions "+str(args))
        
        
        if "human" in args:
            
            if dims>1:
                def vector_writer(vec):
                    if len(vec)!=dims:
                         raise Exception("incorrect vector size "+str(vec)) 
                    
                    for val in vec:
                        output.write(str(val)+os.linesep)
                return vector_writer
            
            if dims==1:
                return lambda val: output.write(str(val)+os.linesep)
            
        elif "binary" in args:
            if "BE" in args:
                raise Exception("Big endian not supported "+str(args))
            
            byte_count=-1
            for val in args:
                if val.startswith("bytes="):
                    byte_count=int(val[6:])
                    break
            
            if byte_count==-1:
                raise Exception("No byte count defined "+str(args))
            
            if byte_count!=4:
                raise Exception("Unsupported byte count "+str(args))
            
            import struct
            
            converter=None
            if "int" in args:
                converter=lambda i:struct.pack('!i', i)
            elif "float" in args:
                converter=lambda i:struct.pack('!f', i)
            else:
                raise Exception("No type "+str(args))
            
            if dims>1:
                def vector_writer(vec):
                    if len(vec)!=dims:
                         raise Exception("incorrect vector size "+str(vec)) 
                    
                    for val in vec:
                        output.write(converter(val))
                return vector_writer
            
            if dims==1:
                return lambda val: output.write(converter(val))
            
        
        raise Exception("Unknown args "+str(args))
    
    dir_path = os.path.dirname(os.path.realpath(__file__))
    local_path='SpikeDetector/bin/x64/SpikeDetector/SpikeDetector.exe'
    
    human_mode=True
    
    proc = subprocess.Popen(local_path, encoding="utf8" if human_mode else None, stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=False)
    try:
        stdout = proc.stdout
        stdin = proc.stdin
        
        def send(data):
            val=str(data)+os.linesep
            if not human_mode:
                val=val.encode("utf8")
            stdin.write(val)
        
        def read_until(delimiter):
            word=""
            while True:
                if proc.poll():
                    return word
                
                char = stdout.read(1)
                if not human_mode:
                    char=char.decode("utf8")
                if char == delimiter:
                    return word
                word+=char
                # print(word)
        
        
        
        while not proc.poll():
            stdin.flush()
            
            what=read_until(" ")
            args=[]
            while True:
                arg=read_until(";")
                if arg=="":
                    break
                args.append(arg)
                
            # print(what, args)
            
            
            if what=="mesh.cordinates":
                send(len(mesh.vertices))
                
                writer=gen_writer(args, proc.stdin)
                for vertex in mesh.vertices:
                    writer(vertex.co)
                
                continue
            
            if what=="mesh.edge_index":
                send(len(mesh.edges))
                
                writer=gen_writer(args, proc.stdin)
                for edge in mesh.edges:
                    writer(edge.vertices)
                
                continue
            
            if what=="locality":
                send(locality)
                continue
            
            if what=="standard_derivation_treshold":
                send(1+(1-treshold)*5)
                continue
            
            if what=="log":
                print("Worker:",args[0])
                continue
            
            if what=="report_got":
                send(1 if len(mesh.vertices)>50000 else 0)
                continue
            
            if what=="human_mode":
                send(1 if human_mode else 0)
                continue
            
            if what=="error":
                raise Exception(args[0])
            
            if what=="rest":
                print("waiting for results...")
                process_wait(True)
                continue
            
            if what=="feed-results":
                process_wait(False)
                
                size=int(args[0])
                index, weights=[0]*size, [0.0]*size
                
                for i in range(size):
                    index[i]=int(read_until(";"))
                    weights[i]=float(read_until(";"))
                
                return (index, weights)
            
            # print("Unknown request", what, args)
            
            raise Exception("Unknown request", what, args)
        
        
    finally:
        proc.kill()

def analyse_mesh(mesh, locality, treshold,process_wait):
    try:
        return analyse_mesh_CPP_impl(mesh, locality, treshold,process_wait)
    except Exception as e:
        print(e)
        import traceback
        traceback.print_exc()
        
        return analyse_mesh_local_impl(mesh, locality, treshold,process_wait)
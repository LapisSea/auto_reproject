
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
                    if new_id!=vt_id and new_id:
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
    

def analyse_mesh(mesh, locality, treshold):
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
import bpy
from . import utils
from .Config import (scan_step_problems,scan_preserve_problems)
from .import_properties import *

def redraw():
    op=bpy.ops.wm.redraw_timer
    if op.poll():
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    else:
        print("da fuk")

class AMR_OT_Reproject(bpy.types.Operator):
    bl_idname = "amr.reproject"
    bl_label = "Reproject"
    bl_description = "Reproject this mesh to the targets"
    bl_options = {"REGISTER", 'UNDO', "INTERNAL"}
    
    @classmethod
    def poll(self, context):
        obj, config = utils.get_context_common(context)
        if obj == None:
            return False
        
        return sum(1 for t in config.targets if t.obj!=None) > 0 and len(scan_step_problems(config.steps))==0

    def execute(self, context):
        
        change_ar=[False]
        
        def change(ch):
            ch=bool(ch)
            if not ch:
                return ch
            
            if change_ar[0]:
                return ch
            
            change_ar[0]=True
            print("Projecting...")
            return ch
        
        obj, config = utils.get_context_common(context)
        config.run_pos=-1
        
        def progress(p):
            config.progress=p*100
        
        for o in bpy.data.objects:
            if o.type!="EMPTY" or not o.name.startswith("_DEBUG"):
                continue
            change(True)
            bpy.data.objects.remove(o)
        
        
        vtg=[]
        
        def get_boundy():
            if vtg:
                return vtg[0].name
            
            group=obj.vertex_groups.new(name="EDGE_MASK")
            vtg.append(group)
            
            me = bpy.context.object.data
            
            index=None
            
            import bmesh
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                
                index=[v.index for v in bm.verts if v.is_boundary]
                
            except:
                pass
            finally:
                bm.free() 
            
            group.add(index, 1, "REPLACE")
            
            return get_boundy()
        
        try:
            if bpy.context.object.mode!="OBJECT":
                bpy.ops.object.mode_set(mode='OBJECT')
                change(True)
            
            mods=obj.modifiers
            
            multires=[None]
            
            for mod in mods:
                if mod.type=="MULTIRES":
                    multires[0]=mod
                    break
            if multires[0]==None:
                multires[0]=mods.new("Multires", "MULTIRES")
                redraw()
            
            def apply_modifier(name):
                bpy.ops.object.modifier_apply(modifier=name, report=True)
            
            def delete_higher():
                change(True)
                print(multires[0].total_levels,"downsampled to", multires[0].levels)
                bpy.ops.object.multires_higher_levels_delete(modifier=multires[0].name)
                redraw()
            
            
            disable_preserve_old=config.force_change
            if config.force_change:
                config.force_change=False
            
            force=disable_preserve_old or len(scan_preserve_problems(config))>0
            
            prediced_levels=config.repeater.choose_level(obj, config, multires[0])
            
            if config.preserve_old and not force:
                if multires[0].total_levels>prediced_levels:
                    multires[0].levels=prediced_levels
                    delete_higher()
                    
                multires[0].levels=multires[0].total_levels
            else:
                multires[0].levels=0
                delete_higher()
                multires[0].subdivision_type=config.subdivision_type

            
            def run_step(step):
                
                if step.typ=="NAN":
                    return
                
                if step.typ=="SUB":
                    bpy.ops.object.multires_subdivide(modifier=multires[0].name, mode=config.subdivision_type)
                    return
                
                if step.typ=="APB":
                    bpy.ops.object.multires_base_apply(modifier=multires[0].name)
                    return
                
                def shrink(wrap_method):
                    proj=mods.new("Shrinkwrap", "SHRINKWRAP")
                    try:
                        proj.show_viewport=False
                        proj.use_positive_direction=True
                        proj.use_negative_direction=True
                        proj.wrap_method=wrap_method
                        proj.target=config.targets[0].obj
                        
                        if step.pin_boundary:
                            proj.invert_vertex_group=True
                            proj.vertex_group=get_boundy()
                        
                        apply_modifier(proj.name)
                    except Exception as e:
                        mods.remove(proj)
                        print(e)
                        
                
                if step.typ=="PRO":
                    shrink("PROJECT")
                    return
                
                if step.typ=="ATT":
                    shrink("NEAREST_SURFACEPOINT")
                    return
                
                def smooth_mod(o, vertex_group, invert):
                    mods=o.modifiers
                    proj=mods.new("Smooth", "SMOOTH")
                    try:
                        proj.show_viewport=False
                        proj.factor=step.smo_strength
                        proj.iterations=step.smo_iter
                        
                        if vertex_group!=None:
                            proj.invert_vertex_group=invert
                            proj.vertex_group=vertex_group
                        
                        apply_modifier(proj.name)
                    except Exception as e:
                        mods.remove(proj)
                        print(e)
                
                if step.typ=="SMO":
                    smooth_mod(obj, get_boundy() if step.pin_boundary else None, True)
                    return
                
                if step.typ=="FIX":
                    if step.smo_iter==0 or step.smo_strength==0:
                        return
                    
                    from . import spike_removal
                    
                    mesh=utils.get_evaluated_mesh(obj)
                    
                    def rest(resting):
                        multires[0].show_viewport=not resting
                    
                    spike_weight=spike_removal.analyse_mesh(mesh, step.fix_locality, step.fix_tolerance, step.fix_min_len, rest)
                    
                    if len(spike_weight[0])==0:
                        return
                        
                    print("Applying smoothing to detected spikes")
                    
                    old_levels=multires[0].total_levels
                    
                    # old_points=[]
                    
                    # if step.fix_debug>0:
                    #     mesh=utils.get_evaluated_mesh(obj)
                        
                    #     for i in spike_weight[0]:
                    #         old_points.append(mesh.vertices[i].co)
                        
                    
                    copy_obj=obj.copy()
                    copy_obj.data = obj.data.copy()
                    
                    obj.users_collection[0].objects.link(copy_obj)
                    
                    bpy.ops.object.select_all(action='DESELECT')
                    
                    
                    copy_obj.select_set(True)
                    bpy.context.view_layer.objects.active = copy_obj
                    
                    
                    bpy.ops.object.convert(target="MESH")
                    
                    try:
                        
                        if step.fix_debug>0:
                            mesh=copy_obj.data
                            
                            for i, w in zip(spike_weight[0], spike_weight[1]):
                                co=mesh.vertices[i].co
                                
                                o=bpy.data.objects.new("_DEBUG", None)
                                
                                bpy.data.collections[0].objects.link(o)
                                
                                o.location=copy_obj.matrix_world@co
                                
                                o.scale*=w*step.fix_debug
                                
                                o.empty_display_type="SPHERE"
                        
                        group=copy_obj.vertex_groups.new(name="SPIKE_MASK")
                        
                        for i, w in zip(spike_weight[0], spike_weight[1]):
                            group.add([i], w, "REPLACE")
                        
                        try:
                            smooth_mod(copy_obj, group.name, False)
                        finally:
                            copy_obj.vertex_groups.remove(group)
                        
                    finally:
                        
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = obj
                        
                        bpy.ops.object.multires_reshape(modifier=multires[0].name)
                        
                        d=copy_obj.data
                        bpy.data.objects.remove(copy_obj)
                        bpy.data.meshes.remove(d)
                    
                    return
                
                raise Exception("Unimplemneted action: "+step.typ)
            
            
            def filtered(lis):
                return [e for e in lis if e.typ!="NAN"]
                
            steps_pre=filtered(config.steps_pre)
            steps=filtered(config.steps)
            steps_post=filtered(config.steps_post)
            
            total=max(1, len(steps_pre)+len(steps)*prediced_levels+len(steps_post))
            count=[0]
            
            if multires[0].levels==0:
                count[0]+=len(steps_pre)
            
            count[0]+=len(steps)*multires[0].levels
            
            def run_steps(lis, start):
                for i, step in enumerate(lis):
                    count[0]+=1
                    progress(count[0]/total)
                    run_step(step)
                    config.run_pos=start+i+1
                    redraw()
            
            
            
            if multires[0].levels==0 and change(steps_pre):
                print("PRE")
                run_steps(steps_pre, 0)
            
            if config.repeater.should_repeat(obj, config, multires[0]):
                print("REPEAT")
                change(steps)
                
                while config.repeater.should_repeat(obj, config, multires[0]):
                    run_steps(steps, len(steps_pre))
            
            if change(steps_post):
                print("POST")
                run_steps(steps_post, len(steps_pre)+len(steps))
            
            
            if not change_ar[0]:
                return {"CANCELLED"}
            
            progress(1)
            
            return {"FINISHED"}
            
        finally:
            config.run_pos=-1
            if vtg:
                obj.vertex_groups.remove(vtg[0])
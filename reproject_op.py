import bpy
from . import utils
from .Config import (scan_step_problems,scan_preserve_problems)
from .import_properties import *

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
        obj, config = utils.get_context_common(context)
        
        print("Projecting...")
        
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
            
            mods=obj.modifiers
            
            multires=None
            for mod in mods:
                if mod.type=="MULTIRES":
                    multires=mod
                    break
            if multires==None:
                multires=mods.new("Multires", "MULTIRES")
            
            
            def delete_higher():
                bpy.ops.object.multires_higher_levels_delete(modifier=multires.name)
            len(config.steps_post)>0
            
            disable_preserve_old=config.force_change
            if config.force_change:
                config.force_change=False
            
            force=disable_preserve_old or len(scan_preserve_problems(config))>0
            
            if config.preserve_old and not force:
                level=config.repeater.choose_level(obj, config, multires)
                if multires.total_levels>level:
                    multires.levels=level
                    delete_higher()
                    
                multires.levels=multires.total_levels
            else:
                multires.levels=0
                delete_higher()
                multires.subdivision_type=config.subdivision_type
            
            
            def run_steps(lis):
                for step in lis:
                    if step.typ=="NAN":
                        continue
                    
                    if step.typ=="SUB":
                        bpy.ops.object.multires_subdivide(modifier=multires.name, mode=config.subdivision_type)
                        continue
                    
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
                            
                            bpy.ops.object.modifier_apply(apply_as='DATA', modifier=proj.name, report=False)
                        except Exception as e:
                            mods.remove(proj)
                            print(e)
                            
                    
                    if step.typ=="PRO":
                        shrink("PROJECT")
                        continue
                    
                    if step.typ=="ATT":
                        shrink("NEAREST_SURFACEPOINT")
                        continue
                    
                    if step.typ=="SMO":
                        proj=mods.new("Smooth", "SMOOTH")
                        try:
                            proj.show_viewport=False
                            proj.factor=step.smo_strength
                            proj.iterations=step.smo_iter
                            
                            if step.pin_boundary:
                                proj.invert_vertex_group=True
                                proj.vertex_group=get_boundy()
                            
                            bpy.ops.object.modifier_apply(apply_as='DATA', modifier=proj.name, report=False)
                        except Exception as e:
                            mods.remove(proj)
                            print(e)
                        continue
                    
                    if step.typ=="FIX":
                        print("SPIKE REMOVAL NOT IMPLEMENTED")
                        continue
                    
                    raise Exception("Unimplemneted action: "+step.typ)
            
            if multires.levels==0:
                print("PRE")
                run_steps(config.steps_pre)
            
            print("REPEAT")
            
            while config.repeater.should_repeat(obj, config, multires):
                run_steps(config.steps)
            
            print("POST")
            run_steps(config.steps_post)
            
            return {"FINISHED"}
            
        except Exception as e:
            print(e)
        finally:
            if vtg:
                obj.vertex_groups.remove(vtg[0])
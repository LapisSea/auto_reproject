import bpy
from . import utils
from .Config import (scan_step_problems, scan_preserve_problems)

class AMR_PT_Panel(bpy.types.Panel):
    bl_idname = "AMR_OPS_PT_PANEL"
    bl_label = "Reproject"
    bl_category = "Reproject"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        obj, config = utils.get_context_common(context)
        
        if obj == None:
            layout = layout.box()
            layout = layout.column(align=False)
            layout.label(text="Select Low Resolution")
            layout.label(text="mesh to reproject to!")
            return
        
        layout.label(text="Auto Reproject settings")
        
        
        
        b = layout.box()
        b = b.column(align=False)
        b.label(text="Subdivision:")
        b.prop(config, "subdivision_type", text="")
        
        r = b.column(align=True)
        r.label(text="Repeat mode:")
        # r = r.row(align=True)
        r.prop(config.repeater, "typ", text="")
        config.repeater.display_values(r)
        
        
        b = layout.box()
        b = b.column(align=False)
        
        targets = config.targets
        b.label(text="Targets:")
        
        r = b.column_flow(columns=1, align=True)
        
        for i, ptr in enumerate(targets):
            r.prop(ptr, "obj", text="Target "+str(i+1))
        
        
        if len(targets) == 1:
            b.label(text="Select target(s) to reproject from!", icon="ERROR")
        
        pos=[0]
        
        def step_list(lis, title):
            b = layout.box()
            b = b.column(align=False)
            
            b.label(text=title)

            r = b.column_flow(columns=1, align=True)
            
            for i, step in enumerate(lis):
                is_nan=step.typ=="NAN"
                
                current=False
                if not is_nan:
                    current=config.run_pos==pos[0]
                    
                    pos[0]+=1
                
                column = r
                if current:
                    column=column.column()
                    column.alert=True
                
                txt="" if is_nan else "Step "+str(i+1)
                
                if step.has_values():
                    column = column.column(align=False)
                    column.prop(step, "typ", text=txt)
                    step.display_values(column)
                else:
                    column.prop(step, "typ", text=txt)
            
            
            return b
        
        step_list(config.steps_pre, "Start Steps:")
        
        b=step_list(config.steps, "Repeating Steps:")
        
        for problem in scan_step_problems(config.steps):
            b.label(text=problem, icon="ERROR")
        
        step_list(config.steps_post, "End Steps:")
        
        problems=scan_preserve_problems(config)
        
        if len(problems)>0:
            ro = layout.box()
            
            ro.prop(config, "preserve_old")
            
            for problem in problems:
                ro.label(text=problem, icon="ERROR")
        else:
            layout.prop(config, "preserve_old")
        
        col = layout.row(align=True)
        col.prop(config, "progress")
        col.scale_x=0.6
        col.scale_y=0.6
        col.enabled=False
        
        col = layout.row(align=True)
        col.prop(config, "auto_update", text="", icon="SNAP_ON" if config.auto_update else "SNAP_OFF")
        col.operator("amr.reproject")


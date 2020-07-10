
import bpy
from .import_properties import *
from . import utils
from .depsgraph import onDepsgraph


def update(scene=None):
    obj = utils.get_active_obj(bpy.context)
    if obj == None:
        return
    
    config = obj.amr_settings
    
    if not config.inited:
        config.inited=True
        
        steps=config.steps
        steps.add()
        steps.add()
        
        steps[0].typ="SUB"
        steps[1].typ="PRO"
    
    def manage_list(lis, is_empty):
        
        if not lis:
            lis.add()
            return
        
        le = len(lis)
        for i, element in enumerate(lis):
            if i+1 < le:
                if is_empty(element):
                    lis.remove(i)
            else:
                if not is_empty(element):
                    lis.add()
    
    objs=[]
    for ptr in config.targets:
        if ptr.obj==obj:
            ptr.obj=None
            continue
        
        if ptr.obj in objs:
            ptr.obj=None
            continue
        else:
            objs.append(ptr.obj)
    
    def is_nan(step):
        return step.typ=="NAN"
    
    manage_list(config.targets, lambda ptr: ptr.obj==None)
    manage_list(config.steps_pre, is_nan)
    manage_list(config.steps, is_nan)
    manage_list(config.steps_post, is_nan)


onDepsgraph(update)

def _on_change(self, context, disable):
    update()
    
    obj = utils.get_active_obj(context)
    if not obj.amr_settings.auto_update:
        return
    
    op=bpy.ops.amr.reproject
    if op.poll():
        op(disable_preserve_old=disable)

def on_change(self, context):
    _on_change(self,context, False)

def on_change_force(self, context):
    _on_change(self,context, True)

class ObjPtr(PropertyGroup):
    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        update=on_change
    )

def scan_step_problems(steps):
    no_subdiv=True
    no_projection=True
    no_steps=True
    
    for step in steps:
        if step.typ=="NAN":
            continue
        
        no_steps=False
        
        if step.typ=="SUB":
            no_subdiv=False
            continue
        
        if step.typ in ("PRO", "ATT"):
            no_projection=False
            continue
    
    if no_steps:
        return ["No steps!"]
    
    problems=[]
    
    if no_subdiv:
        problems.append("No subdivision in steps!")
    
    if no_projection:
        problems.append("No projection in steps!")
    
    return problems

def scan_preserve_problems(config):
    if sum(1 for step in config.steps_post if step.typ!="NAN")>0:
        return ["Preserve not compatabile with post steps"]
    return []


def display_SMO(self, layout):
    lay=layout.row(align=True)
    lay.prop(self,"smo_strength")
    lay.prop(self,"smo_iter")
    layout.prop(self,"pin_boundary")

step_values={
    "SMO": display_SMO,
    # "PRO": display_PRO,
    # "ATT": display_ATT,
}

class Step(PropertyGroup):
    typ: EnumProperty(items=[
        ("NAN", "<No step>", "This represents no step and if at the end will go back to the first step until done"),
        ("SUB", "Subdivide", "Subdivide step"),
        ("PRO", "Project", "Project step"),
        ("ATT", "Attract", "Snap to closest point step"),
        ("SMO", "Smooth", "Smooth step"),
    ], default="NAN", update=on_change_force)
    
    smo_strength: FloatProperty(default=0.5, min=0,soft_max=1, description="Strength of smoothing", name="Strength", update=on_change_force)
    smo_iter: IntProperty(default=1, min=0, description="Number of how many times smoothing repeats", name="Repeats", update=on_change_force)
    
    pin_boundary: BoolProperty(default=False, name="Pin boundary", update=on_change_force)
    
    def has_values(self):
        return self.typ in step_values
        
    def display_values(self, layout):
        step_values[self.typ](self, layout)
        

def get_object_vertex_count(obj):
    return len(obj.evaluated_get(depsgraph=bpy.context.evaluated_depsgraph_get()).data.vertices)

class RepeatMode(PropertyGroup):
    typ: EnumProperty(items=[
        ("NUM", "Fixed number", "Repeat steps a fixed number of times"),
        ("VTC", "Vertex target", "Repeat steps until vertex count becomes more or eual than value"),
        ("CPY", "Vertex count copy", "Repeat steps until vertex count becomes more or eual to target vertex count times multiplier"),
    ], default="NUM", update=on_change)
    
    subdivision_levels: IntProperty(default=3, min=0, soft_max=6, max=255, name="Levels", update=on_change)
    
    vertex_target: IntProperty(default=10000, min=1, name="Target count", update=on_change)
    
    targert_multiplier: FloatProperty(default=0.9, min=0, soft_max=1, name="Multiplier", update=on_change)
    
    def display_values(self, layout):
        layout.prop(self, {
            "NUM": "subdivision_levels",
            "VTC": "vertex_target",
            "CPY": "targert_multiplier",
        }[self.typ])
    
    def calc_target_vertex_sum(self, config):
       return sum( get_object_vertex_count(ptr.obj) for ptr in config.targets if ptr.obj!=None)
    
    def should_repeat(self, obj, config, multires):
        
        get_object_vertex_count(obj)
        
        def count_greater(target):
            count= get_object_vertex_count(obj)
            return target>=count
        
        return {
            "NUM": (lambda: multires.levels<self.subdivision_levels),
            "VTC": (lambda: count_greater(self.vertex_target)),
            "CPY": (lambda: count_greater(self.calc_target_vertex_sum(config)*self.targert_multiplier)),
        }[self.typ]()
    
    def choose_level(self, obj, config, multires):
        
        def downsample(target):
            print(target)
            levels=multires.total_levels
            
            count=get_object_vertex_count(obj)
            
            while count/3.2>=target and levels>0:
                count/=3.2
                levels-=1
            
            return levels
        
        return {
            "NUM": (lambda: self.subdivision_levels),
            "VTC": (lambda: downsample(self.vertex_target)),
            "CPY": (lambda: downsample(self.calc_target_vertex_sum(config)*self.targert_multiplier)),
        }[self.typ]()


class Config(PropertyGroup):
    targets: CollectionProperty(type=ObjPtr)
    
    steps_pre: CollectionProperty(type=Step)
    steps: CollectionProperty(type=Step)
    steps_post: CollectionProperty(type=Step)
    
    subdivision_type: EnumProperty(items=[
        ("CATMULL_CLARK", "Smooth", "Use smooth subdivisons"),
        ("SIMPLE", "Simple", "Use flat subdivisons"),
    ], default="CATMULL_CLARK", update=on_change)
    
    preserve_old: BoolProperty(default=True, name="Preserve old", description="Do not delete existing multiresolution data (repoject from base every time)")
    
    auto_update: BoolProperty(default=True, name="Auto Update")
    
    inited: BoolProperty(default=False)
    
    repeater: PointerProperty(type=RepeatMode)

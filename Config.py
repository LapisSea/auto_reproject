
import bpy
from .import_properties import *
from . import utils
from .depsgraph import onDepsgraph


def update(scene=None):
    obj, config = utils.get_context_common(bpy.context)
    if obj == None:
        return
    
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

def _on_change(self, context):
    update()
    
    obj, config = utils.get_context_common(context)
    if not config.auto_update:
        return
    
    op=bpy.ops.amr.reproject
    if op.poll():
        op()

def on_change(self, context):
    _on_change(self,context)

def on_change_force(self, context):
    obj, config = utils.get_context_common(context)
    config.force_change=True
    _on_change(self,context)

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
    problems=[]
    if not config.preserve_old:
        return problems
    
    if sum(1 for step in config.steps_post if step.typ!="NAN")>0:
        problems.append("Preserve not compatabile with post steps")
    elif config.force_change:
        problems.append("Outdated data")
    
    return problems


def display_SMO(self, layout):
    lay=layout.row(align=True)
    lay.prop(self,"smo_strength")
    lay.prop(self,"smo_iter")
    layout.prop(self,"pin_boundary")

def display_PRO(self, layout):
    layout.prop(self,"pro_distance")

def display_FIX(self, layout):
    layout.prop(self,"fix_repeat")
    
    layout.prop(self,"fix_tolerance")
    layout.prop(self,"fix_locality")
    if self.fix_locality>0:
        layout.prop(self,"fix_min_len")
    layout.prop(self,"fix_debug")
    
    
    layout.label(text="Spike smoothing:")
    lay=layout.row(align=True)
    lay.prop(self,"smo_strength")
    lay.prop(self,"smo_iter")
    
    

step_values={
    "SMO": display_SMO,
    "PRO": display_PRO,
    "FIX": display_FIX,
}

class Step(PropertyGroup):
    typ: EnumProperty(items=[
        ("NAN", "<No step>", "This represents no step and if at the end will go back to the first step until done"),
        ("SUB", "Subdivide", "Subdivide step"),
        ("PRO", "Project", "Project step"),
        ("ATT", "Attract", "Snap to closest point step"),
        ("SMO", "Smooth", "Smooth step"),
        ("FIX", "Remove Spikes (SLOW)", "Remove spikes step. (use statistical edge analisys to mask and smooth points that create spikes)"),
        ("APB", "Apply Base", "Applies shape to base mesh"),
    ], default="NAN", update=on_change_force)
    
    smo_strength: FloatProperty(default=0.5, min=0,soft_max=1, description="Strength of smoothing", name="Strength", update=on_change_force)
    smo_iter: IntProperty(default=1, min=0, description="Number of how many times smoothing repeats", name="Repeats", update=on_change_force)
    
    pin_boundary: BoolProperty(default=False, name="Pin boundary", update=on_change_force)
    
    pro_distance: FloatProperty(default=0, min=0, step=0.03, unit="LENGTH", description="Maximum projection distance, 0 = no maximum (prevent spikes)", name="Max Distance", update=on_change_force)
    
    fix_tolerance: FloatProperty(default=0.1, subtype="FACTOR", min=0, max=1, step=0.05, description="Spike detection tolerance. (0 = the single most spiky vertex, 1 = everything is a spike)", name="Detection tolerance", update=on_change_force)
    
    fix_locality: IntProperty(default=0, min=0, description="If greater than 0 spike detection algorythm switches to localized spike detection mode. (useful for mesh of warying topology densities) If this value is for example 3, then examined area for a vertex is similar to selecting that vertex and using \"select more\" operator 3 times.", name="Detection locality", update=on_change_force)
    
    fix_debug: FloatProperty(default=0,min=0, name="Spike debug scale", update=on_change_force)
    
    fix_min_len: FloatProperty(default=0,min=0, step=0.01, unit="LENGTH", name="Minimum edge length",description="This value represents the minimum edge length for being examed as a potential spike. (WARNING: small spikes may get ignored!)", update=on_change_force)
    
    fix_repeat: IntProperty(default=1,min=1, name="Step Repeat", update=on_change_force)
    
    def has_values(self):
        return self.typ in step_values
        
    def display_values(self, layout):
        step_values[self.typ](self, layout)
        

def get_object_polygon_count(obj):
    return len(utils.get_evaluated_mesh(obj).polygons)

class RepeatMode(PropertyGroup):
    typ: EnumProperty(items=[
        ("NUM", "Fixed number", "Repeat steps a fixed number of times"),
        ("VTC", "Polygon target", "Repeat steps until polygon count becomes more or eual than value"),
        ("CPY", "Polygon count copy", "Repeat steps until polygon count becomes more or eual to target polygon count times multiplier"),
    ], default="CPY", update=on_change)
    
    subdivision_levels: IntProperty(default=3, min=0, soft_max=6, max=255, name="Levels", update=on_change)
    
    polygon_target: IntProperty(default=10000, min=1, name="Min target count", update=on_change)
    
    targert_multiplier: FloatProperty(default=0.5, subtype="FACTOR", min=0, soft_max=1, name="Multiplier", update=on_change)
    
    def display_values(self, layout):
        layout.prop(self, {
            "NUM": "subdivision_levels",
            "VTC": "polygon_target",
            "CPY": "targert_multiplier",
        }[self.typ])
    
    def calc_target_polygon_sum(self, config):
       return sum( get_object_polygon_count(ptr.obj) for ptr in config.targets if ptr.obj!=None)
    
    def should_repeat(self, obj, config, multires):
        
        get_object_polygon_count(obj)
        
        def count_greater(target):
            count= get_object_polygon_count(obj)
            return target>count
        
        return {
            "NUM": (lambda: multires.levels<self.subdivision_levels),
            "VTC": (lambda: count_greater(self.polygon_target)),
            "CPY": (lambda: count_greater(self.calc_target_polygon_sum(config)*self.targert_multiplier)),
        }[self.typ]()
    
    def choose_level(self, obj, config, multires):
        
        def downsample(target):
            levels=multires.total_levels
            
            count=get_object_polygon_count(obj)
            
            while count<target:
                count*=4
                levels+=1
            
            while count/4>=target and levels>0:
                count/=4
                levels-=1
            
            return levels
        
        return {
            "NUM": (lambda: self.subdivision_levels),
            "VTC": (lambda: downsample(self.polygon_target)),
            "CPY": (lambda: downsample(self.calc_target_polygon_sum(config)*self.targert_multiplier)),
        }[self.typ]()


class Config(PropertyGroup):
    targets: CollectionProperty(type=ObjPtr)
    
    steps_pre: CollectionProperty(type=Step)
    steps: CollectionProperty(type=Step)
    steps_post: CollectionProperty(type=Step)
    
    subdivision_type: EnumProperty(items=[
        ("CATMULL_CLARK", "Smooth", "Use smooth subdivisons"),
        ("SIMPLE", "Simple", "Use flat subdivisons"),
    ], default="CATMULL_CLARK", update=on_change_force)
    
    preserve_old: BoolProperty(default=True, name="Preserve old", description="Do not delete existing multiresolution data (repoject from base every time)")
    
    auto_update: BoolProperty(default=True, name="Auto Update")
    
    inited: BoolProperty(default=False)
    
    force_change: BoolProperty(default=False)
    
    repeater: PointerProperty(type=RepeatMode)
    
    progress: IntProperty(soft_min=0, max=100, subtype="PERCENTAGE", name="Progress")
    run_pos: IntProperty(default=-1)


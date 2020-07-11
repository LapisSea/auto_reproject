import bpy

def get_active_obj(context):
    if not hasattr(context, "active_object"):
        return None
    
    obj=context.active_object
    
    if obj==None:
    # if obj==None or not obj.select_get():
        return None
    
    return obj

def get_context_common(context):
    obj=get_active_obj(context)
    return (obj, obj.amr_settings if obj!=None else None)

def get_evaluated_mesh(obj):
    return obj.evaluated_get(depsgraph=bpy.context.evaluated_depsgraph_get()).data
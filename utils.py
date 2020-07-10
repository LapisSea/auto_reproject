
def get_active_obj(context):
    
    obj=context.active_object
    
    if obj==None:
    # if obj==None or not obj.select_get():
        return None
    
    return obj

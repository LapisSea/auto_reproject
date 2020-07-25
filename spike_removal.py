_impl_name="cpp"

impl = __import__('importlib').import_module(__name__+"_impl_"+_impl_name)

def analyse_mesh(mesh, locality, min_derivation, min_length, process_wait):
    return impl.analyse_mesh(mesh, locality, min_derivation, min_length, process_wait)
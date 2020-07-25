# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from bpy.types import (Scene, Object)
from . import auto_load
from .import_properties import *
from .Config import Config

bl_info = {
    "name": "Auto Multires Reproject",
    "author": "LapisSea",
    "description": "",
    "blender": (2, 80, 0),
    "version": (1, 0, 0),
    "location": "3D View -> Tools -> Reproject",
    "category": "Sculpt"
}

auto_load.init()


def register():
    from .depsgraph import reg
    reg()
    
    auto_load.register()
    Object.amr_settings = PointerProperty(type=Config)
    


def unregister():
    from .depsgraph import dereg
    dereg()
    
    try:
        del Object.amr_settings
    except:
        pass
    auto_load.unregister()

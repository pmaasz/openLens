
import math
from typing import List, Optional, Tuple, Any, Dict, Union
try:
    from .vector3 import Vector3, vec3
    from .transform import Matrix4x4
except ImportError:
    from vector3 import Vector3, vec3
    from transform import Matrix4x4

class OpticalNode:
    """
    Base class for all optical nodes (elements, groups, surfaces)
    in the hierarchical optical model.
    """
    def __init__(self, name: str = "Node", parent: Optional['OpticalNode'] = None):
        self.name = name
        self.parent = parent
        self.children: List['OpticalNode'] = []
        
        # Local transformation relative to parent
        self.position = vec3(0, 0, 0) # Translation (x, y, z)
        self.rotation = vec3(0, 0, 0) # Euler angles (deg): Tilt X, Tilt Y, Tilt Z
        
        # Cache for global transform
        self._global_transform: Optional[Matrix4x4] = None

    def add_child(self, node: 'OpticalNode'):
        node.parent = self
        self.children.append(node)
        
    def get_local_transform(self) -> Matrix4x4:
        """Calculates local transformation matrix (T * R)"""
        # Create rotation matrix (R)
        rot_mat = Matrix4x4.from_euler(self.rotation.x, self.rotation.y, self.rotation.z)
        # Create translation matrix (T)
        trans_mat = Matrix4x4.from_translation(self.position.x, self.position.y, self.position.z)
        # Combine: M = T * R (Standard: Rotate then Translate relative to parent)
        return trans_mat * rot_mat

    def get_global_transform(self) -> Matrix4x4:
        """Recursive calculation of global transform matrix"""
        # We could cache this, but need to know when to invalidate.
        # For now, compute on fly.
        local_transform = self.get_local_transform()
        
        if self.parent is None:
            return local_transform
            
        parent_transform = self.parent.get_global_transform()
        # Global = ParentGlobal * Local
        return parent_transform * local_transform

    def get_global_position(self) -> Vector3:
        """Returns the global position of this node's origin"""
        global_transform = self.get_global_transform()
        # Transform (0,0,0) to get position
        return global_transform.multiply_point(vec3(0, 0, 0))

    @property
    def is_element(self) -> bool:
        return False

    def get_flat_list(self, parent_global_pos: Optional[Vector3] = None) -> List[Tuple['OpticalNode', Vector3]]:
        """
        Returns a list of (element, global_position) tuples by traversing the hierarchy.
        Maintained for backward compatibility.
        """
        # Ignoring parent_global_pos argument as we calculate full transform now
        # But for efficiency in recursion we could pass transform.
        
        return self._get_flat_list_recursive(None)

    def _get_flat_list_recursive(self, parent_transform: Optional[Matrix4x4]) -> List[Tuple['OpticalNode', Vector3]]:
        local = self.get_local_transform()
        if parent_transform:
            global_transform = parent_transform * local
        else:
            global_transform = local
            
        global_pos = global_transform.multiply_point(vec3(0, 0, 0))
        
        result = []
        if self.is_element:
            result.append((self, global_pos))
            
        for child in self.children:
            result.extend(child._get_flat_list_recursive(global_transform))
            
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'position': self.position.to_tuple(),
            'rotation': self.rotation.to_tuple(),
            'children': [child.to_dict() for child in self.children],
            'type': self.__class__.__name__
        }

class SurfaceModifier:
    """Base class for surface modifiers (Asphere, Coating, etc.)"""
    def __init__(self, name: str = "Modifier"):
        self.name = name
    
    def to_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'type': self.__class__.__name__}

class OpticalElement(OpticalNode):
    """
    Leaf node representing a single optical element (e.g., Lens).
    """
    def __init__(self, element_model: Any, name: str = "Element", parent: Optional['OpticalNode'] = None):
        super().__init__(name, parent)
        self.element_model = element_model # The physical object (e.g., Lens instance)
        self.modifiers: List[Any] = [] # Surface modifiers (Asphere, Coating, etc.)

    @property
    def is_element(self) -> bool:
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if hasattr(self.element_model, 'to_dict'):
            data['element_model'] = self.element_model.to_dict()
        # TODO: Serialize modifiers
        return data

class OpticalAssembly(OpticalNode):
    """
    Container node for grouping optical elements (e.g., Doublet, Objective).
    """
    pass

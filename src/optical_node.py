
import math
from typing import List, Optional, Tuple, Any, Dict, Union
try:
    from .vector3 import Vector3, vec3
except ImportError:
    from vector3 import Vector3, vec3

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
        self._global_position: Optional[Vector3] = None
        self._global_rotation_matrix = None # To be implemented later

    def add_child(self, node: 'OpticalNode'):
        node.parent = self
        self.children.append(node)
        
    def get_global_position(self) -> Vector3:
        """Recursive calculation of global position"""
        if self.parent is None:
            return self.position
        
        # TODO: Implement full 3D transform with rotation
        # For now, assuming simple translation hierarchy or paraxial layout (mostly along X)
        # Ideally: P_global = Parent_Global_Pos + Parent_Global_Rot * P_local
        
        # Simple recursive sum for translation only (assuming no rotation for now)
        return self.parent.get_global_position() + self.position

    @property
    def is_element(self) -> bool:
        return False

    def get_flat_list(self, parent_global_pos: Optional[Vector3] = None) -> List[Tuple['OpticalNode', Vector3]]:
        """
        Returns a list of (element, global_position) tuples by traversing the hierarchy.
        """
        if parent_global_pos is None:
            parent_global_pos = vec3(0, 0, 0)

        # Calculate my global position
        # P_global = Parent_Global + P_local (Simplified, ignoring rotation)
        my_global_pos = parent_global_pos + self.position
        
        result = []
        if self.is_element:
            result.append((self, my_global_pos))
        
        for child in self.children:
            result.extend(child.get_flat_list(my_global_pos))
            
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

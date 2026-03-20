import math
from typing import List, Union
try:
    from .vector3 import Vector3
except ImportError:
    from vector3 import Vector3

class Matrix4x4:
    """4x4 Matrix for 3D transformations."""
    __slots__ = ('m',)

    def __init__(self, data: List[List[float]] = None):
        if data:
            self.m = data
        else:
            self.identity()

    def identity(self):
        self.m = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]

    def __mul__(self, other: 'Matrix4x4') -> 'Matrix4x4':
        """Matrix multiplication."""
        result = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                for k in range(4):
                    result[i][j] += self.m[i][k] * other.m[k][j]
        return Matrix4x4(result)

    def multiply_point(self, point: Vector3) -> Vector3:
        """Transforms a point (w=1)."""
        x = self.m[0][0] * point.x + self.m[0][1] * point.y + self.m[0][2] * point.z + self.m[0][3]
        y = self.m[1][0] * point.x + self.m[1][1] * point.y + self.m[1][2] * point.z + self.m[1][3]
        z = self.m[2][0] * point.x + self.m[2][1] * point.y + self.m[2][2] * point.z + self.m[2][3]
        # w = self.m[3][0] * point.x + self.m[3][1] * point.y + self.m[3][2] * point.z + self.m[3][3]
        # Assuming w is always 1 for affine transforms and we don't need perspective divide for now
        return Vector3(x, y, z)
    
    def multiply_vector(self, vector: Vector3) -> Vector3:
        """Transforms a direction vector (w=0). Translation is ignored."""
        x = self.m[0][0] * vector.x + self.m[0][1] * vector.y + self.m[0][2] * vector.z
        y = self.m[1][0] * vector.x + self.m[1][1] * vector.y + self.m[1][2] * vector.z
        z = self.m[2][0] * vector.x + self.m[2][1] * vector.y + self.m[2][2] * vector.z
        return Vector3(x, y, z)

    @staticmethod
    def from_translation(x: float, y: float, z: float) -> 'Matrix4x4':
        mat = Matrix4x4()
        mat.m[0][3] = x
        mat.m[1][3] = y
        mat.m[2][3] = z
        return mat

    @staticmethod
    def from_euler(rx: float, ry: float, rz: float) -> 'Matrix4x4':
        """Creates a rotation matrix from Euler angles (in degrees). Order: Z * Y * X"""
        rad_x = math.radians(rx)
        rad_y = math.radians(ry)
        rad_z = math.radians(rz)

        cx, sx = math.cos(rad_x), math.sin(rad_x)
        cy, sy = math.cos(rad_y), math.sin(rad_y)
        cz, sz = math.cos(rad_z), math.sin(rad_z)

        # Rx
        mx = Matrix4x4([
            [1, 0, 0, 0],
            [0, cx, -sx, 0],
            [0, sx, cx, 0],
            [0, 0, 0, 1]
        ])

        # Ry
        my = Matrix4x4([
            [cy, 0, sy, 0],
            [0, 1, 0, 0],
            [-sy, 0, cy, 0],
            [0, 0, 0, 1]
        ])

        # Rz
        mz = Matrix4x4([
            [cz, -sz, 0, 0],
            [sz, cz, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

        # R = Rz * Ry * Rx
        return mz * my * mx

    @staticmethod
    def from_scale(sx: float, sy: float, sz: float) -> 'Matrix4x4':
        mat = Matrix4x4()
        mat.m[0][0] = sx
        mat.m[1][1] = sy
        mat.m[2][2] = sz
        return mat

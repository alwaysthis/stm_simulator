"""GPU sphere impostors with view-space lighting and distance fading."""
import numpy as np
from PyQt6.QtGui import QOpenGLContext
from OpenGL import GL
from OpenGL.GL import shaders
import pyqtgraph.opengl as gl

VERTEX = """#version 140
uniform float u_scale;
uniform mat4 u_modelview;
uniform mat4 u_mvp;
in vec4 a_position;
in vec4 a_color;
in float a_size;
out vec4 v_color;
out float v_distance;
void main() {
    gl_Position = u_mvp * a_position;
    v_color = a_color;
    v_distance = length((u_modelview * a_position).xyz);
    gl_PointSize = a_size / max(v_distance * u_scale, 0.00001);
}
"""
FRAGMENT = """#version 140
in vec4 v_color;
in float v_distance;
out vec4 fragColor;
void main() {
    vec2 xy = (gl_PointCoord - 0.5) * 2.0;
    float radius2 = dot(xy, xy);
    if (radius2 > 1.0) discard;
    vec3 normal = vec3(xy.x, -xy.y, sqrt(1.0-radius2));
    vec3 light = normalize(vec3(-0.45, 0.65, 1.0));
    float diffuse = max(dot(normal, light), 0.0);
    vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
    float specular = pow(max(dot(normal, halfway), 0.0), 36.0);
    float distanceLight = 1.0 / (1.0 + 0.012*v_distance);
    vec3 lit = v_color.rgb*(0.23+0.72*diffuse)*(0.85+0.15*distanceLight);
    lit += vec3(0.8)*specular;
    float alpha = v_color.a < 0.3 ? v_color.a : v_color.a*clamp(0.45+0.55*distanceLight, 0.45, 1.0);
    fragColor = vec4(clamp(lit, 0.0, 1.0), alpha);
}
"""


class GlossyAtoms(gl.GLScatterPlotItem):
    _programs = {}

    def __init__(self, positions, colors, radii):
        self.positions = positions.astype(np.float32)
        self.colors = colors
        self.radii = radii
        self._program = None
        self._camera = None
        super().__init__(pos=self.positions, color=colors, size=radii*2,
                         pxMode=False, glOptions="translucent")

    def getShaderProgram(self):
        group = QOpenGLContext.currentContext().shareGroup()
        if group in self._programs:
            return self._programs[group]
        if self._program is None:
            self._program = shaders.compileProgram(
                shaders.compileShader(VERTEX, GL.GL_VERTEX_SHADER),
                shaders.compileShader(FRAGMENT, GL.GL_FRAGMENT_SHADER))
            GL.glBindAttribLocation(self._program, 0, "a_position")
            GL.glBindAttribLocation(self._program, 1, "a_color")
            GL.glBindAttribLocation(self._program, 2, "a_size")
            GL.glLinkProgram(self._program)
            self._programs[group] = self._program
        return self._program

    def paint(self):
        camera = self.view().cameraPosition()
        position = (camera.x(), camera.y(), camera.z())
        if position != self._camera:
            distances = np.sum((self.positions-np.asarray(position))**2, axis=1)
            order = np.argsort(distances)[::-1]
            self.setData(pos=self.positions[order], color=self.colors[order], size=self.radii[order]*2)
            self._camera = position
        super().paint()

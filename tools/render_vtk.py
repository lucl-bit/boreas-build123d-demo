"""Hochwertige Offscreen-Renderings von STL-Teilen mit VTK (für Folien).

python tools/render_vtk.py out.png teil.stl:1f5fa8 teil2.stl:d9731a [--view iso|front|top|side] [--size 1600x1200]
    [--bg f2ede3] [--label "Text"] [--clip-y]  (Halbschnitt: nur y <= 0 zeigen)
"""
from __future__ import annotations

import argparse

import vtk


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def render(out: str, items: list[tuple[str, str]], view: str = "iso", size=(1600, 1200), bg="f2ede3",
           label: str | None = None, clip_y: bool = False, zoom: float = 1.0, opacity: dict | None = None) -> None:
    ren = vtk.vtkRenderer()
    ren.SetBackground(*hex_rgb(bg))
    for path, col in items:
        r = vtk.vtkSTLReader()
        r.SetFileName(path)
        src = r
        if clip_y:
            plane = vtk.vtkPlane()
            plane.SetOrigin(0, 0, 0)
            plane.SetNormal(0, 1, 0)
            clip = vtk.vtkClipPolyData()
            clip.SetInputConnection(r.GetOutputPort())
            clip.SetClipFunction(plane)
            clip.InsideOutOn()
            src = clip
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(src.GetOutputPort())
        normals.SetFeatureAngle(35)
        normals.SplittingOn()
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(normals.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        p = a.GetProperty()
        p.SetColor(*hex_rgb(col))
        p.SetAmbient(0.25)
        p.SetDiffuse(0.75)
        p.SetSpecular(0.15)
        p.SetSpecularPower(20)
        if opacity and path in opacity:
            p.SetOpacity(opacity[path])
        ren.AddActor(a)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(0, 0, 0)
    pos = {"iso": (1.0, -1.25, 0.65), "front": (0, -1, 0.0001), "side": (1, 0, 0.0001), "top": (0.0001, 0, 1),
           "iso_low": (1.0, -1.3, 0.25), "cut": (0.35, 1.4, 0.35)}[view]
    cam.SetPosition(*pos)
    cam.SetViewUp(0, 0, 1) if view != "top" else cam.SetViewUp(0, 1, 0)
    ren.ResetCamera()
    cam.Zoom(zoom)
    light = vtk.vtkLight()
    light.SetLightTypeToCameraLight()
    light.SetPosition(0.4, 0.6, 1)
    ren.AddLight(light)
    if label:
        t = vtk.vtkTextActor()
        t.SetInput(label)
        tp = t.GetTextProperty()
        tp.SetFontSize(34)
        tp.SetColor(*hex_rgb("0d192f"))
        tp.SetFontFamilyToArial()
        t.SetPosition(30, size[1] - 60)
        ren.AddActor2D(t)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(*size)
    win.SetMultiSamples(8)
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(out)
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("stl", nargs="+")
    ap.add_argument("--view", default="iso")
    ap.add_argument("--size", default="1600x1200")
    ap.add_argument("--bg", default="f2ede3")
    ap.add_argument("--label")
    ap.add_argument("--clip-y", action="store_true")
    ap.add_argument("--zoom", type=float, default=1.0)
    a = ap.parse_args()
    items = []
    for s in a.stl:
        path, _, col = s.rpartition(":") if s.count(":") > 1 or (":" in s and not s[1:3] in (":\\", ":/")) else (s, "", "")
        if not path:
            path, col = s, "8a9bb0"
        items.append((path, col or "8a9bb0"))
    w, h = (int(x) for x in a.size.split("x"))
    render(a.out, items, a.view, (w, h), a.bg, a.label, a.clip_y, a.zoom)


if __name__ == "__main__":
    main()

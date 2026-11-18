"""Draw measured synthetic fixture geometry and global camera positions."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw
from src.scene_graph.metric_scene import load_scene


def draw(scene_path: Path, out_path: Path) -> None:
    scene = load_scene(scene_path)
    scale, pad = 80, 55
    x1, y1 = scene["bounds_m"][2:]
    image = Image.new("RGB", (int(x1 * scale + 2 * pad), int(y1 * scale + 2 * pad)), "white")
    pen = ImageDraw.Draw(image)
    def xy(x, y):
        return (pad + x * scale, pad + (y1 - y) * scale)
    for space in scene["spaces"]:
        x0, y0, x2, y2 = space["bounds_m"]
        pen.rectangle((*xy(x0, y2), *xy(x2, y0)), fill="#e9f1f5" if space["semantic"] == "corridor" else "#f4f4ee")
        pen.text(xy((x0+x2)/2 - .5, (y0+y2)/2), space["id"], fill="#34495e")
    for wall in scene["walls"]:
        x0,y0=wall["p0_m"]; x2,y2=wall["p1_m"]
        pen.line((xy(x0,y0),xy(x2,y2)), fill="#2c3e50", width=10)
        length=math.hypot(x2-x0,y2-y0)
        for op in wall.get("openings", []):
            a=op["u0_m"]/length; b=op["u1_m"]/length
            p=xy(x0+a*(x2-x0),y0+a*(y2-y0)); q=xy(x0+b*(x2-x0),y0+b*(y2-y0))
            pen.line((p,q), fill="#149447" if op["kind"]=="door" else "#429dcc", width=11)
    for obj in scene["objects"]:
        x,y,_=obj["center_m"]; sx,sy,_=obj["size_m"]
        pen.rectangle((*xy(x-sx/2,y+sy/2),*xy(x+sx/2,y-sy/2)),fill="#999999",outline="#444444",width=2)
    for cam in scene["cameras"]:
        x,y,_=cam["eye_m"]; tx,ty,_=cam["target_m"]
        norm=math.hypot(tx-x,ty-y); q=(x+.4*(tx-x)/norm,y+.4*(ty-y)/norm)
        pen.ellipse((xy(x,y)[0]-4,xy(x,y)[1]-4,xy(x,y)[0]+4,xy(x,y)[1]+4), fill="#d13d30")
        pen.line((xy(x,y),xy(*q)),fill="#d13d30",width=3)
    pen.text((pad,15),"SYNTHETIC | 12 x 9 x 2.7 m | 4 rooms + corridor | 16 cameras",fill="#111111")
    out_path.parent.mkdir(parents=True,exist_ok=True)
    image.save(out_path)


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("scene",type=Path); p.add_argument("output",type=Path)
    a=p.parse_args(); draw(a.scene,a.output)

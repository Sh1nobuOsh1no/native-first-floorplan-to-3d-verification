"""Measure cross-door object/metric-depth reprojection in real Blender CPU passes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from src.scene_graph.metric_scene import components, first_hit, load_scene


def check(scene_path: Path, render: Path, out: Path) -> dict:
    scene = load_scene(scene_path)
    frames = {f['camera_id']:f for f in json.loads((render/'camera_metadata.json').read_text())['frames']}
    id_map = json.loads((render/'object_id_map.json').read_text())
    objects = {v['source_id']:int(k) for k,v in id_map.items() if v['kind']=='furniture'}
    boxes = components(scene, False)
    result=[]; tiles=[]
    for wall in scene['walls']:
        for door in wall.get('openings',[]):
            if door['kind']!='door':continue
            best=None
            for obj in scene.get('objects',[]):
                if obj['room_id'] not in door['connects'] or obj['id'] not in objects:continue
                source_ids=[]
                for space in door['connects']:
                    for frame in frames.values():
                        if frame['space_id']!=space:continue
                        ids=np.load(render/frame['object_id_npy'])
                        pixels=int((ids==objects[obj['id']]).sum())
                        if pixels<100 or first_hit(frame['eye_m'],obj['center_m'],boxes,{'wall'}) is not None:continue
                        source_ids.append((space,frame,pixels))
                for a in source_ids:
                    for b in source_ids:
                        if a[0]==b[0]:continue
                        score=min(a[2],b[2])
                        if best is None or score>best[0]:best=(score,obj,a[1],b[1],a[2],b[2])
            if best is None:
                result.append({'door_id':door['id'],'connects':door['connects'],'status':'FAIL_NO_SHARED_OBJECT_IN_BOTH_SIDES'})
                continue
            _,obj,a,b,count_a,count_b=best; oid=objects[obj['id']]
            da=np.load(render/a['depth_npy']);ia=np.load(render/a['object_id_npy'])
            db=np.load(render/b['depth_npy']);ib=np.load(render/b['object_id_npy'])
            y,x=np.where(ia==oid); K=np.asarray(a['K_px']); c2w=np.asarray(a['c2w_blender'])
            xyz=np.stack(((x+.5-K[0,2])/K[0,0]*da[y,x],-(y+.5-K[1,2])/K[1,1]*da[y,x],-da[y,x],np.ones(len(x))))
            world=c2w@xyz;p=np.linalg.inv(np.asarray(b['c2w_blender']))@world;Kb=np.asarray(b['K_px'])
            u=np.rint(Kb[0,0]*p[0]/-p[2]+Kb[0,2]-.5).astype(int)
            v=np.rint(Kb[1,2]-Kb[1,1]*p[1]/-p[2]-.5).astype(int);z=-p[2]
            h,w=db.shape;keep=(u>=0)&(u<w)&(v>=0)&(v<h)&(z>0)
            matched=(ib[v[keep],u[keep]]==oid)&(abs(db[v[keep],u[keep]]-z[keep])<.1)
            ratio=float(matched.mean()) if len(matched) else 0.
            result.append({'door_id':door['id'],'connects':door['connects'],'status':'PASS' if ratio>.9 and keep.sum()>100 else 'FAIL_REPROJECTION',
                'shared_object_id':obj['id'],'side_cameras':[a['camera_id'],b['camera_id']],
                'visible_pixels':[count_a,count_b],'reprojected_pixels':int(keep.sum()),'depth_id_match_ratio':ratio,
                'depth_tolerance_m':.1,'source':'BLENDER_CPU_SYNTHETIC_GEOMETRY'})
            for frame in (a,b):
                tile=Image.open(render/frame['rgb']).convert('RGB');draw=ImageDraw.Draw(tile)
                draw.rectangle((0,0,w,24),fill='black');draw.text((4,4),f"{door['id']} | {frame['camera_id']}",fill='white')
                tiles.append(tile)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'scene_id':scene['scene_id'],'provenance':scene['provenance']['kind'],
        'results':result,'all_pass':all(x['status']=='PASS' for x in result)},indent=2)+'\n')
    if tiles:
        canvas=Image.new('RGB',(tiles[0].width*2,tiles[0].height*((len(tiles)+1)//2)))
        for i,tile in enumerate(tiles):canvas.paste(tile,((i%2)*tile.width,(i//2)*tile.height))
        canvas.save(out.with_suffix('.png'))
    return json.loads(out.read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=check(a.scene,a.render,a.out);print(json.dumps(result));raise SystemExit(0 if result['all_pass'] else 2)

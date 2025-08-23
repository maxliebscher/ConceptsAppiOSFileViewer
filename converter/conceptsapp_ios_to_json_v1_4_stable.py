
#!/usr/bin/env python3
# coding: utf-8
"""
concepts_to_json_shapes_drop.py (CLEAN)
--------------------------------------
Drag&Drop-Version:
  <Name>.concept  ->  <Name>\
                       - <Name>.json
                       - <Name>_Thumb.jpg (falls vorhanden)
                       - images\ (Assets, falls vorhanden)

Features: Strokes + Auto-Shapes (Rect/Ellipse/Polygon) + Transform/Mirror + Images.

Nutzung:
  python concepts_to_json_shapes_drop.py "C:\Pfad\Demofile-1.concept" [weitere...]
"""

import sys, zipfile, plistlib, struct, json, math, re
from pathlib import Path
from plistlib import UID

DEFAULT_MAX_JUMP = 2000.0

# ---------- helpers ----------
def _deref(objects, v):
    return objects[v.data] if isinstance(v, UID) else v

def _unique_points(pts, eps=1e-4):
    if not pts: return pts
    out=[pts[0]]
    for p in pts[1:]:
        if abs(p[0]-out[-1][0])>eps or abs(p[1]-out[-1][1])>eps:
            out.append(p)
    return out

def _total_len(pts):
    L = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0]-pts[i-1][0]; dy = pts[i][1]-pts[i-1][1]
        L += (dx*dx+dy*dy)**0.5
    return L

def _segment_longest(pts, max_jump):
    if not pts: return []
    segs=[]; cur=[pts[0]]
    mj2 = max_jump*max_jump
    for i in range(1,len(pts)):
        dx=pts[i][0]-pts[i-1][0]; dy=pts[i][1]-pts[i-1][1]
        if dx*dx+dy*dy > mj2:
            if len(cur)>=2: segs.append(cur)
            cur=[pts[i]]
        else:
            cur.append(pts[i])
    if len(cur)>=2: segs.append(cur)
    if not segs: return pts if len(pts)>=2 else []
    segs.sort(key=lambda s:_total_len(s), reverse=True)
    return segs[0]

def _bbox(pts):
    if not pts: return None
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]

def _parse_ffII_le(raw):
    """Parse little-endian <ffII> tuples into [x,y] list."""
    if not isinstance(raw,(bytes,bytearray)) or len(raw)<16 or len(raw)%16!=0: 
        return []
    pts=[]; n=len(raw)//16
    try:
        for i in range(n):
            x,y,_,_ = struct.unpack_from('<ffII', raw, i*16)
            if math.isfinite(x) and math.isfinite(y):
                pts.append([float(x), float(y)])
        return pts
    except Exception:
        return []

def _parse_ffII_be(raw):
    """Parse big-endian >ffII tuples into [x,y] list."""
    if not isinstance(raw,(bytes,bytearray)) or len(raw)<16 or len(raw)%16!=0: 
        return []
    pts=[]; n=len(raw)//16
    try:
        for i in range(n):
            x,y,_,_ = struct.unpack_from('>ffII', raw, i*16)
            if math.isfinite(x) and math.isfinite(y):
                pts.append([float(x), float(y)])
        return pts
    except Exception:
        return []

def _ns_points(objs, arr_dict):
    arr = arr_dict.get('NS.objects') or arr_dict.get('NS.values') or []
    pts=[]
    for u in arr:
        kp = _deref(objs, u)
        if isinstance(kp, dict) and 'glPosition' in kp:
            try:
                x,y = struct.unpack('<2f', kp['glPosition'])
                pts.append([float(x), float(y)])
            except Exception:
                pass
    return pts

def _read_mat16_le(raw):
    if not isinstance(raw,(bytes,bytearray)) or len(raw)<64: return None
    try:
        m = list(struct.unpack('<16f', raw[:64]))
        return m
    except Exception:
        return None

def _apply_mat(points, m):
    if not m: return points
    out=[]
    m0,m1,m2,m3, m4,m5,m6,m7, m8,m9,m10,m11, m12,m13,m14,m15 = m
    for x,y in points:
        xp = m0*x + m4*y + m12
        yp = m1*x + m5*y + m13
        out.append([xp, yp])
    return out

def _mirror_pts(points, mirrorX=False, mirrorY=False):
    if not (mirrorX or mirrorY) or not points: return points
    bb = _bbox(points)
    if not bb: return points
    cx = 0.5*(bb[0]+bb[2]); cy = 0.5*(bb[1]+bb[3])
    out=[]
    for x,y in points:
        xx = (2*cx - x) if mirrorX else x
        yy = (2*cy - y) if mirrorY else y
        out.append([xx, yy])
    return out

_rect_re = re.compile(r'\{\{\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\}\s*,\s*\{\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\}\}')

def _parse_rect_str(s):
    """Parse '{{x,y},{w,h}}' → (x,y,w,h)"""
    if not isinstance(s,str): return None
    m = _rect_re.search(s)
    if not m: return None
    x = float(m.group(1)); y = float(m.group(2)); w = float(m.group(3)); h = float(m.group(4))
    return (x,y,w,h)

def _ellipse_poly_from_rect(x,y,w,h, segments=64):
    cx = x + w*0.5; cy = y + h*0.5
    rx = abs(w)*0.5; ry = abs(h)*0.5
    pts=[]
    for i in range(segments+1):
        t = (i/segments)*2*math.pi
        pts.append([cx + rx*math.cos(t), cy + ry*math.sin(t)])
    return pts

def _rect_poly_from_rect(x,y,w,h):
    return [[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]

# ---------- core ----------
def export_one(src_path: str, max_jump: float = DEFAULT_MAX_JUMP):
    src = Path(src_path)
    if not src.exists(): raise FileNotFoundError(src)

    out_dir = src.parent / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    images_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(src, 'r') as z:
        names = set(z.namelist())

        def load_plist(name):
            return plistlib.loads(z.read(name)) if name in names else None

        plS = load_plist('Strokes.plist')
        plR = load_plist('Resources.plist')
        plD = load_plist('Drawing.plist')

        base = src.stem

        if 'Thumb.jpg' in names:
            (out_dir/f'{base}_Thumb.jpg').write_bytes(z.read('Thumb.jpg'))

        # document transform (optional)
        doc_mat = None
        if isinstance(plD, dict) and '$objects' in plD:
            dobj = plD['$objects']
            for obj in dobj:
                if isinstance(obj, dict):
                    for k,v in obj.items():
                        if isinstance(v,(bytes,bytearray)) and len(v)>=64:
                            m = _read_mat16_le(v)
                            if m: doc_mat = m; break
                if doc_mat: break

        # resources (images)
        resmap = {}
        if isinstance(plR, dict) and '$objects' in plR:
            robj = plR['$objects']
            try:
                root = robj[1]
                irm = _deref(robj, root.get('importedResourceMap'))
                keys = irm.get('NS.keys', []) if isinstance(irm, dict) else []
                vals = irm.get('NS.objects', []) or irm.get('NS.values', []) if isinstance(irm, dict) else []
                for ku, vu in zip(keys, vals):
                    k = _deref(robj, ku)
                    v = _deref(robj, vu)
                    if isinstance(v, dict):
                        legacy = _deref(robj, v.get('resourceLegacyId'))
                        ext    = _deref(robj, v.get('resourceExtension'))
                        if isinstance(legacy, str) and isinstance(ext, str):
                            resmap[legacy] = ext
            except Exception:
                pass

        images=[]; strokes=[]

        def append_stroke(poly, width=None, color=None, opacity=None, blend=None, eraser=False, key_pts=None):
            key_pts = key_pts or []
            poly = poly or []
            poly = _unique_points(poly, eps=1e-4)
            seg  = _segment_longest(poly, max_jump=max_jump)
            stroke = {
                'type':'stroke',
                'width': float(width) if width is not None else None,
                'color': color,
                'opacity': float(opacity) if (isinstance(opacity,(int,float))) else None,
                'blendMode': blend,
                'eraser': bool(eraser),
                'polyline': seg if len(seg)>=2 else [],
                'keyPoints': key_pts
            }
            strokes.append(stroke)

        if isinstance(plS, dict) and '$objects' in plS:
            sobj = plS['$objects']
            for o in sobj:
                if not isinstance(o, dict) or '$class' not in o: 
                    continue
                cls = _deref(sobj, o.get('$class'))
                cname = cls.get('$classname') if isinstance(cls, dict) else None

                # ---- Image Items ----
                if cname == 'ImageItem':
                    size = _deref(sobj, o.get('size'))
                    crop = _deref(sobj, o.get('crop'))
                    width=height=None
                    if isinstance(size, str) and size.startswith('{'):
                        try:
                            w,h = size.strip('{}').split(',')
                            width=float(w.strip()); height=float(h.strip())
                        except Exception:
                            pass
                    img_mat=None
                    for key in ('diSavedTransform','localTransform','transform'):
                        vv = o.get(key)
                        if isinstance(vv,(bytes,bytearray)):
                            img_mat = _read_mat16_le(vv)
                            if img_mat: break
                    image_id = _deref(sobj, o.get('imageIdentifier'))
                    ext = resmap.get(image_id)
                    file_path=None
                    if isinstance(image_id,str) and isinstance(ext,str):
                        cand=f'ImportedImages/{image_id}.{ext}'
                        if cand in names: file_path=cand
                    if not file_path and isinstance(image_id,str):
                        for n in names:
                            if n.startswith('ImportedImages/') and image_id in n:
                                file_path=n; break
                    local=None
                    if file_path and file_path in names:
                        local = Path(file_path).name
                        (images_dir/local).write_bytes(z.read(file_path))
                    images.append({
                        'type':'image',
                        'imageIdentifier': image_id if isinstance(image_id,str) else None,
                        'size':[width,height] if (width and height) else None,
                        'crop': crop if isinstance(crop,str) else None,
                        'transform': img_mat,
                        'docTransform': doc_mat,
                        'local': local,
                        'path': f"images/{local}" if local else None
                    })
                    continue

                # ---- Brush / Style ----
                width=None; color=None; opacity=None; blend=None; eraser=False
                bp = _deref(sobj, o.get('brushProperties')) or _deref(sobj, o.get('style'))
                if isinstance(bp, dict):
                    width = bp.get('brushWidth') or bp.get('strokeWidth')
                    col = _deref(sobj, bp.get('brushColor') or bp.get('strokeColor'))
                    if isinstance(col, dict):
                        color = {'r': float(col.get('UIRed',0.0)),
                                 'g': float(col.get('UIGreen',0.0)),
                                 'b': float(col.get('UIBlue',0.0)),
                                 'a': float(col.get('UIAlpha',1.0))}
                    opacity = bp.get('opacity') or bp.get('brushOpacity') or bp.get('UIAlpha')
                    blend = bp.get('blendMode') or bp.get('CGBlendMode')
                    eraser = bool(bp.get('isErasing') or bp.get('eraser') or (blend=='destinationOut'))

                # ---- Transform(s) ----
                obj_mat=None
                for key in ('diSavedTransform','localTransform','transform'):
                    vv = o.get(key)
                    if isinstance(vv,(bytes,bytearray)):
                        obj_mat = _read_mat16_le(vv)
                        if obj_mat: break

                # ---- Strokes ----
                if cname == 'Stroke':
                    key_pts=[]
                    kpu = _deref(sobj, o.get('keyPoints'))
                    if isinstance(kpu, dict):
                        key_pts = _ns_points(sobj, kpu)

                    poly=[]
                    raw = _deref(sobj, o.get('strokePointsNonOptionalAngles'))
                    if isinstance(raw,(bytes,bytearray)):
                        poly = _parse_ffII_le(raw) or _parse_ffII_be(raw)
                    if len(poly)<2:
                        for k,v in o.items():
                            if k=='$class': continue
                            if isinstance(v,(bytes,bytearray)) and len(v)>=16 and (len(v)%16)==0:
                                cand = _parse_ffII_le(v) or _parse_ffII_be(v)
                                if len(cand)>len(poly): poly=cand
                    if len(poly)<2 and key_pts:
                        poly = key_pts

                    if obj_mat: poly = _apply_mat(poly, obj_mat)
                    if doc_mat: poly = _apply_mat(poly, doc_mat)

                    mirX = bool(o.get('mirrorX') or o.get('mirroredX') or o.get('isMirroredX'))
                    mirY = bool(o.get('mirrorY') or o.get('mirroredY') or o.get('isMirroredY') or o.get('mirrored'))
                    if mirX or mirY:
                        poly = _mirror_pts(poly, mirX, mirY)

                    append_stroke(poly, width, color, opacity, blend, eraser, key_pts)
                    continue

                # ---- Shapes (AutoShapes/Shape-Tool) ----
                rect = None
                for k in ('shapeRect','rect','bounds','frame'):
                    v = _deref(sobj, o.get(k))
                    rect = _parse_rect_str(v)
                    if rect: break

                shape_pts = None
                if rect:
                    x,y,w,h = rect
                    name = (cname or '').lower()
                    if ('ellipse' in name) or ('oval' in name) or ('circle' in name):
                        shape_pts = _ellipse_poly_from_rect(x,y,w,h, segments=64)
                    else:
                        shape_pts = _rect_poly_from_rect(x,y,w,h)

                if shape_pts is None:
                    for k in ('points','vertices','keyPoints','controlPoints','pathPoints'):
                        arr = _deref(sobj, o.get(k))
                        if isinstance(arr, dict):
                            pts = _ns_points(sobj, arr)
                            if len(pts)>=2:
                                closed = bool(o.get('closed') or o.get('isClosed'))
                                if closed and (pts[0]!=pts[-1]): 
                                    pts = pts + [pts[0]]
                                shape_pts = pts
                                break

                if shape_pts:
                    if obj_mat: shape_pts = _apply_mat(shape_pts, obj_mat)
                    if doc_mat: shape_pts  = _apply_mat(shape_pts, doc_mat)
                    append_stroke(shape_pts, width, color, opacity, blend, eraser, key_pts=[])
                    continue

        data = {'version':'shapes','images':images,'strokes':strokes,'hasThumb':('Thumb.jpg' in names)}
        (out_dir/f'{base}.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return out_dir, base

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    max_jump = DEFAULT_MAX_JUMP
    for a in list(sys.argv[1:]):
        m = re.match(r'--max-jump=(\d+(?:\.\d+)?)', a)
        if m:
            max_jump=float(m.group(1))

    if not args:
        print("Ziehen Sie eine oder mehrere .concept Dateien auf dieses Skript,\noder rufen Sie es mit Pfaden auf:")
        print("  python concepts_to_json_shapes_drop.py \"C:\\Pfad\\Demofile-1.concept\" [weitere...]")
        sys.exit(0)

    for p in args:
        out_dir, base = export_one(p, max_jump=max_jump)
        print(f"[OK] {p}")
        print(f" -> {out_dir}\\{base}.json")
        thumb = out_dir / f'{base}_Thumb.jpg'
        if thumb.exists():
            print(f" -> {thumb}")
        imgdir = out_dir / 'images'
        if imgdir.exists():
            print(f" -> {imgdir}\\*")

if __name__=='__main__':
    main()

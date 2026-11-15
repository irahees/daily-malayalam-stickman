import bpy, math, os
from mathutils import Vector

OUT = os.environ.get("BLENDER_OUTPUT", "output/blender_preview.mp4")
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def mat(name, color, metallic=0.0, roughness=0.65):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(*color,1); bs.inputs["Metallic"].default_value=metallic; bs.inputs["Roughness"].default_value=roughness
    return m
def cube(name,loc,scale,material,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material)
    if bevel:
        b=o.modifiers.new("soft edges","BEVEL"); b.width=bevel; b.segments=3
        o.modifiers.new("weighted normals","WEIGHTED_NORMAL")
    return o
def sphere(name,loc,scale,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=loc); o=bpy.context.object
    o.name=name; o.scale=scale; o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o
def cylinder(name,loc,radius,depth,material,rotation=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=radius,depth=depth,location=loc,rotation=rotation)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); b=o.modifiers.new("edge bevel","BEVEL"); b.width=.025; b.segments=2
    o.modifiers.new("weighted normals","WEIGHTED_NORMAL"); return o
def aim(obj,point): obj.rotation_euler=(Vector(point)-obj.location).to_track_quat("-Z","Y").to_euler()
sky=mat("sky blue",(.30,.58,.76)); grass=mat("Kerala greenery",(.12,.32,.16)); road=mat("asphalt",(.055,.07,.085))
concrete=mat("warm concrete",(.72,.68,.56)); red=mat("station red",(.72,.055,.045)); white=mat("paint white",(.88,.88,.80))
glass=mat("blue glass",(.12,.34,.43),.15,.25); dark=mat("dark trim",(.025,.035,.045)); skin=mat("warm skin",(.58,.31,.20))
shirt=mat("teal shirt",(.035,.34,.31)); pants=mat("navy trousers",(.045,.075,.13)); hair=mat("black hair",(.025,.018,.014))
# Recognizable petrol station environment
cube("ground",(0,0,-.35),(24,22,.6),grass); cube("road",(0,-5,0),(24,5,.12),road)
for x in (-8,-4,0,4,8): cube("road marking",(x,-5,.07),(1.5,.08,.025),white)
cube("station shop",(0,3.4,2.2),(10,2,4.4),concrete,.12)
cube("red fascia",(0,2.34,3.55),(9.7,.16,.72),red,.05); cube("glass frontage",(0,2.28,2),(8.5,.1,2.1),glass,.04)
for x in (-2.8,0,2.8): cube("shop mullion",(x,2.18,2),(.09,.12,2.1),white)
cube("canopy roof",(0,.1,5.1),(13,5,.38),white,.14); cube("canopy edge",(0,-2.42,4.93),(13,.22,.35),red,.04)
for x in (-5.3,0,5.3): cube("canopy support",(x,-1.2,2.55),(.28,.28,4.8),white,.04)
for x in (-3.7,0,3.7):
    cube("fuel dispenser",(x,-1.35,1.35),(1.05,.75,2.35),white,.12)
    cube("screen bezel",(x,-1.755,1.82),(.72,.045,.38),dark,.035); cube("digital screen",(x,-1.785,1.82),(.55,.025,.19),glass,.02)
    cube("red pump panel",(x,-1.755,.78),(.78,.05,.48),red,.03)
    cylinder("hose",(x+.52,-1.37,1.2),.045,1.15,dark,(0,math.pi/2,0))
    cube("nozzle",(x+.67,-1.38,1.72),(.12,.16,.35),dark,.035)
for px,py,h in [(-8,4,6),(8,4,6.8)]:
    cylinder("palm trunk",(px,py,h/2),.22,h,concrete)
    for a in range(0,360,45):
        r=math.radians(a); f=sphere("palm frond",(px+1.2*math.cos(r),py+math.sin(r),h+.25),(1.35,.22,.10),grass); f.rotation_euler[2]=r
# Presenter composed of 3D rounded meshes
root=bpy.data.objects.new("Presenter root",None); bpy.context.collection.objects.link(root)
def attach(o): o.parent=root; return o
attach(sphere("torso",(0,-3.35,1.55),(.62,.42,.85),shirt))
attach(cylinder("neck",(0,-3.35,2.38),.18,.34,skin))
attach(sphere("head",(0,-3.35,2.92),(.58,.48,.67),skin))
attach(sphere("hair",(0,-3.33,3.37),(.59,.49,.27),hair))
for ex in (-.22,.22):
    attach(sphere("eye",(ex,-3.77,3.02),(.105,.055,.13),white)); attach(sphere("pupil",(ex,-3.82,3.02),(.045,.025,.065),dark))
attach(sphere("smile",(0,-3.80,2.72),(.16,.035,.055),red))
def limb(name,start,end,radius,material):
    mid=(Vector(start)+Vector(end))/2; v=Vector(end)-Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=radius,depth=v.length,location=mid)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); o.rotation_euler=v.to_track_quat("Z","Y").to_euler(); bpy.ops.object.shade_smooth(); return attach(o)
for side in (-1,1):
    limb("arm",(side*.48,-3.35,2),(side*.82,-3.35,1.55),.16,shirt)
    attach(sphere("hand",(side*.82,-3.35,1.52),(.19,.18,.19),skin))
    limb("leg",(side*.25,-3.35,.9),(side*.30,-3.35,.22),.19,pants)
    attach(sphere("shoe",(side*.30,-3.48,.14),(.29,.42,.15),dark))
for frame,z,rot in [(1,0,0),(15,.12,.04),(30,0,0),(45,.12,-.04),(60,0,0),(75,.12,.04),(90,0,0)]:
    root.location.z=z; root.rotation_euler.z=rot; root.keyframe_insert(data_path="location",frame=frame); root.keyframe_insert(data_path="rotation_euler",frame=frame)
car=cube("moving car",(-8,-6.1,.62),(2.7,1.25,.78),glass,.22)
for x in (-8.8,-7.2): cylinder("car wheel",(x,-6.1,.25),.34,.18,dark,(math.pi/2,0,0))
for frame,x in [(1,-8),(90,8)]: car.location.x=x; car.keyframe_insert(data_path="location",frame=frame)
bpy.ops.object.camera_add(location=(10,-20,11)); camera=bpy.context.object; aim(camera,(0,0,2.2)); camera.data.type="ORTHO"; camera.data.ortho_scale=17
scene=bpy.context.scene; scene.camera=camera
bpy.ops.object.light_add(type="AREA",location=(-7,-10,13)); key=bpy.context.object; key.data.energy=1800; key.data.shape="DISK"; key.data.size=9; aim(key,(0,0,2))
bpy.ops.object.light_add(type="AREA",location=(8,2,8)); fill=bpy.context.object; fill.data.energy=900; fill.data.size=7; aim(fill,(0,0,2))
world=bpy.data.worlds.new("soft blue world") if not bpy.data.worlds else bpy.data.worlds[0]
scene.world=world; world.use_nodes=True; world.node_tree.nodes["Background"].inputs[0].default_value=(.12,.18,.25,1); world.node_tree.nodes["Background"].inputs[1].default_value=.7
scene.render.engine="BLENDER_EEVEE_NEXT"; scene.eevee.taa_render_samples=16
scene.render.resolution_x=540; scene.render.resolution_y=960; scene.render.resolution_percentage=100; scene.render.fps=30
scene.frame_start=1; scene.frame_end=90; scene.render.image_settings.file_format="PNG"; scene.render.filepath="//blender_frames/frame_"
scene.view_settings.view_transform="AgX"; scene.frame_set(1)
bpy.ops.render.render(animation=True)

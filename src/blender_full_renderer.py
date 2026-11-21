import bpy, json, math, os
from mathutils import Vector

CONFIG = json.load(open(os.environ["BLENDER_CONFIG"], encoding="utf-8"))
FRAME_DIR = os.environ["BLENDER_FRAMES"]
os.makedirs(FRAME_DIR, exist_ok=True)
FPS = int(CONFIG.get("fps", 30))

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)

def material(name, color, metallic=0.0, roughness=0.7):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value=(*color,1); p.inputs["Metallic"].default_value=metallic; p.inputs["Roughness"].default_value=roughness
    return m

def cube(name, loc, size, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o=bpy.context.object; o.name=name; o.dimensions=size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if bevel:
        b=o.modifiers.new("rounded edges","BEVEL"); b.width=bevel; b.segments=3
    return o

def sphere(name, loc, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def cylinder(name, loc, radius, depth, mat, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=depth, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; o.data.materials.append(mat); return o


def text_label(name, body, loc, size, mat, rotation=(math.pi/2,0,0)):
    curve=bpy.data.curves.new(name,"FONT"); curve.body=body; curve.size=size; curve.extrude=0.003
    # Prefer a Malayalam-capable Noto font when installed.
    import glob
    candidates=glob.glob("/usr/share/fonts/**/*NotoSansMalayalam*Regular*.ttf",recursive=True)
    if not candidates: candidates=glob.glob("/usr/share/fonts/**/*Malayalam*.ttf",recursive=True)
    if candidates:
        try: curve.font=bpy.data.fonts.load(candidates[0])
        except Exception: pass
    obj=bpy.data.objects.new(name,curve); bpy.context.collection.objects.link(obj)
    obj.location=loc; obj.rotation_euler=rotation; obj.data.materials.append(mat)
    return obj

def package_box(name, loc, size, color, label, mats):
    box=cube(name,loc,size,color,.045)
    # A clean front-facing printed label makes the product read as a real shop item.
    x,y,z=loc; sx,sy,sz=size
    cube(name+" label",(x,y-sy/2-.008,z),(sx*.72,.018,sz*.38),mats["white"],.012)
    text_label(name+" print",label,(x-sx*.30,y-sy/2-.021,z-sz*.08),min(.13,sx*.12),mats["dark"])
    return box

def aim(o, point):
    o.rotation_euler=(Vector(point)-o.location).to_track_quat("-Z","Y").to_euler()

def setup_world():
    world=bpy.data.worlds.new("Malayalam 3D world") if not bpy.data.worlds else bpy.data.worlds[0]
    bpy.context.scene.world=world; world.use_nodes=True
    world.node_tree.nodes["Background"].inputs[0].default_value=(0.16,0.23,0.31,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=0.65

def make_materials():
    return {
      "grass":material("Kerala green",(.13,.34,.18)),
      "road":material("Road asphalt",(.055,.07,.085)),
      "concrete":material("Warm concrete",(.68,.64,.54)),
      "red":material("Signal red",(.72,.055,.045)),
      "white":material("Ivory",(.92,.91,.82)),
      "glass":material("Blue glass",(.10,.34,.46),.15,.24),
      "dark":material("Charcoal",(.025,.035,.045)),
      "wood":material("Wood",(.34,.17,.08)),
      "gold":material("Gold",(.95,.58,.08),.72,.22),
      "blue":material("Deep blue",(.055,.18,.42)),
      "green":material("Leaf green",(.12,.40,.19)),
      "skin":material("Warm skin",(.58,.31,.20)),
      "shirt":material("Teal shirt",(.035,.34,.31)),
      "pants":material("Navy trousers",(.045,.075,.13)),
      "hair":material("Black hair",(.025,.018,.014)),
      "yellow":material("Bright yellow",(.98,.70,.08)),
      "orange":material("Orange",(.92,.25,.06))
    }

def build_fuel(m, variant=0):
    cube("station apron",(0,1,-.32),(20,18,.5),m["concrete"])
    cube("road",(0,-7,-.02),(22,5,.12),m["road"])
    cube("shop",(0,5,2.0),(9,2,4),m["concrete"],.12)
    cube("shop fascia",(0,3.93,3.35),(8.8,.15,.62),m["red"],.04)
    text_label("Fuel station channel sign","സിമുലി മലയാളം",(0,3.82,3.30),.34,m["yellow"])
    cube("glass frontage",(0,3.88,1.9),(7.6,.1,1.9),m["glass"],.03)
    cube("canopy",(0,.1,4.65),(12,5,.35),m["white"],.12)
    cube("canopy trim",(0,-2.42,4.47),(12,.18,.3),m["red"],.04)
    text_label("Fuel canopy sign","പെട്രോൾ  •  ഡീസൽ",(2.1,-2.53,4.49),.28,m["dark"])
    for x in (-4.8,4.8): cube("canopy pillar",(x,-1.1,2.2),(.22,.22,4.3),m["white"])
    for x in (-3,0,3):
        cube("fuel dispenser",(x,-1.1,1.18),(.85,.7,2.15),m["white"],.1)
        cube("pump screen",(x,-1.48,1.62),(.57,.04,.32),m["blue"],.03)
        cube("pump red panel",(x,-1.48,.72),(.62,.04,.38),m["red"],.02)
        cylinder("fuel hose",(x+.48,-1.1,1.1),.035,.95,m["dark"],(0,math.pi/2,0))
        cube("nozzle",(x+.62,-1.12,1.55),(.1,.13,.3),m["dark"],.02)
    car=cube("moving blue car",(-6,-5.5,.55),(2.5,1.2,.72),m["blue"],.2)
    for x in (-6.8,-5.2): cylinder("car wheel",(x,-5.5,.23),.28,.15,m["dark"],(math.pi/2,0,0))
    return [car]

def build_shop(m, variant):
    # A recognizable small Kerala neighbourhood grocery: tiled floor, plaster walls,
    # painted fascia, glass frontage, stocked racks and a working checkout.
    cube("shop tiled floor",(0,0,-.32),(18,16,.5),m["concrete"])
    for x in (-6,6):
        cube("side plaster wall",(x,1,2.65),(.28,8,5.3),m["white"])
    cube("rear plaster wall",(0,4.8,2.65),(12,.28,5.3),m["white"])
    cube("shop fascia",(0,4.55,4.65),(11.7,.24,.95),m["green"],.06)
    text_label("Channel branded grocery shop name","SIMULI MALAYALAM",(0,4.405,4.48),.43,m["yellow"])
    # Open entrance and glass display windows.
    for x in (-4.8,4.8):
        cube("front window frame",(x,-3.8,2.35),(2.0,.16,3.25),m["wood"],.04)
        cube("front window glass",(x,-3.90,2.35),(1.78,.035,3.0),m["glass"],.025)
    cube("door frame",(0,-3.82,1.65),(1.7,.18,3.3),m["wood"],.04)
    cube("glass door",(0,-3.93,1.65),(1.48,.035,3.08),m["glass"],.025)
    # Three stocked grocery aisles with detailed shelves and assorted products.
    for x in (-4.0,0,4.0):
        for z in (1.0,2.05,3.1):
            cube("wood grocery shelf",(x,2.35,z),(3.25,.75,.13),m["wood"],.035)
            for k in range(6):
                px=x-1.30+k*.52
                colors=[m["yellow"],m["orange"],m["green"],m["blue"],m["red"],m["white"]]
                package_box("branded grocery packet",(px,1.98,z+.38),(.36,.28,.68),colors[k],["അരി","ചായ","പരിപ്പ്","എണ്ണ","ഉപ്പ്","സോപ്പ്"][k],m)
    # Rice sacks, dhal sacks, oil bottles and crates of fresh produce.
    for x in (-4.2,-2.9,2.9,4.2):
        sack=sphere("stitched rice sack",(x,-1.8,.62),(.48,.42,.66),m["white"])
        sack.scale.z=1.0
        text_label("rice sack label","അരി",(x-.16,-2.18,.65),.20,m["red"])
    for x in (-4.6,-3.45,3.45,4.6):
        cylinder("cooking oil bottle",(x,-.55,.72),.18,1.0,m["yellow"])
        cylinder("oil bottle cap",(x,-.55,1.25),.09,.12,m["red"])
    for x in (-4.3,-2.7,2.7,4.3):
        cube("vegetable crate",(x,-2.9,.28),(1.35,.8,.55),m["wood"],.06)
        for j in range(5):
            xx=x-.48+j*.24
            sphere("fresh tomato",(xx,-3.0,.65),(.16,.16,.15),m["red"])
            sphere("green vegetable",(xx,-2.72,.65),(.14,.14,.16),m["green"])
    # Checkout counter, digital scale and hanging tube lights.
    cube("checkout counter",(0,-1.55,.72),(3.8,1.0,1.4),m["wood"],.08)
    cube("counter glass top",(0,-1.55,1.45),(3.85,1.04,.08),m["glass"],.025)
    cube("digital weighing scale",(0,-1.5,1.62),(.75,.48,.22),m["dark"],.04)
    cube("scale display",(0,-1.76,1.68),(.48,.025,.12),m["green"],.02)
    for x in (-3.5,0,3.5):
        cube("ceiling tube light",(x,.5,4.95),(2.1,.18,.08),m["white"],.035)
    # Small Malayalam price board beside the counter.
    cube("price board",(5.25,-1.5,2.3),(1.15,.12,1.5),m["dark"],.04)
    text_label("price board heading","ഇന്നത്തെ വില",(4.78,-1.575,2.72),.16,m["yellow"])
    text_label("price board rice","അരി  55",(4.78,-1.575,2.40),.15,m["white"])
    text_label("price board dal","പരിപ്പ്  90",(4.78,-1.575,2.12),.14,m["white"])

def build_phone(m, variant):
    cube("room floor",(0,0,-.3),(16,14,.5),m["concrete"])
    cube("back wall",(0,4,2.7),(12,.3,5.4),m["blue"])
    cube("desk",(0,-1,.85),(7,2,.25),m["wood"],.08)
    cube("giant smartphone",(0,-.1,2.2),(2.35,.22,3.7),m["dark"],.18)
    cube("phone display",(0,-.235,2.25),(2.08,.025,3.25),m["glass"],.1)
    if variant % 3 == 0:
        # battery icon
        cube("battery body",(0,-.27,2.2),(.85,.04,1.45),m["white"],.08)
        cube("battery fill",(0,-.30,2.0),(.65,.03,.75),m["green"],.04)
        cube("battery cap",(0,-.30,2.98),(.28,.05,.12),m["white"])
    elif variant % 3 == 1:
        for z in (2.7,2.25,1.8):
            cube("message bubble",(.0,-.29,z),(1.35,.035,.25),m["yellow"],.07)
    else:
        for z in (2.7,2.25,1.8):
            sphere("signal dot",(0,-.3,z),(.18,.04,.18),m["yellow"])
    tower=cube("network tower",(4,1.5,2.0),(.22,.22,4),m["dark"])
    for z in (2.5,3.1,3.7):
        bpy.ops.mesh.primitive_torus_add(major_radius=.48,minor_radius=.035,location=(4,1.5,z),rotation=(math.pi/2,0,0))
        bpy.context.object.data.materials.append(m["yellow"])

def build_rain(m, variant):
    cube("earth",(0,0,-.35),(18,18,.6),m["grass"])
    cube("rainwater channel",(0,-2,.02),(16,2,.12),m["blue"])
    for x in (-5,-2,2,5):
        cube("Kerala house",(x,2,1.25),(2.3,2,2.5),m["concrete"],.08)
        roof=cube("tiled roof",(x,2,2.65),(2.8,2.4,.22),m["red"],.05); roof.rotation_euler[1]=.12
    cloud=sphere("rain cloud",(0,2,6),(2.1,.9,.7),m["dark"])
    for i in range(16):
        x=-2.5+(i%8)*.7; y=-.3+(i//8)*.55
        drop=cylinder("rain streak",(x,y,4.5-(i%3)*.35),.025,.65,m["glass"])
    if variant%2:
        cylinder("water tank",(4,-1,1.0),.85,1.6,m["white"])
        cube("tank stand",(4,-1,.3),(2,.25,.35),m["dark"])

def build_gold(m, variant):
    cube("jewellery floor",(0,0,-.3),(16,14,.5),m["concrete"])
    cube("jewellery back wall",(0,4,2.6),(12,.3,5.2),m["red"])
    cube("display counter",(0,-1,.65),(7,1.2,1.3),m["wood"],.08)
    for x in (-2.5,0,2.5):
        cube("gold display case",(x,-1,1.55),(1.7,.8,.5),m["glass"],.06)
        for j in range(3):
            bpy.ops.mesh.primitive_torus_add(major_radius=.24+j*.06,minor_radius=.035,location=(x,-1.48,1.62))
            bpy.context.object.data.materials.append(m["gold"])
    for x in (-4,4):
        cylinder("gold coin",(x,1,1.3),.48,.15,m["gold"])
    if variant%2:
        cube("bank desk",(0,2,.8),(4,1,.3),m["wood"])


def build_seed(m, variant):
    cube("garden soil",(0,0,-.25),(17,15,.7),m["wood"])
    cube("garden lawn",(0,-2,.15),(17,8,.25),m["grass"])
    sphere("seed",(0,-.7,.62),(.42,.25,.24),m["wood"])
    if variant >= 1:
        cylinder("seedling stem",(0,-.7,1.25+variant*.12),.075,1.15+variant*.22,m["green"])
        for side in (-1,1):
            leaf=sphere("seedling leaf",(side*(.38+variant*.08),-.7,1.45+variant*.16),(.48,.16,.13),m["green"]); leaf.rotation_euler[1]=side*.42
    if variant >= 2:
        for side in (-1,1):
            root=cylinder("growing root",(side*.28,-.7,.20),.035,.9,m["wood"]); root.rotation_euler[1]=side*.5
    for x in (-5,5): cylinder("garden fence post",(x,1.8,1.0),.09,2,m["wood"])

def build_cat(m, variant):
    cube("cat home floor",(0,0,-.3),(16,15,.5),m["concrete"])
    cube("cat home wall",(0,4,2.8),(13,.25,5.6),m["yellow"])
    cube("cat sofa",(0,1,.85),(5,1.5,1.5),m["blue"],.18)
    sphere("cat torso",(0,-1.1,.82),(.95,.43,.5),m["orange"])
    sphere("cat head",(0,-1.35,1.55),(.52,.43,.48),m["orange"])
    for side in (-1,1):
        ear=sphere("cat ear",(side*.34,-1.34,1.93),(.19,.16,.28),m["orange"]); ear.rotation_euler[1]=side*-.28
        sphere("cat eye",(side*.19,-1.75,1.61),(.075,.035,.10),m["dark"])
        sphere("cat paw",(side*.55,-1.12,.32),(.22,.23,.16),m["orange"])
        sphere("cat hind paw",(side*.75,-.8,.32),(.23,.24,.16),m["orange"])
    sphere("cat muzzle",(0,-1.75,1.38),(.22,.10,.15),m["yellow"])
    sphere("cat nose",(0,-1.85,1.45),(.07,.04,.055),m["red"])
    tail=cylinder("cat tail",(1,-.95,1.22),.09,.9,m["orange"]); tail.rotation_euler[1]=1 if variant%2==0 else -1
    if variant%2==0: cylinder("cat food bowl",(2.2,-1,.18),.42,.12,m["white"])

def build_dog(m, variant):
    cube("dog yard",(0,0,-.3),(18,17,.5),m["grass"])
    cube("dog house wall",(0,4,2.1),(12,.25,4.2),m["concrete"])
    sphere("dog body",(0,-1,.9),(1.05,.48,.56),m["orange"])
    sphere("dog head",(.85,-1.05,1.55),(.53,.45,.52),m["orange"])
    for side in (-1,1):
        ear=sphere("dog floppy ear",(.85+side*.39,-1.05,1.65),(.18,.22,.42),m["wood"]); ear.rotation_euler[1]=side*.32
        sphere("dog eye",(.85+side*.19,-1.46,1.68),(.07,.035,.09),m["dark"])
        cylinder("dog leg",(side*.62,-1,.43),.13,.75,m["orange"])
        sphere("dog paw",(side*.62,-1.05,.12),(.23,.28,.13),m["orange"])
    sphere("dog muzzle",(1.18,-1.45,1.38),(.27,.22,.19),m["yellow"])
    sphere("dog nose",(1.25,-1.65,1.48),(.10,.07,.08),m["dark"])
    tail=cylinder("dog wagging tail",(-1.05,-.9,1.25),.10,.8,m["orange"]); tail.rotation_euler[1]=-.8
    if variant%2==0: cylinder("dog water bowl",(2,-1,.16),.48,.16,m["blue"])
    else: sphere("dog ball",(2,-1,.32),(.28,.28,.28),m["red"])

def build_fish(m, variant):
    cube("aquarium water",(0,1,2.2),(15,9,5.2),m["blue"])
    cube("aquarium gravel",(0,-.2,-.25),(15,9,.5),m["wood"])
    for x in (-5,-3,3,5):
        cylinder("aquatic plant stem",(x,-1,.9),.055,2,m["green"])
        for z in (.6,1.1,1.6): sphere("aquatic plant leaf",(x+.35,-1,z),(.42,.12,.14),m["green"])
    sphere("fish body",(0,-2.2,2.1),(1.45,.38,.72),m["orange"])
    tail=sphere("fish tail fin",(-1.45,-2.2,2.1),(.55,.12,.62),m["yellow"]); tail.rotation_euler[1]=.5
    for side in (-1,1): sphere("fish side fin",(.1,-2.2+side*.25,1.75),(.55,.12,.25),m["yellow"])
    sphere("fish eye",(.95,-2.58,2.28),(.13,.07,.14),m["white"])
    sphere("fish pupil",(1,-2.64,2.28),(.06,.035,.07),m["dark"])
    for k in range(5): sphere("oxygen bubble",(2.1+(k%2)*.45,-2,1.1+k*.55),(.10,.10,.10),m["white"])
    if variant%2: cube("aquarium filter",(5,-2,1),(.55,.6,1.7),m["dark"])

def build_ice(m, variant):
    cube("cold kitchen",(0,0,-.3),(16,14,.5),m["concrete"])
    cube("kitchen wall",(0,4,2.8),(12,.25,5.6),m["blue"])
    cylinder("drinking glass",(0,-.6,1.2),.68,1.8,m["glass"])
    cylinder("water in glass",(0,-.6,.95),.58,1,m["blue"])
    for x,z in ((-.24,1.7),(.18,1.8),(0,1.95)):
        ice=cube("floating ice cube",(x,-.6,z),(.42,.42,.42),m["white"],.06); ice.rotation_euler[1]=.25
    if variant in (1,2,3):
        cube("ice tray",(3,-.4,.35),(3,1.5,.25),m["dark"],.08)
        for x in (2,2.65,3.3,3.95): cube("ice tray cube",(x,-.4,.58),(.48,.48,.38),m["glass"],.04)
    if variant in (3,4): cube("lake surface",(0,2,.15),(13,3,.12),m["blue"])

def build_rainbow(m, variant):
    cube("rainbow landscape",(0,0,-.35),(18,18,.6),m["grass"])
    sphere("rain cloud left",(-3,2,6),(1.5,.8,.7),m["white"])
    sphere("rain cloud right",(3,2,6),(1.5,.8,.7),m["white"])
    sphere("sun",(5,-1,6.1),(.8,.8,.8),m["yellow"])
    rainbow_mats=[m["red"],m["orange"],m["yellow"],m["green"],m["blue"],m["white"],m["gold"]]
    for j,rm in enumerate(rainbow_mats):
        curve=bpy.data.curves.new("rainbow arc","CURVE"); curve.dimensions="3D"; curve.bevel_depth=.10; curve.bevel_resolution=3
        spline=curve.splines.new("POLY"); pts=33; spline.points.add(pts-1); radius=4-j*.20
        for k in range(pts):
            a=math.pi*k/(pts-1); spline.points[k].co=(radius*math.cos(a),-1.5,2.1+radius*math.sin(a),1)
        obj=bpy.data.objects.new("rainbow colour band",curve); bpy.context.collection.objects.link(obj); obj.data.materials.append(rm)
    for k in range(12): cylinder("rain drop",(-4+(k%6)*1.4,-.8,3.7-(k//6)*.45),.035,.4,m["glass"])

def build_general(m, variant):
    cube("ground",(0,0,-.35),(18,18,.6),m["grass"])
    cube("home",(0,3,1.7),(7,2,3.4),m["concrete"],.08)
    roof=cube("house roof",(0,3,3.55),(8,2.5,.3),m["red"],.08); roof.rotation_euler[1]=.08
    cube("window",(-1.8,1.92,2),(1.5,.06,1.2),m["glass"])
    cube("door",(1.8,1.92,1.1),(1,.08,2.2),m["wood"])
    if variant%3==1:
        cube("classroom board",(0,1.8,2.8),(4,.12,1.3),m["green"])
    elif variant%3==2:
        cube("science table",(0,-1,.8),(5,1.2,.2),m["white"])

def make_presenter(m):
    root=bpy.data.objects.new("3D Malayalam Presenter",None); bpy.context.collection.objects.link(root)
    def attach(o): o.parent=root; return o
    attach(sphere("torso",(0,-3.2,1.45),(.58,.4,.78),m["shirt"]))
    attach(cylinder("neck",(0,-3.2,2.2),.15,.3,m["skin"]))
    attach(sphere("head",(0,-3.2,2.72),(.52,.45,.62),m["skin"]))
    attach(sphere("hair",(0,-3.17,3.12),(.54,.46,.25),m["hair"]))
    for ex in (-.2,.2):
        attach(sphere("eye",(ex,-3.59,2.82),(.09,.04,.1),m["white"]))
        attach(sphere("pupil",(ex,-3.625,2.82),(.04,.02,.05),m["dark"]))
    attach(sphere("smile",(0,-3.61,2.52),(.13,.025,.04),m["red"]))
    # Distinct 3D limbs attached to the same animated presenter root.
    for side in (-1,1):
        arm=cylinder("animated arm",(side*.66,-3.2,1.72),.13,.82,m["shirt"])
        arm.rotation_euler[1]=side*.35; attach(arm)
        attach(sphere("hand",(side*.83,-3.2,1.32),(.16,.15,.16),m["skin"]))
        leg=cylinder("leg",(side*.23,-3.2,.55),.16,.85,m["pants"])
        attach(leg)
        attach(sphere("shoe",(side*.23,-3.32,.12),(.25,.34,.13),m["dark"]))
    for f,z,rx in ((1,0,0),(15,.1,.04),(30,0,0),(45,.1,-.04)):
        root.location.z=z; root.rotation_euler.y=rx
        root.keyframe_insert(data_path="location",frame=f); root.keyframe_insert(data_path="rotation_euler",frame=f)
    return root

def render_scene(scene_index, line, title, frames, first_frame, category):
    clear_scene(); m=make_materials(); setup_world()
    builders={"fuel":build_fuel,"shop":build_shop,"phone":build_phone,"rain":build_rain,"gold":build_gold,"seed":build_seed,"cat":build_cat,"dog":build_dog,"fish":build_fish,"ice":build_ice,"rainbow":build_rainbow,"general":build_general}
    builder=builders.get(category,build_general)
    extras=builder(m,scene_index) if category=="fuel" else builder(m,scene_index)
    root=make_presenter(m)
    # Scene-to-scene camera composition and gentle animated camera movement.
    bpy.ops.object.camera_add(location=(9,-20,8.5))
    camera=bpy.context.object; camera.data.lens=42; aim(camera,(0,-.1,2.25)); bpy.context.scene.camera=camera
    camera.data.dof.use_dof=False
    bpy.ops.object.light_add(type="AREA",location=(-7,-9,12))
    key=bpy.context.object; key.data.energy=2600; key.data.shape="DISK"; key.data.size=7; key.data.use_shadow=True; aim(key,(0,0,2))
    bpy.ops.object.light_add(type="AREA",location=(7,3,8))
    fill=bpy.context.object; fill.data.energy=1400; fill.data.size=6; fill.data.use_shadow=True; aim(fill,(0,0,2))
    bpy.ops.object.light_add(type="AREA",location=(1,7,9))
    rim=bpy.context.object; rim.data.energy=1700; rim.data.size=5; rim.data.use_shadow=True; aim(rim,(0,0,2))
    scene=bpy.context.scene
    if bpy.app.version >= (4,2,0): scene.render.engine="BLENDER_EEVEE_NEXT"
    else: scene.render.engine="BLENDER_EEVEE"
    scene.eevee.taa_render_samples=8
    # Improve grounded 3D realism: contact shadows and ambient occlusion.
    try:
        scene.eevee.use_gtao=True
        scene.eevee.gtao_distance=3.0
        scene.eevee.gtao_factor=1.35
    except Exception:
        pass
    scene.render.resolution_x=540; scene.render.resolution_y=960; scene.render.resolution_percentage=100
    scene.render.fps=FPS; scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGB"
    scene.render.film_transparent=False; scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.frame_start=1; scene.frame_end=max(frames,1)
    # Animate the host through the scene; each beat has a subtle different gesture.
    for f in range(1,frames+1):
        phase=(f/max(frames,1))*math.tau
        root.location.x=0.18*math.sin(phase)
        root.location.z=.07*(.5+.5*math.sin(phase*2))
        root.rotation_euler.z=.08*math.sin(phase)
        root.keyframe_insert(data_path="location",frame=f)
        root.keyframe_insert(data_path="rotation_euler",frame=f)
        # Independent arm and leg keyframes add visible gestures beyond body sway.
        for obj in bpy.data.objects:
            if obj.name.startswith("animated arm"):
                side=-1 if obj.location.x < 0 else 1
                obj.rotation_euler.y=side*(.28*math.sin(phase*1.4 + (0 if side<0 else math.pi)))
                obj.rotation_euler.x=.12*math.cos(phase*1.4)
                obj.keyframe_insert(data_path="rotation_euler",frame=f)
            elif obj.name.startswith("leg"):
                side=-1 if obj.location.x < 0 else 1
                obj.rotation_euler.y=side*.10*math.sin(phase*1.2)
                obj.keyframe_insert(data_path="rotation_euler",frame=f)
    scene.render.filepath=os.path.join(FRAME_DIR,"frame_%06d.png")
    for local in range(1,frames+1):
        scene.frame_set(local)
        scene.render.filepath=os.path.join(FRAME_DIR,"frame_%06d.png") % (first_frame+local-1)
        bpy.ops.render.render(write_still=True)
    print("Rendered 3D scene",scene_index+1,"category",category,"frames",frames)

def category_for(text):
    t=text.lower()
    # Match concrete subjects before broad terms such as water, rain or money.
    if any(x in t for x in ("പൂച്ച","പൂച്ചയുടെ","മ്യാവൂ","cat","kitten")): return "cat"
    if any(x in t for x in ("നായ","നായയുടെ","വാലാട്ട","dog","puppy")): return "dog"
    if any(x in t for x in ("മത്സ്യം","മത്സ്യ","മീൻ","ചെകിള","fish","gill","aquarium")): return "fish"
    if any(x in t for x in ("വിത്ത്","മുള","ചെടി","വളർച്ച","seed","sprout","plant","കൃഷി")): return "seed"
    if any(x in t for x in ("ഐസ്","മഞ്ഞ്","മഞ്ഞാക","സാന്ദ്രത","ice","frozen","freeze")): return "ice"
    if any(x in t for x in ("മഴവില്ല്","ഏഴ് നിറ","rainbow","പ്രകാശം നിറ","വെളിച്ചം നിറ")): return "rainbow"
    if any(x in t for x in ("പെട്രോൾ","ഇന്ധന","വാഹന","fuel","petrol")): return "fuel"
    if any(x in t for x in ("സ്വർണ്ണ","സ്വർണം","പവൻ","ആഭരണം","gold")): return "gold"
    if any(x in t for x in ("ഫോൺ","ബാറ്ററി","ചാർജ്","മൊബൈൽ","ഇന്റർനെറ്റ്","നെറ്റ്വർക്ക്","ഓൺലൈൻ","battery","internet")): return "phone"
    if any(x in t for x in ("മഴ","വെള്ളം","മണ്ണ്","കടൽ","ജലം","rain","water")): return "rain"
    if any(x in t for x in ("കടകൾ","കടകള","കടയിലെ","കടയിൽ","വില","വാങ്ങ","സാധന","വിതരണ","shop","പണം","രൂപ")): return "shop"
    return "general"

# Each of the six spoken beats gets its own 3D set and continuous animation.
frame_cursor=1
for i,(line,duration) in enumerate(zip(CONFIG["scenes"],CONFIG["scene_durations"])):
    n=max(1,int(round(float(duration)*FPS)))
    category=category_for(CONFIG["title"]+" "+line)
    render_scene(i,line,CONFIG["title"],n,frame_cursor,category)
    frame_cursor+=n
print("3D render complete; frames:",frame_cursor-1)

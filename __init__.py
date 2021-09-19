bl_info = {
	"name": "Friendly Video Cropper",
	"author": "Kenetics",
	"version": (0, 1),
	"blender": (2, 80, 0),
	"location": "View3D > Toolshelf > Add Objects",
	"description": "Allows you to crop videos with camera render border",
	"warning": "",
	"wiki_url": "",
	"category": "Video"
}

import bpy, math, subprocess
from bpy.props import EnumProperty, IntProperty, FloatVectorProperty, BoolProperty, FloatProperty, StringProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel, AddonPreferences

"""
TODO

APNG Compression type

"""

"""
General Notes to Self
list(scene.somethingbig) - To see arrays in console

Props
String
subtype = "DIR_PATH"

Collections
context.scene.collection - Master Scene collection
context.collection - Active Collection
collection.all_objects - all objects in this and child collections
collection.objects - objects in this collection
collection.children - child collections
collection.children.link(collection2) - link collection2 as child of collection
	will throw error if already in collection
collection.children.unlink(collection2) - unlink collection2 as child of collection
collection.objects.link(obj) - link object to collection
collection.objects.unlink(obj) - unlink object

Window
context.area.type - Type of area

Enum
Dynamic
def get_enum_items(self, context):
	enum_list = []
	
	for index, obj in enumerate(context.selected_objects):
		enum_list.append( (obj.name, obj.name, "", "", index) )
	
	return enum_list
obj_name : EnumProperty(
		items=get_enum_items,
		name="Object Name",
		description=""
	)
Static
obj_name : EnumProperty(
		items=[
			("ITEM","Item Name", "Item Description", "UI_ICON", 0),
			("ITEM2","Item Name2", "Item Description", "UI_ICON", 1)
		],
		name="Object Name",
		description=""
	)
"""

## Helper Functions
def make_ffmpeg_args(context, preview=False):
	"""Returns string to use as args for ffmpeg command"""
	render = context.scene.render
	settings = context.window_manager.fvc_settings
	args = []
	
	file_arg = context.scene.world.node_tree.nodes.active.image.filepath
	
	# calc cropping
	crop_top_left_x = math.floor(render.resolution_x * render.border_min_x)
	crop_top_left_y = math.floor(render.resolution_y * render.border_min_y)
	crop_width = math.floor(render.resolution_x * (render.border_max_x - render.border_min_x))
	crop_height = math.floor(render.resolution_y * (render.border_max_y - render.border_min_y))

	# Append input file
	args += ["-i", file_arg]
	
	# append filters
	filters = []
	# for looping apngs
	if settings.make_apng:
		filters.append("setpts=PTS-STARTPTS")
	# crop
	filters.append(f"crop={crop_width}:{crop_height}:{crop_top_left_x}:{crop_top_left_y}")
	# scale
	if settings.use_scale_multiplier:
		filters.append(f"scale={crop_width * settings.scale_multiplier}:-1")
	
	filter_graphs = []
	# dont use with preview, because ffplay freezes with limit colors
	if settings.use_colors_limit and not preview:
		# after split filter, start using ;
		filter_graphs.append("split[s0][s1]")
		filter_graphs.append(f"[s0]palettegen=max_colors={settings.colors_limit}:reserve_transparent=0[pal]")
		filter_graphs.append("[s1][pal]paletteuse")
		# join into 1 string
		filter_graphs = ";".join(filter_graphs)
		filters.append(filter_graphs)
	
	args += ["-vf", f'{", ".join(filters)}']


	if settings.use_start_seconds:
		args.append("-ss")
		args.append(settings.start_seconds)
	if settings.use_end_seconds:
		args.append("-to")
		args.append(settings.end_seconds)
	# Append output arg
	if not preview:
		# overwrite if existing
		args.append("-y")

		if settings.use_fps_limit:
			args.append("-r")
			args.append(str(settings.fps_limit))

		if settings.make_apng:
			args.append("-plays")
			args.append("0")
			# TODO: APNG compression type
			# slow compress
			#args.append("-pred")
			#args.append("mixed")
			args.append(file_arg[:file_arg.rfind(".")] + "-cropped" + ".apng")
		else:
			args.append(file_arg[:file_arg.rfind(".")] + "-cropped" + file_arg[file_arg.rfind("."):])
	return args

def error_check(self, context):
	scene = context.scene
	if not scene.world.use_nodes:
		self.report({"ERROR"}, "World node tree not enabled.")
		return {"CANCELLED"}
	if not scene.world.node_tree:
		self.report({"ERROR"}, "No world node tree")
		return {"CANCELLED"}
	if not scene.world.node_tree.nodes.active:
		self.report({"ERROR"}, "No active world node")
		return {"CANCELLED"}
	if not scene.world.node_tree.nodes.active.type == "TEX_IMAGE":
		self.report({"ERROR"}, "Active world node is not a Texture Image")
		return {"CANCELLED"}
	if not scene.world.node_tree.nodes.active.image.filepath:
		self.report({"ERROR"}, "World tex node doesnt have a file path")
		return {"CANCELLED"}
	return {}


## Structs
class FVC_ExportSettings(PropertyGroup):
	make_apng : BoolProperty(
		name="Make aPNG",
		description="If enabled, creates an animated PNG, else, creates the same format the source is in. Not compatible with preview.",
		default=False
	)
	use_start_seconds : BoolProperty(name="Use Start Seconds", default=False)
	start_seconds : FloatProperty(
		name="Start Seconds",
		description="Starts this many seconds into the video",
		default=0.0,
		min=0.0
	)
	use_end_seconds : BoolProperty(name="Use End Seconds", default=False)
	end_seconds : FloatProperty(
		name="End Seconds",
		description="Ends video this many seconds in",
		default=1.0,
		min=0.0
	)
	use_fps_limit : BoolProperty(name="Use FPS Limit", default=False)
	fps_limit : IntProperty(
		name="FPS Limit",
		default=12,
		min=1
	)
	use_scale_multiplier : BoolProperty(name="Use Scale Multiplier", default=False)
	scale_multiplier : FloatProperty(
		name="Scale Multiplier",
		default=1.0,
		min=0.0
	)
	use_colors_limit : BoolProperty(name="Use Colors Limit", default=False)
	colors_limit : IntProperty(
		name="Colors Limit",
		description="Limit colors to this amount. Not compatible with preview.",
		default=128,
		min=4,
		max=255
	)


## Operators
class FVC_OT_preview_ffmpeg_command(Operator):
	"""Previews the crop FFMPEG command"""
	bl_idname = "fvc.preview_ffmpeg_command"
	bl_label = "FFPlay Preview"
	#bl_options = {'INTERNAL'}
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		return context.scene.world

	def execute(self, context):
		# error checking
		if "CANCELLED" in error_check(self, context):
			return {"CANCELLED"}

		command = ["ffplay"]
		# check prefs for override

		# add args
		command += make_ffmpeg_args(context, preview=True)
		# run ffplay command
		print(f"Running: {command}")
		subprocess.run(command)

		return {'FINISHED'}


class FVC_OT_crop_ffmpeg_command(Operator):
	"""Runs the crop FFMPEG command"""
	bl_idname = "fvc.crop_ffmpeg_command"
	bl_label = "FFmpeg Crop"
	#bl_options = {'INTERNAL'}
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		return context.scene.world

	def execute(self, context):
		# error checking
		if "CANCELLED" in error_check(self, context):
			return {"CANCELLED"}
		
		command = ["ffmpeg"]
		# check prefs for override

		# add args
		command += make_ffmpeg_args(context)
		# run ffplay command
		print(f"Running: {command}")
		subprocess.run(command)

		return {'FINISHED'}

## UI
class FVC_PT_video_cropper_panel(Panel):
	bl_label = "Video Cropper Panel"
	bl_idname = "FVC_PT_video_cropper_panel"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "output"

	def draw(self, context):
		layout = self.layout
		settings = context.window_manager.fvc_settings
		layout.prop(settings, "make_apng")
		col = layout.column(align=True)
		split = col.split(factor=0.1, align=True)
		split.prop(settings, "use_start_seconds", text="")
		split.prop(settings, "start_seconds")
		split = col.split(factor=0.1, align=True)
		split.prop(settings, "use_end_seconds", text="")
		split.prop(settings, "end_seconds")
		split = col.split(factor=0.1, align=True)
		split.prop(settings, "use_fps_limit", text="")
		split.prop(settings, "fps_limit")
		split = col.split(factor=0.1, align=True)
		split.prop(settings, "use_scale_multiplier", text="")
		split.prop(settings, "scale_multiplier")
		split = col.split(factor=0.1, align=True)
		split.prop(settings, "use_colors_limit", text="")
		split.prop(settings, "colors_limit")
		col = layout.column(align=True)
		col.operator(FVC_OT_preview_ffmpeg_command.bl_idname)
		col.operator(FVC_OT_crop_ffmpeg_command.bl_idname)


## Register

classes = (
	FVC_ExportSettings,
	FVC_OT_preview_ffmpeg_command,
	FVC_OT_crop_ffmpeg_command,
	FVC_PT_video_cropper_panel
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	
	## Add Custom Properties
	bpy.types.WindowManager.fvc_settings = bpy.props.PointerProperty(type=FVC_ExportSettings)
	
	## Append to UI
	# bpy.types.CLASS.append(helper_func)

def unregister():
	## Remove from UI
	# bpy.types.CLASS.remove(helper_func)
	
	## Remove Custom Properties
	del bpy.types.WindowManager.fvc_settings
	
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
